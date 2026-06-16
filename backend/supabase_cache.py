"""
Supabase Technical Cache
────────────────────────
Reads precomputed technicals for Nifty 100 from Supabase.
Falls back to live yfinance fetch if data is missing or stale.

Table schema (run once in Supabase SQL editor):
    CREATE TABLE stock_technicals (
        ticker       TEXT PRIMARY KEY,
        sma20        FLOAT,
        sma50        FLOAT,
        sma200       FLOAT,
        ema8         FLOAT,
        ema20        FLOAT,
        ema50        FLOAT,
        rsi          FLOAT,
        macd         FLOAT,
        macd_signal  FLOAT,
        macd_hist    FLOAT,
        bb_upper     FLOAT,
        bb_lower     FLOAT,
        bb_mid       FLOAT,
        avg_vol20    FLOAT,
        vol_ratio    FLOAT,
        high52       FLOAT,
        low52        FLOAT,
        pct_from_52w_high FLOAT,
        pct_from_52w_low  FLOAT,
        updated_at   TIMESTAMPTZ DEFAULT now()
    );
"""

import os
import time
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any, List

# Load environment variables (matching llm_factory.py pattern)
def _load_env_vars():
    """Load SUPABASE env vars from .env file or Cloud Run environment."""
    env_vars = {}
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    
    # Parse .env file if it exists (local dev only)
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        value = value.split("#")[0].strip().strip('"').strip("'")
                        env_vars[key.strip()] = value
        except Exception as e:
            print(f"[SupabaseCache] Warning: could not read .env file: {e}")
    
    # Cloud Run / system env vars take precedence
    for key in ["SUPABASE_URL", "SUPABASE_SERVICE_KEY"]:
        if key in os.environ:
            env_vars[key] = os.environ[key]
    
    return env_vars

_env = _load_env_vars()

# Supabase client — only imported if credentials are present
_supabase = None
_supabase_lock = threading.Lock()   # prevents double-init from parallel threads
_SUPABASE_STALE_HOURS = 4   # fallback: treat rows older than 4h as stale


def _is_stale(updated_raw: str) -> bool:
    """
    Returns True if the cached row should be considered stale.

    Logic:
    - If the row was updated **today** (IST/UTC+5:30), it is fresh for the
      entire trading day — no re-fetch needed until midnight.
    - If the row was updated on a **previous calendar day**, it is stale.
    - Falls back to the 4-hour window if the timestamp cannot be parsed.

    This prevents morning-precomputed data from being marked stale in the
    afternoon just because 4 hours have elapsed.
    """
    if not updated_raw:
        return True
    try:
        updated_at = datetime.fromisoformat(updated_raw.replace("Z", "+00:00"))
        # Use IST (UTC+5:30) as the trading day boundary
        ist_offset = timedelta(hours=5, minutes=30)
        now_ist = datetime.now(timezone.utc) + ist_offset
        updated_ist = updated_at.astimezone(timezone.utc) + ist_offset

        # Fresh if updated on the same calendar day (IST)
        if updated_ist.date() == now_ist.date():
            return False

        # Stale if from a previous day
        return True
    except Exception:
        # Fallback: use the fixed-hour window
        stale_cutoff = datetime.now(timezone.utc) - timedelta(hours=_SUPABASE_STALE_HOURS)
        try:
            updated_at = datetime.fromisoformat(updated_raw.replace("Z", "+00:00"))
            return updated_at < stale_cutoff
        except Exception:
            return True


def _get_client():
    global _supabase
    if _supabase is not None:
        return _supabase

    with _supabase_lock:
        # Double-checked locking — re-check after acquiring the lock
        # in case another thread already initialized it while we waited.
        if _supabase is not None:
            return _supabase

        url = _env.get("SUPABASE_URL", "")
        key = _env.get("SUPABASE_SERVICE_KEY", "")
        if not url or not key:
            return None

        try:
            from supabase import create_client
            _supabase = create_client(url, key)
            print("[SupabaseCache] Connected to Supabase")
        except Exception as e:
            print(f"[SupabaseCache] Failed to connect: {e}")
            _supabase = None

    return _supabase


