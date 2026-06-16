"""
MokshaGPT ReAct Research Agent — LLM-as-Judge Evaluation Harness
Run: python evaluator.py
Logs scores to LangFuse automatically.
"""

import json
import asyncio
import httpx
import os
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional
from langfuse import Langfuse

# ── env loader ────────────────────────────────────────────────────────────────

def _load_env_file(env_path: str) -> dict:
    """
    Parse a .env file and return key-value pairs.
    System / Cloud Run environment variables take precedence over file values.
    """
    env_vars: dict = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    # Strip inline comments and surrounding quotes
                    value = value.split("#")[0].strip().strip('"').strip("'")
                    env_vars[key.strip()] = value
    # System env vars always take precedence (Cloud Run / CI pipelines)
    for key in [
        "ANTHROPIC_API_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_HOST",
        "RESEARCH_AGENT_URL",
    ]:
        if key in os.environ:
            env_vars[key] = os.environ[key]
    return env_vars


# Resolve .env path relative to this file so the harness works regardless of
# the working directory from which it is invoked.
_env_path = os.path.join(os.path.dirname(__file__), ".env")
_env = _load_env_file(_env_path)

# ── config ────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY  = _env.get("ANTHROPIC_API_KEY",  "YOUR_ANTHROPIC_API_KEY")
LANGFUSE_SECRET_KEY = _env.get("LANGFUSE_SECRET_KEY", "YOUR_LANGFUSE_SECRET_KEY")
LANGFUSE_PUBLIC_KEY = _env.get("LANGFUSE_PUBLIC_KEY", "YOUR_LANGFUSE_PUBLIC_KEY")
LANGFUSE_HOST       = _env.get("LANGFUSE_HOST",       "https://cloud.langfuse.com")

# MokshaGPT research agent endpoint
RESEARCH_AGENT_URL  = _env.get("RESEARCH_AGENT_URL",  "http://localhost:8000/research/stream")

# ── data models ───────────────────────────────────────────────────────────────

@dataclass
class EvalScore:
    factual_grounding: float      # 1-5: are claims backed by specific data?
    reasoning_coherence: float    # 1-5: does analysis follow logically from data?
    completeness: float           # 1-5: does it fully address the question?
    hallucination_risk: float     # 1-5: 5=no hallucination, 1=high hallucination
    tool_relevance: float         # 1-5: did agent use the right tools?
    overall: float                # 1-5: overall quality
    explanation: str              # judge's reasoning

@dataclass
class EvalResult:
    query: str
    query_type: str
    agent_response: str
    tool_calls_used: list
    scores: EvalScore
    passed: bool
    trace_id: Optional[str]
    timestamp: str

# ── golden test dataset ───────────────────────────────────────────────────────

