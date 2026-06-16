"""

Hybrid Strategy Backtester Module

- Parses natural language strategy via LLM (unchanged)

- Runs backtest using vectorbt for improved performance and accuracy

- Returns enhanced metrics and chart data

- Maintains backward compatibility with existing API

"""



import json

import re

import time

import yfinance as yf

import pandas as pd

import numpy as np

import vectorbt as vbt

from datetime import datetime, timedelta

from langfuse import observe as traceable

from llm_factory import generate_response, PROMPTS, format_prompt

from supabase_cache import load_ohlcv_from_supabase

from screener import NIFTY_100



_NIFTY100_SET = set(NIFTY_100)



# -- Ticker Normalization ------------------------------------------------------

# Map common index names and aliases to valid yfinance symbols

TICKER_MAPPING = {

    # US Indices

    "US30": "^DJI",           # Dow Jones Industrial Average

    "DJIA": "^DJI",           # Dow Jones (alternative)

    "DOW": "^DJI",            # Dow Jones (alternative)

    "DJI": "^DJI",            # Dow Jones (alternative)

    "SPX": "^GSPC",           # S&P 500

    "SP500": "^GSPC",         # S&P 500 (alternative)

    "NDX": "^IXIC",           # NASDAQ Composite

    "NASDAQ": "^IXIC",        # NASDAQ (alternative)

    "VIX": "^VIX",            # Volatility Index

    

    # International Indices

    "FTSE": "^FTSE",          # FTSE 100 (UK)

    "DAX": "^GDAXI",          # DAX (Germany)

    "CAC": "^FCHI",           # CAC 40 (France)

    "NIKKEI": "^N225",        # Nikkei 225 (Japan)

    "HSI": "^HSI",            # Hang Seng (Hong Kong)

    "ASX": "^AXJO",           # ASX 200 (Australia)

    

    # Commodities (futures)

    "GOLD": "GC=F",           # Gold futures

    "OIL": "CL=F",            # Crude Oil futures

    "NG": "NG=F",             # Natural Gas futures

    "COPPER": "HG=F",         # Copper futures

}



def normalize_ticker(ticker: str) -> str:

    """

    Normalize ticker symbol to valid yfinance format.

    Handles common index names and aliases.

    """

    if not ticker:

        return "AAPL"  # Default fallback

    

    ticker_upper = ticker.upper().strip()

    

    # Check if it's in our mapping

    if ticker_upper in TICKER_MAPPING:

        normalized = TICKER_MAPPING[ticker_upper]

        print(f"[Backtester] Normalized ticker '{ticker}' -> '{normalized}'")

        return normalized

    

    # Return as-is if not in mapping (assume it's already valid)

    return ticker_upper





def is_fractional_asset(ticker: str) -> bool:

    """

    Returns True if the asset supports fractional shares (crypto, forex).

    Returns False for stocks, indices, commodities — which trade in whole numbers.

    """

    t = ticker.upper()

    # Crypto: BTC-USD, ETH-USD, SOL-USD, etc.

    if "-USD" in t or "-USDT" in t or "-BTC" in t or "-ETH" in t:

        return True

    # Forex pairs: EURUSD=X, GBPUSD=X, etc.

    if t.endswith("=X"):

        return True

    # Everything else (stocks, indices ^, futures =F, ETFs) ? whole numbers

    return False





def get_fee_rate(ticker: str) -> tuple[float, str]:

    """

    Return (fee_fraction, description) for a given ticker.

    Fee fraction is applied per trade side by vectorbt (buy + sell = 2x).



    Indian brokers (Zerodha/Groww etc.): flat ?20 per order.

    Approximated as 0.03% — accurate for trades ~?66,000+.

    For smaller trades the real fee is higher; users are notified in the UI.



    US/global stocks & ETFs : 0.1% per side (typical retail broker).

    Crypto                  : 0.1% per side (typical exchange fee).

    Indices / futures       : 0.05% per side (lower, no stamp duty).

    """

    t = ticker.upper()

    # Indian equities

    if t.endswith(".NS") or t.endswith(".BO"):

        return 0.0003, "~?20/order (Indian broker flat fee approximated as 0.03%)"

    # Crypto

    if "-USD" in t or "-USDT" in t or "-BTC" in t or "-ETH" in t:

        return 0.001, "0.1% per trade (crypto exchange fee)"

    # Indices and futures (lower friction)

    if t.startswith("^") or t.endswith("=F"):

        return 0.0005, "0.05% per trade (index/futures)"

    # US and international stocks / ETFs

    return 0.001, "0.1% per trade (retail broker commission)"





# -- Strategy Parsing ----------------------------------------------------------



@traceable(name="backtester:parse_strategy", as_type="tool")

def parse_strategy(strategy_text: str) -> dict:

    """Use LLM to parse natural language strategy and generate signal function code."""

    from datetime import date

    print(f"[Parse Strategy] User query: {strategy_text}")

    today_date = date.today().strftime("%B %d, %Y (%Y-%m-%d)")

    prompt = format_prompt(PROMPTS["backtester_parse_strategy"], strategy_text=strategy_text, today_date=today_date)

    raw = generate_response(prompt, use_search=False)



    # Strip markdown code fences if present

    raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()



    # Extract JSON object

    match = re.search(r"\{.*\}", raw, re.DOTALL)

    if not match:

        raise ValueError(f"Could not parse strategy. Please describe your strategy more clearly, e.g. 'Backtest a 10/50 SMA crossover on AAPL for 2 years with $50,000'.")



    parsed = json.loads(match.group())

    # -- Apply safe defaults BEFORE validation -----------------------------------
    # These guards handle cases where the LLM omits a field despite being asked.

    # Support signal_code as an alias for signal_function (old prompt used signal_code)
    if "signal_function" not in parsed and "signal_code" in parsed:
        parsed["signal_function"] = parsed["signal_code"]

    # Default initial_capital to 100,000 if LLM did not include it
    if "initial_capital" not in parsed or parsed["initial_capital"] is None:
        parsed["initial_capital"] = 100000
        print("[Parse Strategy] initial_capital not found in LLM response — defaulting to 100000")

    # Default strategy_description if missing
    if "strategy_description" not in parsed or not parsed["strategy_description"]:
        entry  = parsed.get("entry_rule", "")
        exit_r = parsed.get("exit_rule", "")
        name   = parsed.get("strategy_name", parsed.get("strategy_type", "Custom"))
        parsed["strategy_description"] = f"{name}. Entry: {entry}. Exit: {exit_r}."

    # Default period_years / period_days if absent (convert old 'period' field if present)
    if "period_years" not in parsed and "period_days" not in parsed:
        period_str = str(parsed.get("period", "2y")).lower()
        if "d" in period_str and not any(c.isalpha() and c != "d" for c in period_str):
            try:
                parsed["period_days"] = int("".join(c for c in period_str if c.isdigit()))
            except ValueError:
                parsed["period_years"] = 2
        elif "mo" in period_str:
            try:
                months = int("".join(c for c in period_str if c.isdigit()))
                parsed["period_years"] = round(months / 12, 2)
            except ValueError:
                parsed["period_years"] = 2
        else:
            try:
                parsed["period_years"] = int("".join(c for c in period_str if c.isdigit())) or 2
            except ValueError:
                parsed["period_years"] = 2

    print(f"[Parse Strategy] signal_function generated:\n{parsed.get('signal_function', 'NONE')}")

    # Validate required fields
    required = ["ticker", "initial_capital", "signal_function"]

    for field in required:

        if field not in parsed:

            raise ValueError(f"Missing required field: {field}")

    

    # Handle explicit date ranges

    has_explicit_dates = "start_date" in parsed and parsed.get("start_date") is not None

    

    # Validate that either explicit dates OR period_years/period_days is present

    if not has_explicit_dates:

        if "period_years" not in parsed and "period_days" not in parsed:

            raise ValueError("Missing required field: either explicit dates (start_date/end_date) or 'period_years'/'period_days' must be specified")

    

    # Set defaults if not present

    if "timeframe" not in parsed:

        parsed["timeframe"] = "1d"

    

    if "period_years" not in parsed:

        parsed["period_years"] = 2  # Default for daily

    

    if "period_days" not in parsed:

        parsed["period_days"] = 60  # Default for intraday

    

    # If explicit dates provided, log them

    if has_explicit_dates:

        print(f"[Parse Strategy] Using explicit date range: {parsed.get('start_date')} to {parsed.get('end_date')}")

    

    return parsed





