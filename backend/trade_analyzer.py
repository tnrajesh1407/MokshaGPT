"""
Trade Analyzer — Brokerage Account Review Engine
-------------------------------------------------
Parses retail brokerage trade history CSVs and computes:
  - Broker detection & column normalization
  - FIFO realized P&L per trade
  - Monthly breakdown (P&L, trade count, win rate, fees)
  - Overtrading detection (volume spikes, revenge trading, win-rate collapse)
  - Consistency score (0–10) with sub-scores
  - Symbol breakdown (best/worst tickers)
  - Holding period analysis (winners vs losers)
  - Day-of-week win rate pattern

Supported brokers (auto-detected):
  zerodha, groww, angel_one, robinhood, ibkr, fidelity, generic
"""

import io
import json
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from langfuse import observe as traceable

# -- Broker Schema Definitions -------------------------------------------------

BROKER_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "zerodha": {
        "required_cols": {"symbol", "trade_type", "quantity", "price", "trade_date"},
        "date_col": "trade_date",
        "symbol_col": "symbol",
        "side_col": "trade_type",
        "qty_col": "quantity",
        "price_col": "price",
        "fee_col": None,
        "buy_values": {"buy", "b"},
        "sell_values": {"sell", "s"},
        "currency": "INR",
        "display_name": "Zerodha",
    },
    "groww": {
        "required_cols": {"scrip_name", "transaction_type", "quantity", "rate", "date"},
        "date_col": "date",
        "symbol_col": "scrip_name",
        "side_col": "transaction_type",
        "qty_col": "quantity",
        "price_col": "rate",
        "fee_col": None,
        "buy_values": {"buy", "b", "purchase"},
        "sell_values": {"sell", "s", "sale"},
        "currency": "INR",
        "display_name": "Groww",
    },
    "angel_one": {
        "required_cols": {"symbol", "buy_sell", "qty", "rate", "date"},
        "date_col": "date",
        "symbol_col": "symbol",
        "side_col": "buy_sell",
        "qty_col": "qty",
        "price_col": "rate",
        "fee_col": None,
        "buy_values": {"buy", "b"},
        "sell_values": {"sell", "s"},
        "currency": "INR",
        "display_name": "Angel One",
    },
    "robinhood": {
        "required_cols": {"symbol", "side", "quantity", "average_price", "date"},
        "date_col": "date",
        "symbol_col": "symbol",
        "side_col": "side",
        "qty_col": "quantity",
        "price_col": "average_price",
        "fee_col": None,
        "buy_values": {"buy"},
        "sell_values": {"sell"},
        "currency": "USD",
        "display_name": "Robinhood",
    },
    "ibkr": {
        "required_cols": {"symbol", "buy_sell", "quantity", "tradeprice", "datetime"},
        "date_col": "datetime",
        "symbol_col": "symbol",
        "side_col": "buy_sell",
        "qty_col": "quantity",
        "price_col": "tradeprice",
        "fee_col": "ibcommission",
        "buy_values": {"buy"},
        "sell_values": {"sell"},
        "currency": "USD",
        "display_name": "Interactive Brokers",
    },
    "fidelity": {
        "required_cols": {"symbol", "action", "quantity", "price", "date"},
        "date_col": "date",
        "symbol_col": "symbol",
        "side_col": "action",
        "qty_col": "quantity",
        "price_col": "price",
        "fee_col": "commission",
        "buy_values": {"bought", "buy"},
        "sell_values": {"sold", "sell"},
        "currency": "USD",
        "display_name": "Fidelity",
    },
}


# -- Broker Detection & Normalization ------------------------------------------


def detect_broker(df: pd.DataFrame) -> str:
    """
    Detect the broker from column names.
    Returns broker key or 'generic' if no match.
    """
    cols = set(df.columns.str.lower().str.strip())
    for broker, schema in BROKER_SCHEMAS.items():
        if schema["required_cols"].issubset(cols):
            return broker
    return "generic"