GOLDEN_DATASET = [
    # ── factual / price queries ──
    {
        "id": "TC001",
        "query": "What is the current price and RSI of RELIANCE.NS?",
        "type": "factual_numeric",
        "expected_tools": ["price", "indicators"],
        "must_contain": ["RSI", "price", "RELIANCE"],
        "must_not_contain": ["I don't know", "cannot access"],
        "pass_threshold": 3.5,
    },
    {
        "id": "TC002",
        "query": "Is HDFCBANK.NS above its 50-day moving average?",
        "type": "factual_numeric",
        "expected_tools": ["indicators", "price"],
        "must_contain": ["SMA", "50", "HDFCBANK"],
        "must_not_contain": [],
        "pass_threshold": 3.5,
    },
    {
        "id": "TC003",
        "query": "What is the current USD/INR exchange rate?",
        "type": "factual_numeric",
        "expected_tools": ["forex"],
        "must_contain": ["USD", "INR"],
        "must_not_contain": [],
        "pass_threshold": 3.5,
    },

    # ── comparative / analytical queries ──
    {
        "id": "TC004",
        "query": "Should I buy Reliance or HDFC Bank right now? Compare both.",
        "type": "comparative",
        "expected_tools": ["price", "indicators", "analyze"],
        "must_contain": ["RELIANCE", "HDFC", "RSI"],
        "must_not_contain": ["financial advice"],
        "pass_threshold": 3.5,
    },
    {
        "id": "TC005",
        "query": "Compare Nifty 50 and Bank Nifty performance over the last month.",
        "type": "comparative",
        "expected_tools": ["price", "analyze"],
        "must_contain": ["Nifty", "Bank Nifty", "%"],
        "must_not_contain": [],
        "pass_threshold": 3.5,
    },

    # ── strategy / advisory queries ──
    {
        "id": "TC006",
        "query": "My EMA crossover strategy on Nifty is giving too many false signals. What should I try instead?",
        "type": "advisory",
        "expected_tools": ["analyze", "backtest"],
        "must_contain": ["strategy", "signal"],
        "must_not_contain": [],
        "pass_threshold": 3.0,
    },
    {
        "id": "TC007",
        "query": "What trading strategies work well for high-volatility markets?",
        "type": "advisory",
        "expected_tools": ["analyze", "general"],
        "must_contain": ["volatility", "strategy"],
        "must_not_contain": [],
        "pass_threshold": 3.0,
    },

    # ── backtest queries ──
    {
        "id": "TC008",
        "query": "Backtest a simple RSI strategy on TCS.NS for the last 2 years.",
        "type": "backtest",
        "expected_tools": ["backtest"],
        "must_contain": ["RSI", "TCS", "Sharpe"],
        "must_not_contain": [],
        "pass_threshold": 3.5,
    },
    {
        "id": "TC009",
        "query": "What is the Sharpe ratio of a buy-and-hold strategy on Nifty 50?",
        "type": "backtest",
        "expected_tools": ["backtest"],
        "must_contain": ["Sharpe", "Nifty"],
        "must_not_contain": [],
        "pass_threshold": 3.5,
    },

    # ── screening queries ──
    {
        "id": "TC010",
        "query": "Find Nifty 50 stocks with RSI below 30 and above their 200-day moving average.",
        "type": "screening",
        "expected_tools": ["screen"],
        "must_contain": ["RSI", "SMA", "200"],
        "must_not_contain": [],
        "pass_threshold": 3.5,
    },
    {
        "id": "TC011",
        "query": "Screen for large-cap Indian stocks with P/E below 20 and positive momentum.",
        "type": "screening",
        "expected_tools": ["screen"],
        "must_contain": ["P/E", "momentum"],
        "must_not_contain": [],
        "pass_threshold": 3.0,
    },

    # ── multi-step reasoning queries ──
    {
        "id": "TC012",
        "query": "Is the Indian market overbought right now? Give me a full technical picture.",
        "type": "multi_step",
        "expected_tools": ["price", "indicators", "analyze"],
        "must_contain": ["RSI", "Nifty", "overbought"],
        "must_not_contain": [],
        "pass_threshold": 3.5,
    },
    {
        "id": "TC013",
        "query": "What is the best entry point for INFY.NS based on technical analysis?",
        "type": "multi_step",
        "expected_tools": ["price", "indicators", "analyze"],
        "must_contain": ["INFY", "support", "resistance"],
        "must_not_contain": [],
        "pass_threshold": 3.0,
    },

    # ── edge cases / robustness ──
    {
        "id": "TC014",
        "query": "What is the price of FAKESTOCKXYZ123?",
        "type": "edge_case",
        "expected_tools": ["price"],
        "must_contain": [],
        "must_not_contain": ["100", "200", "₹"],  # should not hallucinate a price
        "pass_threshold": 3.0,
    },
    {
        "id": "TC015",
        "query": "Give me a complete analysis of the global macro environment and its impact on Nifty.",
        "type": "multi_step",
        "expected_tools": ["price", "analyze", "general"],
        "must_contain": ["Nifty", "macro"],
        "must_not_contain": [],
        "pass_threshold": 3.0,
    },
]

