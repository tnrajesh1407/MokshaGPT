"""
Forex Data Module
─────────────────
Handles forex data fetching, caching, and analysis.
Supports major, minor, and exotic currency pairs.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
import requests
import json
from dataclasses import dataclass

from supabase_cache import _get_client


@dataclass
class ForexRate:
    pair: str
    bid: float
    ask: float
    last_price: float
    change: float
    change_pct: float
    volume: int
    high_24h: float
    low_24h: float
    spread: float
    base_currency: str
    quote_currency: str
    timestamp: datetime


class ForexDataProvider:
    """Forex data provider with multiple data sources and caching."""
    
    def __init__(self):
        self.major_pairs = [
            'EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 
            'USD/CAD', 'USD/CHF', 'NZD/USD'
        ]
        
        self.minor_pairs = [
            'EUR/GBP', 'EUR/JPY', 'GBP/JPY', 'EUR/CHF',
            'EUR/AUD', 'GBP/AUD', 'AUD/JPY', 'CAD/JPY'
        ]
        
        self.exotic_pairs = [
            'USD/TRY', 'USD/ZAR', 'USD/MXN', 'USD/BRL',
            'USD/INR', 'USD/CNY', 'USD/SGD', 'USD/HKD'
        ]
        
        self.all_pairs = self.major_pairs + self.minor_pairs + self.exotic_pairs
        
        # Currency symbols for yfinance (append =X)
        self.yf_symbols = {
            pair.replace('/', ''): f"{pair.replace('/', '')}=X" 
            for pair in self.all_pairs
        }

    def get_forex_rate(self, pair: str, use_cache: bool = True) -> Optional[ForexRate]:
        """
        Get current forex rate for a currency pair.
        
        Args:
            pair: Currency pair (e.g., 'EUR/USD' or 'EURUSD')
            use_cache: Whether to use cached data
            
        Returns:
            ForexRate object or None if not found
        """
        # Normalize pair format
        normalized_pair = self._normalize_pair(pair)
        
        if use_cache:
            cached_rate = self._get_cached_rate(normalized_pair)
            if cached_rate:
                return cached_rate
        
        # Fetch from yfinance
        rate = self._fetch_from_yfinance(normalized_pair)
        if rate:
            self._cache_rate(rate)
            return rate
        
        return None

    def get_multiple_rates(self, pairs: List[str], use_cache: bool = True) -> Dict[str, Optional[ForexRate]]:
        """Get rates for multiple currency pairs efficiently."""
        results = {}
        pairs_to_fetch = []
        
        # Check cache first
        for pair in pairs:
            normalized_pair = self._normalize_pair(pair)
            if use_cache:
                cached_rate = self._get_cached_rate(normalized_pair)
                if cached_rate:
                    results[normalized_pair] = cached_rate
                    continue
            pairs_to_fetch.append(normalized_pair)
        
        # Batch fetch remaining pairs
        if pairs_to_fetch:
            batch_results = self._batch_fetch_yfinance(pairs_to_fetch)
            results.update(batch_results)
            
            # Cache the results
            for rate in batch_results.values():
                if rate:
                    self._cache_rate(rate)
        
        return results

    def get_forex_history(self, pair: str, period: str = "1y", interval: str = "1d") -> Optional[pd.DataFrame]:
        """
        Get historical forex data.
        
        Args:
            pair: Currency pair
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
            
        Returns:
            DataFrame with OHLCV data
        """
        normalized_pair = self._normalize_pair(pair)
        yf_symbol = self._get_yf_symbol(normalized_pair)
        
        if not yf_symbol:
            return None
        
        try:
            ticker = yf.Ticker(yf_symbol)
            hist = ticker.history(period=period, interval=interval)
            
            if hist.empty:
                return None
            
            # Add pair column for identification
            hist['Pair'] = normalized_pair
            
            return hist
            
        except Exception as e:
            print(f"[ForexData] Error fetching history for {pair}: {e}")
            return None

    def compute_forex_technicals(self, pair: str, period: str = "1y") -> Optional[Dict[str, Any]]:
        """Compute technical indicators for a forex pair."""
        hist = self.get_forex_history(pair, period=period)
        if hist is None or len(hist) < 50:
            return None
        
        try:
            close = hist['Close']
            high = hist['High']
            low = hist['Low']
            volume = hist.get('Volume', pd.Series([0] * len(hist)))
            
            # Moving averages
            sma20 = close.rolling(20).mean().iloc[-1]
            sma50 = close.rolling(50).mean().iloc[-1]
            ema20 = close.ewm(span=20).mean().iloc[-1]
            ema50 = close.ewm(span=50).mean().iloc[-1]
            
            # RSI
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss.replace(0, np.nan)
            rsi = (100 - 100 / (1 + rs)).iloc[-1]
            
            # MACD
            ema12 = close.ewm(span=12).mean()
            ema26 = close.ewm(span=26).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9).mean()
            macd = macd_line.iloc[-1]
            macd_signal = signal_line.iloc[-1]
            macd_hist = (macd_line - signal_line).iloc[-1]
            
            # Bollinger Bands
            bb_mid = close.rolling(20).mean()
            bb_std = close.rolling(20).std()
            bb_upper = (bb_mid + 2 * bb_std).iloc[-1]
            bb_lower = (bb_mid - 2 * bb_std).iloc[-1]
            bb_mid_val = bb_mid.iloc[-1]
            
            # ATR (Average True Range)
            tr1 = high - low
            tr2 = (high - close.shift(1)).abs()
            tr3 = (low - close.shift(1)).abs()
            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = true_range.rolling(14).mean().iloc[-1]
            
            # Support/Resistance levels (pivot points)
            prev_high = high.iloc[-2]
            prev_low = low.iloc[-2]
            prev_close = close.iloc[-2]
            
            pivot = (prev_high + prev_low + prev_close) / 3
            r1 = 2 * pivot - prev_low
            s1 = 2 * pivot - prev_high
            r2 = pivot + (prev_high - prev_low)
            s2 = pivot - (prev_high - prev_low)
            
            # Price levels
            current_price = close.iloc[-1]
            high_52w = close.rolling(252).max().iloc[-1] if len(close) >= 252 else close.max()
            low_52w = close.rolling(252).min().iloc[-1] if len(close) >= 252 else close.min()
            
            return {
                'pair': pair,
                'current_price': float(current_price),
                'sma20': float(sma20) if not pd.isna(sma20) else None,
                'sma50': float(sma50) if not pd.isna(sma50) else None,
                'ema20': float(ema20) if not pd.isna(ema20) else None,
                'ema50': float(ema50) if not pd.isna(ema50) else None,
                'rsi': float(rsi) if not pd.isna(rsi) else None,
                'macd': float(macd) if not pd.isna(macd) else None,
                'macd_signal': float(macd_signal) if not pd.isna(macd_signal) else None,
                'macd_hist': float(macd_hist) if not pd.isna(macd_hist) else None,
                'bb_upper': float(bb_upper) if not pd.isna(bb_upper) else None,
                'bb_lower': float(bb_lower) if not pd.isna(bb_lower) else None,
                'bb_mid': float(bb_mid_val) if not pd.isna(bb_mid_val) else None,
                'atr': float(atr) if not pd.isna(atr) else None,
                'pivot': float(pivot) if not pd.isna(pivot) else None,
                'resistance_1': float(r1) if not pd.isna(r1) else None,
                'support_1': float(s1) if not pd.isna(s1) else None,
                'resistance_2': float(r2) if not pd.isna(r2) else None,
                'support_2': float(s2) if not pd.isna(s2) else None,
                'high_52w': float(high_52w) if not pd.isna(high_52w) else None,
                'low_52w': float(low_52w) if not pd.isna(low_52w) else None,
                'pct_from_52w_high': ((current_price - high_52w) / high_52w * 100) if high_52w else None,
                'pct_from_52w_low': ((current_price - low_52w) / low_52w * 100) if low_52w else None,
            }
            
        except Exception as e:
            print(f"[ForexData] Error computing technicals for {pair}: {e}")
            return None

    def get_economic_calendar(self, currency: str = None, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """
        Get upcoming economic events that might affect forex markets.
        This is a placeholder - in production, you'd integrate with an economic calendar API.
        """
        # Placeholder economic events
        events = [
            {
                'date': datetime.now() + timedelta(days=1),
                'currency': 'USD',
                'event': 'Federal Reserve Interest Rate Decision',
                'impact': 'high',
                'forecast': '5.25%',
                'previous': '5.00%'
            },
            {
                'date': datetime.now() + timedelta(days=3),
                'currency': 'EUR',
                'event': 'ECB Interest Rate Decision',
                'impact': 'high',
                'forecast': '4.50%',
                'previous': '4.25%'
            },
            {
                'date': datetime.now() + timedelta(days=5),
                'currency': 'GBP',
                'event': 'UK GDP Growth Rate',
                'impact': 'medium',
                'forecast': '0.2%',
                'previous': '0.1%'
            }
        ]
        
        if currency:
            events = [e for e in events if e['currency'] == currency.upper()]
        
        return events[:days_ahead]

    def analyze_forex_pair(self, pair: str) -> Dict[str, Any]:
        """Comprehensive forex pair analysis."""
        normalized_pair = self._normalize_pair(pair)
        
        # Get current rate
        current_rate = self.get_forex_rate(normalized_pair)
        if not current_rate:
            return {'error': f'Could not fetch data for {pair}'}
        
        # Get technical analysis
        technicals = self.compute_forex_technicals(normalized_pair)
        
        # Get economic events
        base_currency = normalized_pair.split('/')[0]
        quote_currency = normalized_pair.split('/')[1]
        base_events = self.get_economic_calendar(base_currency, days_ahead=7)
        quote_events = self.get_economic_calendar(quote_currency, days_ahead=7)
        
        # Determine trend
        trend = self._determine_trend(technicals) if technicals else 'neutral'
        
        # Generate signals
        signals = self._generate_signals(technicals) if technicals else []
        
        return {
            'pair': normalized_pair,
            'current_rate': {
                'bid': current_rate.bid,
                'ask': current_rate.ask,
                'last': current_rate.last_price,
                'change': current_rate.change,
                'change_pct': current_rate.change_pct,
                'spread': current_rate.spread,
                'volume': current_rate.volume
            },
            'technicals': technicals,
            'trend': trend,
            'signals': signals,
            'economic_events': {
                'base_currency': base_events,
                'quote_currency': quote_events
            },
            'analysis_timestamp': datetime.now(timezone.utc).isoformat()
        }

    def _normalize_pair(self, pair: str) -> str:
        """Normalize currency pair format to XXX/YYY."""
        # Remove spaces and convert to uppercase
        clean_pair = pair.replace(' ', '').upper()
        
        # Add slash if not present
        if '/' not in clean_pair and len(clean_pair) == 6:
            clean_pair = f"{clean_pair[:3]}/{clean_pair[3:]}"
        
        return clean_pair

    def _get_yf_symbol(self, pair: str) -> Optional[str]:
        """Get Yahoo Finance symbol for a currency pair."""
        pair_no_slash = pair.replace('/', '')
        return self.yf_symbols.get(pair_no_slash)

    def _fetch_from_yfinance(self, pair: str) -> Optional[ForexRate]:
        """Fetch forex rate from Yahoo Finance."""
        yf_symbol = self._get_yf_symbol(pair)
        if not yf_symbol:
            return None
        
        try:
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info
            hist = ticker.history(period="2d", interval="1d")
            
            if hist.empty:
                return None
            
            current_price = info.get('regularMarketPrice') or hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2] if len(hist) >= 2 else current_price
            
            change = current_price - prev_close
            change_pct = (change / prev_close * 100) if prev_close != 0 else 0
            
            # For forex, bid/ask spread is typically small
            spread = current_price * 0.0001  # Approximate spread
            bid = current_price - spread / 2
            ask = current_price + spread / 2
            
            base_currency, quote_currency = pair.split('/')
            
            return ForexRate(
                pair=pair,
                bid=bid,
                ask=ask,
                last_price=current_price,
                change=change,
                change_pct=change_pct,
                volume=info.get('regularMarketVolume', 0),
                high_24h=hist['High'].iloc[-1],
                low_24h=hist['Low'].iloc[-1],
                spread=spread,
                base_currency=base_currency,
                quote_currency=quote_currency,
                timestamp=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            print(f"[ForexData] Error fetching {pair} from yfinance: {e}")
            return None

    def _batch_fetch_yfinance(self, pairs: List[str]) -> Dict[str, Optional[ForexRate]]:
        """Batch fetch multiple forex rates from Yahoo Finance."""
        results = {}
        
        # Get yfinance symbols
        yf_symbols = []
        pair_symbol_map = {}
        
        for pair in pairs:
            yf_symbol = self._get_yf_symbol(pair)
            if yf_symbol:
                yf_symbols.append(yf_symbol)
                pair_symbol_map[yf_symbol] = pair
        
        if not yf_symbols:
            return {pair: None for pair in pairs}
        
        try:
            # Batch download
            data = yf.download(yf_symbols, period="2d", interval="1d", group_by="ticker", progress=False)
            
            for yf_symbol in yf_symbols:
                pair = pair_symbol_map[yf_symbol]
                
                try:
                    if len(yf_symbols) == 1:
                        symbol_data = data
                    else:
                        symbol_data = data[yf_symbol]
                    
                    if symbol_data.empty:
                        results[pair] = None
                        continue
                    
                    current_price = symbol_data['Close'].iloc[-1]
                    prev_close = symbol_data['Close'].iloc[-2] if len(symbol_data) >= 2 else current_price
                    
                    change = current_price - prev_close
                    change_pct = (change / prev_close * 100) if prev_close != 0 else 0
                    
                    spread = current_price * 0.0001
                    bid = current_price - spread / 2
                    ask = current_price + spread / 2
                    
                    base_currency, quote_currency = pair.split('/')
                    
                    results[pair] = ForexRate(
                        pair=pair,
                        bid=bid,
                        ask=ask,
                        last_price=current_price,
                        change=change,
                        change_pct=change_pct,
                        volume=0,  # Volume not available in batch mode
                        high_24h=symbol_data['High'].iloc[-1],
                        low_24h=symbol_data['Low'].iloc[-1],
                        spread=spread,
                        base_currency=base_currency,
                        quote_currency=quote_currency,
                        timestamp=datetime.now(timezone.utc)
                    )
                    
                except Exception as e:
                    print(f"[ForexData] Error processing {pair}: {e}")
                    results[pair] = None
            
        except Exception as e:
            print(f"[ForexData] Batch fetch error: {e}")
            return {pair: None for pair in pairs}
        
        return results

    def _get_cached_rate(self, pair: str) -> Optional[ForexRate]:
        """Get cached forex rate from Supabase."""
        client = _get_client()
        if not client:
            return None
        
        try:
            response = client.table('forex_rates').select('*').eq('pair', pair).execute()
            
            if not response.data:
                return None
            
            data = response.data[0]
            
            # Check if data is fresh (within 5 minutes)
            updated_at = datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00'))
            if datetime.now(timezone.utc) - updated_at > timedelta(minutes=5):
                return None
            
            return ForexRate(
                pair=data['pair'],
                bid=data['bid'],
                ask=data['ask'],
                last_price=data['last_price'],
                change=data['change'],
                change_pct=data['change_pct'],
                volume=data['volume'] or 0,
                high_24h=data['high_24h'],
                low_24h=data['low_24h'],
                spread=data['spread'],
                base_currency=data['base_currency'],
                quote_currency=data['quote_currency'],
                timestamp=updated_at
            )
            
        except Exception as e:
            print(f"[ForexData] Cache read error for {pair}: {e}")
            return None

    def _cache_rate(self, rate: ForexRate) -> bool:
        """Cache forex rate to Supabase."""
        client = _get_client()
        if not client:
            return False
        
        try:
            data = {
                'pair': rate.pair,
                'bid': rate.bid,
                'ask': rate.ask,
                'last_price': rate.last_price,
                'change': rate.change,
                'change_pct': rate.change_pct,
                'volume': rate.volume,
                'high_24h': rate.high_24h,
                'low_24h': rate.low_24h,
                'spread': rate.spread,
                'base_currency': rate.base_currency,
                'quote_currency': rate.quote_currency,
                'updated_at': rate.timestamp.isoformat()
            }
            
            client.table('forex_rates').upsert(data, on_conflict='pair').execute()
            return True
            
        except Exception as e:
            print(f"[ForexData] Cache write error for {rate.pair}: {e}")
            return False

    def _determine_trend(self, technicals: Dict[str, Any]) -> str:
        """Determine overall trend from technical indicators."""
        if not technicals:
            return 'neutral'
        
        signals = []
        current_price = technicals.get('current_price')
        
        # Price vs moving averages
        if current_price and technicals.get('sma20'):
            signals.append('bullish' if current_price > technicals['sma20'] else 'bearish')
        
        if current_price and technicals.get('sma50'):
            signals.append('bullish' if current_price > technicals['sma50'] else 'bearish')
        
        # MACD
        macd = technicals.get('macd')
        macd_signal = technicals.get('macd_signal')
        if macd and macd_signal:
            signals.append('bullish' if macd > macd_signal else 'bearish')
        
        # RSI
        rsi = technicals.get('rsi')
        if rsi:
            if rsi > 70:
                signals.append('bearish')  # Overbought
            elif rsi < 30:
                signals.append('bullish')  # Oversold
            else:
                signals.append('neutral')
        
        # Count signals
        bullish_count = signals.count('bullish')
        bearish_count = signals.count('bearish')
        
        if bullish_count > bearish_count:
            return 'bullish'
        elif bearish_count > bullish_count:
            return 'bearish'
        else:
            return 'neutral'

    def _generate_signals(self, technicals: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate trading signals from technical analysis."""
        if not technicals:
            return []
        
        signals = []
        current_price = technicals.get('current_price')
        
        # RSI signals
        rsi = technicals.get('rsi')
        if rsi:
            if rsi > 70:
                signals.append({
                    'type': 'sell',
                    'indicator': 'RSI',
                    'message': f'RSI overbought at {rsi:.1f}',
                    'strength': 'medium'
                })
            elif rsi < 30:
                signals.append({
                    'type': 'buy',
                    'indicator': 'RSI',
                    'message': f'RSI oversold at {rsi:.1f}',
                    'strength': 'medium'
                })
        
        # MACD signals
        macd = technicals.get('macd')
        macd_signal = technicals.get('macd_signal')
        if macd and macd_signal:
            if macd > macd_signal and macd > 0:
                signals.append({
                    'type': 'buy',
                    'indicator': 'MACD',
                    'message': 'MACD bullish crossover above zero',
                    'strength': 'strong'
                })
            elif macd < macd_signal and macd < 0:
                signals.append({
                    'type': 'sell',
                    'indicator': 'MACD',
                    'message': 'MACD bearish crossover below zero',
                    'strength': 'strong'
                })
        
        # Support/Resistance signals
        if current_price:
            support_1 = technicals.get('support_1')
            resistance_1 = technicals.get('resistance_1')
            
            if support_1 and abs(current_price - support_1) / support_1 < 0.001:  # Within 0.1%
                signals.append({
                    'type': 'buy',
                    'indicator': 'Support',
                    'message': f'Price near support level at {support_1:.5f}',
                    'strength': 'medium'
                })
            
            if resistance_1 and abs(current_price - resistance_1) / resistance_1 < 0.001:  # Within 0.1%
                signals.append({
                    'type': 'sell',
                    'indicator': 'Resistance',
                    'message': f'Price near resistance level at {resistance_1:.5f}',
                    'strength': 'medium'
                })
        
        return signals


# Convenience functions
def get_forex_rate(pair: str) -> Optional[ForexRate]:
    """Quick function to get a forex rate."""
    provider = ForexDataProvider()
    return provider.get_forex_rate(pair)


def analyze_forex_pair(pair: str) -> Dict[str, Any]:
    """Quick function to analyze a forex pair."""
    provider = ForexDataProvider()
    return provider.analyze_forex_pair(pair)


# Example usage
if __name__ == "__main__":
    provider = ForexDataProvider()
    
    # Test single pair
    rate = provider.get_forex_rate("EUR/USD")
    if rate:
        print(f"EUR/USD: {rate.last_price:.5f} ({rate.change_pct:+.2f}%)")
    
    # Test analysis
    analysis = provider.analyze_forex_pair("GBP/USD")
    print(f"\nGBP/USD Analysis:")
    print(f"Current Rate: {analysis.get('current_rate', {}).get('last', 'N/A')}")
    print(f"Trend: {analysis.get('trend', 'N/A')}")
    print(f"Signals: {len(analysis.get('signals', []))}")