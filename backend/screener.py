"""
AI Stock Screener
─────────────────
Supports:
  - Index membership  : Nifty 50/100, S&P 500, NASDAQ 100, Dow Jones, FTSE 100, DAX 40, Nikkei 225, Hang Seng, ASX 200, TSX
  - Technical criteria: price vs MA (20/50/200), RSI, 52-week high/low proximity
  - Fundamental       : P/E, market cap, dividend yield, revenue growth, debt
  - Market filter     : US (default), India, UK, Germany, Japan, Hong Kong, Australia, Canada
  - Sector filter
"""

import yfinance as yf
import pandas as pd
import numpy as np
from llm_factory import generate_response, PROMPTS, format_prompt
import json
import re
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from supabase_cache import load_technicals_from_supabase, load_fundamentals_from_supabase


# ── TTL Cache ─────────────────────────────────────────────────────────────────
# Simple in-memory cache with 15-minute TTL to avoid hammering yfinance

_CACHE_TTL_SECONDS = 900  # 15 minutes

class TTLCache:
    def __init__(self):
        self._store: Dict[str, tuple] = {}  # key → (value, expires_at)

    def get(self, key: str) -> Any:
        entry = self._store.get(key)
        if entry and datetime.now() < entry[1]:
            return entry[0]
        return None

    def set(self, key: str, value: Any, ttl: int = _CACHE_TTL_SECONDS):
        self._store[key] = (value, datetime.now() + timedelta(seconds=ttl))

    def clear_expired(self):
        now = datetime.now()
        self._store = {k: v for k, v in self._store.items() if v[1] > now}

_info_cache  = TTLCache()   # ticker → yf.Ticker.info dict
_hist_cache  = TTLCache()   # ticker → technicals dict


# ── Index Constituents ────────────────────────────────────────────────────────

NIFTY_50 = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BEL.NS", "BHARTIARTL.NS",
    "CIPLA.NS", "COALINDIA.NS", "DRREDDY.NS", "EICHERMOT.NS", "ETERNAL.NS",
    "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HINDALCO.NS",
    "HINDUNILVR.NS", "ICICIBANK.NS", "INDIGO.NS", "INFY.NS", "ITC.NS",
    "JIOFIN.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS", "M&M.NS",
    "MARUTI.NS", "MAXHEALTH.NS", "NESTLEIND.NS", "NTPC.NS", "ONGC.NS",
    "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SHRIRAMFIN.NS", "SBIN.NS",
    "SUNPHARMA.NS", "TCS.NS", "TATACONSUM.NS", "TMPV.NS", "TATASTEEL.NS",
    "TECHM.NS", "TITAN.NS", "TRENT.NS", "ULTRACEMCO.NS", "WIPRO.NS",
]

NIFTY_NEXT_50 = [
    "ABB.NS", "ADANIENSOL.NS", "ADANIGREEN.NS", "ADANIPOWER.NS", "AMBUJACEM.NS",
    "BAJAJHLDNG.NS", "BANKBARODA.NS", "BPCL.NS", "BRITANNIA.NS", "BOSCHLTD.NS",
    "CANBK.NS", "CGPOWER.NS", "CHOLAFIN.NS", "CUMMINSIND.NS", "DIVISLAB.NS",
    "DLF.NS", "DMART.NS", "GAIL.NS", "GODREJCP.NS", "HDFCAMC.NS",
    "HAL.NS", "HINDZINC.NS", "HYUNDAI.NS", "INDHOTEL.NS", "IOC.NS",
    "IRFC.NS", "JINDALSTEL.NS", "LODHA.NS", "LTM.NS", "MAZDOCK.NS",
    "MUTHOOTFIN.NS", "PIDILITIND.NS", "PFC.NS", "PNB.NS", "RECLTD.NS",
    "MOTHERSON.NS", "SHREECEM.NS", "SIEMENS.NS", "ENRIN.NS", "SOLARINDS.NS",
    "TATACAP.NS", "TMCV.NS", "TATAPOWER.NS", "TORNTPHARM.NS", "TVSMOTOR.NS",
    "UNIONBK.NS", "UNITDSPR.NS", "VBL.NS", "VEDL.NS", "ZYDUSLIFE.NS",
]

NIFTY_100 = NIFTY_50 + NIFTY_NEXT_50

# Extended NSE Banking / Financial Services universe
NSE_BANKING = list(dict.fromkeys([
    # Large cap banks
    "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS", "KOTAKBANK.NS",
    "INDUSINDBK.NS", "BANKBARODA.NS", "CANBK.NS", "PNB.NS", "BANDHANBNK.NS",
    "IDFCFIRSTB.NS", "FEDERALBNK.NS", "RBLBANK.NS", "YESBANK.NS", "AUBANK.NS",
    # NBFCs & Insurance
    "BAJFINANCE.NS", "BAJAJFINSV.NS", "CHOLAFIN.NS", "SHRIRAMFIN.NS",
    "MUTHOOTFIN.NS", "MANAPPURAM.NS", "LICHSGFIN.NS",
    "HDFCLIFE.NS", "SBILIFE.NS", "ICICIGI.NS", "ICICIPRULI.NS",
    "LICI.NS", "SBICARD.NS", "MFSL.NS",
]))

# Extended NSE IT / Technology universe
NSE_IT = list(dict.fromkeys([
    # Large cap IT (NIFTY 100)
    "TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS", "LTIM.NS",
    "MPHASIS.NS", "PERSISTENT.NS", "OFSS.NS", "NAUKRI.NS",
    # Mid/small cap IT — verified active tickers
    "COFORGE.NS", "KPITTECH.NS", "TATAELXSI.NS", "MASTEK.NS",
    "RATEGAIN.NS", "TANLA.NS", "NEWGEN.NS", "INTELLECT.NS",
    "CYIENT.NS", "SONATSOFTW.NS", "ECLERX.NS",
    "HAPPSTMNDS.NS", "ROUTE.NS", "LTTS.NS",
    "ZENSARTECH.NS", "BSOFT.NS", "NIIT.NS",
]))

SP500_SAMPLE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "UNH", "LLY",
    "JPM", "V", "XOM", "AVGO", "PG", "MA", "HD", "CVX", "MRK", "ABBV",
    "COST", "PEP", "ADBE", "KO", "WMT", "BAC", "CRM", "TMO", "MCD", "CSCO",
    "ACN", "ABT", "NFLX", "LIN", "DHR", "AMD", "TXN", "NEE", "PM", "ORCL",
    "INTC", "QCOM", "HON", "UPS", "IBM", "AMGN", "INTU", "CAT", "GS", "MS",
]

NASDAQ_100_SAMPLE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AVGO", "ADBE", "COST",
    "NFLX", "AMD", "QCOM", "INTU", "CSCO", "AMGN", "TXN", "AMAT", "ISRG", "MU",
    "LRCX", "KLAC", "MRVL", "PANW", "SNPS", "CDNS", "REGN", "ASML", "ABNB", "PYPL",
]

DOW_JONES = [
    "AAPL", "MSFT", "UNH", "GS", "HD", "MCD", "CAT", "V", "AMGN", "TRV",
    "AXP", "IBM", "JPM", "HON", "BA", "CRM", "CVX", "MMM", "WMT", "DIS",
    "NKE", "JNJ", "PG", "MRK", "KO", "INTC", "VZ", "DOW", "CSCO", "WBA",
]

# UK - FTSE 100 Sample
FTSE_100_SAMPLE = [
    "SHEL.L", "AZN.L", "HSBA.L", "ULVR.L", "DGE.L", "BP.L", "GSK.L", "RIO.L",
    "LSEG.L", "NG.L", "REL.L", "BARC.L", "LLOY.L", "VOD.L", "BATS.L",
    "AAL.L", "PRU.L", "BHP.L", "GLEN.L", "IMB.L", "AV.L", "BA.L",
    "RKT.L", "CRH.L", "EXPN.L", "TSCO.L", "NWG.L", "STAN.L", "ANTO.L", "FERG.L",
]

# Germany - DAX 40 Sample
DAX_40_SAMPLE = [
    "SAP.DE", "SIE.DE", "ALV.DE", "AIR.DE", "DTE.DE", "VOW3.DE", "MBG.DE",
    "BMW.DE", "BAS.DE", "MUV2.DE", "EOAN.DE", "DB1.DE", "DBK.DE", "ADS.DE",
    "HEN3.DE", "BEI.DE", "FRE.DE", "RWE.DE", "IFX.DE", "CON.DE",
]