# -- Signal Generation ---------------------------------------------------------



def _validate_signal_code(code: str) -> None:

    """Security check: block dangerous operations in generated code."""

    # Check for import statements (more precise matching)

    import_patterns = [

        r'\bimport\s+\w+',           # import module

        r'\bfrom\s+\w+\s+import',    # from module import

        r'__import__\s*\(',          # __import__()

    ]

    

    for pattern in import_patterns:

        if re.search(pattern, code, re.IGNORECASE):

            raise ValueError(f"Generated code contains disallowed import statement. Use only numpy (np) and pandas (pd) which are already provided.")

    

    # Check for dangerous operations

    BLOCKED_KEYWORDS = [

        "open(", "eval(", "exec(", "compile(",

        "os.", "sys.", "subprocess", "socket",

        "__builtins__", "__globals__", "__locals__",

        "input(", "raw_input(",

    ]

    

    code_lower = code.lower()

    for keyword in BLOCKED_KEYWORDS:

        if keyword.lower() in code_lower:

            raise ValueError(f"Generated code contains disallowed operation: {keyword.strip()}")





def _fix_indentation(code: str) -> str:

    """

    Auto-fix common LLM indentation bugs by repeatedly correcting

    under-indented lines until the code parses cleanly or no more

    fixes can be made (max 10 iterations).



    Strategy per iteration:

    - Try ast.parse(). If it raises IndentationError at line N:

      - Find the previous non-empty line.

      - If it ends with ':', expected indent = its indent + 4.

      - Otherwise, expected indent = its indent.

      - Re-indent line N to the expected level.

    """

    import ast as _ast

    for attempt in range(10):

        try:

            _ast.parse(code)

            return code  # clean — done

        except IndentationError as e:

            lines = code.splitlines()

            bad_line = (e.lineno or 1) - 1  # 0-indexed

            if bad_line < 0 or bad_line >= len(lines):

                return code  # can't locate — give up



            # Find previous non-empty line

            prev_idx = bad_line - 1

            while prev_idx >= 0 and lines[prev_idx].strip() == "":

                prev_idx -= 1

            if prev_idx < 0:

                return code



            prev_line = lines[prev_idx]

            prev_indent = len(prev_line) - len(prev_line.lstrip())

            expected_indent = prev_indent + 4 if prev_line.rstrip().endswith(':') else prev_indent



            old_line = lines[bad_line]

            lines[bad_line] = ' ' * expected_indent + old_line.lstrip()

            print(f"[CodeFix] Attempt {attempt+1}: fixed indent at line {bad_line+1} "

                  f"? {expected_indent} spaces")

            code = '\n'.join(lines)

        except SyntaxError:

            return code  # non-indentation error — let exec report it

    return code  # return best-effort after max iterations





def _generate_signals(df: pd.DataFrame, signal_code: str) -> pd.DataFrame:

    """Execute LLM-generated signal function on the DataFrame."""

    # Security validation

    _validate_signal_code(signal_code)



    # --- Normalize column names to lowercase ----------------------------------

    # yfinance returns capitalized columns (Close, Open, High, Low, Volume).

    # LLM-generated code consistently uses lowercase (df['close'] etc).

    # We lowercase here as the canonical input; we restore casing on exit.

    _original_cols = list(df.columns)

    df = df.copy()

    df.columns = [c.lower() for c in df.columns]

    # -------------------------------------------------------------------------

    

    # Clean up the signal code (remove any problematic characters)

    # Replace literal \n with actual newlines

    signal_code = signal_code.replace('\\n', '\n')

    # Remove backslash line continuations — join with a space so tokens don't merge

    # e.g. "condition and \\\n   other" ? "condition and  other" (valid syntax)

    signal_code = re.sub(r'\\\s*\n\s*', ' ', signal_code)

    # Fix bare operator at end of line — the LLM sometimes drops the backslash when

    # encoding continuations in JSON, leaving "condition and\n   next_condition".

    # Join any line ending with a dangling boolean/comparison operator to the next line.

    signal_code = re.sub(r'(and|or|not|,|\+|-|\*|/|==|!=|<=|>=|<|>|\()\s*\n\s*', r'\1 ', signal_code)

    # Auto-fix indentation errors (LLM sometimes under-indents a statement after if/else)

    print(f"[CodeFix] Running indentation auto-fix...")

    signal_code = _fix_indentation(signal_code)

    print(f"[CodeFix] Indentation auto-fix complete")

    

    # -- Auto-fix else ? elif bug ---------------------------------------------

    # LLM sometimes generates "else:" instead of "elif in_position:" for exit logic

    # in recurring entry/exit strategies. This creates a bug where exits only fire

    # when entry conditions are false. Fix it automatically.

    # Pattern: "if not in_position:\n    ...\nelse:\n    # Exit" ? "elif in_position:"

    if 'in_position' in signal_code and 'else:' in signal_code:

        # Look for the pattern: else: followed by exit-related logic

        # Match: else:\n    (whitespace) # (optional comment with "exit" or "Exit")

        # Also match: else:\n    (whitespace) if (...exit condition...)

        lines = signal_code.split('\n')

        fixed_lines = []

        i = 0

        while i < len(lines):

            line = lines[i]

            # Check if this line is "else:" (with any indentation)

            if re.match(r'^(\s*)else:\s*$', line):

                indent = re.match(r'^(\s*)', line).group(1)

                # Look ahead to see if next non-empty line contains exit logic

                next_idx = i + 1

                while next_idx < len(lines) and lines[next_idx].strip() == '':

                    next_idx += 1

                if next_idx < len(lines):

                    next_line = lines[next_idx].lower()

                    # Check if it's exit-related (comment or condition)

                    if ('exit' in next_line or 

                        'sell' in next_line or 

                        'signal' in next_line and '-1' in next_line or

                        'in_position = false' in next_line.replace(' ', '')):

                        # Replace else: with elif in_position:

                        fixed_lines.append(f'{indent}elif in_position:')

                        print(f"[CodeFix] Replaced 'else:' with 'elif in_position:' at line {i+1}")

                        i += 1

                        continue

            fixed_lines.append(line)

            i += 1

        signal_code = '\n'.join(fixed_lines)

    

    # Prepare restricted execution environment

    safe_globals = {

        "np": np,

        "pd": pd,

        "__builtins__": {

            "range": range,

            "len": len,

            "int": int,

            "float": float,

            "str": str,

            "bool": bool,

            "list": list,

            "dict": dict,

            "tuple": tuple,

            "set": set,

            "abs": abs,

            "min": min,

            "max": max,

            "sum": sum,

            "round": round,

            "enumerate": enumerate,

            "zip": zip,

        }

    }

    

    local_ns = {}

    

    try:

        # Execute the function definition

        exec(signal_code, safe_globals, local_ns)

        

        # Call the function

        if "generate_signals" not in local_ns:

            raise ValueError("Generated code must define a 'generate_signals' function")

        # df is already lowercased at the top of this function — call directly
        result_df = local_ns["generate_signals"](df, np, pd)

        # Restore original column casing (except 'signal' which is new)
        col_map = {c.lower(): c for c in _original_cols}
        result_df.columns = [col_map.get(c, c) for c in result_df.columns]

        # Validate output — check both cased variants

        if "signal" not in result_df.columns and "Signal" not in result_df.columns:

            raise ValueError("Signal function must add a 'signal' column to the DataFrame")

        

        print(f"[Signals] Columns after generate_signals: {list(result_df.columns)}")

        return result_df

        

    except SyntaxError as e:

        # Show the problematic code for debugging

        print(f"[ERROR] Syntax error in generated code:")

        print("=" * 60)

        print(signal_code)

        print("=" * 60)

        raise ValueError(f"Syntax error in generated code at line {e.lineno}: {e.msg}. Please try rephrasing your strategy.")

    except Exception as e:

        print(f"[ERROR] Error executing signal function:")

        print("=" * 60)

        print(signal_code)

        print("=" * 60)

        raise ValueError(f"Error executing signal function: {str(e)}")

        

        return result_df

        

    except Exception as e:

        raise ValueError(f"Error executing signal function: {str(e)}")





