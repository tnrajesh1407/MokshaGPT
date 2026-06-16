"""

ReAct Research Agent for MokshaGPT

--------------------------------------------------------------------------------

Plain-Python ReAct loop -- no LangGraph dependency.

Langfuse tracing is preserved via the @observe decorator on run_research_agent.



Loop structure:

  while step_count < MAX_STEPS:

      reason  -> if final_answer: break

      execute_tool

  if not final_answer: synthesize from observations

"""



from __future__ import annotations



import json

import re

from concurrent.futures import ThreadPoolExecutor, as_completed



import time



import numpy as np

import pandas as pd

import yfinance as yf

from langfuse import observe as traceable



from llm_factory import generate_response, PROMPTS, format_prompt

from backtester import run_strategy_backtest

from screener import run_stock_screener

from asset_detector import detect_assets, get_primary_asset_type, AssetType

from forex_data import analyze_forex_pair

from options_data import get_options_chain

from futures_data import analyze_contango_backwardation



# -- Traced data-source helpers ------------------------------------------------

# These thin wrappers give Langfuse a named span for each external call so

# latency for yfinance, Supabase, etc. is visible in the trace waterfall.



@traceable(name="supabase:load_technicals", as_type="tool")

def _traced_load_technicals(tickers: list) -> dict:

    from supabase_cache import load_technicals_from_supabase

    t0 = time.time()

    result = load_technicals_from_supabase(tickers)

    print(f"[supabase] load_technicals({tickers}): {len(result)} rows in {time.time()-t0:.3f}s")

    return result





@traceable(name="yfinance:fast_info", as_type="tool")

def _traced_fast_info(ticker: str):

    """Traced wrapper around _safe_fast_info for price lookups."""

    t0 = time.time()

    result = _safe_fast_info(ticker)

    print(f"[yfinance] fast_info({ticker}): price={result[2]} in {time.time()-t0:.3f}s")

    return result





@traceable(name="yfinance:history", as_type="tool")

def _traced_history(t_obj, period: str, ticker: str = ""):

    """Traced wrapper around yfinance Ticker.history()."""

    t0 = time.time()

    hist = t_obj.history(period=period)

    rows = len(hist) if hist is not None else 0

    print(f"[yfinance] history({ticker}, period={period}): {rows} rows in {time.time()-t0:.3f}s")

    return hist





# -- Constants -----------------------------------------------------------------



MAX_STEPS = 10

TOOL_RESULT_TRUNCATE = 1800       # chars kept per observation (short tools)

TOOL_RESULT_TRUNCATE_ANALYZE = 3200  # larger budget for single-ticker analyze

TOOL_RESULT_TRUNCATE_ANALYZE_BATCH = 6000  # larger budget for multi-ticker batch



_SYNTHESIS_FORMAT_RULES = (

    "\n\nIMPORTANT FORMATTING RULES:\n"

    "- Use proper markdown tables with each row on its own line\n"

    "- NEVER use | (pipe) characters inside table cell values -- use words like 'Bullish', 'Bearish', 'Above', 'Below' instead\n"

    "- Ensure every ticker requested has a complete data row -- do not write 'No Data' if the research data above contains values for that ticker\n"

    "- Provide a complete, well-structured markdown answer with a clear recommendation."

)



# Module-level cache for structured backtest/screen results so run_research_agent

# can retrieve the full object after the loop finishes.

_backtest_full_result_cache: dict = {}

_screen_full_result_cache: dict = {}



# -- Tool Registry -------------------------------------------------------------



TOOLS_SCHEMA = {

    "price": {

        "description": "Get the latest real-time price for any stock, forex pair, crypto, or index.",

        "parameters": {"ticker": "Ticker symbol e.g. 'AAPL', 'RELIANCE.NS', 'BTC-USD', 'EURUSD=X'"},

    },

    "indicators": {

        "description": (

            "Fetch specific technical indicators for a stock. Use this BEFORE 'analyze' to choose "

            "the right indicators for the asset's market regime. "

            "Available indicators: rsi, macd, macd_signal, macd_hist, "

            "sma9, sma20, sma21, sma50, sma200, ema9, ema20, ema21, ema50, "

            "bb_upper, bb_lower, bb_mid, stoch_k, stoch_d, "

            "vol_ratio, avg_vol20, high52, low52, pct_from_52w_high, pct_from_52w_low, "

            "std_pp, std_r1, std_r2, std_s1, std_s2, "

            "cpr_pp, cpr_tc, cpr_bc, atr14. "

            "Pass 'all' to get every available indicator."

        ),

        "parameters": {

            "ticker": "Ticker symbol e.g. 'RELIANCE.NS', 'AAPL', 'BTC-USD'",

            "indicators": "Comma-separated list e.g. 'rsi,macd,bb_upper,bb_lower' or 'all'",

        },

    },

    "analyze": {

        "description": (

            "Generate a full technical + fundamental analysis narrative for a stock. "

            "For best results, call 'indicators' first to fetch the right data, "

            "then pass those values in the query so the analysis is grounded in real numbers."

        ),

        "parameters": {"query": "Natural language query e.g. 'Analyze RELIANCE.NS' or 'How is AAPL looking?'"},

    },

    "forex": {

        "description": "Analyze a forex currency pair with technical indicators and trading signals.",

        "parameters": {"pair": "Currency pair e.g. 'EUR/USD', 'GBP/JPY', 'USD/INR'"},

    },

    "options": {

        "description": "Analyze an options chain or specific option contract. Returns Greeks, IV, near-the-money strikes.",

        "parameters": {"symbol": "Underlying ticker e.g. 'AAPL', or option symbol e.g. 'AAPL240315C150'"},

    },

    "futures": {

        "description": "Analyze futures contracts, contango/backwardation, commodity spot prices.",

        "parameters": {"query": "Natural language e.g. '/ES futures', 'gold spot price', 'crude oil contango'"},

    },

    "backtest": {

        "description": "Backtest a trading strategy. Returns win rate, total return, max drawdown, Sharpe ratio.",

        "parameters": {"strategy": "Natural language strategy e.g. 'SMA 10/50 crossover on TCS.NS for 2 years'"},

    },

    "screen": {

        "description": "Screen/filter assets by criteria. Returns matching stocks with key metrics.",

        "parameters": {"query": "Natural language criteria e.g. 'Nifty 50 stocks above 200 SMA with RSI below 40'"},

    },

    "general": {

        "description": (

            "Answer general finance/trading questions from knowledge -- concepts, definitions, "

            "educational explanations, market commentary. Use when no live data is needed."

        ),

        "parameters": {"question": "The question to answer"},

    },

    "final_answer": {

        "description": "Return the final synthesized answer. Call this when you have enough information.",

        "parameters": {"answer": "Complete, well-structured markdown answer"},

    },

}





def _tool_schema_text() -> str:

    lines = []

    for name, spec in TOOLS_SCHEMA.items():

        params = ", ".join(f'"{k}": "<{v}>"' for k, v in spec["parameters"].items())

        lines.append(f'- **{name}**: {spec["description"]}\n  Input: {{{params}}}')

    return "\n".join(lines)





# -- Tool Executors ------------------------------------------------------------



def _truncate(text: str) -> str:

    return text[:TOOL_RESULT_TRUNCATE] if len(text) > TOOL_RESULT_TRUNCATE else text





def _truncate_analyze(text: str, limit: int = TOOL_RESULT_TRUNCATE_ANALYZE) -> str:

    """Larger truncation budget for analyze results + clear completion marker."""

    if len(text) <= limit:

        return text + "\n\n[Analysis complete]"

    # Truncate at a sentence boundary where possible

    truncated = text[:limit]

    last_period = truncated.rfind(". ")

    if last_period > limit - 300:

        truncated = truncated[:last_period + 1]

    return truncated + "\n\n[Analysis complete -- use final_answer now]"





@traceable(name="tool:price", as_type="tool")

def _execute_price(ticker: str) -> str:

    try:

        ticker = ticker.strip()

        # Normalize forex: EURUSD -> EURUSD=X

        if re.match(r'^[A-Z]{6}$', ticker.upper()):

            ticker = ticker.upper() + "=X"

        # Use _safe_fast_info: handles KeyError + .NS fallback for Indian stocks

        ticker, _, price, prev_close, currency = _safe_fast_info(ticker)

        if price is None:

            return f"Could not fetch price for {ticker}. Check the ticker symbol."

        change = price - prev_close if prev_close else 0

        change_pct = (change / prev_close * 100) if prev_close else 0

        direction = "^" if change >= 0 else "v"

        return (

            f"{ticker}: {currency} {price:,.2f} "

            f"({direction} {abs(change_pct):.2f}% from prev close {currency} {prev_close:,.2f})"

        )

    except Exception as e:

        return f"Error fetching price for {ticker}: {e}"