# Japan - Nikkei 225 Sample
NIKKEI_225_SAMPLE = [
    "7203.T", "6758.T", "9984.T", "6861.T", "8306.T", "9433.T", "6902.T",
    "8035.T", "6501.T", "7267.T", "4063.T", "4502.T", "4503.T", "8316.T",
    "8001.T", "6954.T", "6367.T", "4568.T", "9020.T", "4911.T",
]

# Hong Kong - Hang Seng Sample
HANG_SENG_SAMPLE = [
    "0700.HK", "9988.HK", "0941.HK", "1299.HK", "0388.HK", "2318.HK", "3690.HK",
    "1398.HK", "0939.HK", "2020.HK", "1810.HK", "0005.HK", "0011.HK", "0016.HK",
    "0883.HK", "1113.HK", "0001.HK", "0002.HK", "0003.HK", "0027.HK",
]

# Australia - ASX 200 Sample
ASX_200_SAMPLE = [
    "CBA.AX", "BHP.AX", "CSL.AX", "NAB.AX", "WBC.AX", "ANZ.AX", "WES.AX",
    "MQG.AX", "RIO.AX", "WDS.AX", "FMG.AX", "TLS.AX", "WOW.AX", "GMG.AX",
    "TCL.AX", "COL.AX", "QBE.AX", "STO.AX", "WTC.AX", "ALL.AX",
]

# Canada - TSX Sample
TSX_SAMPLE = [
    "SHOP.TO", "RY.TO", "TD.TO", "ENB.TO", "CNQ.TO", "BMO.TO", "BNS.TO",
    "CNR.TO", "TRI.TO", "CP.TO", "SU.TO", "CM.TO", "WCN.TO", "MFC.TO",
    "ABX.TO", "BCE.TO", "T.TO", "NTR.TO", "IMO.TO", "CVE.TO",
]

# Map index names to their constituent lists
INDEX_MAP = {
    "nifty 50": NIFTY_50,
    "nifty50": NIFTY_50,
    "nifty_50": NIFTY_50,
    "nifty next 50": NIFTY_NEXT_50,
    "niftynext50": NIFTY_NEXT_50,
    "nifty_next_50": NIFTY_NEXT_50,
    "nifty 100": NIFTY_100,
    "nifty100": NIFTY_100,
    "s&p 500": SP500_SAMPLE,
    "sp500": SP500_SAMPLE,
    "s&p500": SP500_SAMPLE,
    "nasdaq 100": NASDAQ_100_SAMPLE,
    "nasdaq100": NASDAQ_100_SAMPLE,
    "dow jones": DOW_JONES,
    "dow": DOW_JONES,
    "djia": DOW_JONES,
    "ftse 100": FTSE_100_SAMPLE,
    "ftse100": FTSE_100_SAMPLE,
    "ftse": FTSE_100_SAMPLE,
    "dax 40": DAX_40_SAMPLE,
    "dax40": DAX_40_SAMPLE,
    "dax": DAX_40_SAMPLE,
    "nikkei 225": NIKKEI_225_SAMPLE,
    "nikkei225": NIKKEI_225_SAMPLE,
    "nikkei": NIKKEI_225_SAMPLE,
    "hang seng": HANG_SENG_SAMPLE,
    "hangseng": HANG_SENG_SAMPLE,
    "hsi": HANG_SENG_SAMPLE,
    "asx 200": ASX_200_SAMPLE,
    "asx200": ASX_200_SAMPLE,
    "asx": ASX_200_SAMPLE,
    "tsx": TSX_SAMPLE,
}

# Full universe - curated cross-market sample (defaults to US if no market specified)
FULL_UNIVERSE = list(dict.fromkeys(
    SP500_SAMPLE + NASDAQ_100_SAMPLE + DOW_JONES
))


# ── Static Sector Map (avoids API calls for pre-filtering) ───────────────────
# Maps ticker → yfinance sector string for known universe stocks

NSE_SECTOR_MAP: Dict[str, str] = {
    # Technology
    "TCS.NS": "Technology", "INFY.NS": "Technology", "HCLTECH.NS": "Technology",
    "WIPRO.NS": "Technology", "TECHM.NS": "Technology", "LTIM.NS": "Technology",
    "MPHASIS.NS": "Technology", "PERSISTENT.NS": "Technology", "OFSS.NS": "Technology",
    "NAUKRI.NS": "Technology", "COFORGE.NS": "Technology", "KPITTECH.NS": "Technology",
    "TATAELXSI.NS": "Technology", "MASTEK.NS": "Technology", "RATEGAIN.NS": "Technology",
    "TANLA.NS": "Technology", "NEWGEN.NS": "Technology", "INTELLECT.NS": "Technology",
    "CYIENT.NS": "Technology", "SONATSOFTW.NS": "Technology", "ECLERX.NS": "Technology",
    "HAPPSTMNDS.NS": "Technology", "ROUTE.NS": "Technology", "LTTS.NS": "Technology",
    "ZENSARTECH.NS": "Technology", "BSOFT.NS": "Technology", "NIIT.NS": "Technology",
    # Finance / Banking
    "HDFCBANK.NS": "Financial Services", "ICICIBANK.NS": "Financial Services",
    "AXISBANK.NS": "Financial Services", "KOTAKBANK.NS": "Financial Services",
    "SBIN.NS": "Financial Services", "INDUSINDBK.NS": "Financial Services",
    "BAJFINANCE.NS": "Financial Services", "BAJAJFINSV.NS": "Financial Services",
    "HDFCLIFE.NS": "Financial Services", "SBILIFE.NS": "Financial Services",
    "ICICIGI.NS": "Financial Services", "ICICIPRULI.NS": "Financial Services",
    "BANDHANBNK.NS": "Financial Services", "BANKBARODA.NS": "Financial Services",
    "CANBK.NS": "Financial Services", "CHOLAFIN.NS": "Financial Services",
    "IDFCFIRSTB.NS": "Financial Services", "PNB.NS": "Financial Services",
    "SBICARD.NS": "Financial Services", "MFSL.NS": "Financial Services",
    "SHRIRAMFIN.NS": "Financial Services", "LICI.NS": "Financial Services",
    "FEDERALBNK.NS": "Financial Services", "RBLBANK.NS": "Financial Services",
    "YESBANK.NS": "Financial Services", "AUBANK.NS": "Financial Services",
    "MUTHOOTFIN.NS": "Financial Services", "MANAPPURAM.NS": "Financial Services",
    "LICHSGFIN.NS": "Financial Services",
    # Healthcare / Pharma
    "SUNPHARMA.NS": "Healthcare", "DRREDDY.NS": "Healthcare", "CIPLA.NS": "Healthcare",
    "DIVISLAB.NS": "Healthcare", "APOLLOHOSP.NS": "Healthcare", "LUPIN.NS": "Healthcare",
    "AUROPHARMA.NS": "Healthcare", "BIOCON.NS": "Healthcare", "TORNTPHARM.NS": "Healthcare",
    # Energy
    "RELIANCE.NS": "Energy", "ONGC.NS": "Energy", "BPCL.NS": "Energy",
    "NTPC.NS": "Energy", "POWERGRID.NS": "Energy", "TATAPOWER.NS": "Energy",
    "GAIL.NS": "Energy", "IOC.NS": "Energy", "COALINDIA.NS": "Energy",
    "ADANIGREEN.NS": "Energy", "PETRONET.NS": "Energy",
    # Consumer
    "HINDUNILVR.NS": "Consumer", "ITC.NS": "Consumer", "NESTLEIND.NS": "Consumer",
    "BRITANNIA.NS": "Consumer", "DABUR.NS": "Consumer", "MARICO.NS": "Consumer",
    "COLPAL.NS": "Consumer", "GODREJCP.NS": "Consumer", "TATACONSUM.NS": "Consumer",
    "JUBLFOOD.NS": "Consumer", "UBL.NS": "Consumer", "PAGEIND.NS": "Consumer",
    # Industrial / Auto
    "LT.NS": "Industrial", "SIEMENS.NS": "Industrial", "ABB.NS": "Industrial",
    "BOSCHLTD.NS": "Industrial", "HAVELLS.NS": "Industrial", "MOTHERSON.NS": "Industrial",
    "BAJAJ-AUTO.NS": "Industrial", "HEROMOTOCO.NS": "Industrial", "MARUTI.NS": "Industrial",
    "EICHERMOT.NS": "Industrial", "M&M.NS": "Industrial", "TATASTEEL.NS": "Industrial",
    "JSWSTEEL.NS": "Industrial", "HINDALCO.NS": "Industrial", "VEDL.NS": "Industrial",
    "NMDC.NS": "Industrial", "JINDALSTEL.NS": "Industrial", "MRF.NS": "Industrial",
    # Real Estate / Other
    "DLF.NS": "Real Estate", "INDHOTEL.NS": "Consumer", "IRCTC.NS": "Consumer",
    "TITAN.NS": "Consumer", "ASIANPAINT.NS": "Consumer", "PIDILITIND.NS": "Industrial",
    "BERGEPAINT.NS": "Consumer", "ULTRACEMCO.NS": "Industrial", "AMBUJACEM.NS": "Industrial",
    "GRASIM.NS": "Industrial", "ADANIENT.NS": "Industrial", "ADANIPORTS.NS": "Industrial",
    "IGL.NS": "Energy", "IDEA.NS": "Technology", "BHARTIARTL.NS": "Technology",
    "PIIND.NS": "Healthcare", "HDFCLIFE.NS": "Finance",
}