def normalize_trades(df: pd.DataFrame, broker: str) -> pd.DataFrame:
    """
    Map broker-specific columns to a standard schema:
      date | symbol | side (BUY/SELL) | qty | price | value | fees

    Returns a clean DataFrame sorted by date ascending.
    """
    # Normalize column names
    df = df.copy()
    df.columns = df.columns.str.lower().str.strip().str.replace(r"[\s\-/]", "_", regex=True)

    if broker == "generic":
        return _normalize_generic(df)

    schema = BROKER_SCHEMAS[broker]

    # Rename to standard names
    rename_map = {
        schema["date_col"]: "date",
        schema["symbol_col"]: "symbol",
        schema["side_col"]: "side",
        schema["qty_col"]: "qty",
        schema["price_col"]: "price",
    }
    if schema["fee_col"] and schema["fee_col"] in df.columns:
        rename_map[schema["fee_col"]] = "fees"

    df = df.rename(columns=rename_map)

    # Normalize side to BUY / SELL
    buy_vals = schema["buy_values"]
    sell_vals = schema["sell_values"]
    df["side"] = df["side"].astype(str).str.lower().str.strip()
    df["side"] = df["side"].apply(
        lambda x: "BUY" if x in buy_vals else ("SELL" if x in sell_vals else x.upper())
    )

    # Keep only BUY / SELL rows
    df = df[df["side"].isin(["BUY", "SELL"])].copy()

    # Parse dates
    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    df = df.dropna(subset=["date"])

    # Coerce numeric
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce").abs()
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["qty", "price"])
    df = df[df["qty"] > 0]
    df = df[df["price"] > 0]

    # Compute trade value
    df["value"] = df["qty"] * df["price"]

    # Fees
    if "fees" not in df.columns:
        df["fees"] = 0.0
    else:
        df["fees"] = pd.to_numeric(df["fees"], errors="coerce").fillna(0.0).abs()

    # Clean symbol
    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()

    # Sort by date
    df = df.sort_values("date").reset_index(drop=True)

    # Keep only needed columns
    return df[["date", "symbol", "side", "qty", "price", "value", "fees"]]


def _normalize_generic(df: pd.DataFrame) -> pd.DataFrame:
    """
    Best-effort normalization for unknown broker formats.
    Tries to find date, symbol, side, qty, price columns by keyword matching.
    """
    col_map: Dict[str, Optional[str]] = {
        "date": None, "symbol": None, "side": None,
        "qty": None, "price": None, "fees": None,
    }

    date_kws    = ["date", "time", "datetime", "trade_date", "order_date", "transaction_date"]
    symbol_kws  = ["symbol", "ticker", "scrip", "stock", "instrument", "security", "name"]
    side_kws    = ["side", "type", "trade_type", "action", "buy_sell", "transaction_type", "order_type"]
    qty_kws     = ["qty", "quantity", "shares", "units", "lots", "volume"]
    price_kws   = ["price", "rate", "avg_price", "average_price", "trade_price", "execution_price"]
    fee_kws     = ["fee", "fees", "commission", "brokerage", "charges", "cost"]

    cols = list(df.columns)
    for col in cols:
        c = col.lower()
        if col_map["date"] is None and any(k in c for k in date_kws):
            col_map["date"] = col
        if col_map["symbol"] is None and any(k in c for k in symbol_kws):
            col_map["symbol"] = col
        if col_map["side"] is None and any(k in c for k in side_kws):
            col_map["side"] = col
        if col_map["qty"] is None and any(k in c for k in qty_kws):
            col_map["qty"] = col
        if col_map["price"] is None and any(k in c for k in price_kws):
            col_map["price"] = col
        if col_map["fees"] is None and any(k in c for k in fee_kws):
            col_map["fees"] = col

    missing = [k for k, v in col_map.items() if v is None and k != "fees"]
    if missing:
        raise ValueError(
            f"Could not auto-detect columns: {missing}. "
            f"Available columns: {list(df.columns)}. "
            f"Your CSV needs columns for: date (trade date), symbol (ticker/stock name), "
            f"side (buy/sell), qty (quantity/shares), and price (execution price). "
            f"Column names don't need to match exactly — the system looks for keywords. "
            f"Rename your columns to include these keywords and try again."
        )

    out = pd.DataFrame()
    out["date"]   = pd.to_datetime(df[col_map["date"]], errors="coerce", dayfirst=True)
    out["symbol"] = df[col_map["symbol"]].astype(str).str.strip().str.upper()
    out["side"]   = df[col_map["side"]].astype(str).str.strip().str.upper()
    out["qty"]    = pd.to_numeric(df[col_map["qty"]], errors="coerce").abs()
    out["price"]  = pd.to_numeric(df[col_map["price"]], errors="coerce")
    out["fees"]   = pd.to_numeric(df[col_map["fees"]], errors="coerce").fillna(0.0).abs() if col_map["fees"] else 0.0

    # Normalize side
    out["side"] = out["side"].apply(
        lambda x: "BUY" if any(b in x for b in ["BUY", "B", "PURCHASE", "BOUGHT"])
        else ("SELL" if any(s in x for s in ["SELL", "S", "SALE", "SOLD"]) else x)
    )

    out = out.dropna(subset=["date", "qty", "price"])
    out = out[out["side"].isin(["BUY", "SELL"])]
    out = out[out["qty"] > 0]
    out = out[out["price"] > 0]
    out["value"] = out["qty"] * out["price"]
    out = out.sort_values("date").reset_index(drop=True)
    return out[["date", "symbol", "side", "qty", "price", "value", "fees"]]


