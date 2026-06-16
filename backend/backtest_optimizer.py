"""
Backtest Strategy Optimizer  —  LangGraph implementation
=========================================================
Turns the one-shot run_strategy_backtest into an autonomous
optimization loop using a LangGraph StateGraph.

Graph:
  [run_backtest] → [evaluate] → (pass) → END
                              ↘ (fail) → [refine_strategy] → [run_backtest] → …

Exit conditions (whichever comes first):
  • All three quality thresholds are met  (Sharpe, drawdown, win-rate)
  • max_iterations reached (stored in state, not a module global)
"""

from __future__ import annotations

import re
from typing import Any, TypedDict

from langfuse import observe as traceable
from langgraph.graph import END, StateGraph

from backtester import run_strategy_backtest
from llm_factory import generate_response

# ---------------------------------------------------------------------------
# Thresholds — what counts as a "good enough" strategy
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLDS = {
    "min_sharpe":       0.8,
    "max_drawdown_pct": -20.0,   # stored as negative; -20 means ≤ 20% drawdown
    "min_win_rate_pct": 45.0,
}

# ---------------------------------------------------------------------------
# LangGraph State
# ---------------------------------------------------------------------------

class OptimizerState(TypedDict):
    # Inputs — set once, never mutated
    original_strategy: str
    thresholds:        dict   # {min_sharpe, max_drawdown_pct, min_win_rate_pct}
    max_iterations:    int    # ← stored in state so routing closures see it

    # Evolving state
    current_strategy:  str
    iteration:         int
    iterations_log:    list[dict]
    best_result:       dict | None
    best_metrics:      dict | None
    latest_metrics:    dict | None   # ← NEW: metrics from the most recent run
    passed:            bool
    error:             str

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _evaluate_metrics(metrics: dict, thresholds: dict) -> tuple[bool, list[str]]:
    """Returns (passed, failures). passed=True when ALL thresholds are satisfied."""
    failures = []
    sharpe   = metrics.get("sharpe_ratio",    0)
    drawdown = metrics.get("max_drawdown_pct", -100)
    win_rate = metrics.get("win_rate_pct",     0)

    if sharpe < thresholds["min_sharpe"]:
        failures.append(f"Sharpe {sharpe:.3f} < {thresholds['min_sharpe']} (target)")
    if drawdown < thresholds["max_drawdown_pct"]:
        failures.append(
            f"Max drawdown {drawdown:.1f}% worse than {thresholds['max_drawdown_pct']}% limit"
        )
    if win_rate < thresholds["min_win_rate_pct"]:
        failures.append(f"Win rate {win_rate:.1f}% < {thresholds['min_win_rate_pct']}% target")

    return (len(failures) == 0), failures


def _composite_score(m: dict) -> float:
    """Higher is better. Used to track the best result across iterations."""
    return (
        m.get("sharpe_ratio", 0)
        - abs(m.get("max_drawdown_pct", -100)) / 10
        + m.get("win_rate_pct", 0) / 100
    )


# ---------------------------------------------------------------------------
# Refinement prompt
# ---------------------------------------------------------------------------

_REFINE_PROMPT = """You are an expert quantitative trading strategist.
A backtest was run on the following strategy and did NOT meet the quality thresholds.

ORIGINAL STRATEGY REQUEST:
{original_strategy}

CURRENT STRATEGY (iteration {iteration}):
{current_strategy}

LATEST BACKTEST METRICS (this iteration):
- Sharpe Ratio:   {sharpe}
- Max Drawdown:   {drawdown}%
- Win Rate:       {win_rate}%
- Total Return:   {total_return}%
- Total Trades:   {total_trades}

THRESHOLD FAILURES:
{failures}

ITERATION HISTORY (all previous attempts):
{history}

YOUR TASK:
Suggest a refined version of the strategy that directly addresses the failures above.
Keep the same ticker and capital. You may adjust:
  - Indicator periods (e.g. SMA 10/50 → SMA 20/100)
  - Entry/exit conditions (add filters, tighten signals)
  - Position sizing (e.g. add a 2% stop-loss)

Return ONLY a single plain-English strategy description (no JSON, no code, no markdown).
It must be specific enough for the backtester to parse directly.
Example: "SMA 20/100 crossover on AAPL for 3 years with $50,000, 2% stop-loss per trade"
"""


