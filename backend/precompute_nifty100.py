"""
Nifty 100 Precompute Job
─────────────────────────
Precomputes and stores in Supabase:
  1. Technical indicators  (every 15 min)
  2. Daily OHLCV history   (every 15 min — appends new rows, upserts existing)
  3. Slow fundamentals     (once a day — P/E, market cap, sector, etc.)

Usage:
    # First-time setup: loads 5 years of OHLCV + technicals + fundamentals
    python precompute_nifty100.py --init

    # Extend existing 2y data to 5y (OHLCV + technicals only, no fundamentals)
    python precompute_nifty100.py --backfill

    # Scheduled every 15 min: refreshes technicals + appends latest OHLCV row
    python precompute_nifty100.py

    # Scheduled once a day: also refreshes fundamentals
    python precompute_nifty100.py --full

Environment variables required (same as backend/.env):
    SUPABASE_URL
    SUPABASE_SERVICE_KEY
"""

import sys
import os
import time
import argparse

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import yfinance as yf
import pandas as pd
from screener import NIFTY_100, _compute_technicals_from_hist
from supabase_cache import (
    upsert_technicals_to_supabase,
    upsert_ohlcv_to_supabase,
    upsert_fundamentals_to_supabase,
)


def run_technicals_and_ohlcv(period: str = "5y"):
    """
    Single batch yf.download → technicals + OHLCV for all 100 tickers.
    period="5y"  for initial load or full refresh (5y ensures SMA200 warmup
                 is available even for 3-year backtests: 200 warmup + 756 usable)
    period="5d"  for the scheduled 15-min incremental update (much faster)
    """
    tickers = NIFTY_100
    print(f"[Precompute] Downloading OHLCV + technicals for {len(tickers)} tickers (period={period})...")

    try:
        raw = yf.download(
            tickers,
            period=period,
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=True,
            threads=True,
        )
    except Exception as e:
        print(f"[Precompute] Batch download failed: {e}")
        sys.exit(1)

    success, failed = 0, 0

    for i, ticker in enumerate(tickers):
        try:
            hist = raw[ticker] if ticker in raw.columns.get_level_values(0) else pd.DataFrame()

            if hist.empty or "Close" not in hist.columns or len(hist) < 21:
                print(f"[Precompute] Skipping {ticker}: insufficient data")
                failed += 1
                continue

            # Always compute technicals from the full history slice we have
            tech = _compute_technicals_from_hist(hist)
            if tech is None:
                failed += 1
                continue

            upsert_technicals_to_supabase(ticker, tech)

            ohlcv_cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in hist.columns]
            upsert_ohlcv_to_supabase(ticker, hist[ohlcv_cols])

            success += 1
            print(f"[Precompute] [{i+1}/{len(tickers)}] {ticker} ✓  ({len(hist)} rows)")

        except Exception as e:
            print(f"[Precompute] Error for {ticker}: {e}")
            failed += 1

    print(f"\n[Precompute] Technicals+OHLCV done. Success: {success}, Failed: {failed}")


def run_fundamentals():
    """
    Fetch yf.Ticker.info for each Nifty 100 ticker and store slow fundamentals.
    No batch API exists for .info — runs individually with rate-limit pauses.
    Schedule once a day, not every 15 min.
    """
    tickers = NIFTY_100
    print(f"[Precompute] Fetching fundamentals for {len(tickers)} tickers...")

    success, failed = 0, 0

    for i, ticker in enumerate(tickers):
        if i > 0 and i % 10 == 0:
            print(f"[Precompute] Fundamentals progress: {i}/{len(tickers)}...")
            time.sleep(1.0)

        try:
            info = yf.Ticker(ticker).info
            if not info or not info.get("longName"):
                print(f"[Precompute] No info for {ticker}, skipping")
                failed += 1
                continue

            ok = upsert_fundamentals_to_supabase(ticker, info)
            if ok:
                success += 1
                print(f"[Precompute] [{i+1}/{len(tickers)}] {ticker} fundamentals ✓")
            else:
                failed += 1
        except Exception as e:
            print(f"[Precompute] Fundamentals error for {ticker}: {e}")
            failed += 1

    print(f"\n[Precompute] Fundamentals done. Success: {success}, Failed: {failed}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nifty 100 Supabase precompute job")
    parser.add_argument(
        "--init",
        action="store_true",
        help="One-time initial load: 5y OHLCV + technicals + fundamentals for all 100 tickers",
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Re-download 5 years of OHLCV + technicals only (no fundamentals). "
             "Use this to extend existing data from 2y to 5y without a full --init.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Scheduled daily run: 5d OHLCV + technicals + fundamentals refresh",
    )
    args = parser.parse_args()

    if args.init:
        # One-time setup: pull full 5 years for backtesting history
        # 5y = ~1260 trading days → 200 SMA warmup (200) + 3 full years (756) + buffer
        print("=" * 60)
        print("INITIAL LOAD — downloading 5 years of OHLCV for 100 tickers")
        print("This will take ~5-8 minutes. Run once, then switch to cron.")
        print("=" * 60)
        run_technicals_and_ohlcv(period="5y")
        run_fundamentals()
    elif args.backfill:
        # Extend existing 2y data to 5y — OHLCV + technicals only, no fundamentals.
        # Supabase upsert is idempotent so re-inserting existing rows is safe.
        print("=" * 60)
        print("BACKFILL — extending OHLCV history from 2y → 5y for 100 tickers")
        print("Existing rows will be upserted (no duplicates). ~5-8 minutes.")
        print("=" * 60)
        run_technicals_and_ohlcv(period="5y")
    elif args.full:
        # Daily cron: short OHLCV window + fundamentals
        run_technicals_and_ohlcv(period="5d")
        run_fundamentals()
    else:
        # 15-min cron: just refresh latest OHLCV row + recompute technicals snapshot.
        # Use 2y period so SMA200 is computed correctly from sufficient history,
        # but avoid 5y here to keep the 15-min job fast (~2 min vs ~8 min).
        # The daily --full job handles fundamentals; this job only touches OHLCV + technicals.
        run_technicals_and_ohlcv(period="2y")