def _safe_fast_info(ticker: str):
    """
    Safely fetch yfinance fast_info for a ticker.
    Returns (info, price, prev_close, currency) or (None, None, None, 'USD') on failure.

    Handles KeyError: 'currentTradingPeriod' which yfinance raises internally
    when the ticker is invalid or Yahoo returns unexpected JSON.
    Also tries appending .NS as a fallback for Indian stocks.
    """
    ticker = ticker.strip()
    ticker_upper = ticker.upper()
    if ticker_upper in ("NIFTY", "NIFTY50", "NIFTY 50", "NSEI", "^NSEI"):
        ticker = "^NSEI"
    elif ticker_upper in ("BANKNIFTY", "BANK NIFTY", "NSEBANK", "^NSEBANK"):
        ticker = "^NSEBANK"
    elif ticker_upper in ("SENSEX", "BSESN", "^BSESN"):
        ticker = "^BSESN"

    candidates = [ticker]
    # If ticker looks like a bare Indian stock (no dot suffix, all caps, 2-10 chars),
    # try the .NS suffix automatically before giving up.
    if re.match(r'^[A-Z]{2,10}$', ticker.upper()) and not ticker.endswith('=X') and not ticker.startswith('^'):
        candidates.append(ticker + ".NS")

    for sym in candidates:
        try:
            t = yf.Ticker(sym)
            info = t.fast_info
            # Accessing .last_price triggers the internal JSON parse -- wrap it
            price = info.last_price
            prev_close = info.previous_close
            currency = getattr(info, "currency", "USD") or "USD"
            if price is not None:
                print(f"[yf] resolved ticker: {sym} (price={price})")
                return sym, t, price, prev_close, currency
        except (KeyError, Exception) as e:
            # KeyError: 'currentTradingPeriod' is expected for invalid tickers
            if isinstance(e, KeyError) and 'currentTradingPeriod' in str(e):
                print(f"[yf] {sym}: ticker not found, trying next candidate")
            else:
                print(f"[yf] fast_info failed for {sym}: {type(e).__name__}: {e}")
            continue

    return ticker, yf.Ticker(ticker), None, None, "USD"









# -- Indicator catalogue -------------------------------------------------------

# Maps indicator name -> (label, format_fn)

# format_fn receives (value, currency, current_price) and returns a display string.



def _fmt_price(v, currency, _):    return f"{currency} {v:,.2f}"

def _fmt_plain(v, *_):             return f"{v:.4f}"

def _fmt_pct(v, *_):               return f"{v:.2f}%"

def _fmt_ratio(v, *_):             return f"{v:.2f}x"

def _fmt_rsi(v, *_):

    status = "overbought" if v > 70 else "oversold" if v < 30 else "neutral"

    return f"{v:.1f} ({status})"

def _fmt_stoch(v, *_):

    status = "overbought" if v > 0.8 else "oversold" if v < 0.2 else "neutral"

    return f"{v:.3f} ({status})"

def _fmt_macd(v, currency, _):     return f"{currency} {v:,.4f}"

def _fmt_bb(v, currency, price):

    relation = "above" if price > v else "below"

    return f"{currency} {v:,.2f} (price {relation})"

def _fmt_sma(v, currency, price):

    relation = "above" if price > v else "below"

    return f"{currency} {v:,.2f} (price {relation})"



_INDICATOR_CATALOGUE = {

    # Momentum

    "rsi":              ("RSI (14)",                    _fmt_rsi),

    "stoch_k":          ("Stochastic %K",               _fmt_stoch),

    "stoch_d":          ("Stochastic %D",               _fmt_stoch),

    # Trend -- SMAs

    "sma9":             ("SMA 9",                       _fmt_sma),

    "sma20":            ("SMA 20",                      _fmt_sma),

    "sma21":            ("SMA 21",                      _fmt_sma),

    "sma50":            ("SMA 50",                      _fmt_sma),

    "sma200":           ("SMA 200",                     _fmt_sma),

    # Trend -- EMAs

    "ema9":             ("EMA 9",                       _fmt_sma),

    "ema20":            ("EMA 20",                      _fmt_sma),

    "ema21":            ("EMA 21",                      _fmt_sma),

    "ema50":            ("EMA 50",                      _fmt_sma),

    # MACD

    "macd":             ("MACD Line",                   _fmt_macd),

    "macd_signal":      ("MACD Signal",                 _fmt_macd),

    "macd_hist":        ("MACD Histogram",              _fmt_macd),

    # Bollinger Bands

    "bb_upper":         ("BB Upper (20,2sigma)",            _fmt_bb),

    "bb_mid":           ("BB Mid (SMA20)",              _fmt_bb),

    "bb_lower":         ("BB Lower (20,2sigma)",            _fmt_bb),

    # Volume

    "vol_ratio":        ("Volume Ratio (vs 20d avg)",   _fmt_ratio),

    "avg_vol20":        ("Avg Volume (20d)",             lambda v,*_: f"{v:,.0f}"),

    # 52-week range

    "high52":           ("52-Week High",                _fmt_price),

    "low52":            ("52-Week Low",                 _fmt_price),

    "pct_from_52w_high":("% from 52W High",             _fmt_pct),

    "pct_from_52w_low": ("% from 52W Low",              _fmt_pct),

    # ATR (computed on demand -- not in screener dict)

    "atr14":            ("ATR (14)",                    _fmt_price),

    # Standard Pivots

    "std_pp":           ("Pivot Point",                 _fmt_price),

    "std_r1":           ("Resistance 1",                _fmt_price),

    "std_r2":           ("Resistance 2",                _fmt_price),

    "std_s1":           ("Support 1",                   _fmt_price),

    "std_s2":           ("Support 2",                   _fmt_price),

    # CPR

    "cpr_pp":           ("CPR Pivot",                   _fmt_price),

    "cpr_tc":           ("CPR Top Central",             _fmt_price),

    "cpr_bc":           ("CPR Bottom Central",          _fmt_price),

}



_ALL_INDICATOR_KEYS = set(_INDICATOR_CATALOGUE.keys())





@traceable(name="tool:indicators", as_type="tool")

def _execute_indicators(ticker: str, indicators: str) -> str:

    """

    Fetch specific technical indicators for one or more tickers.

    Supports comma-separated tickers for batch comparison (fetched in parallel).

    The LLM decides which indicators to request based on the asset and query context.

    """

    try:

        requested = (

            _ALL_INDICATOR_KEYS

            if indicators.strip().lower() == "all"

            else {i.strip().lower() for i in indicators.split(",") if i.strip()}

        )

        unknown = requested - _ALL_INDICATOR_KEYS

        if unknown:

            print(f"[indicators] Unknown indicators requested: {unknown} -- ignoring")

        requested = requested & _ALL_INDICATOR_KEYS



        # Support comma-separated tickers for batch comparison

        tickers = [t.strip() for t in ticker.split(",") if t.strip()]

        if len(tickers) > 1:

            print(f"[indicators] Batch mode: fetching indicators for {tickers}")

            results = []

            with ThreadPoolExecutor(max_workers=min(len(tickers), 8)) as executor:

                futures = {

                    executor.submit(_fetch_indicators_for_ticker, t, requested): t

                    for t in tickers

                }

                for future in as_completed(futures):

                    results.append(future.result())

            combined = "\n\n---\n\n".join(results)

            # Use a larger truncation limit for batch results -- 4 tickers A-- ~500 chars each

            limit = max(TOOL_RESULT_TRUNCATE_ANALYZE_BATCH, len(tickers) * 1200)

            return combined if len(combined) <= limit else combined[:limit]



        # Single ticker

        return _truncate(_fetch_indicators_for_ticker(tickers[0], requested))



    except Exception as e:

        return f"Error fetching indicators for {ticker}: {e}"





@traceable(name="yfinance:fetch_indicators", as_type="tool")