# -- FIFO P&L Engine -----------------------------------------------------------


def compute_pnl_fifo(trades: pd.DataFrame) -> pd.DataFrame:
    """
    Match BUY/SELL pairs per symbol using FIFO and compute realized P&L.

    Returns the original trades DataFrame with extra columns:
      realized_pnl   — P&L for SELL trades (NaN for BUY)
      cost_basis     — average cost of the matched BUY lots
      days_held      — calendar days between matched BUY and SELL
      is_winner      — True if realized_pnl > 0
    """
    trades = trades.copy()
    trades["realized_pnl"] = np.nan
    trades["cost_basis"]   = np.nan
    trades["days_held"]    = np.nan
    trades["is_winner"]    = np.nan

    # Process each symbol independently
    for symbol, grp in trades.groupby("symbol"):
        buy_queue: List[Dict] = []  # FIFO queue of {qty, price, date, idx}

        for row_idx, row in grp.iterrows():
            if row["side"] == "BUY":
                buy_queue.append({
                    "qty": float(row["qty"]),
                    "price": float(row["price"]),
                    "date": row["date"],
                    "idx": row_idx,
                })
            elif row["side"] == "SELL":
                sell_qty   = float(row["qty"])
                sell_price = float(row["price"])
                sell_date  = row["date"]

                matched_cost  = 0.0
                matched_qty   = 0.0
                earliest_date = None

                remaining = sell_qty
                while remaining > 0 and buy_queue:
                    lot = buy_queue[0]
                    take = min(lot["qty"], remaining)

                    matched_cost += take * lot["price"]
                    matched_qty  += take
                    if earliest_date is None:
                        earliest_date = lot["date"]

                    lot["qty"] -= take
                    remaining  -= take
                    if lot["qty"] <= 1e-9:
                        buy_queue.pop(0)

                if matched_qty > 0:
                    avg_cost = matched_cost / matched_qty
                    pnl = (sell_price - avg_cost) * matched_qty - float(row["fees"])
                    days = (sell_date - earliest_date).days if earliest_date else 0

                    trades.at[row_idx, "realized_pnl"] = round(pnl, 2)
                    trades.at[row_idx, "cost_basis"]   = round(avg_cost, 4)
                    trades.at[row_idx, "days_held"]    = int(days)
                    trades.at[row_idx, "is_winner"]    = pnl > 0

    return trades


# -- Monthly Breakdown ---------------------------------------------------------