def load_technicals_from_supabase(tickers: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Bulk-load precomputed technicals for the given tickers from Supabase.
    Returns a dict of ticker → technicals (or None if missing/stale).
    """
    client = _get_client()
    if client is None:
        return {}

    try:
        resp = (
            client.table("stock_technicals")
            .select("*")
            .in_("ticker", tickers)
            .execute()
        )
        rows = resp.data or []
    except Exception as e:
        print(f"[SupabaseCache] Read error: {e}")
        return {}

    result: Dict[str, Optional[Dict[str, Any]]] = {}

    for row in rows:
        ticker = row["ticker"]
        updated_raw = row.get("updated_at")

        # Check staleness: fresh if updated today (IST), stale if from a previous day
        if _is_stale(updated_raw):
            print(f"[SupabaseCache] Stale data for {ticker}, will re-fetch")
            continue

        # Map DB columns → technicals dict (same keys as _compute_technicals_from_hist)
        tech = {k: row.get(k) for k in [
            "sma9", "sma20", "sma21", "sma50", "sma200",
            "ema8", "ema9", "ema20", "ema21", "ema50",
            "rsi",
            "stoch_k", "stoch_d",
            "macd", "macd_signal", "macd_hist",
            "bb_upper", "bb_lower", "bb_mid",
            "avg_vol20", "vol_ratio",
            "high52", "low52",
            "pct_from_52w_high", "pct_from_52w_low",
            "std_pp", "std_r1", "std_r2", "std_r3", "std_s1", "std_s2", "std_s3",
            "cpr_pp", "cpr_tc", "cpr_bc",
            "cam_h1", "cam_h2", "cam_h3", "cam_h4",
            "cam_l1", "cam_l2", "cam_l3", "cam_l4",
        ]}
        # _hist_close / _hist_df are not stored — custom filters will fall back to live fetch
        result[ticker] = tech

    print(f"[SupabaseCache] Loaded {len(result)}/{len(tickers)} tickers from Supabase")
    return result


def upsert_technicals_to_supabase(ticker: str, tech: Dict[str, Any]) -> bool:
    """
    Write/update a single ticker's technicals to Supabase.
    Called by the precompute job.
    """
    client = _get_client()
    if client is None:
        return False

    # Strip non-serialisable pandas objects before writing
    row = {"ticker": ticker, "updated_at": datetime.now(timezone.utc).isoformat()}
    for col in [
        "sma9", "sma20", "sma21", "sma50", "sma200",
        "ema8", "ema9", "ema20", "ema21", "ema50",
        "rsi",
        "stoch_k", "stoch_d",
        "macd", "macd_signal", "macd_hist",
        "bb_upper", "bb_lower", "bb_mid",
        "avg_vol20", "vol_ratio",
        "high52", "low52",
        "pct_from_52w_high", "pct_from_52w_low",
        "std_pp", "std_r1", "std_r2", "std_r3", "std_s1", "std_s2", "std_s3",
        "cpr_pp", "cpr_tc", "cpr_bc",
        "cam_h1", "cam_h2", "cam_h3", "cam_h4",
        "cam_l1", "cam_l2", "cam_l3", "cam_l4",
    ]:
        val = tech.get(col)
        try:
            row[col] = float(val) if val is not None else None
        except (TypeError, ValueError):
            row[col] = None

    try:
        client.table("stock_technicals").upsert(row, on_conflict="ticker").execute()
        return True
    except Exception as e:
        print(f"[SupabaseCache] Upsert error for {ticker}: {e}")
        return False


# ── OHLCV Daily History Cache ─────────────────────────────────────────────────
# Stores the last 2 years of daily OHLCV for Nifty 100 tickers.
# Backtester reads from here instead of calling yfinance for daily strategies.
#
# Additional table (run once in Supabase SQL editor):
#
#   CREATE TABLE stock_ohlcv (
#       ticker   TEXT        NOT NULL,
#       date     DATE        NOT NULL,
#       open     FLOAT,
#       high     FLOAT,
#       low      FLOAT,
#       close    FLOAT,
#       volume   BIGINT,
#       PRIMARY KEY (ticker, date)
#   );
#   CREATE INDEX idx_stock_ohlcv_ticker_date ON stock_ohlcv (ticker, date DESC);


def load_ohlcv_from_supabase(ticker: str, start_date: str, end_date: str) -> "pd.DataFrame | None":
    """
    Load daily OHLCV for a single ticker between start_date and end_date (YYYY-MM-DD).
    Returns a DataFrame with columns [Open, High, Low, Close, Volume] indexed by date,
    or None if no rows found (caller should fall back to yfinance).
    """
    import pandas as pd

    client = _get_client()
    if client is None:
        return None

    try:
        resp = (
            client.table("stock_ohlcv")
            .select("date,open,high,low,close,volume")
            .eq("ticker", ticker)
            .gte("date", start_date)
            .lte("date", end_date)
            .order("date", desc=False)
            .execute()
        )
        rows = resp.data or []
    except Exception as e:
        print(f"[SupabaseCache] OHLCV read error for {ticker}: {e}")
        return None

    if not rows:
        return None

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    df.columns = [c.capitalize() for c in df.columns]   # open→Open etc.
    df = df[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    df.index.name = "Date"

    print(f"[SupabaseCache] Loaded {len(df)} OHLCV rows for {ticker} from Supabase")
    return df


def upsert_ohlcv_to_supabase(ticker: str, df: "pd.DataFrame") -> bool:
    """
    Bulk-upsert a daily OHLCV DataFrame for one ticker.
    Called by the precompute job.
    """
    import pandas as pd

    client = _get_client()
    if client is None:
        return False

    rows = []
    for date, row in df.iterrows():
        rows.append({
            "ticker": ticker,
            "date": str(date.date()) if hasattr(date, "date") else str(date)[:10],
            "open":   float(row["Open"])   if pd.notna(row["Open"])   else None,
            "high":   float(row["High"])   if pd.notna(row["High"])   else None,
            "low":    float(row["Low"])    if pd.notna(row["Low"])    else None,
            "close":  float(row["Close"])  if pd.notna(row["Close"])  else None,
            "volume": int(row["Volume"])   if pd.notna(row["Volume"]) else None,
        })

    if not rows:
        return False

    try:
        # Upsert in chunks of 500 to stay within Supabase request limits
        chunk_size = 500
        for i in range(0, len(rows), chunk_size):
            client.table("stock_ohlcv").upsert(
                rows[i:i + chunk_size],
                on_conflict="ticker,date"
            ).execute()
        return True
    except Exception as e:
        print(f"[SupabaseCache] OHLCV upsert error for {ticker}: {e}")
        return False


# ── Fundamentals Cache ────────────────────────────────────────────────────────
# Stores slow-moving fundamental data (P/E, market cap, sector, etc.)
# Price, volume, and change_pct are intentionally excluded — always fetched live.
#
# Additional table (run once in Supabase SQL editor):
#
#   CREATE TABLE stock_fundamentals (
#       ticker          TEXT PRIMARY KEY,
#       name            TEXT,
#       sector          TEXT,
#       industry        TEXT,
#       market_cap      FLOAT,
#       trailing_pe     FLOAT,
#       forward_pe      FLOAT,
#       dividend_yield  FLOAT,
#       beta            FLOAT,
#       revenue_growth  FLOAT,
#       debt_to_equity  FLOAT,
#       updated_at      TIMESTAMPTZ DEFAULT now()
#   );

_FUNDAMENTALS_STALE_HOURS = 24   # refresh once a day is enough


def load_fundamentals_from_supabase(tickers: list) -> dict:
    """
    Bulk-load slow fundamentals for the given tickers.
    Returns dict of ticker → fundamentals dict (or empty dict if missing/stale).
    Price/volume are NOT included — caller must still fetch those live.
    """
    client = _get_client()
    if client is None:
        return {}

    try:
        resp = (
            client.table("stock_fundamentals")
            .select("*")
            .in_("ticker", tickers)
            .execute()
        )
        rows = resp.data or []
    except Exception as e:
        print(f"[SupabaseCache] Fundamentals read error: {e}")
        return {}

    stale_cutoff = datetime.now(timezone.utc) - timedelta(hours=_FUNDAMENTALS_STALE_HOURS)
    result = {}

    for row in rows:
        ticker = row["ticker"]
        updated_raw = row.get("updated_at")
        if updated_raw:
            try:
                updated_at = datetime.fromisoformat(updated_raw.replace("Z", "+00:00"))
                if updated_at < stale_cutoff:
                    continue   # stale — let caller re-fetch from yfinance
            except Exception:
                pass

        result[ticker] = {
            "name":           row.get("name", ticker),
            "sector":         row.get("sector", "Unknown"),
            "industry":       row.get("industry", "Unknown"),
            "market_cap":     row.get("market_cap") or 0,
            "trailing_pe":    row.get("trailing_pe"),
            "forward_pe":     row.get("forward_pe"),
            "dividend_yield": row.get("dividend_yield") or 0,
            "beta":           row.get("beta") or 0,
            "revenue_growth": row.get("revenue_growth") or 0,
            "debt_to_equity": row.get("debt_to_equity") or 0,
        }

    print(f"[SupabaseCache] Loaded fundamentals for {len(result)}/{len(tickers)} tickers")
    return result


def upsert_fundamentals_to_supabase(ticker: str, info: dict) -> bool:
    """
    Write slow fundamentals from a yfinance .info dict to Supabase.
    Called by the precompute job.
    """
    client = _get_client()
    if client is None:
        return False

    def _f(val, default=None):
        if val is None:
            return default
        try:
            v = float(val)
            import math
            return default if math.isnan(v) else v
        except (TypeError, ValueError):
            return default

    row = {
        "ticker":         ticker,
        "name":           info.get("longName", ticker),
        "sector":         info.get("sector", "Unknown"),
        "industry":       info.get("industry", "Unknown"),
        "market_cap":     _f(info.get("marketCap")),
        "trailing_pe":    _f(info.get("trailingPE")),
        "forward_pe":     _f(info.get("forwardPE")),
        "dividend_yield": _f((info.get("dividendYield") or 0) * 100),
        "beta":           _f(info.get("beta")),
        "revenue_growth": _f((info.get("revenueGrowth") or 0) * 100),
        "debt_to_equity": _f(info.get("debtToEquity")),
        "updated_at":     datetime.now(timezone.utc).isoformat(),
    }

    try:
        client.table("stock_fundamentals").upsert(row, on_conflict="ticker").execute()
        return True
    except Exception as e:
        print(f"[SupabaseCache] Fundamentals upsert error for {ticker}: {e}")
        return False