def _build_refine_prompt(state: OptimizerState, failures: list[str]) -> str:
    # Use latest_metrics for the prompt — shows what THIS iteration actually produced
    m = state["latest_metrics"] or state["best_metrics"] or {}
    history_lines = []
    for entry in state["iterations_log"]:
        em = entry.get("metrics", {})
        history_lines.append(
            f"  Iter {entry['iteration']}: "
            f"Sharpe={em.get('sharpe_ratio','?')}, "
            f"DD={em.get('max_drawdown_pct','?')}%, "
            f"WR={em.get('win_rate_pct','?')}%  |  {entry.get('strategy','?')[:100]}"
        )

    return _REFINE_PROMPT.format(
        original_strategy=state["original_strategy"],
        iteration=state["iteration"],
        current_strategy=state["current_strategy"],
        sharpe=m.get("sharpe_ratio", "N/A"),
        drawdown=m.get("max_drawdown_pct", "N/A"),
        win_rate=m.get("win_rate_pct", "N/A"),
        total_return=m.get("total_return_pct", "N/A"),
        total_trades=m.get("total_trades", "N/A"),
        failures="\n".join(f"  • {f}" for f in failures),
        history="\n".join(history_lines) if history_lines else "  (none yet)",
    )


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

@traceable(name="optimizer:run_backtest", as_type="tool")
def _node_run_backtest(state: OptimizerState) -> OptimizerState:
    """Node 1 — run the backtest with the current strategy text."""
    iteration = state["iteration"] + 1
    strategy  = state["current_strategy"]
    max_iter  = state["max_iterations"]

    print(f"\n[Optimizer] ── Iteration {iteration}/{max_iter} ──")
    print(f"[Optimizer] Strategy: {strategy[:120]}...")

    try:
        result  = run_strategy_backtest(strategy)
        metrics = result.get("metrics", {})
        print(
            f"[Optimizer] Result: "
            f"Sharpe={metrics.get('sharpe_ratio','?')}, "
            f"Drawdown={metrics.get('max_drawdown_pct','?')}%, "
            f"WinRate={metrics.get('win_rate_pct','?')}%"
        )

        # Update best only if this run scores higher
        is_new_best  = _composite_score(metrics) > _composite_score(state["best_metrics"] or {})
        best_result  = result   if is_new_best else state["best_result"]
        best_metrics = metrics  if is_new_best else state["best_metrics"]

        log_entry = {
            "iteration": iteration,
            "strategy":  strategy,
            "metrics":   metrics,
            "is_best":   is_new_best,
        }

        return {
            **state,
            "iteration":      iteration,
            "iterations_log": state["iterations_log"] + [log_entry],
            "latest_metrics": metrics,      # ← always the current run
            "best_result":    best_result,
            "best_metrics":   best_metrics,
            "error":          "",
        }

    except Exception as e:
        print(f"[Optimizer] Backtest error: {e}")
        return {
            **state,
            "iteration":      iteration,
            "iterations_log": state["iterations_log"] + [{
                "iteration": iteration,
                "strategy":  strategy,
                "error":     str(e),
            }],
            "latest_metrics": None,
            "error":          str(e),
        }


@traceable(name="optimizer:evaluate", as_type="tool")
def _node_evaluate(state: OptimizerState) -> OptimizerState:
    """Node 2 — check if the LATEST run meets all thresholds."""
    if state["error"]:
        print(f"[Optimizer] Evaluate: last run errored — not passed")
        return {**state, "passed": False}

    # Evaluate the LATEST run's metrics, not best_metrics
    # (best_metrics may be from a previous iteration that was better overall
    #  but still didn't pass — we want to know if THIS run passed)
    latest = state["latest_metrics"] or {}
    passed, failures = _evaluate_metrics(latest, state["thresholds"])

    if passed:
        print(f"[Optimizer] ✓ All thresholds met on iteration {state['iteration']} — done")
    else:
        print(f"[Optimizer] ✗ Not met: {failures}")

    return {**state, "passed": passed}


@traceable(name="optimizer:refine_strategy", as_type="tool")
def _node_refine_strategy(state: OptimizerState) -> OptimizerState:
    """Node 3 — ask the LLM to suggest a better strategy."""
    latest   = state["latest_metrics"] or state["best_metrics"] or {}
    _, failures = _evaluate_metrics(latest, state["thresholds"])

    print(f"[Optimizer] Refining after iteration {state['iteration']}...")
    prompt = _build_refine_prompt(state, failures)

    try:
        refined = generate_response(prompt, use_search=False).strip()
        refined = re.sub(r"```[^\n]*\n?", "", refined).strip()
        print(f"[Optimizer] Refined strategy: {refined[:120]}...")
        return {**state, "current_strategy": refined, "error": ""}
    except Exception as e:
        print(f"[Optimizer] Refinement LLM error: {e}")
        return {**state, "error": str(e)}


