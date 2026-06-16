-- Run in Supabase SQL Editor
-- Drop and recreate all three tables cleanly with correct ownership and RLS

DROP TABLE IF EXISTS stock_technicals;
DROP TABLE IF EXISTS stock_ohlcv;
DROP TABLE IF EXISTS stock_fundamentals;

-- Technicals (latest snapshot per ticker)
CREATE TABLE stock_technicals (
    ticker            TEXT PRIMARY KEY,
    sma20             FLOAT,
    sma50             FLOAT,
    sma200            FLOAT,
    ema8              FLOAT,
    ema20             FLOAT,
    ema50             FLOAT,
    rsi               FLOAT,
    stoch_k           FLOAT,
    stoch_d           FLOAT,
    macd              FLOAT,
    macd_signal       FLOAT,
    macd_hist         FLOAT,
    bb_upper          FLOAT,
    bb_lower          FLOAT,
    bb_mid            FLOAT,
    avg_vol20         FLOAT,
    vol_ratio         FLOAT,
    high52            FLOAT,
    low52             FLOAT,
    pct_from_52w_high FLOAT,
    pct_from_52w_low  FLOAT,
    std_pp            FLOAT,
    std_r1            FLOAT,
    std_r2            FLOAT,
    std_r3            FLOAT,
    std_s1            FLOAT,
    std_s2            FLOAT,
    std_s3            FLOAT,
    cpr_pp            FLOAT,
    cpr_tc            FLOAT,
    cpr_bc            FLOAT,
    cam_h1            FLOAT,
    cam_h2            FLOAT,
    cam_h3            FLOAT,
    cam_h4            FLOAT,
    cam_l1            FLOAT,
    cam_l2            FLOAT,
    cam_l3            FLOAT,
    cam_l4            FLOAT,
    updated_at        TIMESTAMPTZ DEFAULT now()
);

-- OHLCV daily history (2 years, used by backtester)
CREATE TABLE stock_ohlcv (
    ticker  TEXT   NOT NULL,
    date    DATE   NOT NULL,
    open    FLOAT,
    high    FLOAT,
    low     FLOAT,
    close   FLOAT,
    volume  BIGINT,
    PRIMARY KEY (ticker, date)
);
CREATE INDEX idx_stock_ohlcv_ticker_date ON stock_ohlcv (ticker, date DESC);

-- Fundamentals (slow-moving, refreshed daily)
CREATE TABLE stock_fundamentals (
    ticker          TEXT PRIMARY KEY,
    name            TEXT,
    sector          TEXT,
    industry        TEXT,
    market_cap      FLOAT,
    trailing_pe     FLOAT,
    forward_pe      FLOAT,
    dividend_yield  FLOAT,
    beta            FLOAT,
    revenue_growth  FLOAT,
    debt_to_equity  FLOAT,
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Enable RLS
ALTER TABLE stock_technicals  ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_ohlcv        ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_fundamentals ENABLE ROW LEVEL SECURITY;

-- service_role has full access (used by backend)
GRANT ALL ON stock_technicals  TO service_role;
GRANT ALL ON stock_ohlcv        TO service_role;
GRANT ALL ON stock_fundamentals TO service_role;

-- Block anon key access
REVOKE ALL ON stock_technicals  FROM anon;
REVOKE ALL ON stock_ohlcv        FROM anon;
REVOKE ALL ON stock_fundamentals FROM anon;
