import asyncio
from functools import partial

# Patch yfinance with a browser User-Agent before any other imports use it.
# Yahoo Finance blocks/rate-limits requests from cloud datacenter IPs when
# the default Python UA is used — this resolves the issue.
from yf_session import patch_yfinance_session
patch_yfinance_session()

from llm_factory import generate_response, _env
from backtester import run_strategy_backtest
from agent import run_agent
from screener import run_stock_screener
from asset_detector import detect_assets, get_primary_asset_type, AssetType
from forex_data import analyze_forex_pair
from options_data import get_options_chain, analyze_covered_call
from futures_data import analyze_contango_backwardation
from report_generator import run_report_generator, REPORT_TYPES
from trade_analyzer import run_trade_review
from ensemble_builder import run_ensemble_builder
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

_use_search = _env.get("USE_SEARCH", "false").lower() == "true"


@app.get("/health")
async def health():
    """Health check endpoint — used by ALB and ECS to verify the container is ready."""
    return {"status": "ok"}


def _run_in_thread(func, *args):
    """Helper: run a blocking function in the default thread pool."""
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, func, *args)


@app.get("/analyze")
async def analyze(ticker: str):
    return await _run_in_thread(
        generate_response,
        f"How is {ticker} to Trade tomorrow?",
    )


class ConversationTurn(BaseModel):
    role: str          # "user" | "assistant"
    content: str       # plain-text summary of the turn


class BacktestRequest(BaseModel):
    strategy: str
    conversation_history: Optional[List[ConversationTurn]] = []


def _build_backtest_context(strategy: str, history: List[ConversationTurn]) -> str:
    """
    Prepend a compact conversation summary to the strategy text so the LLM
    can resolve references like "same ticker", "change RSI to 20", etc.
    Only the last 4 turns are included to keep token usage bounded.
    """
    if not history:
        return strategy

    recent = history[-4:]  # max 4 prior turns (2 exchanges)
    lines = ["Previous conversation context (use to resolve references):"]
    for turn in recent:
        prefix = "User" if turn.role == "user" else "Result"
        lines.append(f"  {prefix}: {turn.content}")
    lines.append(f"\nNew request: {strategy}")
    return "\n".join(lines)


@app.post("/backtest")
async def backtest(req: BacktestRequest):
    try:
        enriched = _build_backtest_context(req.strategy, req.conversation_history or [])
        result = await _run_in_thread(run_strategy_backtest, enriched)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Backtest Q&A endpoint ─────────────────────────────────────────────────────

class BacktestQAMessage(BaseModel):
    role: str     # "user" | "assistant"
    content: str


class BacktestQARequest(BaseModel):
    question: str
    backtest_summary: str                          # compact JSON/text summary of the result
    chat_history: Optional[List[BacktestQAMessage]] = []


def _build_qa_prompt(question: str, backtest_summary: str, history: List[BacktestQAMessage]) -> str:
    from llm_factory import PROMPTS, format_prompt
    history_text = ""
    if history:
        lines = []
        for msg in history[-8:]:   # keep last 4 exchanges (8 messages)
            prefix = "User" if msg.role == "user" else "Assistant"
            lines.append(f"{prefix}: {msg.content}")
        history_text = "\n".join(lines)
    else:
        history_text = "(none yet)"

    return format_prompt(
        PROMPTS["backtest_qa_prompt"],
        backtest_summary=backtest_summary,
        chat_history=history_text,
        question=question,
    )


