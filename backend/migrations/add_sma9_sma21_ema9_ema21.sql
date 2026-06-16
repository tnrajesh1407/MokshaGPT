-- Migration: add SMA 9, SMA 21, EMA 9, EMA 21 to stock_technicals
-- Run once in Supabase SQL Editor

ALTER TABLE stock_technicals
    ADD COLUMN IF NOT EXISTS sma9  FLOAT,
    ADD COLUMN IF NOT EXISTS sma21 FLOAT,
    ADD COLUMN IF NOT EXISTS ema9  FLOAT,
    ADD COLUMN IF NOT EXISTS ema21 FLOAT;