# -- Backtest Engine -----------------------------------------------------------



def _compute_kelly_fraction(close_prices: pd.Series, entries: pd.Series, exits: pd.Series,

                            initial_capital: float, fee_rate: float, half: bool = True) -> float:

    """

    Two-pass Kelly Criterion:

    Pass 1 — run a quick all-in backtest to get win rate and avg win/loss ratio.

    Pass 2 — caller uses the returned fraction for the real backtest.



    Kelly formula:  f = W - (1-W) / R

      W = win rate (fraction)

      R = avg win / avg loss (ratio of absolute values)



    Returns half-Kelly by default (f/2) to reduce volatility.

    Clamps result to [0.01, 0.95] — never bet less than 1% or more than 95%.

    """

    try:

        pf_pilot = vbt.Portfolio.from_signals(

            close_prices,

            entries=entries,

            exits=exits,

            init_cash=initial_capital,

            size=np.inf,

            fees=fee_rate,

            freq='1D',

        )

        trades_df = pf_pilot.trades.records_readable

        if len(trades_df) == 0:

            print("[Kelly] No trades in pilot run — defaulting to 10%")

            return 0.10



        pnls = trades_df["PnL"].values

        wins  = pnls[pnls > 0]

        losses = pnls[pnls < 0]



        if len(wins) == 0 or len(losses) == 0:

            print("[Kelly] All wins or all losses — defaulting to 10%")

            return 0.10



        win_rate = len(wins) / len(pnls)

        avg_win  = float(np.mean(wins))

        avg_loss = float(np.abs(np.mean(losses)))

        win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 1.0



        kelly = win_rate - (1 - win_rate) / win_loss_ratio

        fraction = kelly / 2.0 if half else kelly   # half-Kelly by default

        fraction = float(np.clip(fraction, 0.01, 0.95))



        label = "Half-Kelly" if half else "Full Kelly"

        print(f"[Kelly] W={win_rate:.2%}, R={win_loss_ratio:.2f} ? Kelly={kelly:.2%} ? "

              f"{label}={fraction:.2%} of capital per trade")

        return fraction



    except Exception as e:

        print(f"[Kelly] Pilot run failed ({e}) — defaulting to 10%")

        return 0.10





@traceable(name="vectorbt:run_backtest", as_type="tool")