def _fetch_indicators_for_ticker(ticker: str, requested: set) -> str:

    """

    Compute and format indicators for a single ticker.

    Resolution order:

      1. Supabase precomputed cache  -- fastest, no Yahoo Finance call needed

      2. yfinance history fetch      -- fallback for cache misses or ATR14

    """

    try:

        ticker = ticker.strip()



        # -- Layer 1: live price (always needed, fast_info is lightweight) --------

        ticker, t_obj, price, prev_close, currency = _safe_fast_info(ticker)

        if price is None:

            return f"Could not fetch data for {ticker}. Check the ticker symbol."



        change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0



        # -- Layer 2: Supabase precomputed technicals ------------------------------

        supabase_result = _traced_load_technicals([ticker])

        tech = supabase_result.get(ticker)

        hist = None  # only fetched if needed



        if tech:

            print(f"[indicators] {ticker}: loaded from Supabase cache")

            # Check if any requested indicators are None in the cache -- if so,

            # fall back to yfinance to fill the gaps (stale/incomplete cache rows).

            # ATR14 is always computed from history, skip it here.

            non_atr_requested = requested - {"atr14"}

            missing_in_cache = {k for k in non_atr_requested if tech.get(k) is None}

            if missing_in_cache:

                print(f"[indicators] {ticker}: cache missing {missing_in_cache} -- fetching from Yahoo Finance to fill gaps")

                from screener import _compute_technicals_from_hist

                hist = t_obj.history(period="2y")

                if hist.empty:

                    hist = t_obj.history(period="1y")

                if not hist.empty:

                    live_tech = _compute_technicals_from_hist(hist)

                    if live_tech:

                        # Patch only the missing keys -- keep cached values for the rest

                        for k in missing_in_cache:

                            if live_tech.get(k) is not None:

                                tech[k] = live_tech[k]

                        print(f"[indicators] {ticker}: patched {[k for k in missing_in_cache if tech.get(k) is not None]} from yfinance")

        else:

            # -- Layer 3: yfinance history fallback --------------------------------

            print(f"[indicators] {ticker}: Supabase miss -- fetching from Yahoo Finance")

            from screener import _compute_technicals_from_hist

            hist = t_obj.history(period="2y")

            if hist.empty:

                hist = t_obj.history(period="1y")

            if hist.empty:

                hist = t_obj.history(period="6mo")

            if hist.empty:

                return f"{ticker}: Could not fetch price history."

            tech = _compute_technicals_from_hist(hist)

            if not tech:

                return f"{ticker}: Could not compute indicators."



        # -- ATR(14): not stored in Supabase -- compute from history if requested --

        atr14_val = None

        if "atr14" in requested:

            try:

                if hist is None:

                    hist = t_obj.history(period="2y")

                if not hist.empty:

                    high_low = hist["High"] - hist["Low"]

                    high_pc  = (hist["High"] - hist["Close"].shift(1)).abs()

                    low_pc   = (hist["Low"]  - hist["Close"].shift(1)).abs()

                    tr       = pd.concat([high_low, high_pc, low_pc], axis=1).max(axis=1)

                    atr14_val = float(tr.rolling(14).mean().iloc[-1])

            except Exception:

                pass



        print(f"[indicators] {ticker}: computing {len(requested)} indicators")



        lines = [

            f"## {ticker} -- Technical Indicators",

            f"**Current Price:** {currency} {price:,.2f} ({change_pct:+.2f}% today)",

            "",

        ]



        categories = [

            ("Momentum",        ["rsi", "stoch_k", "stoch_d"]),

            ("MACD",            ["macd", "macd_signal", "macd_hist"]),

            ("Moving Averages", ["sma9", "sma20", "sma21", "sma50", "sma200",

                                 "ema9", "ema20", "ema21", "ema50"]),

            ("Bollinger Bands", ["bb_upper", "bb_mid", "bb_lower"]),

            ("Volatility",      ["atr14", "vol_ratio", "avg_vol20"]),

            ("52-Week Range",   ["high52", "low52", "pct_from_52w_high", "pct_from_52w_low"]),

            ("Pivot Points",    ["std_pp", "std_r1", "std_r2", "std_s1", "std_s2",

                                 "cpr_pp", "cpr_tc", "cpr_bc"]),

        ]



        for cat_name, keys in categories:

            cat_lines = []

            for key in keys:

                if key not in requested:

                    continue

                val = atr14_val if key == "atr14" else tech.get(key)

                if val is None:

                    continue

                label, fmt_fn = _INDICATOR_CATALOGUE[key]

                try:

                    cat_lines.append(f"- **{label}:** {fmt_fn(val, currency, price)}")

                except Exception:

                    cat_lines.append(f"- **{label}:** {val}")

            if cat_lines:

                lines.append(f"### {cat_name}")

                lines.extend(cat_lines)

                lines.append("")



        # Market regime hint

        regime_hints = []

        rsi_val    = tech.get("rsi")

        macd_val   = tech.get("macd")

        macd_sig   = tech.get("macd_signal")

        sma50_val  = tech.get("sma50")

        sma200_val = tech.get("sma200")

        bb_u       = tech.get("bb_upper")

        bb_l       = tech.get("bb_lower")



        if rsi_val and sma50_val and sma200_val:

            if price > sma50_val and price > sma200_val and rsi_val < 70:

                regime_hints.append("Trending upward (price above SMA50 & SMA200, RSI not overbought)")

            elif price < sma50_val and price < sma200_val:

                regime_hints.append("Downtrend (price below SMA50 & SMA200)")

            elif bb_u and bb_l and (bb_u - bb_l) / price < 0.05:

                regime_hints.append("Low volatility / consolidation (tight Bollinger Bands)")

        if macd_val and macd_sig:

            if macd_val > macd_sig:

                regime_hints.append("MACD bullish crossover (momentum building)")

            else:

                regime_hints.append("MACD bearish (momentum fading)")



        if regime_hints:

            lines.append("### Market Regime")

            for h in regime_hints:

                lines.append(f"- {h}")



        print(f"[indicators] {ticker}: returned {len(requested)} indicators")

        return "\n".join(lines)



    except Exception as e:

        return f"Error fetching indicators for {ticker}: {e}"





@traceable(name="tool:analyze", as_type="tool")