# ---------------------------------------------------------------------------
# Routing — reads max_iterations from STATE, not module global
# ---------------------------------------------------------------------------

def _route_after_evaluate(state: OptimizerState) -> str:
    if state["passed"]:
        return END
    if state["iteration"] >= state["max_iterations"]:
        print(f"[Optimizer] Max iterations ({state['max_iterations']}) reached — stopping")
        return END
    return "refine_strategy"


def _route_after_refine(state: OptimizerState) -> str:
    # If refinement itself errored and we're at the limit, stop
    if state["error"] and state["iteration"] >= state["max_iterations"]:
        return END
    return "run_backtest"


# ---------------------------------------------------------------------------
# Build & compile the graph (once at import time)
# ---------------------------------------------------------------------------

_graph_builder = StateGraph(OptimizerState)
_graph_builder.add_node("run_backtest",    _node_run_backtest)
_graph_builder.add_node("evaluate",        _node_evaluate)
_graph_builder.add_node("refine_strategy", _node_refine_strategy)

_graph_builder.set_entry_point("run_backtest")
_graph_builder.add_edge("run_backtest", "evaluate")
_graph_builder.add_conditional_edges(
    "evaluate",
    _route_after_evaluate,
    {"refine_strategy": "refine_strategy", END: END},
)
_graph_builder.add_conditional_edges(
    "refine_strategy",
    _route_after_refine,
    {"run_backtest": "run_backtest", END: END},
)

optimizer_graph = _graph_builder.compile()
print("[Optimizer] LangGraph backtest optimizer compiled successfully")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

@traceable(name="run-backtest-optimizer", as_type="chain")
def run_backtest_optimizer(
    strategy: str,
    thresholds: dict | None = None,
    max_iterations: int = 5,
) -> dict:
    """
    Run the autonomous backtest optimization loop.

    Args:
        strategy:        Natural-language strategy description.
        thresholds:      Override default quality thresholds.
                         Keys: min_sharpe, max_drawdown_pct, min_win_rate_pct
        max_iterations:  Hard cap on backtest runs (default 5, max 10).

    Returns:
        {
          "passed":          bool,
          "iterations":      int,
          "best_result":     dict,
          "best_metrics":    dict,
          "iterations_log":  list[dict],
          "final_strategy":  str,
          "summary":         str,
        }
    """
    resolved_thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    capped_iterations   = min(max(max_iterations, 1), 10)  # clamp 1–10

    initial_state: OptimizerState = {
        "original_strategy": strategy,
        "thresholds":        resolved_thresholds,
        "max_iterations":    capped_iterations,   # ← in state, not module global
        "current_strategy":  strategy,
        "iteration":         0,
        "iterations_log":    [],
        "best_result":       None,
        "best_metrics":      None,
        "latest_metrics":    None,
        "passed":            False,
        "error":             "",
    }

    final_state = optimizer_graph.invoke(initial_state)

    m = final_state.get("best_metrics") or {}
    if final_state["passed"]:
        summary = (
            f"✓ Strategy optimized in {final_state['iteration']} iteration(s). "
            f"Final metrics — Sharpe: {m.get('sharpe_ratio','?')}, "
            f"Max Drawdown: {m.get('max_drawdown_pct','?')}%, "
            f"Win Rate: {m.get('win_rate_pct','?')}%."
        )
    else:
        summary = (
            f"Optimization stopped after {final_state['iteration']} iteration(s) "
            f"without meeting all thresholds. "
            f"Best result — Sharpe: {m.get('sharpe_ratio','?')}, "
            f"Max Drawdown: {m.get('max_drawdown_pct','?')}%, "
            f"Win Rate: {m.get('win_rate_pct','?')}%."
        )

    return {
        "passed":         final_state["passed"],
        "iterations":     final_state["iteration"],
        "best_result":    final_state["best_result"],
        "best_metrics":   final_state["best_metrics"],
        "iterations_log": final_state["iterations_log"],
        "final_strategy": final_state["current_strategy"],
        "summary":        summary,
    }