SECTOR_ALIASES = {
    "technology": ["Technology"],
    "tech": ["Technology"],
    "it": ["Technology"],
    "finance": ["Financial Services", "Finance"],
    "financial": ["Financial Services", "Finance"],
    "banking": ["Financial Services", "Finance"],
    "bank": ["Financial Services", "Finance"],
    "healthcare": ["Healthcare", "Health Care"],
    "pharma": ["Healthcare", "Health Care"],
    "energy": ["Energy"],
    "oil": ["Energy"],
    "consumer": ["Consumer Cyclical", "Consumer Defensive", "Consumer"],
    "fmcg": ["Consumer Cyclical", "Consumer Defensive", "Consumer"],
    "industrial": ["Industrials", "Industrial"],
    "realestate": ["Real Estate"],
}

def compute_technicals(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Fetch 2 years of daily price history and compute:
      - SMA 20, 50, 200
      - RSI 14
      - Price vs 52-week high/low (%)
    Returns None on failure. Uses cache to avoid repeat fetches.
    2y period ensures SMA200 always has sufficient data (~500 bars vs 200 needed).
    """
    cached = _hist_cache.get(ticker)
    if cached is not None:
        return cached

    try:
        hist = yf.Ticker(ticker).history(period="2y")
        if hist.empty or len(hist) < 21:
            return None

        result = _compute_technicals_from_hist(hist)
        _hist_cache.set(ticker, result)
        return result
    except Exception as e:
        print(f"[Screener] Technicals error for {ticker}: {e}")
        return None


def batch_compute_technicals(tickers: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Three-layer technicals resolution (fastest → slowest):
      1. In-process TTL cache  — zero I/O
      2. Supabase precomputed  — single DB query for all tickers
      3. yfinance batch fetch  — one API call for remaining misses

    This means under normal operation (precompute job running every 15 min)
    user requests never hit yfinance for Nifty 100 technicals.
    """
    results: Dict[str, Optional[Dict[str, Any]]] = {}
    to_fetch: List[str] = []

    # ── Layer 1: in-process TTL cache ─────────────────────────────────────────
    for t in tickers:
        cached = _hist_cache.get(t)
        if cached is not None:
            results[t] = cached
        else:
            to_fetch.append(t)

    if not to_fetch:
        return results

    # ── Layer 2: Supabase precomputed technicals ───────────────────────────────
    supabase_data = load_technicals_from_supabase(to_fetch)
    still_missing: List[str] = []

    for ticker in to_fetch:
        if ticker in supabase_data:
            tech = supabase_data[ticker]
            _hist_cache.set(ticker, tech)   # warm the in-process cache
            results[ticker] = tech
        else:
            still_missing.append(ticker)

    if not still_missing:
        return results

    # ── Layer 3: yfinance batch download (only for cache/DB misses) ────────────
    print(f"[Screener] Batch downloading history for {len(still_missing)} tickers (Supabase miss)...")
    try:
        raw = yf.download(
            still_missing,
            period="2y",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )

        for ticker in still_missing:
            try:
                if len(still_missing) == 1:
                    hist = raw
                else:
                    hist = raw[ticker] if ticker in raw.columns.get_level_values(0) else pd.DataFrame()

                if hist.empty or "Close" not in hist.columns or len(hist) < 21:
                    results[ticker] = None
                    continue

                tech = _compute_technicals_from_hist(hist)
                _hist_cache.set(ticker, tech)
                results[ticker] = tech
            except Exception as e:
                print(f"[Screener] Technicals parse error for {ticker}: {e}")
                results[ticker] = None

    except Exception as e:
        print(f"[Screener] Batch download failed: {e}, falling back to individual fetches")
        for ticker in still_missing:
            results[ticker] = compute_technicals(ticker)

    return results


def _compute_technicals_from_hist(hist: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """Compute technical indicators from a price history DataFrame."""
    def safe_float(value, default=None):
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return default
        try:
            v = float(value)
            return None if np.isnan(v) else v
        except (ValueError, TypeError):
            return default

    close = hist["Close"]
    current = safe_float(close.iloc[-1])
    if current is None:
        return None

    def safe_sma(series, window):
        try:
            # Use min_periods=window to require full window; with 2y history this is always satisfied for SMA200
            val = series.rolling(window, min_periods=window).mean().iloc[-1]
            return safe_float(val)
        except:
            return None

    def safe_ema(series, span):
        try:
            return safe_float(series.ewm(span=span, adjust=False).mean().iloc[-1])
        except:
            return None

    # Pre-compute common SMA/EMA periods — plus store the close series for dynamic lookup
    sma9   = safe_sma(close, 9)
    sma20  = safe_sma(close, 20)
    sma21  = safe_sma(close, 21)
    sma50  = safe_sma(close, 50)
    sma200 = safe_sma(close, 200)
    ema8   = safe_ema(close, 8)
    ema9   = safe_ema(close, 9)
    ema20  = safe_ema(close, 20)
    ema21  = safe_ema(close, 21)
    ema50  = safe_ema(close, 50)

    try:
        delta = close.diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta.clip(upper=0)).rolling(14).mean()
        rs    = gain / loss.replace(0, np.nan)
        rsi   = safe_float((100 - 100 / (1 + rs)).iloc[-1])
    except:
        rsi = None

    # MACD (12/26/9)
    try:
        ema12       = close.ewm(span=12, adjust=False).mean()
        ema26       = close.ewm(span=26, adjust=False).mean()
        macd_line   = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd        = safe_float(macd_line.iloc[-1])
        macd_signal = safe_float(signal_line.iloc[-1])
        macd_hist   = safe_float((macd_line - signal_line).iloc[-1])
    except:
        macd = macd_signal = macd_hist = None

    # Bollinger Bands (20, 2σ)
    try:
        bb_mid_s = close.rolling(20).mean()
        bb_std   = close.rolling(20).std()
        bb_upper = safe_float((bb_mid_s + 2 * bb_std).iloc[-1])
        bb_lower = safe_float((bb_mid_s - 2 * bb_std).iloc[-1])
        bb_mid_v = safe_float(bb_mid_s.iloc[-1])
    except:
        bb_upper = bb_lower = bb_mid_v = None

    # Volume spike: current volume vs 20-day avg volume
    try:
        vol_series = hist["Volume"]
        avg_vol20  = safe_float(vol_series.rolling(20).mean().iloc[-1])
        cur_vol    = safe_float(vol_series.iloc[-1])
        vol_ratio  = (cur_vol / avg_vol20) if avg_vol20 and avg_vol20 > 0 else None
    except:
        avg_vol20 = vol_ratio = None

    try:
        high52 = safe_float(close.rolling(252).max().iloc[-1])
        low52  = safe_float(close.rolling(252).min().iloc[-1])
        pct_from_high = ((current - high52) / high52 * 100) if high52 else None
        pct_from_low  = ((current - low52)  / low52  * 100) if low52  else None
    except:
        high52 = low52 = pct_from_high = pct_from_low = None

    # ── Stochastic RSI (14, 14, 3, 3) ────────────────────────────────────────
    # StochRSI = (RSI - min(RSI,14)) / (max(RSI,14) - min(RSI,14))
    # %K = 3-period SMA of StochRSI;  %D = 3-period SMA of %K
    try:
        delta     = close.diff()
        gain      = delta.clip(lower=0).rolling(14).mean()
        loss      = (-delta.clip(upper=0)).rolling(14).mean()
        rs        = gain / loss.replace(0, np.nan)
        rsi_series = 100 - 100 / (1 + rs)
        rsi_min   = rsi_series.rolling(14).min()
        rsi_max   = rsi_series.rolling(14).max()
        rsi_range = (rsi_max - rsi_min).replace(0, np.nan)
        stoch_rsi  = (rsi_series - rsi_min) / rsi_range
        stoch_k    = safe_float(stoch_rsi.rolling(3).mean().iloc[-1])
        stoch_d    = safe_float(stoch_rsi.rolling(3).mean().rolling(3).mean().iloc[-1])
    except:
        stoch_k = stoch_d = None

    # ── Pivot Points (based on previous day's High, Low, Close) ──────────────
    try:
        # Squeeze out any MultiIndex column (happens with single-ticker batch download)
        def _scalar(series, idx):
            val = series.iloc[idx]
            if hasattr(val, '__len__'):   # Series/array — take first element
                val = val.iloc[0] if hasattr(val, 'iloc') else float(val[0])
            return safe_float(val)

        prev_high  = _scalar(hist["High"],  -2)
        prev_low   = _scalar(hist["Low"],   -2)
        prev_close = _scalar(hist["Close"], -2)
    except Exception:
        prev_high = prev_low = prev_close = None

    # Guard: all three must be valid non-zero numbers
    _pivots_ok = (
        prev_high  is not None and prev_high  > 0 and
        prev_low   is not None and prev_low   > 0 and
        prev_close is not None and prev_close > 0
    )

    # Standard Pivot Points
    std_pp = std_r1 = std_s1 = std_r2 = std_s2 = std_r3 = std_s3 = None
    if _pivots_ok:
        try:
            std_pp = (prev_high + prev_low + prev_close) / 3
            std_r1 = (2 * std_pp) - prev_low
            std_s1 = (2 * std_pp) - prev_high
            std_r2 = std_pp + (prev_high - prev_low)
            std_s2 = std_pp - (prev_high - prev_low)
            std_r3 = prev_high + 2 * (std_pp - prev_low)
            std_s3 = prev_low  - 2 * (prev_high - std_pp)
            std_pp, std_r1, std_s1 = safe_float(std_pp), safe_float(std_r1), safe_float(std_s1)
            std_r2, std_s2         = safe_float(std_r2),  safe_float(std_s2)
            std_r3, std_s3         = safe_float(std_r3),  safe_float(std_s3)
        except Exception:
            pass

    # CPR — Central Pivot Range (TC, PP, BC)
    cpr_pp = cpr_tc = cpr_bc = None
    if _pivots_ok:
        try:
            cpr_pp = (prev_high + prev_low + prev_close) / 3
            cpr_bc = (prev_high + prev_low) / 2
            cpr_tc = cpr_pp + (cpr_pp - cpr_bc)
            cpr_pp, cpr_tc, cpr_bc = safe_float(cpr_pp), safe_float(cpr_tc), safe_float(cpr_bc)
        except Exception:
            pass

    # Camarilla Pivot Points
    cam_h1 = cam_h2 = cam_h3 = cam_h4 = None
    cam_l1 = cam_l2 = cam_l3 = cam_l4 = None
    if _pivots_ok:
        try:
            rng    = prev_high - prev_low
            cam_h1 = safe_float(prev_close + rng * 1.1 / 12)
            cam_h2 = safe_float(prev_close + rng * 1.1 / 6)
            cam_h3 = safe_float(prev_close + rng * 1.1 / 4)
            cam_h4 = safe_float(prev_close + rng * 1.1 / 2)
            cam_l1 = safe_float(prev_close - rng * 1.1 / 12)
            cam_l2 = safe_float(prev_close - rng * 1.1 / 6)
            cam_l3 = safe_float(prev_close - rng * 1.1 / 4)
            cam_l4 = safe_float(prev_close - rng * 1.1 / 2)
        except Exception:
            pass

    result = {
        "sma9": sma9, "sma20": sma20, "sma21": sma21, "sma50": sma50, "sma200": sma200,
        "ema8": ema8, "ema9": ema9, "ema20": ema20, "ema21": ema21, "ema50": ema50,
        "rsi": rsi,
        "stoch_k": stoch_k, "stoch_d": stoch_d,
        "macd": macd, "macd_signal": macd_signal, "macd_hist": macd_hist,
        "bb_upper": bb_upper, "bb_lower": bb_lower, "bb_mid": bb_mid_v,
        "avg_vol20": avg_vol20, "vol_ratio": vol_ratio,
        "high52": high52, "low52": low52,
        "pct_from_52w_high": pct_from_high, "pct_from_52w_low": pct_from_low,
        # Standard pivots
        "std_pp": std_pp,
        "std_r1": std_r1, "std_r2": std_r2, "std_r3": std_r3,
        "std_s1": std_s1, "std_s2": std_s2, "std_s3": std_s3,
        # CPR
        "cpr_pp": cpr_pp, "cpr_tc": cpr_tc, "cpr_bc": cpr_bc,
        # Camarilla
        "cam_h1": cam_h1, "cam_h2": cam_h2, "cam_h3": cam_h3, "cam_h4": cam_h4,
        "cam_l1": cam_l1, "cam_l2": cam_l2, "cam_l3": cam_l3, "cam_l4": cam_l4,
        "_hist_close": close,
        "_hist_df": hist,
    }
    return result


# ── Fundamental Data Fetch ────────────────────────────────────────────────────

def fetch_stock_data(ticker: str, prefetched_tech: Optional[Dict] = None, prefetched_fundamentals: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch fundamental + technical data for a single ticker.
    - prefetched_tech: from batch_compute_technicals (Supabase or yfinance batch)
    - prefetched_fundamentals: slow fields from Supabase (P/E, sector, market cap, etc.)
      When provided, only live price/volume are fetched from yfinance.
    """
    def safe_float(value, default=0):
        if value is None:
            return default
        try:
            v = float(value)
            return default if (np.isnan(v) or pd.isna(v)) else v
        except (ValueError, TypeError):
            return default

    try:
        # ── Live price data (always fresh from yfinance) ───────────────────────
        info = _info_cache.get(ticker)
        if info is None:
            info = yf.Ticker(ticker).info
            _info_cache.set(ticker, info)

        print(f"[Screener] Fetching {ticker}: currentPrice={info.get('currentPrice')}, regularMarketPrice={info.get('regularMarketPrice')}")

        current_price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
        if not current_price or current_price <= 0:
            print(f"[Screener] {ticker}: No valid price found")
            return None

        prev_close = info.get("previousClose") or current_price
        change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close and prev_close > 0 else 0

        volume = info.get("volume", 0) or 0
        if volume >= 1e9:   volume_str = f"{volume/1e9:.2f}B"
        elif volume >= 1e6: volume_str = f"{volume/1e6:.2f}M"
        elif volume >= 1e3: volume_str = f"{volume/1e3:.2f}K"
        else:               volume_str = str(volume)

        ticker_suffix = ticker.split(".")[-1] if "." in ticker else ""
        currency_map = {
            "NS": "₹", "L": "£", "DE": "€", "T": "¥",
            "HK": "HK$", "AX": "A$", "TO": "C$",
        }
        currency_symbol = currency_map.get(ticker_suffix, "$")

        # ── Slow fundamentals: Supabase first, yfinance info as fallback ────────
        fund = prefetched_fundamentals or {}
        name           = fund.get("name")           or info.get("longName", ticker)
        sector         = fund.get("sector")         or info.get("sector", "Unknown")
        industry       = fund.get("industry")       or info.get("industry", "Unknown")
        market_cap     = fund.get("market_cap")     or info.get("marketCap", 0) or 0
        trailing_pe    = fund.get("trailing_pe")    if fund.get("trailing_pe") is not None else safe_float(info.get("trailingPE"), -1)
        forward_pe     = fund.get("forward_pe")     if fund.get("forward_pe")  is not None else safe_float(info.get("forwardPE"), -1)
        dividend_yield = fund.get("dividend_yield") if fund.get("dividend_yield") is not None else safe_float((info.get("dividendYield") or 0) * 100)
        beta           = fund.get("beta")           if fund.get("beta")          is not None else safe_float(info.get("beta"))
        revenue_growth = fund.get("revenue_growth") if fund.get("revenue_growth") is not None else safe_float((info.get("revenueGrowth") or 0) * 100)
        debt_to_equity = fund.get("debt_to_equity") if fund.get("debt_to_equity") is not None else safe_float(info.get("debtToEquity"))

        if market_cap >= 1e12:
            market_cap_str = f"{currency_symbol}{market_cap/1e12:.2f}T"
        elif market_cap >= 1e9:
            market_cap_str = f"{currency_symbol}{market_cap/1e9:.2f}B"
        elif market_cap >= 1e6:
            market_cap_str = f"{currency_symbol}{market_cap/1e6:.2f}M"
        else:
            market_cap_str = f"{currency_symbol}{market_cap:,.0f}"

        # ── Technicals ─────────────────────────────────────────────────────────
        tech = prefetched_tech if prefetched_tech is not None else (compute_technicals(ticker) or {})

        return {
            "ticker": ticker,
            "name": name,
            "price": safe_float(current_price),
            "currency": currency_symbol,
            "change_pct": safe_float(change_pct),
            "market_cap": market_cap,
            "market_cap_str": market_cap_str,
            "pe_ratio": safe_float(trailing_pe, -1),
            "forward_pe": safe_float(forward_pe, -1),
            "volume": volume,
            "volume_str": volume_str,
            "sector": sector,
            "industry": industry,
            "dividend_yield": safe_float(dividend_yield),
            "beta": safe_float(beta),
            "revenue_growth": safe_float(revenue_growth),
            "debt_to_equity": safe_float(debt_to_equity),
            "sma9":   safe_float(tech.get("sma9")),
            "sma20":  safe_float(tech.get("sma20")),
            "sma21":  safe_float(tech.get("sma21")),
            "sma50":  safe_float(tech.get("sma50")),
            "sma200": safe_float(tech.get("sma200")),
            "ema8":   safe_float(tech.get("ema8")),
            "ema9":   safe_float(tech.get("ema9")),
            "ema20":  safe_float(tech.get("ema20")),
            "ema21":  safe_float(tech.get("ema21")),
            "ema50":  safe_float(tech.get("ema50")),
            **{k: safe_float(v) for k, v in tech.items()
               if re.match(r"(ema|sma)\d+$", k) and k not in ("sma9","sma20","sma21","sma50","sma200","ema8","ema9","ema20","ema21","ema50")},
            "rsi":    safe_float(tech.get("rsi")),
            "macd":        safe_float(tech.get("macd")),
            "macd_signal": safe_float(tech.get("macd_signal")),
            "macd_hist":   safe_float(tech.get("macd_hist")),
            "bb_upper": safe_float(tech.get("bb_upper")),
            "bb_lower": safe_float(tech.get("bb_lower")),
            "bb_mid":   safe_float(tech.get("bb_mid")),
            "vol_ratio": safe_float(tech.get("vol_ratio")),
            "high52": safe_float(tech.get("high52")),
            "low52":  safe_float(tech.get("low52")),
            "pct_from_52w_high": safe_float(tech.get("pct_from_52w_high")),
            "pct_from_52w_low":  safe_float(tech.get("pct_from_52w_low")),
        }
    except Exception as e:
        print(f"[Screener] Error fetching {ticker}: {e}")
        return None


# ── Criteria Matching ─────────────────────────────────────────────────────────

def apply_criteria(stock: Dict[str, Any], criteria: Dict[str, Any]) -> tuple[bool, str]:
    """
    Returns (matches, reason_string).
    Checks both fundamental and technical criteria.
    """
    reasons = []

    # ── Market filter ──────────────────────────────────────────────────────────
    if criteria.get("market"):
        market = criteria["market"].lower()
        ticker_suffix = stock["ticker"].split(".")[-1] if "." in stock["ticker"] else ""
        
        # Check market match based on ticker suffix
        if market in ["india", "indian", "nse"] and ticker_suffix != "NS":
            return False, ""
        if market in ["us", "usa", "american"] and ticker_suffix in ["NS", "L", "DE", "T", "HK", "AX", "TO"]:
            return False, ""
        if market in ["uk", "britain", "british", "london"] and ticker_suffix != "L":
            return False, ""
        if market in ["germany", "german", "deutschland"] and ticker_suffix != "DE":
            return False, ""
        if market in ["japan", "japanese", "tokyo"] and ticker_suffix != "T":
            return False, ""
        if market in ["hong kong", "hongkong", "hk"] and ticker_suffix != "HK":
            return False, ""
        if market in ["australia", "australian", "aussie"] and ticker_suffix != "AX":
            return False, ""
        if market in ["canada", "canadian"] and ticker_suffix != "TO":
            return False, ""
        
        # Add market label to reasons
        market_labels = {
            "NS": "NSE (India)", "L": "LSE (UK)", "DE": "XETRA (Germany)",
            "T": "TSE (Japan)", "HK": "HKEX (Hong Kong)", "AX": "ASX (Australia)",
            "TO": "TSX (Canada)"
        }
        reasons.append(market_labels.get(ticker_suffix, "US Market"))

    # ── Sector filter ──────────────────────────────────────────────────────────
    if criteria.get("sector"):
        criteria_sector = criteria["sector"].lower()
        allowed = SECTOR_ALIASES.get(criteria_sector, [criteria["sector"]])
        if stock["sector"].lower() not in [s.lower() for s in allowed]:
            return False, ""
        reasons.append(f"Sector: {stock['sector']}")

    # ── Fundamental filters ────────────────────────────────────────────────────
    if criteria.get("min_market_cap"):
        if stock["market_cap"] < criteria["min_market_cap"]:
            return False, ""
        reasons.append(f"Mkt cap > ${criteria['min_market_cap']/1e9:.0f}B")

    if criteria.get("max_market_cap"):
        if stock["market_cap"] > criteria["max_market_cap"]:
            return False, ""
        reasons.append(f"Mkt cap < ${criteria['max_market_cap']/1e9:.0f}B")

    if criteria.get("max_pe"):
        if stock["pe_ratio"] <= 0 or stock["pe_ratio"] > criteria["max_pe"]:
            return False, ""
        reasons.append(f"P/E < {criteria['max_pe']}")

    if criteria.get("min_pe"):
        if stock["pe_ratio"] <= 0 or stock["pe_ratio"] < criteria["min_pe"]:
            return False, ""
        reasons.append(f"P/E > {criteria['min_pe']}")

    if criteria.get("min_dividend_yield"):
        if stock["dividend_yield"] < criteria["min_dividend_yield"]:
            return False, ""
        reasons.append(f"Div yield > {criteria['min_dividend_yield']}%")

    if criteria.get("min_change_pct") is not None:
        if stock["change_pct"] < criteria["min_change_pct"]:
            return False, ""
        reasons.append(f"Change > {criteria['min_change_pct']}%")

    if criteria.get("max_change_pct") is not None:
        if stock["change_pct"] > criteria["max_change_pct"]:
            return False, ""
        reasons.append(f"Change < {criteria['max_change_pct']}%")

    if criteria.get("min_volume"):
        if stock["volume"] < criteria["min_volume"]:
            return False, ""
        reasons.append("High volume")

    if criteria.get("min_revenue_growth"):
        if stock["revenue_growth"] < criteria["min_revenue_growth"]:
            return False, ""
        reasons.append(f"Rev growth > {criteria['min_revenue_growth']}%")

    if criteria.get("max_debt_to_equity"):
        if stock["debt_to_equity"] > criteria["max_debt_to_equity"]:
            return False, ""
        reasons.append("Low debt")

    # ── Technical filters ──────────────────────────────────────────────────────

    # Price vs SMA — handled by dynamic loop below (price_vs_sma20, price_vs_sma50, price_vs_sma200, etc.)

    # RSI filters
    if criteria.get("max_rsi"):
        rsi = stock.get("rsi")
        if rsi is None or rsi <= 0 or rsi > criteria["max_rsi"]:
            return False, ""
        reasons.append(f"RSI < {criteria['max_rsi']} ({rsi:.1f})")

    if criteria.get("min_rsi"):
        rsi = stock.get("rsi")
        if rsi is None or rsi <= 0 or rsi < criteria["min_rsi"]:
            return False, ""
        reasons.append(f"RSI > {criteria['min_rsi']} ({rsi:.1f})")

    # 52-week proximity
    if criteria.get("near_52w_low"):
        pct = stock.get("pct_from_52w_low")
        if pct is None or pct > 10:   # within 10% of 52w low
            return False, ""
        reasons.append(f"Near 52w low ({pct:.1f}% above)")

    if criteria.get("near_52w_high"):
        pct = stock.get("pct_from_52w_high")
        if pct is None or pct < -10:  # within 10% of 52w high
            return False, ""
        reasons.append(f"Near 52w high ({pct:.1f}% below)")

    # EMA filters — dynamic: handles price_vs_ema8, price_vs_ema20, price_vs_ema50, price_vs_ema_N
    for key, val in list(criteria.items()):
        m = re.match(r"price_vs_ema_?(\d+)$", key)
        if not m:
            continue
        rel = val
        if not rel:  # Skip if criteria value is null/empty
            continue
        period = int(m.group(1))
        ema_val = stock.get(f"ema{period}")
        if ema_val is None or ema_val <= 0:
            return False, ""  # Reject stocks without required EMA data
        rel = rel.lower()
        if rel == "below" and stock["price"] >= ema_val:
            return False, ""
        if rel == "above" and stock["price"] <= ema_val:
            return False, ""
        cur = stock.get("currency", "")
        reasons.append(f"Price {rel} {period}-EMA ({cur}{ema_val:.2f})")

    # SMA filters — dynamic: handles price_vs_sma20, price_vs_sma50, price_vs_sma_N
    for key, val in list(criteria.items()):
        m = re.match(r"price_vs_sma_?(\d+)$", key)
        if not m:
            continue
        rel = val
        if not rel:  # Skip if criteria value is null/empty
            continue
        period = int(m.group(1))
        sma_val = stock.get(f"sma{period}")
        if sma_val is None or sma_val <= 0:
            return False, ""  # Reject stocks without required SMA data
        rel = rel.lower()
        if rel == "below" and stock["price"] >= sma_val:
            return False, ""
        if rel == "above" and stock["price"] <= sma_val:
            return False, ""
        cur = stock.get("currency", "")
        reasons.append(f"Price {rel} {period}-SMA ({cur}{sma_val:.2f})")

    # MACD filters
    if criteria.get("macd_bullish"):
        macd = stock.get("macd")
        sig  = stock.get("macd_signal")
        if macd is None or sig is None or macd <= sig:
            return False, ""
        reasons.append(f"MACD bullish ({macd:.2f} > signal {sig:.2f})")

    if criteria.get("macd_bearish"):
        macd = stock.get("macd")
        sig  = stock.get("macd_signal")
        if macd is None or sig is None or macd >= sig:
            return False, ""
        reasons.append(f"MACD bearish ({macd:.2f} < signal {sig:.2f})")

    # Bollinger Band filters
    if criteria.get("bb_squeeze"):
        bb_upper = stock.get("bb_upper")
        bb_lower = stock.get("bb_lower")
        bb_mid   = stock.get("bb_mid")
        if bb_upper is None or bb_lower is None or bb_mid is None or bb_mid <= 0:
            return False, ""
        band_width_pct = (bb_upper - bb_lower) / bb_mid * 100
        if band_width_pct > 10:
            return False, ""
        reasons.append(f"BB squeeze (width {band_width_pct:.1f}%)")

    if criteria.get("price_above_bb_upper"):
        bb_upper = stock.get("bb_upper")
        if bb_upper is None or stock["price"] <= bb_upper:
            return False, ""
        reasons.append(f"Price above BB upper ({bb_upper:.2f})")

    if criteria.get("price_below_bb_lower"):
        bb_lower = stock.get("bb_lower")
        if bb_lower is None or stock["price"] >= bb_lower:
            return False, ""
        reasons.append(f"Price below BB lower ({bb_lower:.2f})")

    # Volume spike
    if criteria.get("volume_spike"):
        vol_ratio = stock.get("vol_ratio")
        threshold = criteria["volume_spike"] if isinstance(criteria["volume_spike"], (int, float)) else 2.0
        if vol_ratio is None or vol_ratio < threshold:
            return False, ""
        reasons.append(f"Volume spike {vol_ratio:.1f}x avg")

    # Beta filters
    if criteria.get("max_beta"):
        beta = stock.get("beta")
        if beta is None or beta <= 0 or beta > criteria["max_beta"]:
            return False, ""
        reasons.append(f"Beta < {criteria['max_beta']} ({beta:.2f})")

    if criteria.get("min_beta"):
        beta = stock.get("beta")
        if beta is None or beta < criteria["min_beta"]:
            return False, ""
        reasons.append(f"Beta > {criteria['min_beta']} ({beta:.2f})")

    if not reasons:
        reasons.append("Matches criteria")

    return True, " • ".join(reasons)


# ── Custom Filter Executor ────────────────────────────────────────────────────

def execute_custom_filter(filter_code: str, hist: pd.DataFrame) -> bool:
    """
    Safely execute an LLM-generated custom_filter(df, np, pd) -> bool.
    Runs in a restricted namespace with only numpy and pandas available.
    Returns False on any error.
    """
    if not filter_code or not isinstance(filter_code, str):
        return True  # no custom filter = pass

    # Reject obviously dangerous patterns
    forbidden = ["import ", "__import__", "open(", "exec(", "eval(", "compile(",
                 "os.", "sys.", "subprocess", "socket", "requests", "urllib"]
    code_lower = filter_code.lower()
    if any(f in code_lower for f in forbidden):
        print("[Screener] Custom filter rejected: forbidden pattern detected")
        return False

    try:
        namespace = {"np": np, "pd": pd}
        exec(compile(filter_code, "<custom_filter>", "exec"), namespace)  # noqa: S102
        fn = namespace.get("custom_filter")
        if not callable(fn):
            return True
        result = fn(hist.copy(), np, pd)
        return bool(result)
    except Exception as e:
        print(f"[Screener] Custom filter error: {e}")
        return False


# ── LLM Criteria Parser ───────────────────────────────────────────────────────

def parse_screening_criteria(query: str) -> Dict[str, Any]:
    prompt = format_prompt(PROMPTS["screener_parse_prompt"], query=query)
    raw = generate_response(prompt, use_search=False).strip()
    
    print(f"[Screener] LLM raw response: {raw}")
    
    try:
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            print(f"[Screener] Parsed JSON: {result}")
            
            # Map new filters/universe schema to flat criteria_dict & criteria list expected by backend
            if "criteria_dict" in result:
                return result
                
            criteria_dict = {}
            criteria_list = []
            
            universe = result.get("universe", "")
            if universe:
                if universe in ("nifty50", "nifty 50", "nifty_50"):
                    criteria_dict["index"] = "nifty 50"
                    criteria_list.append("Nifty 50 index")
                elif universe in ("nifty100", "nifty 100", "nifty_100"):
                    criteria_dict["index"] = "nifty 100"
                    criteria_list.append("Nifty 100 index")
                elif universe in ("nifty500", "nifty 500", "nifty_500"):
                    criteria_dict["index"] = "nifty 500"
                    criteria_list.append("Nifty 500 index")
                elif universe in ("sp500", "s&p 500", "s&p500"):
                    criteria_dict["index"] = "s&p 500"
                    criteria_list.append("S&P 500 index")
                elif universe in ("nasdaq100", "nasdaq 100"):
                    criteria_dict["index"] = "nasdaq 100"
                    criteria_list.append("NASDAQ 100 index")
                else:
                    criteria_dict["index"] = universe
                    criteria_list.append(f"{universe.title()} index")
            
            query_lower = query.lower()
            if any(k in query_lower for k in ("india", "indian", "nse", "bse")):
                criteria_dict["market"] = "india"
            elif any(k in query_lower for k in ("us", "usa", "american", "sp500", "nasdaq")):
                criteria_dict["market"] = "us"
            elif any(k in query_lower for k in ("uk", "london", "ftse")):
                criteria_dict["market"] = "uk"
            elif any(k in query_lower for k in ("germany", "german", "dax")):
                criteria_dict["market"] = "germany"
            elif any(k in query_lower for k in ("japan", "tokyo", "nikkei")):
                criteria_dict["market"] = "japan"
            
            filters = result.get("filters", [])
            for f in filters:
                ind = f.get("indicator", "").lower()
                cond = f.get("condition", "").lower()
                val = f.get("value")
                val2 = f.get("value2")
                
                if ind.startswith("sma") or ind.startswith("ema"):
                    criteria_dict[f"price_vs_{ind}"] = cond
                    m_period = re.search(r'\d+', ind)
                    period_str = f" {m_period.group()}-day" if m_period else ""
                    type_str = "SMA" if ind.startswith("sma") else "EMA"
                    criteria_list.append(f"Price {cond} {period_str} {type_str}")
                    continue
                
                if ind == "pe_ratio":
                    if cond == "below":
                        criteria_dict["max_pe"] = val
                        criteria_list.append(f"P/E < {val}")
                    elif cond == "above":
                        criteria_dict["min_pe"] = val
                        criteria_list.append(f"P/E > {val}")
                    elif cond == "between" and val is not None and val2 is not None:
                        criteria_dict["min_pe"] = val
                        criteria_dict["max_pe"] = val2
                        criteria_list.append(f"P/E between {val} and {val2}")
                elif ind == "market_cap":
                    if cond == "above":
                        is_india = criteria_dict.get("market") == "india" or universe in ("nifty50", "nifty100", "nifty500")
                        scaled_val = val * 1e7 if (is_india and val < 1e7) else val
                        criteria_dict["min_market_cap"] = scaled_val
                        criteria_list.append(f"Market Cap > {val} Cr" if (is_india and val < 1e7) else f"Market Cap > {val}")
                    elif cond == "below":
                        is_india = criteria_dict.get("market") == "india" or universe in ("nifty50", "nifty100", "nifty500")
                        scaled_val = val * 1e7 if (is_india and val < 1e7) else val
                        criteria_dict["max_market_cap"] = scaled_val
                        criteria_list.append(f"Market Cap < {val} Cr" if (is_india and val < 1e7) else f"Market Cap < {val}")
                elif ind == "rsi":
                    if cond == "below":
                        criteria_dict["max_rsi"] = val
                        criteria_list.append(f"RSI < {val}")
                    elif cond == "above":
                        criteria_dict["min_rsi"] = val
                        criteria_list.append(f"RSI > {val}")
                    elif cond == "between" and val is not None and val2 is not None:
                        criteria_dict["min_rsi"] = val
                        criteria_dict["max_rsi"] = val2
                        criteria_list.append(f"RSI between {val} and {val2}")
                elif ind == "dividend_yield":
                    if cond == "above":
                        criteria_dict["min_dividend_yield"] = val
                        criteria_list.append(f"Dividend Yield > {val}%")
                elif ind == "change_pct":
                    if cond == "above":
                        criteria_dict["min_change_pct"] = val
                        criteria_list.append(f"Change % > {val}%")
                    elif cond == "below":
                        criteria_dict["max_change_pct"] = val
                        criteria_list.append(f"Change % < {val}%")
                elif ind == "volume_ratio":
                    if cond == "above":
                        criteria_dict["volume_spike"] = val
                        criteria_list.append(f"Volume Ratio > {val}x")
                elif ind == "pct_from_52w_low":
                    criteria_dict["near_52w_low"] = True
                    criteria_list.append("Near 52-week low")
                elif ind == "pct_from_52w_high":
                    criteria_dict["near_52w_high"] = True
                    criteria_list.append("Near 52-week high")
                elif ind == "macd":
                    if cond in ("above", "bullish"):
                        criteria_dict["macd_bullish"] = True
                        criteria_list.append("MACD Bullish")
                    elif cond in ("below", "bearish"):
                        criteria_dict["macd_bearish"] = True
                        criteria_list.append("MACD Bearish")
                elif ind == "bb_squeeze":
                    criteria_dict["bb_squeeze"] = True
                    criteria_list.append("Bollinger Band Squeeze")
                elif ind == "bb_upper" and cond == "above":
                    criteria_dict["price_above_bb_upper"] = True
                    criteria_list.append("Price above BB Upper")
                elif ind == "bb_lower" and cond == "below":
                    criteria_dict["price_below_bb_lower"] = True
                    criteria_list.append("Price below BB Lower")
                elif ind == "beta":
                    if cond == "below":
                        criteria_dict["max_beta"] = val
                        criteria_list.append(f"Beta < {val}")
                    elif cond == "above":
                        criteria_dict["min_beta"] = val
                        criteria_list.append(f"Beta > {val}")
            
            if result.get("sort_by"):
                criteria_dict["sort_by"] = result["sort_by"]
            if result.get("sort_order"):
                criteria_dict["sort_order"] = result["sort_order"]
            if result.get("max_results"):
                criteria_dict["limit"] = result["max_results"]
                
            mapped_result = {
                "query": query,
                "criteria": criteria_list,
                "criteria_dict": criteria_dict,
                "custom_filter_function": result.get("custom_filter_function")
            }
            print(f"[Screener] Mapped Output: {mapped_result}")
            return mapped_result
        else:
            print(f"[Screener] No JSON found in response")
            return {"query": query, "criteria": [], "criteria_dict": {}}
    except Exception as e:
        print(f"[Screener] Failed to parse criteria: {e}")
        return {"query": query, "criteria": [], "criteria_dict": {}}


# ── Main Entry Point ──────────────────────────────────────────────────────────

def run_stock_screener(query: str) -> Dict[str, Any]:
    print(f"[Screener] Query: {query}")
    _info_cache.clear_expired()
    _hist_cache.clear_expired()

    parsed        = parse_screening_criteria(query)
    criteria      = parsed.get("criteria_dict", {})
    criteria_list = parsed.get("criteria", [])
    index_name    = (criteria.get("index") or "").lower().strip()
    custom_filter_code = parsed.get("custom_filter_function")  # may be None or a code string

    print(f"[Screener] Parsed result: {parsed}")
    print(f"[Screener] Criteria dict: {criteria}")
    print(f"[Screener] Custom filter: {'yes' if custom_filter_code else 'no'}")

    # Resolve universe — use index list if specified, else market-filtered universe
    if index_name and index_name in INDEX_MAP:
        tickers = INDEX_MAP[index_name]
        print(f"[Screener] Using index universe: {index_name} ({len(tickers)} stocks)")
        # If a sector is ALSO specified, intersect the index with the sector universe
        # so queries like "Nifty 50 banking stocks" work correctly.
        sector = (criteria.get("sector") or "").lower().strip()
        if sector:
            allowed_sectors = SECTOR_ALIASES.get(sector, [sector.title()])
            sector_tickers = [t for t in tickers if NSE_SECTOR_MAP.get(t, "").lower() in [s.lower() for s in allowed_sectors]]
            if sector_tickers:
                tickers = sector_tickers
                print(f"[Screener] Intersected with sector '{sector}': {len(tickers)} stocks")
            else:
                # Sector map had no matches — fall back to full index so we don't return 0 results,
                # and let the post-fetch sector pre-filter handle it.
                print(f"[Screener] Sector '{sector}' intersection empty, keeping full index universe")
    else:
        market = (criteria.get("market") or "").lower().strip()
        sector = (criteria.get("sector") or "").lower().strip()
        
        # Indian market
        if market in ["india", "indian", "nse"]:
            # Use sector-specific NSE list when available for better coverage
            if sector == "technology":
                tickers = list(dict.fromkeys(NSE_IT + NIFTY_100))
                print(f"[Screener] Using NSE IT universe ({len(tickers)} stocks)")
            elif sector in ["financial services", "finance", "banking", "bank"]:
                tickers = list(dict.fromkeys(NSE_BANKING + NIFTY_100))
                print(f"[Screener] Using NSE Banking universe ({len(tickers)} stocks)")
            else:
                tickers = NIFTY_100
                print(f"[Screener] Using NSE universe ({len(tickers)} stocks)")
        
        # US market (explicit only)
        elif market in ["us", "usa", "american"]:
            tickers = list(dict.fromkeys(SP500_SAMPLE + NASDAQ_100_SAMPLE + DOW_JONES))
            print(f"[Screener] Using US universe ({len(tickers)} stocks)")
        
        # UK market
        elif market in ["uk", "britain", "british", "london"]:
            tickers = FTSE_100_SAMPLE
            print(f"[Screener] Using UK (FTSE 100) universe ({len(tickers)} stocks)")
        
        # German market
        elif market in ["germany", "german", "deutschland"]:
            tickers = DAX_40_SAMPLE
            print(f"[Screener] Using German (DAX 40) universe ({len(tickers)} stocks)")
        
        # Japanese market
        elif market in ["japan", "japanese", "tokyo"]:
            tickers = NIKKEI_225_SAMPLE
            print(f"[Screener] Using Japanese (Nikkei 225) universe ({len(tickers)} stocks)")
        
        # Hong Kong market
        elif market in ["hong kong", "hongkong", "hk"]:
            tickers = HANG_SENG_SAMPLE
            print(f"[Screener] Using Hong Kong (Hang Seng) universe ({len(tickers)} stocks)")
        
        # Australian market
        elif market in ["australia", "australian", "aussie"]:
            tickers = ASX_200_SAMPLE
            print(f"[Screener] Using Australian (ASX 200) universe ({len(tickers)} stocks)")
        
        # Canadian market
        elif market in ["canada", "canadian"]:
            tickers = TSX_SAMPLE
            print(f"[Screener] Using Canadian (TSX) universe ({len(tickers)} stocks)")
        
        # Fallback to US (default)
        else:
            tickers = list(dict.fromkeys(SP500_SAMPLE + NASDAQ_100_SAMPLE + DOW_JONES))
            print(f"[Screener] Using default US universe ({len(tickers)} stocks)")

    # Deduplicate while preserving order
    seen = set()
    tickers = [t for t in tickers if not (t in seen or seen.add(t))]

    # ── Pre-filter by sector using static map (zero API calls) ────────────────
    sector_filter = (criteria.get("sector") or "").lower().strip()
    if sector_filter and tickers:
        allowed_sectors = SECTOR_ALIASES.get(sector_filter, [sector_filter.title()])
        pre_filtered = [t for t in tickers if NSE_SECTOR_MAP.get(t, "").lower() in [s.lower() for s in allowed_sectors]]
        # Only apply pre-filter if we have known mappings; unknown tickers pass through
        unknown = [t for t in tickers if t not in NSE_SECTOR_MAP]
        tickers = pre_filtered + unknown
        print(f"[Screener] Pre-filtered to {len(tickers)} tickers for sector '{sector_filter}' (skipped {len(seen) - len(tickers) if seen else 0} non-matching)")

    needs_technicals = any(criteria.get(k) for k in [
        "price_vs_sma20", "price_vs_sma50", "price_vs_sma200",
        "max_rsi", "min_rsi", "near_52w_low", "near_52w_high",
        "price_vs_ema20", "price_vs_ema50", "macd_bullish", "macd_bearish",
        "bb_squeeze", "price_above_bb_upper", "price_below_bb_lower", "volume_spike",
    ]) or any(re.match(r"price_vs_(ema|sma)_?\d+$", k) for k in criteria) or bool(custom_filter_code)

    # Extract custom EMA/SMA periods the LLM requested that are NOT already
    # precomputed in Supabase (sma20/50/200, ema8/20/50 are always available)
    _PRECOMPUTED_SMA = {9, 20, 21, 50, 200}
    _PRECOMPUTED_EMA = {8, 9, 20, 21, 50}
    custom_ema_periods = [
        int(m.group(1)) for k in criteria
        for m in [re.match(r"price_vs_ema_?(\d+)$", k)] if m
        if int(m.group(1)) not in _PRECOMPUTED_EMA
    ]
    custom_sma_periods = [
        int(m.group(1)) for k in criteria
        for m in [re.match(r"price_vs_sma_?(\d+)$", k)] if m
        if int(m.group(1)) not in _PRECOMPUTED_SMA
    ]
    
    print(f"[Screener] Needs technicals: {needs_technicals}")

    # ── Batch fetch technicals (1 API call instead of N) ──────────────────────
    tech_map: Dict[str, Optional[Dict]] = {}
    if needs_technicals:
        tech_map = batch_compute_technicals(tickers)

        # Inject any custom EMA/SMA periods not pre-computed.
        # When data came from Supabase, _hist_close is None — fall back to
        # stock_ohlcv (already in Supabase) or a targeted yfinance fetch.
        if custom_ema_periods or custom_sma_periods:
            # Collect tickers that need hist but don't have it in memory
            needs_hist = [t for t, tech in tech_map.items()
                          if tech is not None and tech.get("_hist_close") is None]

            if needs_hist:
                print(f"[Screener] Fetching OHLCV for {len(needs_hist)} tickers to compute custom periods...")
                try:
                    raw_extra = yf.download(
                        needs_hist, period="2y", interval="1d",
                        group_by="ticker", auto_adjust=True,
                        progress=False, threads=True,
                    )
                    for ticker in needs_hist:
                        try:
                            hist = raw_extra[ticker] if len(needs_hist) > 1 else raw_extra
                            if not hist.empty and "Close" in hist.columns:
                                tech_map[ticker]["_hist_close"] = hist["Close"]
                                tech_map[ticker]["_hist_df"]    = hist
                        except Exception:
                            pass
                except Exception as e:
                    print(f"[Screener] Extra OHLCV fetch failed: {e}")

            for ticker, tech in tech_map.items():
                if tech is None:
                    continue
                close = tech.get("_hist_close")
                if close is None:
                    continue
                for p in custom_ema_periods:
                    key = f"ema{p}"
                    if key not in tech or tech[key] is None:
                        try:
                            tech[key] = float(close.ewm(span=p, adjust=False).mean().iloc[-1])
                        except:
                            tech[key] = None
                for p in custom_sma_periods:
                    key = f"sma{p}"
                    if key not in tech or tech[key] is None:
                        try:
                            tech[key] = float(close.rolling(p).mean().iloc[-1]) if len(close) >= p else None
                        except:
                            tech[key] = None

    # ── Bulk load fundamentals from Supabase (1 DB query for all tickers) ──────
    fund_map = load_fundamentals_from_supabase(tickers)
    print(f"[Screener] Supabase fundamentals: {len(fund_map)}/{len(tickers)} tickers cached")

    # ── Fetch live price/volume concurrently (thread pool) ────────────────────
    # yf.Ticker().info has no batch API — parallelise to cut wall-clock time
    # from ~25s sequential → ~3-5s concurrent for 50 tickers.
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _fetch_one(ticker):
        return ticker, fetch_stock_data(
            ticker,
            prefetched_tech=tech_map.get(ticker),
            prefetched_fundamentals=fund_map.get(ticker),
        )

    raw_results: Dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(_fetch_one, t): t for t in tickers}
        for future in as_completed(futures):
            try:
                ticker, data = future.result()
                raw_results[ticker] = data
            except Exception as e:
                print(f"[Screener] fetch error: {e}")

    matching_stocks = []
    for ticker in tickers:   # preserve original order
        stock_data = raw_results.get(ticker)
        if not stock_data:
            continue
        matches, reason = apply_criteria(stock_data, criteria)
        if not matches:
            continue

        # Run custom filter if present (uses raw OHLCV history)
        if custom_filter_code:
            ticker_tech = tech_map.get(ticker) or {}
            hist_df = ticker_tech.get("_hist_df")
            if hist_df is None:
                continue
            if not execute_custom_filter(custom_filter_code, hist_df):
                continue
            if not reason:
                reason = "Custom filter match"

        entry = {
            "ticker": stock_data["ticker"],
            "name": stock_data["name"],
            "price": stock_data["price"],
            "currency": stock_data.get("currency", "$"),
            "change_pct": stock_data["change_pct"],
            "market_cap": stock_data["market_cap_str"],
            "pe_ratio": stock_data["pe_ratio"],
            "volume": stock_data["volume_str"],
            "sector": stock_data["sector"],
            "match_reason": reason,
        }
        # Include technical values in result if they were used
        if needs_technicals:
            if stock_data.get("sma20"):
                entry["sma20"] = round(stock_data["sma20"], 2)
            if stock_data.get("rsi"):
                entry["rsi"] = round(stock_data["rsi"], 1)
            if stock_data.get("pct_from_52w_high") is not None:
                entry["pct_from_52w_high"] = round(stock_data["pct_from_52w_high"], 1)
        matching_stocks.append(entry)

    # Sort by market cap descending
    def cap_sort_key(x):
        s = x["market_cap"].replace("$", "").replace("₹", "").replace(",", "")
        if "T" in s: return float(s.replace("T", "")) * 1e12
        if "B" in s: return float(s.replace("B", "")) * 1e9
        if "M" in s: return float(s.replace("M", "")) * 1e6
        return float(s) if s else 0

    matching_stocks.sort(key=cap_sort_key, reverse=True)

    print(f"[Screener] Found {len(matching_stocks)} matching stocks")

    # Apply limit from parsed criteria (default to 50 if not specified)
    limit = criteria.get("limit") or 50
    limited_stocks = matching_stocks[:limit]

    return {
        "query": query,
        "criteria": criteria_list,
        "stocks": limited_stocks,
        "total_matches": len(matching_stocks),
    }