def _execute_analyze(query: str) -> str:

    """

    Fetches live price + SMA20/50 + RSI + 52w range, injects into LLM prompt.

    Supports batch analysis: if query contains multiple comma-separated tickers,

    fetches data for all in parallel and returns combined analysis.

    """

    try:

        # Fast path: detect tickers directly from query without an LLM call.

        # Strategy: prefer explicit exchange-suffixed symbols (RELIANCE.NS, SHEL.L, BTC-USD)

        # over bare uppercase words, which are often indicator names injected by the LLM.

        direct_tickers = []



        # First pass: extract symbols with explicit exchange suffix -- these are unambiguous

        suffixed = re.findall(

            r'\b([A-Z][A-Z0-9&]{1,9}(?:\.[A-Z]{1,3}|-USD|-INR|-EUR|-GBP))\b', query

        )

        if suffixed:

            # Deduplicate while preserving order at detection time

            seen_s: set = set()

            direct_tickers = [t for t in suffixed if not (t in seen_s or seen_s.add(t))]

        else:

            # Second pass: bare uppercase words -- filter with stop-word list

            bare = re.findall(r'\b([A-Z]{2,10})\b', query)

            # Comprehensive stop list: indicator names + financial terms + common words

            _STOP_WORDS = {

                "RSI", "SMA", "EMA", "MACD", "ATR", "ADX", "OBV", "VWAP",

                "SMA9", "SMA20", "SMA21", "SMA50", "SMA200",

                "EMA9", "EMA20", "EMA21", "EMA50",

                "BB", "BBU", "BBL", "BBM", "STOCH", "CCI", "MFI", "ROC",

                "ATR14", "ATR7", "CPR", "PDH", "PDL", "PDC",

                "NSE", "BSE", "NYSE", "NASDAQ", "LSE", "XETRA", "TSE", "HKEX",

                "USD", "INR", "GBP", "EUR", "JPY", "AUD", "CAD", "CHF",

                "ETF", "IPO", "NFO", "FNO", "MCX",

                "LLM", "API", "AI", "ML", "DL", "NLP",

                "BUY", "SELL", "HOLD", "LONG", "SHORT",

                "HIGH", "LOW", "OPEN", "CLOSE", "VOLUME",

                "AND", "THE", "FOR", "WITH", "FROM", "INTO",

                # Extra words that appear in indicator output

                "ABOVE", "BELOW", "NEUTRAL", "BULLISH", "BEARISH",

                "CURRENT", "PRICE", "SIGNAL", "TREND", "BAND",

                "UPPER", "LOWER", "MID", "AVG", "VOL", "RATIO",

            }

            direct_tickers = [t for t in bare if t not in _STOP_WORDS]

        

        ticker = None

        if direct_tickers:

            ticker = ", ".join(direct_tickers)

            print(f"[analyze] Fast-path ticker detection: {ticker}")

        else:

            ticker_prompt = format_prompt(PROMPTS["price_extract_ticker_prompt"], message=query)

            raw = generate_response(ticker_prompt, use_search=False).strip()

            try:

                m = re.search(r'\{.*\}', raw, re.DOTALL)

                if m:

                    ticker = json.loads(m.group()).get("ticker", "").strip()

            except Exception:

                pass



        # Check if multiple tickers are provided (comma-separated)

        if ticker and "," in ticker:

            # Deduplicate while preserving order

            seen = set()

            tickers = []

            for t in ticker.split(","):

                t = t.strip()

                if t and t not in seen:

                    seen.add(t)

                    tickers.append(t)

            if len(tickers) > 1:

                print(f"[analyze] Batch mode: {len(tickers)} tickers -- using indicators data already in scratchpad")

                # For batch comparisons the ReAct loop already ran the 'indicators' tool

                # which fetched MACD, RSI, SMA, vol_ratio, BB, 52w range etc. for all tickers.

                # Re-fetching a subset here creates two conflicting datasets and confuses the

                # synthesis LLM. Instead, just signal that all data is ready in the scratchpad.

                msg = (

                    f"Indicator data for {', '.join(tickers)} has already been fetched by the "

                    f"indicators tool above. Use that data to compare and rank all tickers.\n\n"

                    f"[DATA READY -- synthesize comparison using indicators data above and call final_answer now]"

                )

                print(f"[analyze] Batch signalled -- deferring to indicators observation")

                return msg



        # Single ticker analysis (original logic)

        data_context = ""

        if ticker:

            try:

                ticker, t, price, prev_close, currency = _safe_fast_info(ticker)

                print(f"[yf] {ticker}: fast_info price={price}, prev_close={prev_close}")



                hist = t.history(period="3mo")

                if hist.empty:

                    print(f"[yf] {ticker}: 3mo history empty, retrying with 6mo")

                    hist = t.history(period="6mo")

                if hist.empty:

                    print(f"[yf] {ticker}: history still empty -- Yahoo Finance may be blocking cloud IP")



                if price and not hist.empty:

                    close = hist["Close"]

                    sma20 = close.rolling(20).mean().iloc[-1]

                    sma50 = close.rolling(50).mean().iloc[-1]

                    delta = close.diff()

                    gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()

                    loss = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()

                    rs = gain / loss.replace(0, np.nan)

                    rsi = float((100 - (100 / (1 + rs))).iloc[-1])

                    hist_1y = t.history(period="1y")

                    if hist_1y.empty:

                        hist_1y = hist

                    high_52w = float(hist_1y["High"].max()) if not hist_1y.empty else None

                    low_52w = float(hist_1y["Low"].min()) if not hist_1y.empty else None

                    change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0

                    # Format technical indicators with proper null handling

                    def format_sma(val, period, currency, price):

                        if val and not np.isnan(val):

                            relation = 'above' if price > val else 'below'

                            return f"- {period}-day SMA: {currency} {val:,.2f} ({relation} SMA)"

                        return f"- {period}-day SMA: Not available (insufficient data)"

                    

                    def format_rsi(val):

                        if val and not np.isnan(val):

                            status = 'overbought >70' if val > 70 else 'oversold <30' if val < 30 else 'neutral'

                            return f"- RSI (14): {val:.1f} ({status})"

                        return "- RSI (14): Not available (insufficient data)"

                    

                    def format_52w(val, label, currency):

                        if val and not np.isnan(val):

                            return f"- 52-week {label}: {currency} {val:,.2f}"

                        return f"- 52-week {label}: Not available"



                    data_context = (

                        f"\n\nLIVE MARKET DATA for {ticker}:\n"

                        f"- Current Price: {currency} {price:,.2f} ({change_pct:+.2f}% today)\n"

                        f"{format_sma(sma20, 20, currency, price)}\n"

                        f"{format_sma(sma50, 50, currency, price)}\n"

                        f"{format_rsi(rsi)}\n"

                        f"{format_52w(high_52w, 'High', currency)}\n"

                        f"{format_52w(low_52w, 'Low', currency)}\n"

                        f"Use this live data in your analysis.\n"

                    )

                    print(f"[yf] {ticker}: data_context built successfully")

                elif price and hist.empty:

                    change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0

                    data_context = (

                        f"\n\nLIVE MARKET DATA for {ticker} (partial -- historical data unavailable):\n"

                        f"- Current Price: {currency} {price:,.2f} ({change_pct:+.2f}% today)\n"

                        f"- Previous Close: {currency} {prev_close:,.2f}\n"

                        f"Note: SMA, RSI, and 52-week range could not be computed.\n"

                        f"Use this live price in your analysis and note the data limitation.\n"

                    )

                    print(f"[yf] {ticker}: partial data_context (price only, no history)")

            except Exception as data_err:

                print(f"[yf] {ticker}: live data fetch exception -- {type(data_err).__name__}: {data_err}")

                data_context = f"\n(Live data fetch failed for {ticker}: {data_err})\n"



        result = generate_response(query + data_context, use_search=False)

        return _truncate_analyze(result) + "\n\n[ANALYSIS COMPLETE -- call final_answer now]"

    except Exception as e:

        return f"Error running analysis: {e}"





@traceable(name="tool:forex", as_type="tool")

def _execute_forex(pair: str) -> str:

    try:

        result = analyze_forex_pair(pair.strip())

        if "error" in result:

            return f"Error analyzing {pair}: {result['error']}"

        current_rate = result.get("current_rate", {})

        technicals = result.get("technicals", {})

        trend = result.get("trend", "neutral")

        signals = result.get("signals", [])

        lines = [f"# {pair} Analysis"]

        rate_val = current_rate.get("last", "N/A")

        try:

            lines.append(f"**Current Rate:** {float(rate_val):.5f}")

        except (TypeError, ValueError):

            lines.append(f"**Current Rate:** {rate_val}")

        lines.append(f"**Change:** {current_rate.get('change_pct', 0):+.2f}%")

        lines.append(f"**Trend:** {trend.title()}")

        if technicals:

            lines.append(f"**RSI:** {technicals.get('rsi', 'N/A')}")

            lines.append(f"**SMA20:** {technicals.get('sma20', 'N/A')}")

            lines.append(f"**SMA50:** {technicals.get('sma50', 'N/A')}")

        if signals:

            lines.append("\n**Signals:**")

            for s in signals:

                lines.append(f"- {s.get('type','').upper()} ({s.get('indicator','')}): {s.get('message','')}")

        return _truncate("\n".join(lines))

    except Exception as e:

        return f"Error analyzing forex {pair}: {e}"





@traceable(name="tool:options", as_type="tool")

def _execute_options(symbol: str) -> str:

    try:

        symbol = symbol.strip()

        if len(symbol) > 10 and any(c in symbol for c in ["C", "P"]):

            from options_data import get_option_contract

            contract = get_option_contract(symbol)

            if not contract:

                return f"Could not find option contract: {symbol}"

            lines = [

                f"# {contract.symbol} Option",

                f"**Underlying:** {contract.underlying}  **Strike:** {contract.currency} {contract.strike}",

                f"**Expiry:** {contract.expiry.strftime('%Y-%m-%d')}  **Type:** {contract.option_type.title()}",

                f"**Last:** {contract.currency} {contract.last:.2f}  **Bid/Ask:** {contract.bid:.2f}/{contract.ask:.2f}",

                f"**IV:** {contract.implied_volatility:.1%}  **Days to Expiry:** {contract.days_to_expiry}",

                f"**Greeks:** Delta {contract.delta:.3f}  Gamma {contract.gamma:.3f}  Theta {contract.theta:.3f}  V {contract.vega:.3f}",

                f"**Volume:** {contract.volume:,}  **OI:** {contract.open_interest:,}",

            ]

            return "\n".join(lines)

        chain = get_options_chain(symbol)

        if not chain:

            return f"Could not fetch options chain for {symbol}"

        next_expiry = chain.expiry_dates[0]

        lines = [

            f"# {symbol} Options Chain",

            f"**Spot:** {chain.currency} {chain.spot_price:.2f}  **IV Rank:** {chain.iv_rank:.1f}%  **30d Avg IV:** {chain.iv_30d_avg:.1%}",

            f"**Expiries:** {', '.join(e.strftime('%Y-%m-%d') for e in chain.expiry_dates[:4])}",

            "\n**Near-the-Money Calls (next expiry):**",

        ]

        ntm_calls = sorted(

            [c for c in chain.calls if c.expiry == next_expiry],

            key=lambda x: abs(x.strike - chain.spot_price),

        )[:5]

        for c in ntm_calls:

            lines.append(

                f"  {chain.currency} {c.strike} Call: {c.last:.2f} "

                f"(IV {c.implied_volatility:.1%}, Delta {c.delta:.3f})"

            )

        if not ntm_calls:

            lines.append(f"  No call data available for {next_expiry.strftime('%Y-%m-%d')}")

        lines.append("\n**Near-the-Money Puts (next expiry):**")

        ntm_puts = sorted(

            [p for p in chain.puts if p.expiry == next_expiry],

            key=lambda x: abs(x.strike - chain.spot_price),

        )[:5]

        for p in ntm_puts:

            lines.append(

                f"  {chain.currency} {p.strike} Put: {p.last:.2f} "

                f"(IV {p.implied_volatility:.1%}, Delta {p.delta:.3f})"

            )

        if not ntm_puts:

            lines.append(f"  No put data available for {next_expiry.strftime('%Y-%m-%d')}")

        return _truncate("\n".join(lines))

    except Exception as e:

        return f"Error analyzing options for {symbol}: {e}"





@traceable(name="tool:futures", as_type="tool")