def _run_backtest_vectorbt(df: pd.DataFrame, initial_capital: float, ticker: str = "", fee_rate: float = 0.001, position_sizing: dict = None, timeframe: str = "1d") -> tuple:

    """

    Vectorized backtest using vectorbt for improved performance and accuracy.

    Returns: (df_with_portfolio, trades_list, final_cash, final_position, total_fees)



    position_sizing modes:

      {"mode": "all_in"}                        — invest all available cash (default)

      {"mode": "fixed_shares", "value": N}      — buy exactly N shares per trade

      {"mode": "fixed_amount", "value": X}      — invest $X per trade

      {"mode": "pct_capital",  "value": P}      — invest P% of current capital per trade

      {"mode": "risk_pct",     "value": R,

       "stop_loss_pct": S}                      — size so that S% stop = R% capital risk

    

    Signal convention:

      - For LONG-only strategies: signal=1 for entry, signal=-1 for exit

      - For SHORT-only strategies: signal=-1 for short entry, signal=1 for short exit

      - Detects strategy type by checking first non-zero signal

    """

    if position_sizing is None:

        position_sizing = {"mode": "all_in"}

    print(f"[VectorBT Backtest] Starting with {len(df)} bars, initial capital: ${initial_capital}")

    

    try:

        # Prepare data for vectorbt

        close_prices = df["Close"]

        signals = df["signal"]

        

        # Detect if this is a short-only strategy by checking the first non-zero signal

        # If first signal is -1, it's a short entry (short-only strategy)

        # If first signal is 1, it's a long entry (long-only strategy)

        first_signal = signals[signals != 0].iloc[0] if len(signals[signals != 0]) > 0 else 1

        is_short_only = (first_signal == -1)

        

        if is_short_only:

            print(f"[VectorBT Backtest] Detected SHORT-only strategy")

            # For short-only: signal=-1 means short entry, signal=1 means cover/exit

            # We need to invert the signals for vectorbt (which expects long convention)

            # Short entry (-1) ? Long entry (1) with negative size

            # Short exit (1) ? Long exit (-1)

            short_entries = (signals == -1) & (signals.shift(1) != -1)

            short_exits = (signals == 1) & (signals.shift(1) != 1)

            entries = short_entries

            exits = short_exits

            # Flag to track that we're shorting

            is_shorting = True

        else:

            print(f"[VectorBT Backtest] Detected LONG-only strategy")

            # For long-only: signal=1 means long entry, signal=-1 means exit

            # Entry: signal changes from 0 to 1

            # Exit: signal changes from 1 to -1 or from 1 to 0

            entries = (signals == 1) & (signals.shift(1) != 1)

            exits = (signals == -1) & (signals.shift(1) != -1)

            is_shorting = False

        

        # Handle first bar edge case

        entries.iloc[0] = signals.iloc[0] == (-1 if is_short_only else 1)

        exits.iloc[0] = False

        

        print(f"[VectorBT Backtest] Generated {entries.sum()} entries, {exits.sum()} exits")



        # -- Unified stop-loss / take-profit safety net -----------------------

        # Merges SL/TP exits with signal-function exits.

        # The safety net ADDS exits when SL/TP is hit before the signal function's

        # own exit — it never wipes valid signal exits.

        # Supports four column types set by the signal function:

        #   stop_loss_usd  / take_profit_usd  — total dollar P&L threshold

        #   stop_loss_pts  / take_profit_pts  — per-share/per-point threshold

        #   stop_loss_pct  / take_profit_pct  — percentage of entry price

        has_sl_usd = "stop_loss_usd" in df.columns

        has_tp_usd = "take_profit_usd" in df.columns

        has_sl_pts = "stop_loss_pts" in df.columns

        has_tp_pts = "take_profit_pts" in df.columns

        has_sl_pct = "stop_loss_pct" in df.columns

        has_tp_pct = "take_profit_pct" in df.columns



        if has_sl_usd or has_tp_usd or has_sl_pts or has_tp_pts or has_sl_pct or has_tp_pct:

            sl_usd = float(df["stop_loss_usd"].iloc[0]) if has_sl_usd else None

            tp_usd = float(df["take_profit_usd"].iloc[0]) if has_tp_usd else None

            sl_pts = float(df["stop_loss_pts"].iloc[0]) if has_sl_pts else None

            tp_pts = float(df["take_profit_pts"].iloc[0]) if has_tp_pts else None

            sl_pct = float(df["stop_loss_pct"].iloc[0]) / 100.0 if has_sl_pct else None

            tp_pct = float(df["take_profit_pct"].iloc[0]) / 100.0 if has_tp_pct else None



            if sl_usd: print(f"[VectorBT Backtest] Applying dollar stop-loss: ${sl_usd}")

            if tp_usd: print(f"[VectorBT Backtest] Applying dollar take-profit: ${tp_usd}")

            if sl_pts: print(f"[VectorBT Backtest] Applying points stop-loss: {sl_pts} pts")

            if tp_pts: print(f"[VectorBT Backtest] Applying points take-profit: {tp_pts} pts")

            if sl_pct: print(f"[VectorBT Backtest] Applying pct stop-loss: {sl_pct*100:.1f}%")

            if tp_pct: print(f"[VectorBT Backtest] Applying pct take-profit: {tp_pct*100:.1f}%")



            # DO NOT wipe signal-function exits — we only add earlier exits when

            # SL/TP is hit before the signal function's own exit fires.

            open_prices = df["Open"]

            in_position = False

            entry_price = 0.0

            shares_held = 0.0



            for i in range(len(df)):

                close = float(close_prices.iloc[i])



                if not in_position:

                    if entries.iloc[i]:

                        in_position = True

                        entry_price = close

                        shares_held = initial_capital / entry_price

                else:

                    # Check if signal function already exits this bar — respect it

                    if exits.iloc[i]:

                        in_position = False

                        continue



                    # Evaluate SL/TP conditions

                    # For SHORT positions, price_diff is NEGATIVE when price goes UP (loss)

                    # and POSITIVE when price goes DOWN (profit)

                    if is_short_only:

                        price_diff = entry_price - close  # Inverted for shorts

                    else:

                        price_diff = close - entry_price  # Normal for longs

                    

                    total_pnl  = price_diff * shares_held     # total dollar P&L



                    sl_hit = (

                        (sl_usd is not None and total_pnl  <= -sl_usd) or

                        (sl_pts is not None and price_diff <= -sl_pts) or

                        (sl_pct is not None and price_diff / entry_price <= -sl_pct)

                    )

                    tp_hit = (

                        (tp_usd is not None and total_pnl  >= tp_usd) or

                        (tp_pts is not None and price_diff >= tp_pts) or

                        (tp_pct is not None and price_diff / entry_price >= tp_pct)

                    )



                    if sl_hit or tp_hit:

                        reason = "TP" if tp_hit else "SL"

                        # Exit at next bar's open for realistic fill; fall back to same bar

                        exit_bar = i + 1 if i + 1 < len(df) else i

                        exits.iloc[exit_bar] = True

                        entries.iloc[exit_bar] = False  # prevent same-bar re-entry

                        in_position = False

                        exit_price_approx = float(open_prices.iloc[exit_bar])

                        print(f"[VectorBT Backtest] {reason} triggered: close={close:.2f}, "

                              f"pts={price_diff:.2f}, PnL=${total_pnl:.2f} — exit at bar {exit_bar} "

                              f"({df.index[exit_bar].date()}) open˜{exit_price_approx:.2f}")



            # Close any position still open at end of data

            if in_position:

                exits.iloc[-1] = True

                print(f"[VectorBT Backtest] Closing open position at final bar")



        print(f"[VectorBT Backtest] Final entries: {entries.sum()}, exits: {exits.sum()}")



        # -- Position sizing ---------------------------------------------------

        mode = position_sizing.get("mode", "all_in")

        ps_value = position_sizing.get("value", None)



        if mode == "fixed_shares":

            # Buy exactly N shares per trade

            vbt_size = float(ps_value) if ps_value else np.inf

            size_type = "shares"

            print(f"[VectorBT Backtest] Position sizing: fixed {vbt_size} shares per trade")



        elif mode == "fixed_amount":

            # Invest $X per trade — vectorbt size_type='value' interprets size as cash amount

            vbt_size = float(ps_value) if ps_value else np.inf

            size_type = "value"

            print(f"[VectorBT Backtest] Position sizing: fixed ${vbt_size} per trade")



        elif mode == "pct_capital":

            # Invest P% of current capital — use size as fraction of portfolio value

            pct = float(ps_value) / 100.0 if ps_value else 1.0

            vbt_size = pct

            size_type = "percent"

            print(f"[VectorBT Backtest] Position sizing: {ps_value}% of capital per trade")



        elif mode == "risk_pct":

            # Risk R% of capital per trade given a stop-loss distance

            risk_pct = float(ps_value) / 100.0 if ps_value else 0.01

            sl_pct   = float(position_sizing.get("stop_loss_pct", 2)) / 100.0

            vbt_size = min(risk_pct / sl_pct, 1.0)

            size_type = "percent"

            print(f"[VectorBT Backtest] Position sizing: risk {ps_value}% per trade "

                  f"with {position_sizing.get('stop_loss_pct', 2)}% SL ? {vbt_size*100:.1f}% of capital")



        elif mode in ("kelly", "half_kelly"):

            # Two-pass Kelly Criterion:

            # Pass 1: quick all-in run to compute win rate & win/loss ratio

            # Pass 2: re-run with the Kelly fraction as pct_capital

            use_half = (mode == "half_kelly") or position_sizing.get("half", True)

            kelly_frac = _compute_kelly_fraction(

                close_prices, entries.copy(), exits.copy(),

                initial_capital, fee_rate, half=use_half

            )

            vbt_size  = kelly_frac

            size_type = "percent"

            # Store computed fraction back so it surfaces in metrics/frontend

            position_sizing["computed_kelly_pct"] = round(kelly_frac * 100, 2)

            label = "Half-Kelly" if use_half else "Full Kelly"

            print(f"[VectorBT Backtest] Position sizing: {label} ? {kelly_frac*100:.1f}% of capital per trade")



        else:

            # all_in — default: use all available cash

            vbt_size = np.inf

            size_type = "shares"

            print(f"[VectorBT Backtest] Position sizing: all-in (default)")



        # Map timeframe to vectorbt freq string for correct metric annualization

        _VBT_FREQ = {

            "1d": "1D",

            "1h": "1h",

            "30m": "30T",

            "15m": "15T",

            "5m": "5T",

            "1m": "1T",

        }

        vbt_freq = _VBT_FREQ.get(timeframe, "1D")



        # Slippage: half the typical bid-ask spread, applied per side.

        # Indices/futures: 0.02% (tight spread), stocks/ETFs: 0.05%, crypto: 0.1%

        t = ticker.upper()

        if t.startswith("^") or t.endswith("=F"):

            slippage_rate = 0.0002   # 0.02% per side for indices/futures

        elif "-USD" in t or "-USDT" in t:

            slippage_rate = 0.001    # 0.1% per side for crypto

        else:

            slippage_rate = 0.0005   # 0.05% per side for stocks/ETFs

        print(f"[VectorBT Backtest] Applying slippage: {slippage_rate*100:.3f}% per side")



        # Run vectorbt portfolio simulation

        pf_kwargs = dict(

            entries=entries,

            exits=exits,

            init_cash=initial_capital,

            fees=fee_rate,

            slippage=slippage_rate,

            freq=vbt_freq,

            short_entries=entries if is_short_only else None,  # Enable shorting for short-only strategies

            short_exits=exits if is_short_only else None,

        )

        

        # For short-only strategies, we need to use from_signals with short parameters

        if is_short_only:

            # Use short_entries and short_exits instead of entries/exits

            pf_kwargs_short = dict(

                short_entries=entries,

                short_exits=exits,

                init_cash=initial_capital,

                fees=fee_rate,

                slippage=slippage_rate,

                freq=vbt_freq,

            )

            _vbt_t0 = time.time()

            if size_type == "percent":

                pf = vbt.Portfolio.from_signals(

                    close_prices,

                    size=vbt_size,

                    size_type="targetpercent",

                    **pf_kwargs_short,

                )

            elif size_type == "value":

                pf = vbt.Portfolio.from_signals(

                    close_prices,

                    size=vbt_size,

                    size_type="value",

                    **pf_kwargs_short,

                )

            else:

                pf = vbt.Portfolio.from_signals(

                    close_prices,

                    size=vbt_size,

                    **pf_kwargs_short,

                )

            print(f"[vectorbt] Portfolio.from_signals (short) completed in {time.time() - _vbt_t0:.3f}s")

        else:

            # Long-only strategy (original code)

            _vbt_t0 = time.time()

            if size_type == "percent":

                pf = vbt.Portfolio.from_signals(

                    close_prices,

                    size=vbt_size,

                    size_type="targetpercent",

                    **pf_kwargs,

                )

            elif size_type == "value":

                pf = vbt.Portfolio.from_signals(

                    close_prices,

                    size=vbt_size,

                    size_type="value",

                    **pf_kwargs,

                )

            else:

                pf = vbt.Portfolio.from_signals(

                    close_prices,

                    size=vbt_size,

                    **pf_kwargs,

                )

            print(f"[vectorbt] Portfolio.from_signals completed in {time.time() - _vbt_t0:.3f}s")

        

        # Get portfolio values over time

        portfolio_values = pf.value()

        

        # Extract trades information

        trades_df = pf.trades.records_readable

        trades_list = []

        

        # Identify indicator columns for trade context

        # Exclude internal helper columns injected by the backtester

        _INTERNAL_COLS = {"Open", "High", "Low", "Close", "Volume", "signal", "portfolio_value",

                          "_timestamp", "date", "_daily_high", "_daily_low", "_daily_close"}

        base_cols = _INTERNAL_COLS

        indicator_cols = [c for c in df.columns if c not in base_cols]

        

        if len(trades_df) > 0:

            # Debug: print actual columns and first row to understand vectorbt output

            print(f"[VectorBT Backtest] Trade columns: {list(trades_df.columns)}")

            print(f"[VectorBT Backtest] First trade row:\n{trades_df.iloc[0]}")

            

            for _, trade in trades_df.iterrows():

                # Use correct vectorbt column names

                entry_idx = trade['Entry Timestamp']

                exit_idx = trade['Exit Timestamp'] if pd.notna(trade['Exit Timestamp']) else None

                entry_price = trade['Avg Entry Price']

                exit_price = trade['Avg Exit Price'] if pd.notna(trade.get('Avg Exit Price', np.nan)) else None

                size = trade['Size']

                pnl = trade['PnL']

                return_pct = trade['Return'] * 100  # Convert to percentage

                

                # Compute shares: use size from vectorbt, but fallback to capital/price if size is 0 or near-zero

                shares = float(size)

                if shares < 1e-9:

                    # Recompute from entry price and initial capital

                    shares = initial_capital / float(entry_price)

                    print(f"[VectorBT Backtest] size was near-zero ({size}), recomputed shares = {shares:.6f}")

                

                # Round to whole numbers for stocks/indices/commodities; keep decimals for crypto/forex

                if is_fractional_asset(ticker):

                    shares = round(shares, 6)

                else:

                    whole_shares = int(shares)  # floor to whole number

                    shares = whole_shares if whole_shares > 0 else shares  # keep fractional if can't afford 1

                

                # Get indicator values at entry

                indicators = {}

                if entry_idx in df.index:

                    for col in indicator_cols:

                        try:

                            val = df.loc[entry_idx, col]

                            if not pd.isna(val):

                                indicators[col] = round(float(val), 4)

                        except (KeyError, TypeError, ValueError):

                            pass

                

                # Entry trade

                entry_trade = {

                    "date": str(entry_idx.date()) if hasattr(entry_idx, 'date') else str(entry_idx),

                    "type": "SHORT" if is_short_only else "BUY",

                    "price": round(float(entry_price), 2),

                    "shares": round(shares, 6),

                    "value": round(float(entry_price) * shares, 2),

                    "pnl": 0,

                    "pnl_pct": 0,

                    "days_held": 0,

                }

                entry_trade.update(indicators)

                trades_list.append(entry_trade)

                

                # Exit trade (if position was closed)

                if exit_idx is not None and pd.notna(exit_idx) and pd.notna(exit_price):

                    # Get indicator values at exit

                    exit_indicators = {}

                    if exit_idx in df.index:

                        for col in indicator_cols:

                            try:

                                val = df.loc[exit_idx, col]

                                if not pd.isna(val):

                                    exit_indicators[col] = round(float(val), 4)

                            except (KeyError, TypeError, ValueError):

                                pass

                    

                    days_held = (exit_idx - entry_idx).days if hasattr(exit_idx, 'date') and hasattr(entry_idx, 'date') else 0

                    

                    # Recompute pnl from our corrected shares to stay consistent with displayed values

                    entry_value = float(entry_price) * shares

                    exit_value = float(exit_price) * shares

                    

                    # For SHORT positions, profit when exit price < entry price

                    if is_short_only:

                        computed_pnl = entry_value - exit_value  # Inverted for shorts

                    else:

                        computed_pnl = exit_value - entry_value  # Normal for longs

                    

                    computed_pnl_pct = (computed_pnl / entry_value * 100) if entry_value != 0 else 0.0



                    exit_trade = {

                        "date": str(exit_idx.date()) if hasattr(exit_idx, 'date') else str(exit_idx),

                        "_timestamp": str(exit_idx),  # full timestamp used for chart trimming

                        "type": "COVER" if is_short_only else "SELL",

                        "price": round(float(exit_price), 2),

                        "shares": round(shares, 6),

                        "value": round(exit_value, 2),

                        "pnl": round(computed_pnl, 2),

                        "pnl_pct": round(computed_pnl_pct, 2),

                        "days_held": days_held,

                    }

                    exit_trade.update(exit_indicators)

                    trades_list.append(exit_trade)

        

        # Add portfolio values to dataframe

        df_result = df.copy()

        df_result["portfolio_value"] = portfolio_values.values

        

        # Calculate final cash and position from trades

        final_cash = float(pf.cash().iloc[-1])

        total_fees_paid = float(pf.fees_paid().sum()) if hasattr(pf, 'fees_paid') else 0.0

        

        # Calculate final position by checking if last trade was a buy or sell

        final_position = 0

        if len(trades_list) > 0:

            last_trade = trades_list[-1]

            if last_trade["type"] == "BUY":

                final_position = round(last_trade["shares"], 6)

            # If last trade was SELL, position is 0 (already set above)

        

        print(f"[VectorBT Backtest] Completed. Final cash: ${final_cash:.2f}, Final position: {final_position} shares, Total fees: ${total_fees_paid:.2f}")

        print(f"[VectorBT Backtest] Generated {len(trades_list)} trade records")

        

        return df_result, trades_list, final_cash, final_position, total_fees_paid

        

    except Exception as e:

        print(f"[VectorBT Backtest] Error: {e}. Falling back to legacy implementation.")

        df_r, trades_r, cash_r, pos_r = _run_backtest_legacy(df, initial_capital)

        return df_r, trades_r, cash_r, pos_r, 0.0