# ── judge prompt ──────────────────────────────────────────────────────────────

JUDGE_SYSTEM_PROMPT = """You are an expert evaluator for financial AI research agents.
Your job is to objectively score agent responses on five dimensions.
You must return ONLY valid JSON — no preamble, no markdown, no explanation outside the JSON.
Be strict. A score of 5 means truly excellent. Most responses should score 2-4."""

def build_judge_prompt(query: str, response: str, tool_calls: list,
                       must_contain: list, must_not_contain: list) -> str:
    # Get the current local date for the evaluation environment context
    today_date = datetime.now().strftime("%B %d, %Y")
    
    return f"""Evaluate this financial research agent response.

CURRENT DATE CONTEXT (Today is): {today_date}
(Note: Do NOT penalize the agent if its response is dated on or around this date. This is the real current date in the evaluation environment, not a hallucination.)

MOKSHAGPT AGENT TOOLS AND THEIR PURPOSE:
- indicators: Fetch and compute technical indicators (RSI, moving averages, Bollinger Bands, CPR, Camarilla pivots, volatility, ATR, 52-week range) for a stock or index.
- analyze: Run a natural language technical and fundamental analysis narrative on a stock/index.
- price: Fetch the latest real-time price or rate for an asset.
- forex: Analyze a forex currency pair.
- options: Analyze options chains and contract details.
- futures: Analyze futures curves, contango/backwardation, and commodities.
- backtest: Run a historical backtest of a strategy.
- screen: Screen stocks using fundamental/technical filters.
- general: Answer general concept/educational finance questions (no ticker/real-time data).
- final_answer: Return the final synthesized answer.

QUERY: {query}

TOOLS CALLED BY AGENT: {json.dumps(tool_calls)}
(Note: Do NOT penalize the agent's tool relevance for calling "indicators" or "analyze" for technical/analytical stock or index queries, as they are the correct data fetching and narrative analysis tools in this system. Do NOT penalize using "general" for conceptual queries with no specific tickers.)

AGENT RESPONSE:
{response}

MUST CONTAIN (check if these appear): {must_contain}
MUST NOT CONTAIN (check if these appear, penalise if they do): {must_not_contain}

Score each dimension from 1 to 5:
- factual_grounding: Are specific data points cited (prices, RSI values, percentages, dates)? 5=highly specific data, 1=vague generalities
- reasoning_coherence: Does the analysis follow logically from the tool outputs? 5=tight logical flow, 1=conclusions not supported by data
- completeness: Does it fully address what was asked? 5=comprehensive answer, 1=misses the main question
- hallucination_risk: Did the agent make claims not grounded in tool outputs? 5=no hallucination detected, 1=clear hallucination.
  IMPORTANT: Do NOT penalize hallucination merely because you cannot independently verify real-time prices, exchange rates, or indicator values. If the agent called a tool (price, forex, indicators, etc.) and then cited specific numbers, assume those numbers came from the tool. Only penalize if the agent cited data without calling any relevant tool, or if values are logically impossible.
- tool_relevance: Did the agent call appropriate tools for this query? 5=perfect tool selection, 1=wrong tools or missing critical ones
- overall: Holistic quality score

Return ONLY this JSON:
{{
  "factual_grounding": <1-5>,
  "reasoning_coherence": <1-5>,
  "completeness": <1-5>,
  "hallucination_risk": <1-5>,
  "tool_relevance": <1-5>,
  "overall": <1-5>,
  "explanation": "<2-3 sentence summary of why you gave these scores>"
}}"""

# ── agent caller ──────────────────────────────────────────────────────────────