def _execute_futures(query: str) -> str:

    try:

        msg = query.lower()

        commodity_map = {

            "gold": "XAUUSD", "silver": "XAGUSD",

            "oil": "XTIUSD", "crude": "XTIUSD",

            "natural gas": "XNGUSD", "copper": "XCOPUSD",

            "corn": "XCORNUSD", "wheat": "XWHEUSD", "coffee": "XCOFUSD",

        }

        for keyword, sym in commodity_map.items():

            if keyword in msg:

                try:

                    from futures_data import analyze_commodity_spot

                    spot = analyze_commodity_spot(sym)

                    if "error" not in spot:

                        technicals = spot.get("technicals", {})

                        lines = [

                            f"# {spot.get('name', sym)} Spot",

                            f"**Price:** ${spot.get('current_price', 0):.2f} {spot.get('unit', 'USD')}  "

                            f"**Change:** {spot.get('change_pct', 0):+.2f}%",

                        ]

                        if technicals:

                            lines.append(

                                f"**RSI:** {technicals.get('rsi', 'N/A'):.1f}  "

                                f"**SMA20:** ${technicals.get('sma20', 0):.2f}  "

                                f"**SMA50:** ${technicals.get('sma50', 0):.2f}"

                            )

                        insights = spot.get("market_insights", [])

                        if insights:

                            lines.append("\n**Insights:**")

                            lines.extend(f"- {i}" for i in insights)

                        return _truncate("\n".join(lines))

                except Exception:

                    pass

        futures_sym = None

        sym_match = re.search(r'(/[A-Z]{2,3}|[A-Z]{2,3}[FGHJKMNQUVXZ]\d{2})', query.upper())

        futures_sym = sym_match.group(1) if sym_match else "/ES"

        curve = analyze_contango_backwardation(futures_sym)

        if "error" in curve:

            return f"Error analyzing {futures_sym}: {curve['error']}"

        front = curve.get("front_month", {})

        back = curve.get("back_month", {})

        shape = curve.get("curve_shape", "unknown")

        lines = [

            f"# {futures_sym} Futures",

            f"**Front Month ({front.get('contract','N/A')}):** ${front.get('price',0):.2f}",

            f"**Back Month ({back.get('contract','N/A')}):** ${back.get('price',0):.2f}",

            f"**Curve Shape:** {shape.title()}  **Spread:** {curve.get('price_difference_pct',0):+.2f}%  **Roll Yield:** {curve.get('roll_yield_estimate',0):+.2f}%",

        ]

        if shape == "contango":

            lines.append("Contango: futures > spot -- storage costs or low near-term demand.")

        elif shape == "backwardation":

            lines.append("Backwardation: futures < spot -- immediate demand or supply squeeze.")

        return _truncate("\n".join(lines))

    except Exception as e:

        return f"Error analyzing futures '{query}': {e}"





@traceable(name="tool:backtest", as_type="tool")

def _execute_backtest(strategy: str) -> str:

    try:

        result = run_strategy_backtest(strategy)

        _backtest_full_result_cache["last"] = result

        if isinstance(result, dict):

            parts = []

            if "strategy_description" in result:

                parts.append(f"Strategy: {result['strategy_description']}")

            if "ticker" in result:

                parts.append(f"Ticker: {result['ticker']}")

            m = result.get("metrics", {})

            if m:

                parts.append(

                    f"Total Return: {m.get('total_return_pct','N/A')}%  "

                    f"Win Rate: {m.get('win_rate_pct', m.get('win_rate','N/A'))}%  "

                    f"Max Drawdown: {m.get('max_drawdown_pct','N/A')}%  "

                    f"Trades: {m.get('total_trades','N/A')}  "

                    f"Sharpe: {m.get('sharpe_ratio','N/A')}"

                )

            if result.get("error"):

                parts.append(f"Error: {result['error']}")

            return _truncate("\n".join(parts)) if parts else _truncate(str(result))

        return _truncate(str(result))

    except Exception as e:

        return f"Error running backtest: {e}"





@traceable(name="tool:screen", as_type="tool")

def _execute_screen(query: str) -> str:

    try:

        result = run_stock_screener(query)

        _screen_full_result_cache["last"] = result

        if isinstance(result, dict):

            stocks = result.get("stocks", [])

            total = result.get("total_matches", 0)

            criteria = result.get("criteria", [])

            lines = [f"Found {total} stocks matching: {', '.join(criteria)}"]

            for s in stocks[:10]:

                pe = s.get("pe_ratio")

                pe_str = f" | P/E {pe:.1f}" if pe is not None and pe != -1 else ""

                lines.append(

                    f"  - {s.get('ticker','')} ({s.get('name','')}): "

                    f"{s.get('price','')} | RSI {s.get('rsi','N/A')} | "

                    f"Change {s.get('change_pct','N/A')}%{pe_str}"

                )

            return _truncate("\n".join(lines))

        return _truncate(str(result))

    except Exception as e:

        return f"Error running screener: {e}"





@traceable(name="tool:general", as_type="tool")

def _execute_general(question: str) -> str:

    try:

        result = generate_response(question, use_search=False)

        return _truncate(result)

    except Exception as e:

        return f"Error answering question: {e}"





def execute_tool(tool_name: str, tool_input: dict) -> str:

    """Dispatch to the right executor."""

    dispatch = {

        "price":      lambda: _execute_price(tool_input.get("ticker", "")),

        "indicators": lambda: _execute_indicators(

                          tool_input.get("ticker", ""),

                          tool_input.get("indicators", "all"),

                      ),

        "analyze":    lambda: _execute_analyze(tool_input.get("query", "")),

        "forex":      lambda: _execute_forex(tool_input.get("pair", "")),

        "options":    lambda: _execute_options(tool_input.get("symbol", "")),

        "futures":    lambda: _execute_futures(tool_input.get("query", "")),

        "backtest":   lambda: _execute_backtest(tool_input.get("strategy", "")),

        "screen":     lambda: _execute_screen(tool_input.get("query", "")),

        "general":    lambda: _execute_general(tool_input.get("question", "")),

    }

    fn = dispatch.get(tool_name)

    if fn:

        return fn()

    return f"Unknown tool: {tool_name}"





# -- Prompt Builder ------------------------------------------------------------



def _summarize_assistant_turn(content: str, max_chars: int = 200) -> str:

    """

    Compress a long assistant answer into a short context summary.

    Extracts the first meaningful sentence/line rather than truncating mid-word.

    This keeps multi-turn context useful without bloating the prompt.

    """

    if len(content) <= max_chars:

        return content

    # Try to find a natural break point (sentence end, newline, bullet)

    for sep in ["\n\n", "\n", ". ", "! ", "? "]:

        idx = content.find(sep, 80)  # at least 80 chars

        if 80 <= idx <= max_chars:

            return content[:idx + len(sep)].strip() + " [...]"

    return content[:max_chars].rsplit(" ", 1)[0] + " [...]"





def _build_react_prompt(

    user_message: str,

    conversation_history: list[dict],

    scratchpad: list[dict],

    step_count: int,

) -> str:

    history_text = "(no prior conversation)"

    if conversation_history:

        lines = []

        # Keep last 4 turns (2 exchanges) -- enough for reference resolution,

        # not so much that it bloats every ReAct step with stale context.

        for turn in conversation_history[-4:]:

            role = "User" if turn["role"] == "user" else "Assistant"

            content = turn["content"]

            if role == "Assistant":

                # Compress long answers to a short summary -- the LLM only needs

                # to know what was concluded, not the full formatted report.

                content = _summarize_assistant_turn(content, max_chars=200)

            else:

                # User messages are usually short; cap at 300 chars

                content = content[:300]

            lines.append(f"{role}: {content}")

        history_text = "\n".join(lines)



    scratchpad_text = ""

    for step in scratchpad:

        scratchpad_text += f"\nThought: {step['thought']}"

        if step.get("tool"):

            scratchpad_text += f"\nAction: {step['tool']}"

            scratchpad_text += f"\nAction Input: {json.dumps(step['tool_input'])}"

            scratchpad_text += f"\nObservation: {step['observation']}"



    detected = detect_assets(user_message)

    primary = get_primary_asset_type(user_message)

    asset_hint = f"Detected asset type: {primary.value}"

    if detected:

        asset_hint += f" | Symbols: {', '.join(a.symbol for a in detected[:3])}"



    return format_prompt(

        PROMPTS.get("react_agent_prompt", ""),

        tools=_tool_schema_text(),

        conversation_history=history_text,

        scratchpad=scratchpad_text or "(no steps taken yet)",

        user_message=user_message,

        step_count=str(step_count),

        max_steps=str(MAX_STEPS),

        asset_hint=asset_hint,

    )





# -- Response Parser -----------------------------------------------------------



def _sanitize_final_answer(text: str) -> str:

    """

    Guard against the LLM accidentally putting its ReAct JSON reasoning blob

    into the answer field. If the text looks like a raw tool-call JSON

    (has "action", "tool", "tool_input" keys), extract just the thought or

    trigger a re-synthesis signal by returning empty string.

    """

    stripped = text.strip()

    # Detect if the answer IS a raw ReAct JSON object

    if stripped.startswith("{"):

        try:

            obj = json.loads(stripped)

            # It's a tool-call blob, not a real answer

            if "action" in obj and "tool" in obj and obj.get("action") != "final_answer":

                print("[ReAct] WARNING: final_answer contained a tool-call JSON blob -- discarding")

                return ""

            # It's a final_answer blob -- extract the nested answer

            if obj.get("action") == "final_answer" or obj.get("tool") == "final_answer":

                nested = obj.get("tool_input", {}).get("answer", "")

                if nested:

                    return nested

        except (json.JSONDecodeError, TypeError):

            pass

    return text