def _run_backtest_legacy(df: pd.DataFrame, initial_capital: float) -> tuple:

    """

    Legacy backtest implementation as fallback.

    Simple long-only backtest: buy on signal=1, sell on signal=-1.

    """

    print(f"[Legacy Backtest] Starting fallback implementation")

    

    capital = initial_capital

    position = 0  # shares held

    portfolio_values = []

    trades = []



    # Identify indicator columns (everything except OHLCV, signal, portfolio_value, and internal helpers)

    _INTERNAL_COLS = {"Open", "High", "Low", "Close", "Volume", "signal", "portfolio_value",

                      "date", "_daily_high", "_daily_low", "_daily_close"}

    base_cols = _INTERNAL_COLS

    indicator_cols = [c for c in df.columns if c not in base_cols]



    prev_signal = 0

    last_buy_price = 0

    last_buy_date = None



    for i, row in df.iterrows():

        price = float(row["Close"])

        sig = int(row["signal"])



        # Snapshot indicator values at this bar

        indicators = {}

        for col in indicator_cols:

            try:

                val = row[col]

                if not pd.isna(val):

                    indicators[col] = round(float(val), 4)

            except (KeyError, TypeError, ValueError):

                pass



        # Entry: buy signal and not in position

        if sig == 1 and prev_signal != 1 and position == 0 and capital > 0:

            shares = capital // price

            if shares > 0:

                position = shares

                cost = shares * price

                capital -= cost

                last_buy_price = price

                last_buy_date = i

                trade = {

                    "date": str(i.date()), 

                    "type": "BUY", 

                    "price": round(price, 2), 

                    "shares": shares,

                    "value": round(cost, 2),

                    "pnl": 0,

                    "pnl_pct": 0,

                    "days_held": 0,

                }

                trade.update(indicators)

                trades.append(trade)



        # Exit: sell signal and in position

        elif sig == -1 and prev_signal != -1 and position > 0:

            proceeds = position * price

            capital += proceeds

            

            # Calculate P&L

            cost_basis = position * last_buy_price

            pnl = proceeds - cost_basis

            pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0

            

            # Calculate holding period

            days_held = (i - last_buy_date).days if last_buy_date else 0

            

            trade = {

                "date": str(i.date()), 

                "type": "SELL", 

                "price": round(price, 2), 

                "shares": position,

                "value": round(proceeds, 2),

                "pnl": round(pnl, 2),

                "pnl_pct": round(pnl_pct, 2),

                "days_held": days_held,

            }

            trade.update(indicators)

            trades.append(trade)

            position = 0

            last_buy_price = 0

            last_buy_date = None



        portfolio_value = capital + position * price

        portfolio_values.append(portfolio_value)

        prev_signal = sig



    df_result = df.copy()

    df_result["portfolio_value"] = portfolio_values

    return df_result, trades, capital, position