@app.post("/backtest/chat")
async def backtest_chat(req: BacktestQARequest):
    """
    Q&A chat grounded in a completed backtest result.
    Does NOT re-run the backtest — answers questions about the existing result.
    Returns: { answer: str }
    """
    try:
        from llm_factory import generate_response
        prompt = _build_qa_prompt(req.question, req.backtest_summary, req.chat_history or [])
        answer = await _run_in_thread(generate_response, prompt, None, None, False)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── LangGraph Agent endpoint ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Single unified endpoint powered by the LangGraph agent.
    Runs in a thread pool so the event loop stays free for other requests.
    Returns: { type: "analysis" | "backtest" | "unknown", content: ... }
    """
    try:
        result = await _run_in_thread(run_agent, req.message)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Stock Screener endpoint ───────────────────────────────────────────────────

class ScreenerRequest(BaseModel):
    query: str


@app.post("/screen")
async def screen(req: ScreenerRequest):
    """
    AI-powered stock screener endpoint.
    Accepts natural language queries and returns matching stocks.
    Returns: { query: str, criteria: list, stocks: list, total_matches: int }
    """
    try:
        result = await _run_in_thread(run_stock_screener, req.query)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Multi-Asset Analysis endpoints ───────────────────────────────────────────

class ForexRequest(BaseModel):
    pair: str


@app.post("/forex")
async def forex_analysis(req: ForexRequest):
    """
    Forex pair analysis endpoint.
    Analyzes currency pairs with technical indicators and economic events.
    """
    try:
        result = await _run_in_thread(analyze_forex_pair, req.pair)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class OptionsRequest(BaseModel):
    symbol: str  # Either option symbol (AAPL240315C150) or underlying (AAPL)


@app.post("/options")
async def options_analysis(req: OptionsRequest):
    """
    Options analysis endpoint.
    Analyzes options chains, Greeks, and strategies.
    """
    try:
        from options_data import get_options_chain, get_option_contract
        
        # Detect if it's a specific option contract or underlying
        if len(req.symbol) > 10 and any(c in req.symbol for c in ['C', 'P']):
            # Specific option contract
            contract = get_option_contract(req.symbol)
            if not contract:
                raise HTTPException(status_code=404, detail=f"Option contract {req.symbol} not found")
            
            result = {
                "type": "option_contract",
                "contract": {
                    "symbol": contract.symbol,
                    "underlying": contract.underlying,
                    "strike": contract.strike,
                    "expiry": contract.expiry.isoformat(),
                    "option_type": contract.option_type,
                    "last_price": contract.last,
                    "bid": contract.bid,
                    "ask": contract.ask,
                    "volume": contract.volume,
                    "open_interest": contract.open_interest,
                    "implied_volatility": contract.implied_volatility,
                    "greeks": {
                        "delta": contract.delta,
                        "gamma": contract.gamma,
                        "theta": contract.theta,
                        "vega": contract.vega,
                        "rho": contract.rho
                    },
                    "intrinsic_value": contract.intrinsic_value,
                    "time_value": contract.time_value,
                    "days_to_expiry": contract.days_to_expiry
                }
            }
        else:
            # Options chain for underlying
            chain = get_options_chain(req.symbol)
            if not chain:
                raise HTTPException(status_code=404, detail=f"Options chain for {req.symbol} not found")
            
            result = {
                "type": "options_chain",
                "underlying": chain.underlying,
                "spot_price": chain.spot_price,
                "iv_rank": chain.iv_rank,
                "iv_30d_avg": chain.iv_30d_avg,
                "expiry_dates": [exp.isoformat() for exp in chain.expiry_dates],
                "calls": [
                    {
                        "strike": c.strike,
                        "expiry": c.expiry.isoformat(),
                        "last": c.last,
                        "bid": c.bid,
                        "ask": c.ask,
                        "volume": c.volume,
                        "open_interest": c.open_interest,
                        "implied_volatility": c.implied_volatility,
                        "delta": c.delta,
                        "gamma": c.gamma,
                        "theta": c.theta,
                        "vega": c.vega
                    } for c in chain.calls[:20]  # Limit to first 20
                ],
                "puts": [
                    {
                        "strike": p.strike,
                        "expiry": p.expiry.isoformat(),
                        "last": p.last,
                        "bid": p.bid,
                        "ask": p.ask,
                        "volume": p.volume,
                        "open_interest": p.open_interest,
                        "implied_volatility": p.implied_volatility,
                        "delta": p.delta,
                        "gamma": p.gamma,
                        "theta": p.theta,
                        "vega": p.vega
                    } for p in chain.puts[:20]  # Limit to first 20
                ]
            }
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class FuturesRequest(BaseModel):
    symbol: str  # e.g., "/ES", "/GC", "/CL"


@app.post("/futures")
async def futures_analysis(req: FuturesRequest):
    """
    Futures analysis endpoint.
    Analyzes futures curves, contango/backwardation, and roll strategies.
    """
    try:
        result = await _run_in_thread(analyze_contango_backwardation, req.symbol)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class AssetDetectionRequest(BaseModel):
    query: str


@app.post("/detect-assets")
async def detect_assets_endpoint(req: AssetDetectionRequest):
    """
    Asset detection endpoint.
    Detects asset types and symbols from natural language queries.
    """
    try:
        assets = detect_assets(req.query)
        primary_type = get_primary_asset_type(req.query)
        
        return {
            "query": req.query,
            "primary_asset_type": primary_type.value,
            "detected_assets": [
                {
                    "asset_type": asset.asset_type.value,
                    "symbol": asset.symbol,
                    "exchange": asset.exchange,
                    "metadata": asset.metadata
                } for asset in assets
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from three_s_trader import run_3s_trader
from research_agent import run_research_agent, run_research_agent_stream
from backtest_optimizer import run_backtest_optimizer, DEFAULT_THRESHOLDS


# ── ReAct Research Agent endpoint ────────────────────────────────────────────

class ResearchTurn(BaseModel):
    role: str      # "user" | "assistant"
    content: str


class ResearchRequest(BaseModel):
    message: str
    conversation_history: Optional[List[ResearchTurn]] = []
    session_id: Optional[str] = None   # passed by frontend for Langfuse session grouping
    user_id: Optional[str] = None      # optional user identifier


@app.post("/research")
async def research(req: ResearchRequest):
    """
    Multi-step ReAct research agent endpoint.

    Unlike /chat (one-shot router that calls exactly one tool and returns raw output),
    this agent uses the ReAct (Reasoning + Acting) loop:
    - Fetches live price + technicals before LLM analysis (grounded in real numbers)
    - Chains multiple tools (analyze → backtest → screen) based on intermediate results
    - Supports multi-turn conversation history for context resolution
    - Returns the full reasoning trace (scratchpad) so users can see how the answer was built

    Use /chat for simple, single-intent queries ("price of AAPL", "backtest SMA on TCS").
    Use /research for complex, multi-part questions ("Should I buy Reliance vs HDFC?",
    "My SMA strategy isn't working, what should I try instead?").

    Returns:
    {
      "type":     str,          # intent badge (analysis/price/backtest/screen/forex/options/futures)
      "content":  str,          # final synthesized answer (markdown) — same key as /chat
      "answer":   str,          # alias of content (for API consumers)
      "steps": [                # reasoning trace (not present in /chat)
        {
          "thought": str,
          "tool": str,
          "tool_input": dict,
          "observation": str
        }
      ],
      "step_count": int
    }
    """
    try:
        history = [{"role": t.role, "content": t.content} for t in (req.conversation_history or [])]
        result = await _run_in_thread(
            run_research_agent,
            req.message,
            history,
            req.session_id,
            req.user_id,
        )
        # Mirror /chat's response shape so the frontend works with both endpoints.
        # For structured results (screen, backtest) the content field already holds
        # the rich dict the frontend needs — don't overwrite it with the answer string.
        if result.get("type") not in ("screen", "backtest"):
            result["content"] = result.get("answer", "")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/research/stream")
async def research_stream(req: ResearchRequest):
    """
    Streaming variant of /research using Server-Sent Events (SSE).

    Emits a stream of SSE events while the ReAct agent runs:
      data: {"event": "step",   "thought": str, "tool": str, "label": str, "step": int}
      data: {"event": "result", "type": str, "answer": str, "content": any, ...}
      data: {"event": "error",  "message": str}

    The client reads the stream and updates the UI progressively.
    """
    history = [{"role": t.role, "content": t.content} for t in (req.conversation_history or [])]

    def event_generator():
        for chunk in run_research_agent_stream(req.message, history, req.session_id, req.user_id):
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Ensemble Builder endpoint ────────────────────────────────────────────────

class EnsembleRequest(BaseModel):
    query: str

@app.post("/ensemble-backtest")
async def ensemble_backtest(req: EnsembleRequest):
    """
    Multi-Strategy Ensemble Builder
    Generates 3 diverse strategies for the asset and runs them concurrently,
    returning the aggregated portfolio metrics and combined equity curve.
    """
    try:
        result = await run_ensemble_builder(req.query)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Backtest Optimizer endpoints ─────────────────────────────────────────────

class BacktestOptimizeRequest(BaseModel):
    strategy: str
    thresholds: Optional[dict] = None   # override DEFAULT_THRESHOLDS keys
    max_iterations: Optional[int] = 5


@app.post("/backtest/optimize")
async def backtest_optimize(req: BacktestOptimizeRequest):
    """
    Autonomous backtest optimization loop (LangGraph).

    Runs the strategy, evaluates Sharpe / drawdown / win-rate against thresholds,
    and iteratively refines the strategy via LLM until all thresholds are met
    or max_iterations is reached.

    Body:
      strategy        — natural-language strategy (same format as /backtest)
      thresholds      — optional overrides:
                          min_sharpe        (default 0.8)
                          max_drawdown_pct  (default -20.0)
                          min_win_rate_pct  (default 45.0)
      max_iterations  — hard cap on backtest runs (default 5, max 10)

    Returns:
      {
        "passed":         bool,
        "iterations":     int,
        "best_result":    dict,   // full backtest result of the best run
        "best_metrics":   dict,
        "iterations_log": list,   // one entry per iteration
        "final_strategy": str,    // strategy text of the best run
        "summary":        str     // human-readable outcome
      }
    """
    try:
        max_iter = min(req.max_iterations or 5, 10)   # hard cap at 10
        result = await _run_in_thread(
            run_backtest_optimizer,
            req.strategy,
            req.thresholds,
            max_iter,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/backtest/optimize/thresholds")
async def backtest_optimize_thresholds():
    """Return the default quality thresholds used by the optimizer."""
    return {"defaults": DEFAULT_THRESHOLDS}


class ThreeSTraderRequest(BaseModel):
    tickers: List[str]
    initial_strategy: Optional[str] = None
    strategy_history: Optional[List[dict]] = None
    last_week_result: Optional[dict] = None


@app.post("/3s-trader")
async def three_s_trader(req: ThreeSTraderRequest):
    """
    3S-Trader: Multi-LLM Framework for Adaptive Stock Scoring, Strategy, and Selection.
    Runs in a thread pool to avoid blocking the event loop.
    """
    try:
        fn = partial(
            run_3s_trader,
            tickers=req.tickers,
            initial_strategy=req.initial_strategy,
            strategy_history=req.strategy_history,
            last_week_result=req.last_week_result,
        )
        result = await _run_in_thread(fn)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── AI Report Generator endpoints ────────────────────────────────────────────

@app.get("/report/templates")
async def report_templates():
    """
    Return available report types and their display names.
    Used by the frontend to populate the report type selector.
    """
    return {
        "report_types": [
            {"id": k, "label": v}
            for k, v in REPORT_TYPES.items()
        ],
        "tones": [
            {"id": "professional", "label": "Professional"},
            {"id": "formal", "label": "Formal"},
            {"id": "conversational", "label": "Conversational"},
        ],
    }


@app.post("/report/generate")
async def generate_report_endpoint(
    file: UploadFile = File(...),
    report_type: str = Form("portfolio_summary"),
    firm_name: str = Form("Our Firm"),
    client_name: str = Form("Valued Client"),
    report_period: str = Form(""),
    custom_instructions: str = Form(""),
    tone: str = Form("professional"),
):
    """
    AI-powered financial report generator.

    Accepts an Excel (.xlsx/.xls) or CSV file plus report configuration,
    and returns a structured narrative report with sections, executive summary,
    and QC warnings.

    Form fields:
      - file:                 Excel or CSV file (multipart upload)
      - report_type:          portfolio_summary | performance_review | market_commentary |
                              client_letter | risk_report | custom
      - firm_name:            Wealth management firm name
      - client_name:          Client name for personalised reports
      - report_period:        e.g. "Q1 2026", "January 2026"
      - custom_instructions:  Additional guidance for the LLM
      - tone:                 professional | formal | conversational

    Returns:
      {
        "report_type": str,
        "title": str,
        "generated_at": str,
        "firm_name": str,
        "client_name": str,
        "report_period": str,
        "currency": str,
        "as_of_date": str | null,
        "executive_summary": str,
        "sections": [{"heading": str, "content": str}, ...],
        "qc_warnings": list[str],
        "qc_errors": list[str],
        "qc_passed": bool,
        "metadata": dict
      }
    """
    # Validate file type
    filename = file.filename or "upload.xlsx"
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext not in ("xlsx", "xls", "xlsm", "csv"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{ext}'. Please upload an Excel (.xlsx/.xls) or CSV file.",
        )

    # Read file bytes
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {e}")

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(file_bytes) > 20 * 1024 * 1024:  # 20 MB limit
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 20 MB.")

    # Run report generation in thread pool
    try:
        fn = partial(
            run_report_generator,
            file_bytes=file_bytes,
            filename=filename,
            report_type=report_type,
            firm_name=firm_name,
            client_name=client_name,
            report_period=report_period,
            custom_instructions=custom_instructions,
            tone=tone,
        )
        result = await _run_in_thread(fn)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Trade Analyzer (Retail) endpoint ─────────────────────────────────────────

@app.post("/tradeanalyzer/analyze")
async def trade_review_endpoint(
    file: UploadFile = File(...),
    trader_name: str = Form("Trader"),
    review_period: str = Form(""),
):
    """
    Retail brokerage account review.

    Accepts a CSV or Excel trade history export from Zerodha, Groww, Angel One,
    Robinhood, IBKR, Fidelity, or any generic format, and returns:
      - Broker auto-detection
      - FIFO realized P&L per trade
      - Monthly breakdown (P&L, win rate, trade count, fees)
      - Overtrading detection (volume spikes, revenge trading, win-rate collapse)
      - Consistency score (0–10) with sub-scores
      - Symbol breakdown (best/worst tickers)
      - Holding period analysis (winners vs losers)
      - Day-of-week win rate pattern
      - AI narrative (plain-English coaching summary)

    Form fields:
      - file:          CSV or Excel trade history file (max 10 MB)
      - trader_name:   Your name (used in the report)
      - review_period: e.g. "Jan–Mar 2026" (auto-detected if empty)
    """
    filename = file.filename or "trades.csv"
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext not in ("xlsx", "xls", "xlsm", "csv"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{ext}'. Please upload a CSV or Excel file.",
        )

    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {e}")

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10 MB.")

    try:
        fn = partial(
            run_trade_review,
            file_bytes=file_bytes,
            filename=filename,
            trader_name=trader_name,
            review_period=review_period,
        )
        result = await _run_in_thread(fn)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