def _parse_react_response(raw: str) -> dict:

    cleaned = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()



    # -- Attempt 1: strict JSON parse ------------------------------------------

    m = re.search(r'\{.*\}', cleaned, re.DOTALL)

    if m:

        try:

            parsed = json.loads(m.group())

            action = parsed.get("action", "")

            tool = parsed.get("tool", "")

            if not action and tool == "final_answer":

                action = "final_answer"

            elif not action and tool in TOOLS_SCHEMA:

                action = "tool_call"

            return {

                "thought": parsed.get("thought", ""),

                "action": action,

                "tool": tool,

                "tool_input": parsed.get("tool_input", {}),

            }

        except json.JSONDecodeError:

            pass



    # -- Attempt 2: fix common LLM JSON escaping mistakes then retry -----------

    # LLMs often forget to escape newlines inside the "answer" string value.

    # Strategy: find the "answer" key, extract everything between its opening

    # quote and the closing `"}}` or `"}\n}`, then re-escape it properly.

    if m:

        blob = m.group()

        # Find the answer value start

        ans_key_pos = blob.find('"answer"')

        if ans_key_pos != -1:

            # Find the colon + opening quote after "answer"

            colon_pos = blob.find(':', ans_key_pos)

            if colon_pos != -1:

                # Skip whitespace and find the opening quote

                val_start = colon_pos + 1

                while val_start < len(blob) and blob[val_start] in ' \t\r\n':

                    val_start += 1

                if val_start < len(blob) and blob[val_start] == '"':

                    val_start += 1  # skip opening quote

                    # Find the closing: last `"` before `}}` at end of blob

                    # Walk backwards from end to find `}}` then the `"` before it

                    end_pos = len(blob) - 1

                    while end_pos > val_start and blob[end_pos] in ' \t\r\n}':

                        end_pos -= 1

                    # end_pos should now point at the closing `"` of the answer value

                    if blob[end_pos] == '"':

                        raw_answer = blob[val_start:end_pos]

                        # Unescape JSON sequences

                        answer_text = (

                            raw_answer

                            .replace("\\n", "\n")

                            .replace("\\t", "\t")

                            .replace('\\"', '"')

                            .replace("\\\\", "\\")

                        )

                        # Extract thought if present

                        thought_m = re.search(r'"thought"\s*:\s*"(.*?)"(?=\s*,\s*"action")', blob, re.DOTALL)

                        thought = ""

                        if thought_m:

                            thought = thought_m.group(1).replace("\\n", "\n").replace('\\"', '"')

                        return {

                            "thought": thought,

                            "action": "final_answer",

                            "tool": "final_answer",

                            "tool_input": {"answer": answer_text},

                        }



    # -- Attempt 3: detect action/tool from regex, extract tool_input ----------

    action_match = re.search(r'"action"\s*:\s*"([^"]+)"', cleaned)

    tool_match   = re.search(r'"tool"\s*:\s*"([^"]+)"', cleaned)

    action_val   = action_match.group(1) if action_match else ""

    tool_val     = tool_match.group(1)   if tool_match   else ""



    if action_val and action_val != "final_answer" and tool_val in TOOLS_SCHEMA:

        # It's a tool call with malformed JSON -- try to extract tool_input

        ti_match = re.search(r'"tool_input"\s*:\s*(\{[^{}]*\})', cleaned, re.DOTALL)

        tool_input = {}

        if ti_match:

            try:

                tool_input = json.loads(ti_match.group(1))

            except json.JSONDecodeError:

                pass

        thought_match = re.search(r'"thought"\s*:\s*"(.*?)"(?=\s*,\s*"action")', cleaned, re.DOTALL)

        thought = thought_match.group(1).replace("\\n", "\n") if thought_match else ""

        return {

            "thought": thought,

            "action": "tool_call",

            "tool": tool_val,

            "tool_input": tool_input,

        }



    # -- Fallback: treat whole response as final answer ------------------------

    return {

        "thought": "Could not parse structured response.",

        "action": "final_answer",

        "tool": "final_answer",

        "tool_input": {"answer": _sanitize_final_answer(raw.strip())},

    }





def _fix_table_formatting(text: str) -> str:

    """

    Fix common table formatting issues where table rows get concatenated.

    Conservative approach -- only fix clear concatenation artifacts.

    """

    # Fix concatenated rows: "| content || content |" -> split at ||

    text = text.replace('||', '|\n|')



    # Fix "| |" (row boundary with space) -> newline

    text = text.replace('| |', '|\n|')



    # Fix text running directly into a table (colon immediately before pipe)

    text = text.replace(':| ', ':\n\n| ')



    return text





def _unescape_answer(text: str) -> str:

    """Convert JSON-escaped sequences in the answer string to real characters."""

    unescaped = (

        text

        .replace("\\n", "\n")

        .replace("\\t", "\t")

        .replace('\\"', '"')

        .replace("\\\\", "\\")

    )

    # Apply table formatting fix

    return _fix_table_formatting(unescaped)







@traceable(name="run-research-agent", as_type="chain")