# -- Metrics Calculation -------------------------------------------------------



def _calc_metrics_vectorbt(df: pd.DataFrame, trades: list, initial_capital: float, final_capital: float, final_position: int, timeframe: str = "1d") -> dict:

    """

    Calculate comprehensive metrics using vectorbt's built-in analytics.

    """

    print(f"[VectorBT Metrics] Calculating metrics for {len(df)} bars")

    

    close_prices = df["Close"]

    portfolio_values = df["portfolio_value"]

    

    # Create a simple vectorbt portfolio for metrics calculation

    # We'll use the portfolio values we already calculated

    returns = portfolio_values.pct_change().dropna()

    

    # Final portfolio value (liquidate remaining position)

    final_value = final_capital + final_position * float(close_prices.iloc[-1])

    

    # Basic returns

    total_return = (final_value - initial_capital) / initial_capital * 100

    bh_return = (float(close_prices.iloc[-1]) - float(close_prices.iloc[0])) / float(close_prices.iloc[0]) * 100

    

    # Determine annualization factor based on timeframe

    timeframe_factors = {

        "1d": 252,

        "1h": 252 * 6.5,

        "30m": 252 * 13,

        "15m": 252 * 26,

        "5m": 252 * 78,

        "1m": 252 * 390

    }

    annual_factor = timeframe_factors.get(timeframe, 252)

    

    # Calculate metrics using vectorbt-style calculations

    # Sharpe ratio

    if len(returns) > 1 and returns.std() > 0:

        sharpe = returns.mean() / returns.std() * np.sqrt(annual_factor)

    else:

        sharpe = 0

    

    # Max drawdown using vectorbt method

    rolling_max = portfolio_values.expanding().max()

    drawdowns = (portfolio_values - rolling_max) / rolling_max

    max_drawdown = float(drawdowns.min() * 100)

    

    # Sortino ratio (downside deviation)

    downside_returns = returns[returns < 0]

    if len(downside_returns) > 1 and downside_returns.std() > 0:

        sortino = returns.mean() / downside_returns.std() * np.sqrt(annual_factor)

    else:

        sortino = 0

    

    # Calmar ratio (annualized return / max drawdown)

    n_periods = len(df)

    years = n_periods / annual_factor

    annualized_return = ((final_value / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0

    calmar = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0

    

    # Trade statistics

    buy_trades = [t for t in trades if t["type"] in ("BUY", "SHORT")]  # Include SHORT entries

    sell_trades = [t for t in trades if t["type"] in ("SELL", "COVER")]  # Include COVER exits

    

    # Match buy/sell pairs for win rate calculation

    wins = 0

    losses = 0

    total_pnl = 0

    winning_trades_pnl = []

    losing_trades_pnl = []

    

    for sell_trade in sell_trades:

        pnl = sell_trade.get("pnl", 0)

        total_pnl += pnl

        if pnl > 0:

            wins += 1

            winning_trades_pnl.append(pnl)

        else:

            losses += 1

            losing_trades_pnl.append(pnl)

    

    total_closed = wins + losses

    win_rate = (wins / total_closed * 100) if total_closed > 0 else 0

    

    # Profit factor

    gross_profit = sum(winning_trades_pnl) if winning_trades_pnl else 0

    gross_loss = abs(sum(losing_trades_pnl)) if losing_trades_pnl else 0

    if gross_loss > 0:

        profit_factor = gross_profit / gross_loss

    elif gross_profit > 0:

        profit_factor = 999.99  # Cap at 999.99 instead of infinity for JSON serialization

    else:

        profit_factor = 0

    

    # Average trade metrics

    avg_win = np.mean(winning_trades_pnl) if winning_trades_pnl else 0

    avg_loss = np.mean(losing_trades_pnl) if losing_trades_pnl else 0

    

    # Expectancy

    expectancy = (win_rate / 100 * avg_win) + ((100 - win_rate) / 100 * avg_loss) if total_closed > 0 else 0

    

    print(f"[VectorBT Metrics] Calculated {total_closed} closed trades, {wins} wins, {losses} losses")

    

    return {

        "initial_capital": round(initial_capital, 2),

        "final_value": round(final_value, 2),

        "total_return_pct": round(total_return, 2),

        "buy_hold_return_pct": round(bh_return, 2),

        "annualized_return_pct": round(annualized_return, 2),

        "sharpe_ratio": round(float(sharpe), 3),

        "sortino_ratio": round(float(sortino), 3),

        "calmar_ratio": round(float(calmar), 3),

        "max_drawdown_pct": round(max_drawdown, 2),

        "total_trades": len(buy_trades),

        "total_closed_trades": total_closed,

        "win_rate_pct": round(win_rate, 2),

        "wins": wins,

        "losses": losses,

        "profit_factor": round(profit_factor, 3),

        "expectancy": round(expectancy, 2),

        "avg_win": round(avg_win, 2),

        "avg_loss": round(avg_loss, 2),

        "gross_profit": round(gross_profit, 2),

        "gross_loss": round(gross_loss, 2),

    }





def _calc_metrics_legacy(df: pd.DataFrame, trades: list, initial_capital: float, final_capital: float, final_position: int, timeframe: str = "1d") -> dict:

    """Legacy metrics calculation as fallback."""

    close = df["Close"]

    portfolio = df["portfolio_value"]



    # Final portfolio value (liquidate remaining position)

    final_value = final_capital + final_position * float(close.iloc[-1])



    total_return = (final_value - initial_capital) / initial_capital * 100



    # Buy & hold return

    bh_return = (float(close.iloc[-1]) - float(close.iloc[0])) / float(close.iloc[0]) * 100



    # Daily returns

    daily_ret = portfolio.pct_change().dropna()

    

    # Adjust annualization factor based on timeframe

    timeframe_factors = {

        "1d": 252,

        "1h": 252 * 6.5,

        "30m": 252 * 13,

        "15m": 252 * 26,

        "5m": 252 * 78,

        "1m": 252 * 390

    }

    annual_factor = timeframe_factors.get(timeframe, 252)



    # Sharpe ratio (assume 0% risk-free)

    sharpe = (daily_ret.mean() / daily_ret.std() * np.sqrt(annual_factor)) if daily_ret.std() > 0 else 0



    # Max drawdown

    rolling_max = portfolio.cummax()

    drawdown = (portfolio - rolling_max) / rolling_max

    max_drawdown = float(drawdown.min() * 100)



    # Win rate from trades - include both BUY/SELL and SHORT/COVER

    buy_trades = [t for t in trades if t["type"] in ("BUY", "SHORT")]

    sell_trades = [t for t in trades if t["type"] in ("SELL", "COVER")]

    wins = 0

    losses = 0

    for b, s in zip(buy_trades, sell_trades):

        # For SHORT trades, profit when exit price < entry price

        if b["type"] == "SHORT":

            if s["price"] < b["price"]:

                wins += 1

            else:

                losses += 1

        else:

            # For LONG trades, profit when exit price > entry price

            if s["price"] > b["price"]:

                wins += 1

            else:

                losses += 1

    total_closed = wins + losses

    win_rate = (wins / total_closed * 100) if total_closed > 0 else 0



    # Annualized return

    n_periods = len(df)

    years = n_periods / annual_factor

    annualized_return = ((final_value / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0



    return {

        "initial_capital": round(initial_capital, 2),

        "final_value": round(final_value, 2),

        "total_return_pct": round(total_return, 2),

        "buy_hold_return_pct": round(bh_return, 2),

        "annualized_return_pct": round(annualized_return, 2),

        "sharpe_ratio": round(float(sharpe), 3),

        "max_drawdown_pct": round(max_drawdown, 2),

        "total_trades": len(buy_trades),

        "win_rate_pct": round(win_rate, 2),

        "wins": wins,

        "losses": losses,

    }





# -- Chart Data Builder --------------------------------------------------------



def _build_chart_data(df: pd.DataFrame, trades: list) -> dict:

    """Build serializable chart data for the frontend."""



    # -- Trim to last trade exit date -----------------------------------------

    # When SL/TP closes the position early, df still contains all bars through

    # the original end date. Trim to the exit bar so charts don't show a long

    # flat tail of idle cash after the trade is closed.

    sell_trades = [t for t in trades if t.get("type") == "SELL"]

    if sell_trades:

        last_sell = sell_trades[-1]

        # Prefer full timestamp if available (intraday), fall back to date string (daily)

        last_exit_str = last_sell.get("_timestamp") or last_sell.get("date", "")

        try:

            last_exit_ts = pd.Timestamp(last_exit_str)

            df_index = df.index

            # Match timezone: if index is tz-aware, make the target tz-aware too

            if df_index.tz is not None:

                last_exit_ts = last_exit_ts.tz_localize(df_index.tz) if last_exit_ts.tzinfo is None \
                               else last_exit_ts.tz_convert(df_index.tz)

            # side="right" lands just after the exit timestamp; step back 1 to get the exit bar

            exit_pos = df_index.searchsorted(last_exit_ts, side="right") - 1

            exit_pos = max(exit_pos, 0)

            # Keep one extra bar past the exit so the exit point is visible

            trim_pos = min(exit_pos + 1, len(df) - 1)

            df = df.iloc[: trim_pos + 1]

            print(f"[Chart] Trimmed to exit {last_exit_str!r} (bar {trim_pos}/{len(df_index)-1})")

        except Exception as e:

            print(f"[Chart] Could not trim to exit date: {e}")



    # Downsample if too many points (keep max 500 for performance)

    if len(df) > 500:

        step = len(df) // 500

        df_plot = df.iloc[::step]

    else:

        df_plot = df



    price_series = []

    for idx, row in df_plot.iterrows():

        point = {

            "date": str(idx.date()),

            "close": round(float(row["Close"]), 2),

            "portfolio": round(float(row["portfolio_value"]), 2),

        }

        # Add ALL numeric indicator columns except base OHLCV and internal helpers

        _CHART_EXCLUDE = {"Open", "High", "Low", "Close", "Volume", "portfolio_value",

                          "signal", "_timestamp", "date", "_daily_high", "_daily_low", "_daily_close"}

        for col in df_plot.columns:

            if col not in _CHART_EXCLUDE:

                if col in row and not pd.isna(row[col]):

                    try:

                        point[col] = round(float(row[col]), 4)

                    except (ValueError, TypeError):

                        pass  # Skip non-numeric columns

        price_series.append(point)



    # Drawdown series

    portfolio = df["portfolio_value"]

    rolling_max = portfolio.cummax()

    drawdown_pct = ((portfolio - rolling_max) / rolling_max * 100)

    drawdown_series = []

    for idx, val in drawdown_pct.items():

        drawdown_series.append({"date": str(idx.date()), "drawdown": round(float(val), 2)})

    if len(drawdown_series) > 500:

        step = len(drawdown_series) // 500

        drawdown_series = drawdown_series[::step]



    return {

        "price_series": price_series,

        "drawdown_series": drawdown_series,

        "trades": trades,

    }





# -- Main Entry Point ----------------------------------------------------------



@traceable(name="supabase:load_ohlcv", as_type="tool")

def _fetch_ohlcv_supabase(ticker: str, start: str, end: str):

    """Traced wrapper around Supabase OHLCV cache load."""

    print(f"[Backtest] Fetching {ticker} from Supabase ({start} ? {end})")

    return load_ohlcv_from_supabase(ticker, start, end)





@traceable(name="yfinance:download_ohlcv", as_type="tool")

def _fetch_ohlcv_yfinance(ticker: str, start_date: datetime, end_date: datetime, interval: str):

    """Traced wrapper around yfinance OHLCV download."""

    print(f"[Backtest] Fetching {ticker} from yfinance (interval={interval})")

    t0 = time.time()

    raw = yf.download(

        ticker,

        start=start_date.strftime("%Y-%m-%d"),

        end=end_date.strftime("%Y-%m-%d"),

        interval=interval,

        progress=False,

        auto_adjust=True,

    )

    elapsed = time.time() - t0

    rows = 0 if raw is None else len(raw)

    print(f"[yfinance] {ticker}: {rows} rows in {elapsed:.2f}s")

    return raw





@traceable(name="backtester:run_strategy", as_type="chain")

def run_strategy_backtest(strategy_text: str) -> dict:

    """

    Full pipeline:

    1. Parse strategy from natural language (LLM generates signal function)

    2. Download price data (supports daily and intraday timeframes)

    3. Execute signal function on data

    4. Run backtest

    5. Return metrics + chart data

    """

    # Step 1: Parse strategy and get LLM-generated signal function

    parsed = parse_strategy(strategy_text)



    ticker = normalize_ticker(parsed.get("ticker", "AAPL"))

    signal_code = parsed.get("signal_function")

    period_years = parsed.get("period_years", 2)

    period_days = parsed.get("period_days", 60)

    initial_capital = float(parsed.get("initial_capital", 100000))

    strategy_description = parsed.get("strategy_description", "Custom strategy")

    timeframe = parsed.get("timeframe", "1d")  # Default to daily

    position_sizing = parsed.get("position_sizing", {"mode": "all_in"})



    # Step 2: Download data with appropriate timeframe

    end_date = datetime.today()

    

    # Check if explicit dates were provided

    explicit_start = parsed.get("start_date")

    explicit_end = parsed.get("end_date")

    

    if explicit_start:

        try:

            start_date = datetime.strptime(explicit_start, "%Y-%m-%d")

            print(f"[Backtest] Using explicit start date: {start_date.date()}")

        except (ValueError, TypeError):

            print(f"[Backtest] Invalid start_date format: {explicit_start}, using period_years instead")

            start_date = end_date - timedelta(days=int(period_years) * 365)

    else:

        # Use period_years or period_days based on timeframe

        if timeframe == "1d":

            start_date = end_date - timedelta(days=int(period_years) * 365)

        else:

            start_date = end_date - timedelta(days=int(period_days))

    

    if explicit_end:

        try:

            end_date = datetime.strptime(explicit_end, "%Y-%m-%d")

            print(f"[Backtest] Using explicit end date: {end_date.date()}")

        except (ValueError, TypeError):

            print(f"[Backtest] Invalid end_date format: {explicit_end}, using today instead")

            end_date = datetime.today()

    

    # Validate date range and fix common issues

    if start_date > end_date:

        print(f"[Backtest] WARNING: start_date ({start_date.date()}) is after end_date ({end_date.date()})")

        

        # Check if this looks like a year parsing error (e.g., 2026 vs 2024)

        if explicit_end and explicit_end.startswith("2024") and explicit_start and "2026" in explicit_start:

            print(f"[Backtest] Detected year parsing error. Correcting end_date year from 2024 to 2026")

            end_date = end_date.replace(year=2026)

            print(f"[Backtest] Corrected end_date to: {end_date.date()}")

        else:

            # Generic swap

            print(f"[Backtest] Swapping start_date and end_date")

            start_date, end_date = end_date, start_date

    

    # Additional check: if end_date is in the past and we have explicit_start, use today as end_date

    today = datetime.today()

    if explicit_end and end_date < today and explicit_start:

        print(f"[Backtest] WARNING: end_date ({end_date.date()}) is in the past. Using today ({today.date()}) instead")

        end_date = today

    

    # Determine interval based on timeframe

    if timeframe == "1d":

        interval = "1d"

    else:

        # Intraday: apply yfinance limits

        days_requested = int((end_date - start_date).days)

        

        # Define yfinance limits for intraday data

        limits = {

            "1m": 7,      # Max 7 days for 1-minute

            "5m": 60,     # Max 60 days for 5-minute

            "15m": 60,    # Max 60 days for 15-minute

            "30m": 60,    # Max 60 days for 30-minute

            "1h": 730,    # Max 730 days for hourly

        }

        max_days = limits.get(timeframe, 60)

        

        # Check if user's explicit date range exceeds limits

        if explicit_start and explicit_end and days_requested > max_days:

            raise ValueError(

                f"Yahoo Finance only provides {timeframe} data for the last {max_days} days. "

                f"You requested {days_requested} days (from {start_date.date()} to {end_date.date()}). "

                f"Please either:\n"

                f"1. Use a shorter date range (max {max_days} days for {timeframe})\n"

                f"2. Use a longer timeframe (e.g., '1h' for up to 730 days, or '1d' for years of data)\n"

                f"3. Remove explicit dates and let the system use the default period"

            )

        

        # Adjust start_date if needed to respect limits (for non-explicit dates)

        if days_requested > max_days:

            start_date = end_date - timedelta(days=max_days)

            print(f"[Backtest] Adjusted start date to respect {timeframe} limit: {start_date.date()} (max {max_days} days)")

        

        interval = timeframe

    

    # -- Fetch OHLCV: Supabase first (daily Nifty 100), else yfinance ---------

    raw = None

    if timeframe == "1d" and ticker in _NIFTY100_SET:

        raw = _fetch_ohlcv_supabase(

            ticker,

            start_date.strftime("%Y-%m-%d"),

            end_date.strftime("%Y-%m-%d"),

        )

        if raw is not None and raw.empty:

            raw = None   # treat empty result as a miss



    if raw is None:

        raw = _fetch_ohlcv_yfinance(ticker, start_date, end_date, interval)



    # Retry logic for Indian tickers: yfinance occasionally returns 404 for

    # .NS tickers on the first attempt due to Yahoo Finance rate-limiting or

    # transient CDN errors. Retry once after a short delay, then try the .BO

    # (BSE) suffix as a fallback before giving up.

    if (raw is None or raw.empty) and ticker.upper().endswith(".NS"):

        import time

        print(f"[Backtest] {ticker} returned empty — retrying after 2s...")

        time.sleep(2)

        raw = _fetch_ohlcv_yfinance(ticker, start_date, end_date, interval)

        if raw is None or raw.empty:

            bo_ticker = ticker[:-3] + ".BO"

            print(f"[Backtest] {ticker} still empty — trying BSE fallback: {bo_ticker}")

            raw = _fetch_ohlcv_yfinance(bo_ticker, start_date, end_date, interval)

            if raw is not None and not raw.empty:

                print(f"[Backtest] Using BSE ticker {bo_ticker} as fallback for {ticker}")

                ticker = bo_ticker  # update ticker so fees/slippage logic stays correct



    if raw is None or raw.empty:

        raise ValueError(f"No price data found for ticker '{ticker}' with interval '{interval}'. "

                         f"The ticker may be temporarily unavailable on Yahoo Finance. "

                         f"Please try again in a moment or verify the symbol is correct.")



    # Flatten multi-level columns if present

    if isinstance(raw.columns, pd.MultiIndex):

        raw.columns = raw.columns.get_level_values(0)



    df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()

    df.dropna(inplace=True)



    # -- Inject accurate daily close for intraday pivot calculations -----------

    # For intraday timeframes (5m, 15m, 30m, 1h, 1m), the last bar of each day

    # in yfinance data is typically the 3:55 PM bar, NOT the official 4:00 PM

    # closing print. This causes Camarilla / pivot levels to be off by several

    # points because they use prev_close = last_5m_bar.Close instead of the

    # true daily close.

    #

    # Fix: fetch a separate daily OHLCV series and inject a '_daily_close'

    # column (and '_daily_high' / '_daily_low') that are constant for each

    # trading day. The LLM-generated signal function is instructed (via the

    # prompt) to prefer these columns when computing pivot levels.

    if timeframe != "1d":

        try:

            daily_start = start_date - timedelta(days=5)  # a few extra days for the first pivot day

            daily_raw = yf.download(

                ticker,

                start=daily_start.strftime("%Y-%m-%d"),

                end=(end_date + timedelta(days=1)).strftime("%Y-%m-%d"),

                interval="1d",

                progress=False,

                auto_adjust=True,

            )

            if isinstance(daily_raw.columns, pd.MultiIndex):

                daily_raw.columns = daily_raw.columns.get_level_values(0)

            if not daily_raw.empty:

                # Build a date ? (high, low, close) lookup

                daily_raw.index = pd.to_datetime(daily_raw.index)

                daily_lookup = {

                    idx.date(): (float(row["High"]), float(row["Low"]), float(row["Close"]))

                    for idx, row in daily_raw.iterrows()

                }

                # Map each intraday bar to its day's official OHLC

                bar_dates = pd.to_datetime(df.index).date

                df["_daily_high"]  = [daily_lookup.get(d, (np.nan, np.nan, np.nan))[0] for d in bar_dates]

                df["_daily_low"]   = [daily_lookup.get(d, (np.nan, np.nan, np.nan))[1] for d in bar_dates]

                df["_daily_close"] = [daily_lookup.get(d, (np.nan, np.nan, np.nan))[2] for d in bar_dates]

                print(f"[Backtest] Injected _daily_high/_daily_low/_daily_close for accurate intraday pivot calculations")

        except Exception as e:

            print(f"[Backtest] Warning: could not inject daily close ({e}). Pivot levels may be slightly off.")



    # Step 3: Execute LLM-generated signal function

    df = _generate_signals(df, signal_code)



    # Step 4: Run backtest using vectorbt

    fee_rate, fee_desc = get_fee_rate(ticker)

    print(f"[Backtest] Applying fees: {fee_desc}")

    

    # Compute slippage rate (same logic as in _run_backtest_vectorbt)

    t = ticker.upper()

    if t.startswith("^") or t.endswith("=F"):

        slippage_rate = 0.0002   # 0.02% per side for indices/futures

        slippage_desc = "0.02% per trade (index/futures bid-ask spread)"

    elif "-USD" in t or "-USDT" in t:

        slippage_rate = 0.001    # 0.1% per side for crypto

        slippage_desc = "0.1% per trade (crypto bid-ask spread)"

    else:

        slippage_rate = 0.0005   # 0.05% per side for stocks/ETFs

        slippage_desc = "0.05% per trade (stock/ETF bid-ask spread)"

    

    df, trades, final_capital, final_position, total_fees = _run_backtest_vectorbt(

        df, initial_capital, ticker, fee_rate, position_sizing, timeframe

    )



    # Step 5: Compute metrics using vectorbt analytics (with fallback)

    try:

        metrics = _calc_metrics_vectorbt(df, trades, initial_capital, final_capital, final_position, timeframe)

    except Exception as e:

        print(f"[VectorBT Metrics] Error: {e}. Falling back to legacy metrics.")

        metrics = _calc_metrics_legacy(df, trades, initial_capital, final_capital, final_position, timeframe)



    # Inject fee and slippage info into metrics

    metrics["total_fees"] = round(total_fees, 2)

    metrics["fee_rate_pct"] = round(fee_rate * 100, 4)

    metrics["fee_description"] = fee_desc

    metrics["slippage_rate_pct"] = round(slippage_rate * 100, 4)

    metrics["slippage_description"] = slippage_desc



    # Step 6: Build chart data

    chart_data = _build_chart_data(df, trades)

    

    # Debug: log first trade to verify indicator columns are present

    if trades:

        print(f"[Backtest] Sample trade keys: {list(trades[0].keys())}")



    return {

        "parsed_strategy": {

            "ticker": ticker,

            "strategy_description": strategy_description,

            "period_years": period_years if timeframe == "1d" and not explicit_start else None,

            "period_days": period_days if timeframe != "1d" and not explicit_start else None,

            "start_date": start_date.strftime("%Y-%m-%d") if explicit_start else None,

            "end_date": end_date.strftime("%Y-%m-%d") if explicit_start else None,

            "timeframe": timeframe,

            "initial_capital": initial_capital,

            "signal_code": signal_code,

            "fee_rate_pct": round(fee_rate * 100, 4),

            "fee_description": fee_desc,

            "slippage_rate_pct": round(slippage_rate * 100, 4),

            "slippage_description": slippage_desc,

            "position_sizing": position_sizing,

        },

        "metrics": metrics,

        "chart_data": chart_data,

    }



