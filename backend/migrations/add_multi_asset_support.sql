-- Multi-Asset Support Database Schema
-- ===================================
-- Adds support for Forex, Options, Futures, and Crypto data

-- ── Forex Data ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS forex_rates (
    pair TEXT PRIMARY KEY,
    bid FLOAT,
    ask FLOAT,
    spread FLOAT,
    last_price FLOAT,
    change FLOAT,
    change_pct FLOAT,
    volume BIGINT,
    high_24h FLOAT,
    low_24h FLOAT,
    base_currency TEXT,
    quote_currency TEXT,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_forex_rates_updated_at ON forex_rates (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_forex_rates_base_quote ON forex_rates (base_currency, quote_currency);

-- ── Forex Historical Data ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS forex_ohlcv (
    pair TEXT NOT NULL,
    date DATE NOT NULL,
    open FLOAT,
    high FLOAT,
    low FLOAT,
    close FLOAT,
    volume BIGINT,
    PRIMARY KEY (pair, date)
);

CREATE INDEX IF NOT EXISTS idx_forex_ohlcv_pair_date ON forex_ohlcv (pair, date DESC);

-- ── Options Data ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS options_chains (
    underlying TEXT NOT NULL,
    expiry DATE NOT NULL,
    strike FLOAT NOT NULL,
    option_type TEXT NOT NULL, -- 'call' or 'put'
    bid FLOAT,
    ask FLOAT,
    last FLOAT,
    change FLOAT,
    change_pct FLOAT,
    volume BIGINT,
    open_interest BIGINT,
    implied_volatility FLOAT,
    delta FLOAT,
    gamma FLOAT,
    theta FLOAT,
    vega FLOAT,
    rho FLOAT,
    intrinsic_value FLOAT,
    time_value FLOAT,
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (underlying, expiry, strike, option_type)
);

-- Indexes for options queries
CREATE INDEX IF NOT EXISTS idx_options_underlying_expiry ON options_chains (underlying, expiry);
CREATE INDEX IF NOT EXISTS idx_options_expiry_date ON options_chains (expiry);
CREATE INDEX IF NOT EXISTS idx_options_updated_at ON options_chains (updated_at DESC);

-- ── Options Volatility Surface ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS options_iv_surface (
    underlying TEXT NOT NULL,
    date DATE NOT NULL,
    expiry DATE NOT NULL,
    strike FLOAT NOT NULL,
    option_type TEXT NOT NULL,
    implied_volatility FLOAT,
    delta FLOAT,
    moneyness FLOAT, -- strike / spot price
    time_to_expiry FLOAT, -- in years
    PRIMARY KEY (underlying, date, expiry, strike, option_type)
);

CREATE INDEX IF NOT EXISTS idx_iv_surface_underlying_date ON options_iv_surface (underlying, date DESC);

-- ── Futures Data ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS futures_data (
    symbol TEXT NOT NULL,
    contract_month TEXT NOT NULL,
    last_price FLOAT,
    change FLOAT,
    change_pct FLOAT,
    volume BIGINT,
    open_interest BIGINT,
    settlement FLOAT,
    high FLOAT,
    low FLOAT,
    contract_type TEXT, -- 'index', 'commodity', 'currency', 'bond'
    expiry_date DATE,
    tick_size FLOAT,
    tick_value FLOAT,
    margin_requirement FLOAT,
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (symbol, contract_month)
);

-- Indexes for futures queries
CREATE INDEX IF NOT EXISTS idx_futures_symbol ON futures_data (symbol);
CREATE INDEX IF NOT EXISTS idx_futures_contract_type ON futures_data (contract_type);
CREATE INDEX IF NOT EXISTS idx_futures_expiry ON futures_data (expiry_date);
CREATE INDEX IF NOT EXISTS idx_futures_updated_at ON futures_data (updated_at DESC);

-- ── Futures Historical Data ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS futures_ohlcv (
    symbol TEXT NOT NULL,
    contract_month TEXT NOT NULL,
    date DATE NOT NULL,
    open FLOAT,
    high FLOAT,
    low FLOAT,
    close FLOAT,
    volume BIGINT,
    open_interest BIGINT,
    PRIMARY KEY (symbol, contract_month, date)
);

CREATE INDEX IF NOT EXISTS idx_futures_ohlcv_symbol_date ON futures_ohlcv (symbol, contract_month, date DESC);

-- ── Futures Curve Data ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS futures_curves (
    symbol TEXT NOT NULL,
    date DATE NOT NULL,
    contract_month TEXT NOT NULL,
    price FLOAT,
    days_to_expiry INTEGER,
    is_front_month BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (symbol, date, contract_month)
);

CREATE INDEX IF NOT EXISTS idx_futures_curves_symbol_date ON futures_curves (symbol, date DESC);

-- ── Cryptocurrency Data ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS crypto_data (
    symbol TEXT PRIMARY KEY, -- BTC-USD, ETH-USD, etc.
    name TEXT,
    last_price FLOAT,
    change_24h FLOAT,
    change_pct_24h FLOAT,
    volume_24h FLOAT,
    market_cap FLOAT,
    high_24h FLOAT,
    low_24h FLOAT,
    circulating_supply FLOAT,
    total_supply FLOAT,
    max_supply FLOAT,
    base_currency TEXT,
    quote_currency TEXT,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_crypto_updated_at ON crypto_data (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_crypto_market_cap ON crypto_data (market_cap DESC);

-- ── Crypto Historical Data ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS crypto_ohlcv (
    symbol TEXT NOT NULL,
    date DATE NOT NULL,
    open FLOAT,
    high FLOAT,
    low FLOAT,
    close FLOAT,
    volume FLOAT,
    market_cap FLOAT,
    PRIMARY KEY (symbol, date)
);

CREATE INDEX IF NOT EXISTS idx_crypto_ohlcv_symbol_date ON crypto_ohlcv (symbol, date DESC);

-- ── Economic Indicators (for Forex analysis) ──────────────────────────────────

CREATE TABLE IF NOT EXISTS economic_indicators (
    country TEXT NOT NULL,
    indicator TEXT NOT NULL,
    release_date DATE NOT NULL,
    value FLOAT,
    previous_value FLOAT,
    forecast FLOAT,
    impact TEXT, -- 'high', 'medium', 'low'
    unit TEXT,
    frequency TEXT, -- 'monthly', 'quarterly', 'yearly'
    source TEXT,
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (country, indicator, release_date)
);

CREATE INDEX IF NOT EXISTS idx_economic_indicators_country ON economic_indicators (country, release_date DESC);
CREATE INDEX IF NOT EXISTS idx_economic_indicators_impact ON economic_indicators (impact, release_date DESC);

-- ── Central Bank Rates ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS central_bank_rates (
    country TEXT NOT NULL,
    currency TEXT NOT NULL,
    rate_type TEXT NOT NULL, -- 'policy_rate', 'discount_rate', etc.
    rate FLOAT,
    previous_rate FLOAT,
    change_date DATE,
    next_meeting_date DATE,
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (country, currency, rate_type)
);

CREATE INDEX IF NOT EXISTS idx_cb_rates_currency ON central_bank_rates (currency, change_date DESC);

-- ── Multi-Asset Technicals Cache ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS multi_asset_technicals (
    symbol TEXT NOT NULL,
    asset_type TEXT NOT NULL, -- 'stock', 'forex', 'crypto', 'futures'
    sma9 FLOAT,
    sma20 FLOAT,
    sma21 FLOAT,
    sma50 FLOAT,
    sma200 FLOAT,
    ema8 FLOAT,
    ema9 FLOAT,
    ema20 FLOAT,
    ema21 FLOAT,
    ema50 FLOAT,
    rsi FLOAT,
    stoch_k FLOAT,
    stoch_d FLOAT,
    macd FLOAT,
    macd_signal FLOAT,
    macd_hist FLOAT,
    bb_upper FLOAT,
    bb_lower FLOAT,
    bb_mid FLOAT,
    atr FLOAT,
    avg_vol20 FLOAT,
    vol_ratio FLOAT,
    high52 FLOAT,
    low52 FLOAT,
    pct_from_52w_high FLOAT,
    pct_from_52w_low FLOAT,
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (symbol, asset_type)
);

CREATE INDEX IF NOT EXISTS idx_multi_asset_technicals_type ON multi_asset_technicals (asset_type, updated_at DESC);

-- ── Asset Metadata ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS asset_metadata (
    symbol TEXT PRIMARY KEY,
    asset_type TEXT NOT NULL,
    name TEXT,
    description TEXT,
    exchange TEXT,
    sector TEXT,
    industry TEXT,
    country TEXT,
    currency TEXT,
    timezone TEXT,
    market_hours JSONB, -- {"open": "09:30", "close": "16:00", "timezone": "America/New_York"}
    tick_size FLOAT,
    min_quantity FLOAT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_asset_metadata_type ON asset_metadata (asset_type);
CREATE INDEX IF NOT EXISTS idx_asset_metadata_exchange ON asset_metadata (exchange);

-- ── Cross-Asset Correlations ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS asset_correlations (
    symbol1 TEXT NOT NULL,
    symbol2 TEXT NOT NULL,
    asset_type1 TEXT NOT NULL,
    asset_type2 TEXT NOT NULL,
    correlation_1d FLOAT,
    correlation_7d FLOAT,
    correlation_30d FLOAT,
    correlation_90d FLOAT,
    correlation_1y FLOAT,
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (symbol1, symbol2)
);

CREATE INDEX IF NOT EXISTS idx_correlations_symbol1 ON asset_correlations (symbol1, correlation_30d DESC);

-- ── Market Sessions ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS market_sessions (
    market TEXT PRIMARY KEY,
    timezone TEXT NOT NULL,
    open_time TIME NOT NULL,
    close_time TIME NOT NULL,
    days_of_week INTEGER[], -- [1,2,3,4,5] for Mon-Fri
    holidays JSONB, -- Array of holiday dates
    is_active BOOLEAN DEFAULT TRUE
);

-- Insert default market sessions
INSERT INTO market_sessions (market, timezone, open_time, close_time, days_of_week) VALUES
('NYSE', 'America/New_York', '09:30:00', '16:00:00', ARRAY[1,2,3,4,5]),
('NASDAQ', 'America/New_York', '09:30:00', '16:00:00', ARRAY[1,2,3,4,5]),
('LSE', 'Europe/London', '08:00:00', '16:30:00', ARRAY[1,2,3,4,5]),
('NSE', 'Asia/Kolkata', '09:15:00', '15:30:00', ARRAY[1,2,3,4,5]),
('TSE', 'Asia/Tokyo', '09:00:00', '15:00:00', ARRAY[1,2,3,4,5]),
('FOREX', 'UTC', '00:00:00', '23:59:59', ARRAY[1,2,3,4,5,6,7]),
('CRYPTO', 'UTC', '00:00:00', '23:59:59', ARRAY[1,2,3,4,5,6,7])
ON CONFLICT (market) DO NOTHING;

-- ── Views for Easy Querying ───────────────────────────────────────────────────

-- Latest forex rates with metadata
CREATE OR REPLACE VIEW v_forex_latest AS
SELECT 
    fr.*,
    am.name,
    am.description,
    am.tick_size
FROM forex_rates fr
LEFT JOIN asset_metadata am ON fr.pair = am.symbol
WHERE fr.updated_at > NOW() - INTERVAL '1 hour';

-- Active options chains
CREATE OR REPLACE VIEW v_options_active AS
SELECT 
    oc.*,
    am.name as underlying_name
FROM options_chains oc
LEFT JOIN asset_metadata am ON oc.underlying = am.symbol
WHERE oc.expiry >= CURRENT_DATE
AND oc.updated_at > NOW() - INTERVAL '4 hours';

-- Active futures contracts
CREATE OR REPLACE VIEW v_futures_active AS
SELECT 
    fd.*,
    am.name,
    am.description
FROM futures_data fd
LEFT JOIN asset_metadata am ON fd.symbol = am.symbol
WHERE (fd.expiry_date IS NULL OR fd.expiry_date >= CURRENT_DATE)
AND fd.updated_at > NOW() - INTERVAL '1 hour';

-- Latest crypto prices
CREATE OR REPLACE VIEW v_crypto_latest AS
SELECT 
    cd.*,
    am.description
FROM crypto_data cd
LEFT JOIN asset_metadata am ON cd.symbol = am.symbol
WHERE cd.updated_at > NOW() - INTERVAL '5 minutes';

-- ── Functions for Data Management ─────────────────────────────────────────────

-- Function to clean old data
CREATE OR REPLACE FUNCTION clean_old_market_data()
RETURNS void AS $$
BEGIN
    -- Keep only last 2 years of OHLCV data
    DELETE FROM forex_ohlcv WHERE date < CURRENT_DATE - INTERVAL '2 years';
    DELETE FROM futures_ohlcv WHERE date < CURRENT_DATE - INTERVAL '2 years';
    DELETE FROM crypto_ohlcv WHERE date < CURRENT_DATE - INTERVAL '2 years';
    
    -- Keep only last 6 months of options data
    DELETE FROM options_chains WHERE expiry < CURRENT_DATE - INTERVAL '6 months';
    DELETE FROM options_iv_surface WHERE date < CURRENT_DATE - INTERVAL '6 months';
    
    -- Keep only last 1 year of economic indicators
    DELETE FROM economic_indicators WHERE release_date < CURRENT_DATE - INTERVAL '1 year';
    
    -- Keep only last 30 days of real-time rates
    DELETE FROM forex_rates WHERE updated_at < NOW() - INTERVAL '30 days';
    DELETE FROM crypto_data WHERE updated_at < NOW() - INTERVAL '30 days';
    DELETE FROM futures_data WHERE updated_at < NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;

-- Function to update asset metadata
CREATE OR REPLACE FUNCTION upsert_asset_metadata(
    p_symbol TEXT,
    p_asset_type TEXT,
    p_name TEXT DEFAULT NULL,
    p_exchange TEXT DEFAULT NULL,
    p_currency TEXT DEFAULT NULL
)
RETURNS void AS $$
BEGIN
    INSERT INTO asset_metadata (symbol, asset_type, name, exchange, currency, updated_at)
    VALUES (p_symbol, p_asset_type, p_name, p_exchange, p_currency, NOW())
    ON CONFLICT (symbol) 
    DO UPDATE SET
        name = COALESCE(EXCLUDED.name, asset_metadata.name),
        exchange = COALESCE(EXCLUDED.exchange, asset_metadata.exchange),
        currency = COALESCE(EXCLUDED.currency, asset_metadata.currency),
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- ── Triggers for Automatic Updates ────────────────────────────────────────────

-- Update timestamp trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers to relevant tables
CREATE TRIGGER update_forex_rates_updated_at 
    BEFORE UPDATE ON forex_rates 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_options_chains_updated_at 
    BEFORE UPDATE ON options_chains 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_futures_data_updated_at 
    BEFORE UPDATE ON futures_data 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_crypto_data_updated_at 
    BEFORE UPDATE ON crypto_data 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ── Sample Data for Testing ───────────────────────────────────────────────────

-- Insert sample asset metadata
INSERT INTO asset_metadata (symbol, asset_type, name, exchange, currency) VALUES
('EUR/USD', 'forex', 'Euro / US Dollar', 'FOREX', 'USD'),
('GBP/USD', 'forex', 'British Pound / US Dollar', 'FOREX', 'USD'),
('USD/JPY', 'forex', 'US Dollar / Japanese Yen', 'FOREX', 'JPY'),
('/ES', 'futures', 'E-mini S&P 500 Futures', 'CME', 'USD'),
('/GC', 'futures', 'Gold Futures', 'COMEX', 'USD'),
('/CL', 'futures', 'Crude Oil Futures', 'NYMEX', 'USD'),
('BTC-USD', 'crypto', 'Bitcoin', 'CRYPTO', 'USD'),
('ETH-USD', 'crypto', 'Ethereum', 'CRYPTO', 'USD')
ON CONFLICT (symbol) DO NOTHING;

-- Insert sample market sessions
INSERT INTO market_sessions (market, timezone, open_time, close_time, days_of_week) VALUES
('CME', 'America/Chicago', '17:00:00', '16:00:00', ARRAY[1,2,3,4,5]),
('COMEX', 'America/New_York', '18:00:00', '17:00:00', ARRAY[1,2,3,4,5]),
('NYMEX', 'America/New_York', '18:00:00', '17:00:00', ARRAY[1,2,3,4,5])
ON CONFLICT (market) DO NOTHING;

COMMIT;