def compute_monthly_breakdown(trades: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Aggregate closed trades (SELL rows with realized_pnl) by calendar month.

    Returns list of dicts sorted by month ascending:
      month_label, year, month, total_pnl, trade_count, win_count,
      loss_count, win_rate, gross_profit, gross_loss, fees_paid,
      best_trade_pnl, worst_trade_pnl, avg_trade_pnl
    """
    closed = trades[trades["realized_pnl"].notna()].copy()
    if closed.empty:
        return []

    closed["year_month"] = closed["date"].dt.to_period("M")

    rows = []
    for period, grp in closed.groupby("year_month"):
        pnls = grp["realized_pnl"].tolist()
        wins  = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        fees  = grp["fees"].sum() if "fees" in grp.columns else 0.0

        rows.append({
            "month_label":    period.strftime("%b %Y"),
            "year":           int(period.year),
            "month":          int(period.month),
            "total_pnl":      round(sum(pnls), 2),
            "trade_count":    len(pnls),
            "win_count":      len(wins),
            "loss_count":     len(losses),
            "win_rate":       round(len(wins) / len(pnls) * 100, 1) if pnls else 0.0,
            "gross_profit":   round(sum(wins), 2),
            "gross_loss":     round(sum(losses), 2),
            "fees_paid":      round(float(fees), 2),
            "best_trade_pnl": round(max(pnls), 2) if pnls else 0.0,
            "worst_trade_pnl":round(min(pnls), 2) if pnls else 0.0,
            "avg_trade_pnl":  round(sum(pnls) / len(pnls), 2) if pnls else 0.0,
        })

    return sorted(rows, key=lambda r: (r["year"], r["month"]))


# -- Overtrading Detection -----------------------------------------------------


def detect_overtrading(
    trades: pd.DataFrame,
    monthly: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Flag months with overtrading signals.

    Three signals:
      1. volume_spike   — month trade count > 1.5× rolling 3-month average
      2. revenge_trading — trades placed on same day as a losing trade
      3. winrate_collapse — win rate < 40% AND trade count >= average

    Returns list of flagged months with reasons.
    """
    if not monthly:
        return []

    flags: List[Dict[str, Any]] = []
    counts = [m["trade_count"] for m in monthly]
    avg_count = sum(counts) / len(counts) if counts else 0

    closed = trades[trades["realized_pnl"].notna()].copy()
    closed["trade_date_only"] = closed["date"].dt.date

    for i, m in enumerate(monthly):
        reasons: List[str] = []

        # Signal 1: Volume spike
        window_start = max(0, i - 3)
        rolling_avg = sum(counts[window_start:i]) / max(len(counts[window_start:i]), 1)
        if rolling_avg > 0 and m["trade_count"] > rolling_avg * 1.5:
            reasons.append(
                f"Trade volume spike: {m['trade_count']} trades vs "
                f"{rolling_avg:.1f} rolling average (+{((m['trade_count']/rolling_avg)-1)*100:.0f}%)"
            )

        # Signal 2: Revenge trading — trades on same day as a loss
        month_trades = closed[
            (closed["date"].dt.year == m["year"]) &
            (closed["date"].dt.month == m["month"])
        ]
        if not month_trades.empty:
            loss_days = set(
                month_trades[month_trades["realized_pnl"] < 0]["trade_date_only"].tolist()
            )
            revenge_count = 0
            for day in loss_days:
                day_trades = month_trades[month_trades["trade_date_only"] == day]
                # More than 1 trade on a losing day = potential revenge trading
                if len(day_trades) > 1:
                    revenge_count += len(day_trades) - 1
            if revenge_count >= 2:
                reasons.append(
                    f"Possible revenge trading: {revenge_count} extra trades placed on losing days"
                )

        # Signal 3: Win-rate collapse
        if m["win_rate"] < 40 and m["trade_count"] >= avg_count * 0.8:
            reasons.append(
                f"Win-rate collapse: {m['win_rate']}% win rate with {m['trade_count']} trades"
            )

        if reasons:
            flags.append({
                "month_label": m["month_label"],
                "year": m["year"],
                "month": m["month"],
                "trade_count": m["trade_count"],
                "win_rate": m["win_rate"],
                "total_pnl": m["total_pnl"],
                "reasons": reasons,
            })

    return flags


# -- Consistency Score ---------------------------------------------------------


def compute_consistency_score(
    monthly: List[Dict[str, Any]],
    trades: pd.DataFrame,
) -> Dict[str, Any]:
    """
    Compute a 0–10 consistency score from 4 sub-scores.

    Sub-scores:
      win_rate_score     (0–10): overall win rate / 10
      pnl_stability      (0–10): 1 - coefficient of variation of monthly P&L
      sizing_consistency (0–10): 1 - CV of trade values
      improvement_trend  (0–10): slope of monthly win rate (positive = improving)

    Returns dict with overall score and sub-scores.
    """
    if not monthly or len(monthly) < 2:
        return {
            "overall": None,
            "win_rate_score": None,
            "pnl_stability": None,
            "sizing_consistency": None,
            "improvement_trend": None,
            "interpretation": "Not enough data (need at least 2 months of trades)",
        }

    closed = trades[trades["realized_pnl"].notna()]
    all_pnls = [m["total_pnl"] for m in monthly]
    all_win_rates = [m["win_rate"] for m in monthly]

    # 1. Win rate score
    overall_wins  = sum(m["win_count"] for m in monthly)
    overall_total = sum(m["trade_count"] for m in monthly)
    overall_wr = overall_wins / overall_total * 100 if overall_total else 0
    win_rate_score = min(overall_wr / 10, 10.0)

    # 2. P&L stability — lower CV = more stable = higher score
    pnl_mean = np.mean(all_pnls)
    pnl_std  = np.std(all_pnls)
    if abs(pnl_mean) > 0:
        pnl_cv = pnl_std / abs(pnl_mean)
        pnl_stability = max(0.0, min(10.0, (1 - min(pnl_cv, 1.0)) * 10))
    else:
        pnl_stability = 5.0

    # 3. Sizing consistency — lower CV of trade values = more consistent sizing
    if not closed.empty and "value" in closed.columns:
        val_mean = closed["value"].mean()
        val_std  = closed["value"].std()
        if val_mean > 0:
            val_cv = val_std / val_mean
            sizing_consistency = max(0.0, min(10.0, (1 - min(val_cv, 1.0)) * 10))
        else:
            sizing_consistency = 5.0
    else:
        sizing_consistency = 5.0

    # 4. Improvement trend — linear slope of monthly win rates
    if len(all_win_rates) >= 3:
        x = np.arange(len(all_win_rates), dtype=float)
        slope = float(np.polyfit(x, all_win_rates, 1)[0])
        # Normalize: +2 pts/month slope ? 10, -2 pts/month ? 0
        improvement_trend = max(0.0, min(10.0, 5.0 + slope * 2.5))
    else:
        improvement_trend = 5.0  # neutral if not enough months

    # Weighted average
    overall = round(
        win_rate_score     * 0.35 +
        pnl_stability      * 0.25 +
        sizing_consistency * 0.20 +
        improvement_trend  * 0.20,
        1,
    )

    # Interpretation
    if overall >= 8:
        interpretation = "Excellent — highly consistent trading with strong risk-adjusted returns."
    elif overall >= 6:
        interpretation = "Good — reasonably consistent with room for improvement in sizing or win rate."
    elif overall >= 4:
        interpretation = "Fair — noticeable inconsistency in results. Focus on position sizing and trade selection."
    else:
        interpretation = "Poor — high variance in results. Consider reducing trade frequency and reviewing your strategy."

    return {
        "overall": overall,
        "win_rate_score": round(win_rate_score, 1),
        "pnl_stability": round(pnl_stability, 1),
        "sizing_consistency": round(sizing_consistency, 1),
        "improvement_trend": round(improvement_trend, 1),
        "interpretation": interpretation,
    }


# -- Symbol Breakdown ----------------------------------------------------------


def compute_symbol_breakdown(trades: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Aggregate realized P&L by symbol.
    Returns list sorted by total_pnl descending.
    """
    closed = trades[trades["realized_pnl"].notna()].copy()
    if closed.empty:
        return []

    rows = []
    for symbol, grp in closed.groupby("symbol"):
        pnls = grp["realized_pnl"].tolist()
        wins = [p for p in pnls if p > 0]
        rows.append({
            "symbol":      symbol,
            "total_pnl":   round(sum(pnls), 2),
            "trade_count": len(pnls),
            "win_rate":    round(len(wins) / len(pnls) * 100, 1) if pnls else 0.0,
            "best_trade":  round(max(pnls), 2) if pnls else 0.0,
            "worst_trade": round(min(pnls), 2) if pnls else 0.0,
        })

    return sorted(rows, key=lambda r: r["total_pnl"], reverse=True)


# -- Holding Period Analysis ---------------------------------------------------


def compute_holding_analysis(trades: pd.DataFrame) -> Dict[str, Any]:
    """
    Compare average holding period for winning vs losing trades.
    A common retail mistake: holding losers too long, cutting winners too early.
    """
    closed = trades[trades["realized_pnl"].notna() & trades["days_held"].notna()].copy()
    if closed.empty:
        return {}

    winners = closed[closed["realized_pnl"] > 0]["days_held"]
    losers  = closed[closed["realized_pnl"] <= 0]["days_held"]

    result: Dict[str, Any] = {
        "avg_days_held_overall": round(float(closed["days_held"].mean()), 1),
        "avg_days_winners":      round(float(winners.mean()), 1) if not winners.empty else None,
        "avg_days_losers":       round(float(losers.mean()), 1) if not losers.empty else None,
    }

    if result["avg_days_winners"] and result["avg_days_losers"]:
        ratio = result["avg_days_losers"] / max(result["avg_days_winners"], 0.1)
        result["holding_ratio"] = round(ratio, 2)
        if ratio > 2.0:
            result["insight"] = (
                f"You hold losing trades {ratio:.1f}× longer than winning trades on average. "
                f"This is a common pattern — consider setting tighter stop-losses to cut losses faster."
            )
        elif ratio < 0.5:
            result["insight"] = (
                f"You exit losing trades faster than winners ({ratio:.1f}× ratio). "
                f"Good discipline on cutting losses."
            )
        else:
            result["insight"] = (
                f"Your holding periods for winners ({result['avg_days_winners']} days) and "
                f"losers ({result['avg_days_losers']} days) are reasonably balanced."
            )

    return result


# -- Day-of-Week Pattern -------------------------------------------------------


def compute_dow_pattern(trades: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Win rate and average P&L by day of week.
    Helps identify if the trader performs better/worse on specific days.
    """
    closed = trades[trades["realized_pnl"].notna()].copy()
    if closed.empty:
        return []

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    closed["dow"] = closed["date"].dt.dayofweek

    rows = []
    for dow in range(7):
        grp = closed[closed["dow"] == dow]
        if grp.empty:
            continue
        pnls = grp["realized_pnl"].tolist()
        wins = [p for p in pnls if p > 0]
        rows.append({
            "day":         day_names[dow],
            "dow":         dow,
            "trade_count": len(pnls),
            "win_rate":    round(len(wins) / len(pnls) * 100, 1),
            "total_pnl":   round(sum(pnls), 2),
            "avg_pnl":     round(sum(pnls) / len(pnls), 2),
        })

    return sorted(rows, key=lambda r: r["dow"])


# -- Fee Drag Analysis ---------------------------------------------------------


def compute_fee_drag(trades: pd.DataFrame) -> Dict[str, Any]:
    """
    Total fees paid and their impact as % of gross profit.
    """
    closed = trades[trades["realized_pnl"].notna()].copy()
    total_fees = float(trades["fees"].sum()) if "fees" in trades.columns else 0.0
    gross_profit = float(closed[closed["realized_pnl"] > 0]["realized_pnl"].sum())
    total_pnl = float(closed["realized_pnl"].sum())

    fee_pct_of_gross = (total_fees / gross_profit * 100) if gross_profit > 0 else 0.0
    fee_pct_of_pnl   = (total_fees / abs(total_pnl) * 100) if total_pnl != 0 else 0.0

    return {
        "total_fees":         round(total_fees, 2),
        "gross_profit":       round(gross_profit, 2),
        "fee_pct_of_gross":   round(fee_pct_of_gross, 2),
        "fee_pct_of_net_pnl": round(fee_pct_of_pnl, 2),
        "insight": (
            f"Fees consumed {fee_pct_of_gross:.1f}% of your gross profit."
            if gross_profit > 0 else "No gross profit to compare fees against."
        ),
    }


# -- Overall Summary -----------------------------------------------------------


def compute_overall_summary(
    trades: pd.DataFrame,
    monthly: List[Dict[str, Any]],
    broker: str,
) -> Dict[str, Any]:
    """
    Top-level summary statistics across the entire trade history.
    """
    closed = trades[trades["realized_pnl"].notna()].copy()
    all_pnls = closed["realized_pnl"].tolist() if not closed.empty else []
    wins   = [p for p in all_pnls if p > 0]
    losses = [p for p in all_pnls if p <= 0]

    date_range_start = trades["date"].min().strftime("%d %b %Y") if not trades.empty else "N/A"
    date_range_end   = trades["date"].max().strftime("%d %b %Y") if not trades.empty else "N/A"

    total_pnl      = round(sum(all_pnls), 2)
    gross_profit   = round(sum(wins), 2)
    gross_loss     = round(sum(losses), 2)
    win_rate       = round(len(wins) / len(all_pnls) * 100, 1) if all_pnls else 0.0
    profit_factor  = round(gross_profit / abs(gross_loss), 2) if gross_loss != 0 else None
    avg_win        = round(sum(wins) / len(wins), 2) if wins else 0.0
    avg_loss       = round(sum(losses) / len(losses), 2) if losses else 0.0
    best_trade_pnl = round(max(all_pnls), 2) if all_pnls else 0.0
    worst_trade_pnl= round(min(all_pnls), 2) if all_pnls else 0.0
    total_fees     = round(float(trades["fees"].sum()), 2) if "fees" in trades.columns else 0.0

    broker_info = BROKER_SCHEMAS.get(broker, {})
    currency    = broker_info.get("currency", "USD")
    broker_name = broker_info.get("display_name", "Unknown Broker")

    return {
        "broker":           broker_name,
        "currency":         currency,
        "date_range_start": date_range_start,
        "date_range_end":   date_range_end,
        "total_trades":     len(all_pnls),
        "total_buy_trades": int((trades["side"] == "BUY").sum()),
        "total_sell_trades":int((trades["side"] == "SELL").sum()),
        "unique_symbols":   int(trades["symbol"].nunique()),
        "total_pnl":        total_pnl,
        "gross_profit":     gross_profit,
        "gross_loss":       gross_loss,
        "win_rate":         win_rate,
        "win_count":        len(wins),
        "loss_count":       len(losses),
        "profit_factor":    profit_factor,
        "avg_win":          avg_win,
        "avg_loss":         avg_loss,
        "best_trade_pnl":   best_trade_pnl,
        "worst_trade_pnl":  worst_trade_pnl,
        "total_fees":       total_fees,
        "months_active":    len(monthly),
    }


# -- LLM Narrative Generation --------------------------------------------------


@traceable(name="trade-analyzer-narrative", as_type="generation")
def generate_review_narrative(
    summary: Dict[str, Any],
    monthly: List[Dict[str, Any]],
    overtrading_flags: List[Dict[str, Any]],
    consistency: Dict[str, Any],
    symbol_breakdown: List[Dict[str, Any]],
    holding_analysis: Dict[str, Any],
    fee_drag: Dict[str, Any],
    trader_name: str,
    review_period: str,
) -> str:
    """
    Build the LLM prompt context and call generate_response.
    The LLM only writes narrative — all numbers come from pre-computed stats.
    """
    from llm_factory import generate_response

    currency = summary.get("currency", "USD")
    curr_sym = "?" if currency == "INR" else ("£" if currency == "GBP" else ("€" if currency == "EUR" else "$"))

    context = {
        "trader_name":       trader_name,
        "review_period":     review_period,
        "broker":            summary.get("broker"),
        "currency":          currency,
        "currency_symbol":   curr_sym,
        "summary":           summary,
        "monthly_breakdown": monthly,
        "overtrading_flags": overtrading_flags,
        "consistency_score": consistency,
        "top_symbols":       symbol_breakdown[:5],
        "bottom_symbols":    symbol_breakdown[-3:] if len(symbol_breakdown) >= 3 else [],
        "holding_analysis":  holding_analysis,
        "fee_drag":          fee_drag,
    }

    prompt = f"""You are a trading coach writing a brokerage account review for a retail trader.

IMPORTANT: Use ONLY the numbers provided below. Do NOT invent, estimate, or hallucinate any figures.
Write in plain English. Be honest, direct, and constructive. Avoid jargon.

Trader: {trader_name}
Period: {review_period}
Broker: {summary.get('broker')}
Currency: {currency} ({curr_sym})

=== COMPUTED STATISTICS ===
{json.dumps(context, indent=2, default=str)}
=== END STATISTICS ===

Write a brokerage account review with these 4 sections. Use markdown headings (##).

## Overall Performance
2-3 sentences summarising total P&L, win rate, and profit factor. Be direct — if they lost money, say so clearly but constructively.

## Monthly Breakdown
Describe the month-by-month pattern. Highlight the best and worst months. If there are overtrading flags, explain them in plain English (e.g. "In February you placed X trades but only won Y% of them — this looks like revenge trading after early losses.").

## What's Working & What Isn't
Based on the symbol breakdown and holding period data, identify 2-3 specific strengths and 2-3 specific weaknesses. Be concrete — reference actual symbols or patterns from the data.

## Recommendations
3-5 actionable, specific recommendations based on the data. Each should be one sentence. Focus on the biggest issues: overtrading, holding losers too long, position sizing inconsistency, fee drag, etc.

Keep the total response under 500 words. Do not add a disclaimer or sign-off."""

    try:
        return generate_response(prompt)
    except Exception as e:
        return f"[Narrative generation failed: {e}]"


# -- Public Entry Point --------------------------------------------------------


@traceable(name="run-trade-analyzer", as_type="chain")
def run_trade_review(
    file_bytes: bytes,
    filename: str,
    trader_name: str = "Trader",
    review_period: str = "",
) -> Dict[str, Any]:
    """
    Main entry point called by the FastAPI endpoint.

    Args:
        file_bytes:    Raw bytes of the uploaded CSV/Excel file
        filename:      Original filename (for extension detection)
        trader_name:   Trader's name for the report
        review_period: e.g. "Jan–Mar 2026" (auto-detected if empty)

    Returns:
        Full review dict with summary, monthly, overtrading, consistency,
        symbols, holding, fee_drag, narrative, broker, detected_broker
    """
    # 1. Parse file
    ext = filename.lower().rsplit(".", 1)[-1]
    try:
        if ext in ("xlsx", "xls", "xlsm"):
            xl = pd.ExcelFile(io.BytesIO(file_bytes))
            df = xl.parse(xl.sheet_names[0], header=0)
        elif ext == "csv":
            df = pd.read_csv(io.BytesIO(file_bytes))
        else:
            raise ValueError(f"Unsupported file type '.{ext}'. Please upload a CSV or Excel file.")
    except Exception as e:
        raise ValueError(f"Failed to parse file '{filename}': {e}")

    if df.empty:
        raise ValueError("The uploaded file contains no data.")

    # 2. Detect broker & normalize
    broker = detect_broker(df)
    try:
        trades = normalize_trades(df, broker)
    except ValueError as e:
        raise ValueError(f"Could not read trade data: {e}")

    if trades.empty:
        raise ValueError(
            "No valid BUY/SELL trades found in the file. "
            "This tool works with any broker — your CSV just needs columns for "
            "date, symbol, side (buy/sell), quantity, and price. "
            "Check that the side/action column contains values like BUY/SELL, B/S, bought/sold, or purchase/sale."
        )

    # 3. FIFO P&L
    trades = compute_pnl_fifo(trades)

    closed_count = int(trades["realized_pnl"].notna().sum())
    if closed_count == 0:
        raise ValueError(
            "No closed trades found (no matched BUY/SELL pairs). "
            "The file may contain only open positions or only one side of trades."
        )

    # 4. Compute all analytics
    monthly          = compute_monthly_breakdown(trades)
    overtrading      = detect_overtrading(trades, monthly)
    consistency      = compute_consistency_score(monthly, trades)
    symbol_breakdown = compute_symbol_breakdown(trades)
    holding          = compute_holding_analysis(trades)
    dow_pattern      = compute_dow_pattern(trades)
    fee_drag         = compute_fee_drag(trades)
    summary          = compute_overall_summary(trades, monthly, broker)

    # 5. Auto-detect review period if not provided
    if not review_period and monthly:
        if len(monthly) == 1:
            review_period = monthly[0]["month_label"]
        else:
            review_period = f"{monthly[0]['month_label']} – {monthly[-1]['month_label']}"

    # 6. LLM narrative
    narrative = generate_review_narrative(
        summary=summary,
        monthly=monthly,
        overtrading_flags=overtrading,
        consistency=consistency,
        symbol_breakdown=symbol_breakdown,
        holding_analysis=holding,
        fee_drag=fee_drag,
        trader_name=trader_name,
        review_period=review_period,
    )

    return {
        "detected_broker":   broker,
        "broker_display":    BROKER_SCHEMAS.get(broker, {}).get("display_name", "Generic"),
        "trader_name":       trader_name,
        "review_period":     review_period,
        "summary":           summary,
        "monthly_breakdown": monthly,
        "overtrading_flags": overtrading,
        "consistency_score": consistency,
        "symbol_breakdown":  symbol_breakdown,
        "holding_analysis":  holding,
        "dow_pattern":       dow_pattern,
        "fee_drag":          fee_drag,
        "narrative":         narrative,
        "total_rows_parsed": len(df),
        "closed_trades":     closed_count,
    }