def run_research_agent(

    user_message: str,

    conversation_history: list[dict] | None = None,

    session_id: str | None = None,

    user_id: str | None = None,

) -> dict:

    """

    Run the ReAct research agent.



    Args:

        user_message:          The user's current question.

        conversation_history:  Prior turns [{"role": "user"|"assistant", "content": str}].

        session_id:            Optional session ID for Langfuse session grouping.

        user_id:               Optional user identifier for Langfuse trace tagging.



    Returns:

        {

            "type":       str,        # dominant tool used (for frontend intent badge)

            "answer":     str,        # final synthesized answer (markdown)

            "steps":      list[dict], # reasoning trace

            "step_count": int,

        }

    """

    # Attach session/user context so all child spans in this trace are

    # tagged and filterable in Langfuse under the same session.

    if session_id or user_id:

        from langfuse import get_client

        get_client().update_current_trace(

            session_id=session_id or None,

            user_id=user_id or None,

        )



    history = conversation_history or []

    scratchpad: list[dict] = []

    step_count = 0

    final_answer = ""

    error = ""



    # -- ReAct loop ------------------------------------------------------------

    while step_count < MAX_STEPS:

        print(f"[ReAct] reason -> step {step_count + 1}/{MAX_STEPS}")



        prompt = _build_react_prompt(user_message, history, scratchpad, step_count)

        try:

            raw = generate_response(prompt, use_search=False)

            parsed = _parse_react_response(raw)

            print(f"[ReAct] thought: {parsed['thought'][:100]}...")

            print(f"[ReAct] action={parsed['action']}  tool={parsed.get('tool','-')}")

        except Exception as e:

            print(f"[ReAct] reason ERROR: {e}")

            observations = [s["observation"] for s in scratchpad if s.get("observation")]

            if observations:

                final_answer = (

                    "I encountered a connectivity issue while researching further, "

                    "but here's what I found so far:\n\n" + "\n\n".join(observations)

                )

            else:

                final_answer = (

                    f"I'm unable to complete this request right now due to a connectivity issue "

                    f"(`{type(e).__name__}: {e}`). "

                    f"Please check that the backend has internet access and try again."

                )

            break



        if parsed["action"] == "final_answer":

            raw_answer = parsed["tool_input"].get("answer", raw.strip())

            final_answer = _unescape_answer(_sanitize_final_answer(raw_answer))

            if not final_answer:

                print("[ReAct] final_answer was a reasoning blob, continuing loop for synthesis")

                step_count += 1

                continue

            break



        # Queue the tool call on the scratchpad

        scratchpad.append({

            "thought": parsed["thought"],

            "action": parsed["action"],

            "tool": parsed["tool"],

            "tool_input": parsed["tool_input"],

            "observation": "",

        })



        # Guard: skip exact duplicate tool calls -- LLM sometimes retries when

        # it sees a truncated observation and thinks the call failed.

        last = scratchpad[-1]

        prior_calls = [

            (s["tool"], json.dumps(s["tool_input"], sort_keys=True))

            for s in scratchpad[:-1]

            if s.get("observation")

        ]

        this_call = (last["tool"], json.dumps(last["tool_input"], sort_keys=True))

        if this_call in prior_calls:

            print(f"[ReAct] duplicate tool call detected ({last['tool']}) -- skipping, injecting prior result")

            # Find the prior observation and reuse it

            for s in scratchpad[:-1]:

                if s["tool"] == last["tool"] and json.dumps(s["tool_input"], sort_keys=True) == this_call[1]:

                    scratchpad[-1]["observation"] = s["observation"] + "\n[Note: result already fetched above -- use final_answer now]"

                    break

            step_count += 1

            continue



        # Execute the tool

        last = scratchpad[-1]

        print(f"[ReAct] execute_tool -> {last['tool']}({last['tool_input']})")

        observation = execute_tool(last["tool"], last["tool_input"])

        print(f"[ReAct] observation: {observation[:120]}...")

        scratchpad[-1]["observation"] = observation

        # Ensure analyze always carries the completion marker so _DONE_MARKERS fires.
        if last["tool"] == "analyze" and "[ANALYSIS COMPLETE" not in observation:
            observation = observation + "\n\n[ANALYSIS COMPLETE -- call final_answer now]"
            scratchpad[-1]["observation"] = observation

        step_count += 1



        # Hard guard: if the tool signals completion, force synthesis immediately

        # instead of letting the LLM decide whether to call more tools.

        _DONE_MARKERS = ("[ANALYSIS COMPLETE", "[DATA READY")

        if any(m in observation for m in _DONE_MARKERS):

            print(f"[ReAct] completion marker detected -- forcing final answer synthesis")

            observations = [s["observation"] for s in scratchpad if s.get("observation")]

            synthesis_prompt = (

                f"You are a financial research analyst. Based on the research data below, "

                f"answer the user's question with a clear, structured markdown recommendation.\n\n"

                f"User question: {user_message}\n\n"

                f"Research data:\n\n"

                + "\n\n---\n\n".join(observations)

                + "\n\nIMPORTANT FORMATTING RULES:\n"

                "- Use proper markdown tables with each row on its own line\n"

                "- NEVER use | (pipe) characters inside table cell values -- use words like 'and', 'vs', 'above/below' instead\n"

                "- For MACD: write 'Bullish' or 'Bearish' not 'Bullish Crossover | Signal'\n"

                "- Ensure every ticker has a complete row -- do not write 'No Data' if the research data above contains values for that ticker\n"

                "- Provide a complete, well-structured markdown answer with a clear recommendation."

            )

            try:

                final_answer = generate_response(synthesis_prompt, use_search=False)

                final_answer = _unescape_answer(_sanitize_final_answer(final_answer))

            except Exception as synth_err:

                print(f"[ReAct] forced synthesis failed: {synth_err}")

                final_answer = "Based on my research:\n\n" + "\n\n".join(observations)

            break



    # -- Max-steps fallback: synthesize via LLM --------------------------------

    if not final_answer:

        print("[ReAct] max steps reached, forcing final answer via LLM synthesis")

        observations = [s["observation"] for s in scratchpad if s.get("observation")]

        if observations:

            # Check if all observations are errors -- surface them directly

            error_obs = [o for o in observations if o.lower().startswith("error")]

            if error_obs and len(error_obs) == len(observations):

                final_answer = (

                    "I was unable to complete your request. Here's what happened:\n\n"

                    + "\n\n".join(f"- {o}" for o in error_obs)

                    + "\n\nPlease check the ticker symbol and try again. "

                    "For Indian stocks, use the format `TICKER.NS` (NSE) or `TICKER.BO` (BSE)."

                )

            else:

                synthesis_prompt = (

                    f"You are a financial research analyst. Based on the research data below, "

                    f"answer the user's question with a clear, structured recommendation.\n\n"

                    f"User question: {user_message}\n\n"

                    f"Research data gathered:\n\n"

                    + "\n\n---\n\n".join(observations)

                    + _SYNTHESIS_FORMAT_RULES

                )

                try:

                    final_answer = generate_response(synthesis_prompt, use_search=False)

                    if not final_answer or not final_answer.strip():

                        final_answer = "Based on my research:\n\n" + "\n\n".join(observations)

                except Exception as synth_err:

                    print(f"[ReAct] synthesis LLM call failed: {synth_err}")

                    final_answer = "Based on my research:\n\n" + "\n\n".join(observations)

        else:

            final_answer = "I was unable to gather enough data to answer your question. Please try again."



    # -- Build response --------------------------------------------------------

    if error:

        observations = [s["observation"] for s in scratchpad if s.get("observation")]

        if observations:

            answer = "I hit an error while researching further, but here's what I found:\n\n" + "\n\n".join(observations)

        else:

            answer = (

                f"I'm unable to complete this request due to a connectivity issue. "

                f"Please ensure the backend has internet access and try again.\n\n*Error: {error}*"

            )

        return {"type": "unknown", "content": answer, "answer": answer, "steps": [], "step_count": step_count}



    tools_used = [s["tool"] for s in scratchpad if s.get("tool")]

    type_map = {

        "analyze": "analysis", "price": "price", "backtest": "backtest",

        "screen": "screen", "forex": "forex", "options": "options",

        "futures": "futures", "general": "unknown",

    }



    # When screen is followed by analyze/general, the final_answer is the recommendation

    has_post_screen_analysis = "screen" in tools_used and any(

        t in tools_used for t in ("analyze", "forex", "options", "futures", "general")

    )

    if has_post_screen_analysis:

        dominant_type = "analysis"

    else:

        dominant_type = type_map.get(tools_used[0], "analysis") if tools_used else "analysis"



    # Return full structured backtest object so frontend charts render correctly

    if "backtest" in tools_used and "last" in _backtest_full_result_cache:

        full_bt = _backtest_full_result_cache.pop("last")

        _screen_full_result_cache.pop("last", None)

        bt_summary = ""

        try:

            ps = full_bt.get("parsed_strategy", {})

            m  = full_bt.get("metrics", {})

            bt_summary = (

                f"Backtest result for {ps.get('ticker','?')} using {ps.get('strategy_description','?')}: "

                f"Total return {m.get('total_return_pct','?')}%, "

                f"Buy & hold {m.get('buy_hold_return_pct','?')}%, "

                f"Win rate {m.get('win_rate_pct','?')}%, "

                f"Max drawdown {m.get('max_drawdown_pct','?')}%, "

                f"Sharpe {m.get('sharpe_ratio','?')}, "

                f"Total trades {m.get('total_trades','?')}."

            )

        except Exception:

            bt_summary = "Backtest completed (structured result)."

        return {"type": "backtest", "content": full_bt, "answer": bt_summary, "steps": [], "step_count": step_count}



    # Return full structured screener object only when screen was the sole tool used

    screen_only = "screen" in tools_used and not any(

        t in tools_used for t in ("analyze", "forex", "options", "futures", "general")

    )

    if screen_only and "last" in _screen_full_result_cache:

        full_sc = _screen_full_result_cache.pop("last")

        _backtest_full_result_cache.pop("last", None)

        if isinstance(full_sc, dict) and "criteria" in full_sc:

            sc_summary = ""

            try:

                criteria = ", ".join(full_sc.get("criteria", []))

                stocks   = full_sc.get("stocks", [])

                total    = full_sc.get("total_matches", len(stocks))

                top_lines = [

                    f"{s.get('ticker','?')} ({s.get('name','?')}): price {s.get('price','?')}, "

                    f"RSI {s.get('rsi','?')}, change {s.get('change_pct','?')}%"

                    for s in stocks[:10]

                ]

                sc_summary = f"Screener found {total} stocks matching: {criteria}.\n" + "\n".join(top_lines)

            except Exception:

                sc_summary = "Screener completed (structured result)."

            return {"type": "screen", "content": full_sc, "answer": sc_summary, "steps": [], "step_count": step_count}



    # Clear stale cache entries

    _backtest_full_result_cache.pop("last", None)

    _screen_full_result_cache.pop("last", None)



    steps = [

        {

            "thought": s.get("thought", ""),

            "tool": s.get("tool", ""),

            "tool_input": s.get("tool_input", {}),

            "observation": s.get("observation", ""),

        }

        for s in scratchpad

    ]



    # Safety: if dominant type is screen/backtest but no structured object, render as text

    if dominant_type in ("screen", "backtest"):

        dominant_type = "unknown"



    return {

        "type": dominant_type,

        "content": final_answer,

        "answer": final_answer,

        "steps": steps,

        "step_count": step_count,

    }





# -- Streaming variant ---------------------------------------------------------



_TOOL_LABELS = {

    "price":      "Fetching live price",

    "indicators": "Computing technical indicators",

    "analyze":    "Running stock analysis",

    "forex":      "Analyzing forex pair",

    "options":    "Analyzing options chain",

    "futures":    "Analyzing futures",

    "backtest":   "Running backtest",

    "screen":     "Screening stocks",

    "general":    "Answering from knowledge",

    "final_answer": "Composing final answer",

}