async def call_research_agent(query: str) -> tuple[str, list, Optional[str]]:
    """
    Call your MokshaGPT research agent.
    Returns (response_text, tool_calls_list, trace_id)
    Adapt this to match your actual /research/stream endpoint behaviour.
    """
    response_text = ""
    tool_calls = []
    trace_id = None

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST", RESEARCH_AGENT_URL,
                json={"message": query},
                headers={"Content-Type": "application/json"}
            ) as response:
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    # Parse SSE format: "data: {...}"
                    # Backend emits: {"event": "step"|"result"|"error", ...}
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            event = data.get("event", "")

                            if event == "step":
                                # Intermediate tool-call step
                                tool = data.get("tool", "")
                                if tool and tool not in tool_calls:
                                    tool_calls.append(tool)

                            elif event == "result":
                                # Final answer — prefer "answer" field, fall back to "content"
                                response_text = data.get("answer") or data.get("content", "")
                                trace_id = data.get("trace_id")

                            elif event == "error":
                                response_text = f"[Agent error] {data.get('message', '')}"

                        except json.JSONDecodeError:
                            response_text += line[6:]

    except httpx.ConnectError:
        # Agent not running — return mock for testing the eval harness itself
        response_text = f"[MOCK] Agent not reachable. Query was: {query}"
        tool_calls = ["mock_tool"]

    return response_text, tool_calls, trace_id

# ── llm judge ─────────────────────────────────────────────────────────────────

async def judge_response(query: str, response: str, tool_calls: list,
                          must_contain: list, must_not_contain: list) -> EvalScore:
    """Call Claude as the judge to score the agent response."""
    prompt = build_judge_prompt(query, response, tool_calls, must_contain, must_not_contain)

    async with httpx.AsyncClient(timeout=30.0) as client:
        result = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5",
                "max_tokens": 512,
                "system": JUDGE_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}]
            }
        )
        result.raise_for_status()
        raw = result.json()["content"][0]["text"].strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        scores = json.loads(raw)
        return EvalScore(
            factual_grounding=float(scores["factual_grounding"]),
            reasoning_coherence=float(scores["reasoning_coherence"]),
            completeness=float(scores["completeness"]),
            hallucination_risk=float(scores["hallucination_risk"]),
            tool_relevance=float(scores["tool_relevance"]),
            overall=float(scores["overall"]),
            explanation=scores["explanation"]
        )

# ── langfuse logger ───────────────────────────────────────────────────────────

def log_to_langfuse(lf: Langfuse, result: EvalResult):
    """Push eval scores back into LangFuse so they appear on agent traces."""
    try:
        scores = asdict(result.scores)

        # If we have the original trace ID from the agent run, attach scores to it
        if result.trace_id:
            for metric_name, value in scores.items():
                if metric_name == "explanation":
                    continue
                lf.create_score(
                    trace_id=result.trace_id,
                    name=f"eval_{metric_name}",
                    value=value,
                    comment=result.scores.explanation
                )
        else:
            # No agent trace ID — create a synthetic trace ID and log scores against it
            trace_id = lf.create_trace_id()
            for metric_name, value in scores.items():
                if metric_name == "explanation":
                    continue
                lf.create_score(
                    trace_id=trace_id,
                    name=f"eval_{metric_name}",
                    value=value,
                    comment=result.scores.explanation
                )
    except Exception as e:
        print(f"  [WARN] LangFuse logging failed: {e}")

# ── report printer ────────────────────────────────────────────────────────────

def print_report(results: list[EvalResult]):
    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]

    print("\n" + "=" * 70)
    print("  MOKSHAGPT RESEARCH AGENT -- EVALUATION REPORT")
    print("=" * 70)
    print(f"  Total:   {len(results)} test cases")
    print(f"  Passed:  {len(passed)}  ({100*len(passed)//len(results)}%)")
    print(f"  Failed:  {len(failed)}")

    # Average scores
    def avg(metric):
        return sum(getattr(r.scores, metric) for r in results) / len(results)

    print(f"\n  Average scores:")
    print(f"  Factual grounding   {avg('factual_grounding'):.2f} / 5.0")
    print(f"  Reasoning coherence {avg('reasoning_coherence'):.2f} / 5.0")
    print(f"  Completeness        {avg('completeness'):.2f} / 5.0")
    print(f"  Hallucination risk  {avg('hallucination_risk'):.2f} / 5.0")
    print(f"  Tool relevance      {avg('tool_relevance'):.2f} / 5.0")
    print(f"  Overall             {avg('overall'):.2f} / 5.0")

    # By query type
    types = sorted(set(r.query_type for r in results))
    print(f"\n  Results by query type:")
    for t in types:
        group = [r for r in results if r.query_type == t]
        p = len([r for r in group if r.passed])
        avg_overall = sum(r.scores.overall for r in group) / len(group)
        print(f"  {t:<20} {p}/{len(group)} passed   avg overall {avg_overall:.2f}")

    # Failed cases
    if failed:
        print(f"\n  Failed test cases:")
        for r in failed:
            print(f"  [FAIL] [{r.query_type}] {r.query[:60]}...")
            print(f"    Overall: {r.scores.overall:.1f} | {r.scores.explanation[:100]}...")

    print("=" * 70 + "\n")

# ── save results ──────────────────────────────────────────────────────────────

def save_results(results: list[EvalResult]):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"eval_results_{timestamp}.json"
    with open(filename, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)
    print(f"  Results saved to {filename}")

# ── main runner ───────────────────────────────────────────────────────────────

async def run_single(tc: dict, lf: Langfuse) -> EvalResult:
    print(f"  Running {tc['id']}: {tc['query'][:55]}...")

    # Step 1 — call your agent
    response, tool_calls, trace_id = await call_research_agent(tc["query"])

    # Step 2 — judge the response
    scores = await judge_response(
        query=tc["query"],
        response=response,
        tool_calls=tool_calls,
        must_contain=tc.get("must_contain", []),
        must_not_contain=tc.get("must_not_contain", [])
    )

    # Step 3 — determine pass/fail
    passed = scores.overall >= tc["pass_threshold"]

    result = EvalResult(
        query=tc["query"],
        query_type=tc["type"],
        agent_response=response,
        tool_calls_used=tool_calls,
        scores=scores,
        passed=passed,
        trace_id=trace_id,
        timestamp=datetime.now().isoformat()
    )

    # Step 4 — log to LangFuse
    log_to_langfuse(lf, result)

    status = "[PASS]" if passed else "[FAIL]"
    print(f"  {status} Overall: {scores.overall:.1f}/5.0 | Hallucination: {scores.hallucination_risk:.1f} | {scores.explanation[:70]}...")

    return result


async def run_eval(test_ids: Optional[list] = None):
    """
    Run the full evaluation suite.
    Pass test_ids=["TC001","TC002"] to run specific tests only.
    """
    lf = Langfuse(
        secret_key=LANGFUSE_SECRET_KEY,
        public_key=LANGFUSE_PUBLIC_KEY,
        host=LANGFUSE_HOST
    )

    dataset = GOLDEN_DATASET
    if test_ids:
        dataset = [tc for tc in GOLDEN_DATASET if tc["id"] in test_ids]

    print(f"\nMokshaGPT Research Agent Evaluation")
    print(f"Running {len(dataset)} test cases...\n")

    results = []
    for tc in dataset:
        try:
            result = await run_single(tc, lf)
            results.append(result)
            await asyncio.sleep(1)  # rate limit buffer
        except Exception as e:
            print(f"  ERROR on {tc['id']}: {e}")

    print_report(results)
    save_results(results)

    lf.flush()
    return results


if __name__ == "__main__":
    import sys
    # Run specific tests: python evaluator.py TC001 TC002
    # Run all: python evaluator.py
    test_ids = sys.argv[1:] if len(sys.argv) > 1 else None
    asyncio.run(run_eval(test_ids))