def run_research_agent_stream(
    user_message: str,
    conversation_history: list[dict] | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
):
    """
    Generator version of run_research_agent that yields SSE-formatted strings.

    Yields:
        SSE lines of the form:
          data: <json>\n\n

        Event shapes:
          {"event": "step",   "thought": str, "tool": str, "label": str, "step": int}
          {"event": "result", "type": str, "answer": str, "content": any,
                              "steps": list, "step_count": int}
          {"event": "error",  "message": str}
    """
    import queue
    import threading
    from contextvars import copy_context
    from langfuse import get_client as _lf_get_client

    # Generator functions cannot use @observe: the decorator wraps the generator
    # and the span context is not active inside the function body. Instead we
    # create the root span explicitly, tag user_id/session_id immediately, then
    # run the worker via copy_context().run() so it inherits the full contextvars
    # state (including the active OTel span) without any manual attach/detach.
    _lf = _lf_get_client()
    with _lf.start_as_current_span(
        name="run-research-agent-stream",
        input={"message": user_message, "history_turns": len(conversation_history or [])},
    ):
        if user_id or session_id:
            _lf.update_current_trace(
                user_id=user_id or None,
                session_id=session_id or None,
            )

        # Snapshot contextvars AFTER the span is open so the worker inherits it.
        _ctx_snapshot = copy_context()

        q: queue.Queue = queue.Queue()
        SENTINEL = object()

        def _emit(obj: dict):
            q.put(json.dumps(obj))

        def _worker_body():
            """ReAct loop -- runs inside copy_context() so OTel context is inherited."""
            print(f"[stream] worker started for: {user_message[:80]}")
            history = conversation_history or []
            scratchpad: list[dict] = []
            step_count = 0
            final_answer = ""

            try:
                while step_count < MAX_STEPS:
                    print(f"[stream] ReAct step {step_count + 1}/{MAX_STEPS}")
                    prompt = _build_react_prompt(user_message, history, scratchpad, step_count)
                    try:
                        raw = generate_response(prompt, use_search=False)
                        parsed = _parse_react_response(raw)
                        print(f"[stream] step {step_count+1} -> action={parsed['action']} tool={parsed.get('tool','-')}")
                    except Exception as e:
                        observations = [s["observation"] for s in scratchpad if s.get("observation")]
                        final_answer = (
                            "I encountered a connectivity issue while researching further, "
                            "but here's what I found so far:\n\n" + "\n\n".join(observations)
                            if observations
                            else f"Unable to complete request: `{type(e).__name__}: {e}`"
                        )
                        break

                    if parsed["action"] == "final_answer":
                        raw_answer = parsed["tool_input"].get("answer", raw.strip())
                        final_answer = _unescape_answer(_sanitize_final_answer(raw_answer))
                        if not final_answer:
                            step_count += 1
                            continue
                        break

                    # Emit step event for streaming UI
                    tool_name = parsed.get("tool", "")
                    _emit({
                        "event": "step",
                        "thought": parsed.get("thought", ""),
                        "tool": tool_name,
                        "label": _TOOL_LABELS.get(tool_name, "Thinking..."),
                        "step": step_count + 1,
                    })

                    scratchpad.append({
                        "thought": parsed["thought"],
                        "action": parsed["action"],
                        "tool": parsed["tool"],
                        "tool_input": parsed["tool_input"],
                        "observation": "",
                    })

                    # Guard: skip duplicate tool calls
                    last = scratchpad[-1]
                    prior_calls = [
                        (s["tool"], json.dumps(s["tool_input"], sort_keys=True))
                        for s in scratchpad[:-1]
                        if s.get("observation")
                    ]
                    this_call = (last["tool"], json.dumps(last["tool_input"], sort_keys=True))
                    if this_call in prior_calls:
                        print(f"[stream] duplicate tool call ({last['tool']}) -- skipping")
                        for s in scratchpad[:-1]:
                            if s["tool"] == last["tool"] and json.dumps(s["tool_input"], sort_keys=True) == this_call[1]:
                                scratchpad[-1]["observation"] = s["observation"] + "\n[Note: result already fetched above]"
                                break
                        step_count += 1
                        continue

                    # Execute tool
                    print(f"[stream] execute_tool -> {last['tool']}({last['tool_input']})")
                    observation = execute_tool(last["tool"], last["tool_input"])
                    print(f"[stream] observation[{last['tool']}]: {observation[:120]}...")
                    scratchpad[-1]["observation"] = observation

                    # Ensure analyze always carries the completion marker.
                    if last["tool"] == "analyze" and "[ANALYSIS COMPLETE" not in observation:
                        observation = observation + "\n\n[ANALYSIS COMPLETE -- call final_answer now]"
                        scratchpad[-1]["observation"] = observation

                    step_count += 1

                    # Completion marker: force synthesis
                    _DONE_MARKERS = ("[ANALYSIS COMPLETE", "[DATA READY")
                    if any(m in observation for m in _DONE_MARKERS):
                        observations = [s["observation"] for s in scratchpad if s.get("observation")]
                        synthesis_prompt = (
                            f"You are a financial research analyst. Based on the research data below, "
                            f"answer the user's question with a clear, structured markdown recommendation.\n\n"
                            f"User question: {user_message}\n\nResearch data:\n\n"
                            + "\n\n---\n\n".join(observations)
                            + "\n\nProvide a complete, well-structured markdown answer."
                        )
                        try:
                            final_answer = generate_response(synthesis_prompt, use_search=False)
                            final_answer = _unescape_answer(_sanitize_final_answer(final_answer))
                        except Exception as synth_err:
                            print(f"[stream] forced synthesis failed: {synth_err}")
                            final_answer = "Based on my research:\n\n" + "\n\n".join(observations)
                        break

                # Max-steps fallback
                if not final_answer:
                    observations = [s["observation"] for s in scratchpad if s.get("observation")]
                    if observations:
                        synthesis_prompt = (
                            f"You are a financial research analyst. Based on the research data below, "
                            f"answer the user's question with a clear, structured recommendation.\n\n"
                            f"User question: {user_message}\n\nResearch data:\n\n"
                            + "\n\n---\n\n".join(observations)
                        )
                        try:
                            final_answer = generate_response(synthesis_prompt, use_search=False)
                            if not final_answer or not final_answer.strip():
                                final_answer = "Based on my research:\n\n" + "\n\n".join(observations)
                        except Exception:
                            final_answer = "Based on my research:\n\n" + "\n\n".join(observations)
                    else:
                        final_answer = "I was unable to gather enough data to answer your question. Please try again."

                # Build result payload
                tools_used = [s["tool"] for s in scratchpad if s.get("tool")]
                type_map = {
                    "analyze": "analysis", "price": "price", "backtest": "backtest",
                    "screen": "screen", "forex": "forex", "options": "options",
                    "futures": "futures", "general": "unknown",
                }
                has_post_screen = "screen" in tools_used and any(
                    t in tools_used for t in ("analyze", "forex", "options", "futures", "general")
                )
                dominant_type = "analysis" if has_post_screen else (
                    type_map.get(tools_used[0], "analysis") if tools_used else "analysis"
                )

                steps = [
                    {
                        "thought": s.get("thought", ""),
                        "tool": s.get("tool", ""),
                        "tool_input": s.get("tool_input", {}),
                        "observation": s.get("observation", ""),
                    }
                    for s in scratchpad
                ]

                # Return full structured backtest object
                if "backtest" in tools_used and "last" in _backtest_full_result_cache:
                    full_bt = _backtest_full_result_cache.pop("last")
                    _screen_full_result_cache.pop("last", None)
                    _lf.update_current_span(output={"answer": final_answer, "type": "backtest", "step_count": step_count})
                    _emit({"event": "result", "type": "backtest", "content": full_bt,
                           "answer": final_answer, "steps": steps, "step_count": step_count})
                    return

                # Return full structured screener object
                screen_only = "screen" in tools_used and not any(
                    t in tools_used for t in ("analyze", "forex", "options", "futures", "general")
                )
                if screen_only and "last" in _screen_full_result_cache:
                    full_sc = _screen_full_result_cache.pop("last")
                    _backtest_full_result_cache.pop("last", None)
                    if isinstance(full_sc, dict) and "criteria" in full_sc:
                        _lf.update_current_span(output={"answer": final_answer, "type": "screen", "step_count": step_count})
                        _emit({"event": "result", "type": "screen", "content": full_sc,
                               "answer": final_answer, "steps": steps, "step_count": step_count})
                        return

                _backtest_full_result_cache.pop("last", None)
                _screen_full_result_cache.pop("last", None)

                if dominant_type in ("screen", "backtest"):
                    dominant_type = "unknown"

                final_answer = _fix_table_formatting(final_answer)
                _lf.update_current_span(output={"answer": final_answer, "type": dominant_type, "step_count": step_count})
                _emit({
                    "event": "result",
                    "type": dominant_type,
                    "answer": final_answer,
                    "content": final_answer,
                    "steps": steps,
                    "step_count": step_count,
                })

            except Exception as e:
                _emit({"event": "error", "message": str(e)})
            finally:
                q.put(SENTINEL)

        def _worker():
            _ctx_snapshot.run(_worker_body)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

        while True:
            item = q.get()
            if item is SENTINEL:
                break
            yield f"data: {item}\n\n"

