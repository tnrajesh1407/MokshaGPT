"""
Futures Data Module
───────────────────
Handles futures data fetching, contango/backwardation analysis, and roll strategies.
Supports index futures, commodity futures, currency futures, and bond futures.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import calendar

from supabase_cache import _get_client


@dataclass
class FuturesContract:
    symbol: str
    contract_month: str
    underlying: str
    last_price: float
    change: float
    change_pct: float
    volume: int
    open_interest: int
    settlement: float
    high: float
    low: float
    contract_type: str  # 'index', 'commodity', 'currency', 'bond'
    expiry_date: datetime
    days_to_expiry: int
    tick_size: float
    tick_value: float
    margin_requirement: float
    is_front_month: bool
    currency: str  # Market-specific currency
    exchange: str  # Exchange information


@dataclass
class FuturesCurve:
    underlying: str
    curve_date: datetime
    contracts: List[FuturesContract]
    curve_shape: str  # 'contango', 'backwardation', 'flat'
    front_month_price: float
    back_month_price: float
    curve_slope: float  # Annualized percentage difference
    roll_yield: float  # Expected return from rolling


class FuturesDataProvider:
    """Futures data provider with curve analysis and roll strategies."""
    
    def __init__(self):
        # Futures contract specifications
        self.contract_specs = {
            # Index Futures
            '/ES': {
                'name': 'E-mini S&P 500',
                'type': 'index',
                'tick_size': 0.25,
                'tick_value': 12.50,
                'margin': 13200,
                'multiplier': 50,
                'exchange': 'CME',
                'months': ['H', 'M', 'U', 'Z']  # Mar, Jun, Sep, Dec
            },
            '/NQ': {
                'name': 'E-mini NASDAQ 100',
                'type': 'index',
                'tick_size': 0.25,
                'tick_value': 5.00,
                'margin': 19800,
                'multiplier': 20,
                'exchange': 'CME',
                'months': ['H', 'M', 'U', 'Z']
            },
            '/RTY': {
                'name': 'E-mini Russell 2000',
                'type': 'index',
                'tick_size': 0.10,
                'tick_value': 5.00,
                'margin': 5500,
                'multiplier': 50,
                'exchange': 'CME',
                'months': ['H', 'M', 'U', 'Z']
            },
            
            # Commodity Futures - Energy
            '/CL': {
                'name': 'Crude Oil',
                'type': 'energy',
                'tick_size': 0.01,
                'tick_value': 10.00,
                'margin': 6600,
                'multiplier': 1000,
                'exchange': 'NYMEX',
                'months': ['F', 'G', 'H', 'J', 'K', 'M', 'N', 'Q', 'U', 'V', 'X', 'Z']
            },
            '/NG': {
                'name': 'Natural Gas',
                'type': 'energy',
                'tick_size': 0.001,
                'tick_value': 10.00,
                'margin': 4400,
                'multiplier': 10000,
                'exchange': 'NYMEX',
                'months': ['F', 'G', 'H', 'J', 'K', 'M', 'N', 'Q', 'U', 'V', 'X', 'Z']
            },
            
            # Commodity Futures - Metals
            '/GC': {
                'name': 'Gold',
                'type': 'metals',
                'tick_size': 0.10,
                'tick_value': 10.00,
                'margin': 11000,
                'multiplier': 100,
                'exchange': 'COMEX',
                'months': ['G', 'J', 'M', 'Q', 'V', 'Z']
            },
            '/SI': {
                'name': 'Silver',
                'type': 'metals',
                'tick_size': 0.005,
                'tick_value': 25.00,
                'margin': 14300,
                'multiplier': 5000,
                'exchange': 'COMEX',
                'months': ['H', 'K', 'N', 'U', 'Z']
            },
            '/HG': {
                'name': 'Copper',
                'type': 'metals',
                'tick_size': 0.0005,
                'tick_value': 12.50,
                'margin': 4400,
                'multiplier': 25000,
                'exchange': 'COMEX',
                'months': ['H', 'K', 'N', 'U', 'Z']
            },
            '/PL': {
                'name': 'Platinum',
                'type': 'metals',
                'tick_size': 0.10,
                'tick_value': 5.00,
                'margin': 1100,
                'multiplier': 50,
                'exchange': 'NYMEX',
                'months': ['F', 'J', 'N', 'V']
            },
            '/PA': {
                'name': 'Palladium',
                'type': 'metals',
                'tick_size': 0.05,
                'tick_value': 5.00,
                'margin': 1650,
                'multiplier': 100,
                'exchange': 'NYMEX',
                'months': ['H', 'M', 'U', 'Z']
            },
            
            # Agricultural Futures
            '/ZC': {
                'name': 'Corn',
                'type': 'agriculture',
                'tick_size': 0.25,
                'tick_value': 12.50,
                'margin': 2200,
                'multiplier': 5000,
                'exchange': 'CBOT',
                'months': ['H', 'K', 'N', 'U', 'Z']
            },
            '/ZS': {
                'name': 'Soybeans',
                'type': 'agriculture',
                'tick_size': 0.25,
                'tick_value': 12.50,
                'margin': 4950,
                'multiplier': 5000,
                'exchange': 'CBOT',
                'months': ['F', 'H', 'K', 'N', 'Q', 'U', 'X']
            },
            '/ZW': {
                'name': 'Wheat',
                'type': 'agriculture',
                'tick_size': 0.25,
                'tick_value': 12.50,
                'margin': 3300,
                'multiplier': 5000,
                'exchange': 'CBOT',
                'months': ['H', 'K', 'N', 'U', 'Z']
            },
            '/KC': {
                'name': 'Coffee',
                'type': 'agriculture',
                'tick_size': 0.05,
                'tick_value': 18.75,
                'margin': 4400,
                'multiplier': 37500,
                'exchange': 'ICE',
                'months': ['H', 'K', 'N', 'U', 'Z']
            },
            '/SB': {
                'name': 'Sugar',
                'type': 'agriculture',
                'tick_size': 0.01,
                'tick_value': 11.20,
                'margin': 1540,
                'multiplier': 112000,
                'exchange': 'ICE',
                'months': ['H', 'K', 'N', 'V']
            },
            '/CC': {
                'name': 'Cocoa',
                'type': 'agriculture',
                'tick_size': 1.00,
                'tick_value': 10.00,
                'margin': 1980,
                'multiplier': 10,
                'exchange': 'ICE',
                'months': ['H', 'K', 'N', 'U', 'Z']
            },
            '/CT': {
                'name': 'Cotton',
                'type': 'agriculture',
                'tick_size': 0.01,
                'tick_value': 5.00,
                'margin': 2750,
                'multiplier': 50000,
                'exchange': 'ICE',
                'months': ['H', 'K', 'N', 'V', 'Z']
            },
            '/LBS': {
                'name': 'Lumber',
                'type': 'agriculture',
                'tick_size': 0.10,
                'tick_value': 11.00,
                'margin': 1980,
                'multiplier': 110,
                'exchange': 'CME',
                'months': ['F', 'H', 'K', 'N', 'U', 'X']
            },
            
            # Currency Futures
            '/6E': {
                'name': 'Euro FX',
                'type': 'currency',
                'tick_size': 0.00005,
                'tick_value': 6.25,
                'margin': 2200,
                'multiplier': 125000,
                'exchange': 'CME',
                'months': ['H', 'M', 'U', 'Z']
            },
            '/6B': {
                'name': 'British Pound',
                'type': 'currency',
                'tick_size': 0.0001,
                'tick_value': 6.25,
                'margin': 2750,
                'multiplier': 62500,
                'exchange': 'CME',
                'months': ['H', 'M', 'U', 'Z']
            },
            
            # Bond Futures
            '/ZN': {
                'name': '10-Year Treasury Note',
                'type': 'bonds',
                'tick_size': 0.015625,  # 1/64
                'tick_value': 15.625,
                'margin': 1650,
                'multiplier': 1000,
                'exchange': 'CBOT',
                'months': ['H', 'M', 'U', 'Z']
            }
        }
        
        # Month code mapping
        self.month_codes = {
            'F': 1, 'G': 2, 'H': 3, 'J': 4, 'K': 5, 'M': 6,
            'N': 7, 'Q': 8, 'U': 9, 'V': 10, 'X': 11, 'Z': 12
        }
        
        self.code_to_month = {v: k for k, v in self.month_codes.items()}
    
    def get_futures_contract(self, symbol: str, contract_month: str = None, use_cache: bool = True) -> Optional[FuturesContract]:
        """
        Get futures contract data.
        
        Args:
            symbol: Futures symbol (e.g., '/ES', '/GC')
            contract_month: Specific contract (e.g., 'ESM24') or None for front month
            use_cache: Whether to use cached data
            
        Returns:
            FuturesContract object or None
        """
        if use_cache:
            cached_contract = self._get_cached_contract(symbol, contract_month)
            if cached_contract:
                return cached_contract
        
        # Fetch from yfinance
        contract = self._fetch_contract_yfinance(symbol, contract_month)
        if contract:
            self._cache_contract(contract)
            return contract
        
        return None
    
    def get_futures_curve(self, symbol: str, use_cache: bool = True) -> Optional[FuturesCurve]:
        """
        Get complete futures curve for analysis.
        
        Args:
            symbol: Base futures symbol (e.g., '/ES', '/GC')
            use_cache: Whether to use cached data
            
        Returns:
            FuturesCurve object with all available contracts
        """
        if use_cache:
            cached_curve = self._get_cached_curve(symbol)
            if cached_curve:
                return cached_curve
        
        # Fetch curve from yfinance
        curve = self._fetch_curve_yfinance(symbol)
        if curve:
            self._cache_curve(curve)
            return curve
        
        return None
    
    def analyze_contango_backwardation(self, symbol: str) -> Dict[str, Any]:
        """
        Analyze contango/backwardation in futures curve.
        
        Args:
            symbol: Futures symbol
            
        Returns:
            Analysis of curve shape and roll yield
        """
        curve = self.get_futures_curve(symbol)
        if not curve or len(curve.contracts) < 2:
            return {'error': f'Insufficient data for {symbol} curve analysis'}
        
        # Sort contracts by expiry
        sorted_contracts = sorted(curve.contracts, key=lambda x: x.expiry_date)
        
        if len(sorted_contracts) < 2:
            return {'error': 'Need at least 2 contracts for curve analysis'}
        
        front_contract = sorted_contracts[0]
        back_contract = sorted_contracts[1]
        
        # Calculate curve metrics
        price_diff = back_contract.last_price - front_contract.last_price
        price_diff_pct = (price_diff / front_contract.last_price) * 100
        
        # Annualize the difference
        days_between = (back_contract.expiry_date - front_contract.expiry_date).days
        if days_between > 0:
            annualized_diff = (price_diff_pct * 365) / days_between
        else:
            annualized_diff = 0
        
        # Determine curve shape
        if price_diff > 0:
            curve_shape = 'contango'
            roll_yield = -abs(annualized_diff)  # Negative for contango
        elif price_diff < 0:
            curve_shape = 'backwardation'
            roll_yield = abs(annualized_diff)  # Positive for backwardation
        else:
            curve_shape = 'flat'
            roll_yield = 0
        
        # Calculate roll cost/benefit
        roll_cost_per_day = price_diff / days_between if days_between > 0 else 0
        
        # Generate curve data for charting
        curve_data = []
        for contract in sorted_contracts:
            curve_data.append({
                'contract': contract.contract_month,
                'expiry': contract.expiry_date.isoformat(),
                'price': contract.last_price,
                'days_to_expiry': contract.days_to_expiry,
                'volume': contract.volume,
                'open_interest': contract.open_interest
            })
        
        return {
            'symbol': symbol,
            'curve_shape': curve_shape,
            'front_month': {
                'contract': front_contract.contract_month,
                'price': front_contract.last_price,
                'expiry': front_contract.expiry_date.isoformat(),
                'days_to_expiry': front_contract.days_to_expiry
            },
            'back_month': {
                'contract': back_contract.contract_month,
                'price': back_contract.last_price,
                'expiry': back_contract.expiry_date.isoformat(),
                'days_to_expiry': back_contract.days_to_expiry
            },
            'price_difference': price_diff,
            'price_difference_pct': price_diff_pct,
            'annualized_difference': annualized_diff,
            'roll_yield_estimate': roll_yield,
            'roll_cost_per_day': roll_cost_per_day,
            'curve_data': curve_data,
            'analysis_timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def calculate_roll_strategy(self, symbol: str, strategy_type: str = 'front_month') -> Dict[str, Any]:
        """
        Calculate optimal roll strategy for futures position.
        
        Args:
            symbol: Futures symbol
            strategy_type: 'front_month', 'optimal_liquidity', 'calendar_spread'
            
        Returns:
            Roll strategy recommendations
        """
        curve = self.get_futures_curve(symbol)
        if not curve:
            return {'error': f'Could not fetch curve for {symbol}'}
        
        # Sort by expiry
        contracts = sorted(curve.contracts, key=lambda x: x.expiry_date)
        
        if strategy_type == 'front_month':
            # Always roll to front month
            current_contract = contracts[0] if contracts else None
            next_contract = contracts[1] if len(contracts) > 1 else None
            
            if not current_contract or not next_contract:
                return {'error': 'Insufficient contracts for front month strategy'}
            
            # Recommend roll when 5-10 days to expiry
            roll_recommended = current_contract.days_to_expiry <= 10
            
            return {
                'strategy_type': 'front_month',
                'current_contract': current_contract.contract_month,
                'target_contract': next_contract.contract_month,
                'roll_recommended': roll_recommended,
                'days_to_roll': current_contract.days_to_expiry,
                'roll_cost': next_contract.last_price - current_contract.last_price,
                'reasoning': f'Roll from {current_contract.contract_month} to {next_contract.contract_month} when {current_contract.days_to_expiry} days remain'
            }
        
        elif strategy_type == 'optimal_liquidity':
            # Roll to contract with best liquidity (volume + open interest)
            best_contract = max(contracts, key=lambda x: x.volume + x.open_interest)
            
            return {
                'strategy_type': 'optimal_liquidity',
                'recommended_contract': best_contract.contract_month,
                'volume': best_contract.volume,
                'open_interest': best_contract.open_interest,
                'price': best_contract.last_price,
                'reasoning': f'{best_contract.contract_month} has highest liquidity with {best_contract.volume:,} volume and {best_contract.open_interest:,} OI'
            }
        
        else:
            return {'error': f'Unknown strategy type: {strategy_type}'}
    
    def get_futures_technicals(self, symbol: str, contract_month: str = None, period: str = "6mo") -> Optional[Dict[str, Any]]:
        """Get technical analysis for futures contract."""
        # Get historical data
        hist = self._get_futures_history(symbol, contract_month, period)
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
            
            # RSI
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss.replace(0, np.nan)
            rsi = (100 - 100 / (1 + rs)).iloc[-1]
            
            # ATR
            tr1 = high - low
            tr2 = (high - close.shift(1)).abs()
            tr3 = (low - close.shift(1)).abs()
            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = true_range.rolling(14).mean().iloc[-1]
            
            # Support/Resistance
            current_price = close.iloc[-1]
            high_20 = high.rolling(20).max().iloc[-1]
            low_20 = low.rolling(20).min().iloc[-1]
            
            return {
                'symbol': symbol,
                'current_price': float(current_price),
                'sma20': float(sma20) if not pd.isna(sma20) else None,
                'sma50': float(sma50) if not pd.isna(sma50) else None,
                'ema20': float(ema20) if not pd.isna(ema20) else None,
                'rsi': float(rsi) if not pd.isna(rsi) else None,
                'atr': float(atr) if not pd.isna(atr) else None,
                'resistance_20d': float(high_20) if not pd.isna(high_20) else None,
                'support_20d': float(low_20) if not pd.isna(low_20) else None,
                'volatility_pct': (atr / current_price * 100) if not pd.isna(atr) and current_price > 0 else None
            }
            
        except Exception as e:
            print(f"[FuturesData] Error computing technicals for {symbol}: {e}")
            return None
    
    def _fetch_contract_yfinance(self, symbol: str, contract_month: str = None) -> Optional[FuturesContract]:
        """Fetch single futures contract from Yahoo Finance."""
        try:
            # If no specific contract, get front month
            if not contract_month:
                contract_month = self._get_front_month_symbol(symbol)
            
            # Convert to yfinance format
            yf_symbol = self._get_yf_futures_symbol(symbol, contract_month)
            if not yf_symbol:
                return None
            
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info
            hist = ticker.history(period="2d")
            
            if hist.empty:
                return None
            
            # Get contract specs and currency info
            specs = self.contract_specs.get(symbol, {})
            currency = info.get('currency', self._get_default_currency(symbol))
            exchange = info.get('exchange', specs.get('exchange', 'Unknown'))
            
            current_price = info.get('regularMarketPrice') or hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2] if len(hist) >= 2 else current_price
            
            change = current_price - prev_close
            change_pct = (change / prev_close * 100) if prev_close != 0 else 0
            
            # Calculate expiry date
            expiry_date = self._calculate_expiry_date(symbol, contract_month)
            days_to_expiry = (expiry_date - datetime.now()).days if expiry_date else 0
            
            return FuturesContract(
                symbol=yf_symbol,
                contract_month=contract_month,
                underlying=symbol,
                last_price=current_price,
                change=change,
                change_pct=change_pct,
                volume=info.get('regularMarketVolume', 0),
                open_interest=info.get('openInterest', 0),
                settlement=current_price,  # Approximation
                high=hist['High'].iloc[-1],
                low=hist['Low'].iloc[-1],
                contract_type=specs.get('type', 'unknown'),
                expiry_date=expiry_date,
                days_to_expiry=days_to_expiry,
                tick_size=specs.get('tick_size', 0.01),
                tick_value=specs.get('tick_value', 1.0),
                margin_requirement=specs.get('margin', 0),
                is_front_month=True,  # Simplified
                currency=currency,
                exchange=exchange
            )
            
        except Exception as e:
            print(f"[FuturesData] Error fetching {symbol} contract: {e}")
            return None
    
    def _fetch_curve_yfinance(self, symbol: str) -> Optional[FuturesCurve]:
        """Fetch futures curve from Yahoo Finance."""
        try:
            contracts = []
            
            # Get next 4 contract months
            contract_months = self._get_next_contract_months(symbol, 4)
            
            for i, month_symbol in enumerate(contract_months):
                contract = self._fetch_contract_yfinance(symbol, month_symbol)
                if contract:
                    contract.is_front_month = (i == 0)
                    contracts.append(contract)
            
            if len(contracts) < 2:
                return None
            
            # Analyze curve shape
            front_price = contracts[0].last_price
            back_price = contracts[-1].last_price
            
            if back_price > front_price:
                curve_shape = 'contango'
            elif back_price < front_price:
                curve_shape = 'backwardation'
            else:
                curve_shape = 'flat'
            
            # Calculate curve slope (annualized)
            days_diff = (contracts[-1].expiry_date - contracts[0].expiry_date).days
            price_diff_pct = ((back_price - front_price) / front_price) * 100
            curve_slope = (price_diff_pct * 365) / days_diff if days_diff > 0 else 0
            
            # Estimate roll yield
            roll_yield = -curve_slope if curve_shape == 'contango' else curve_slope
            
            return FuturesCurve(
                underlying=symbol,
                curve_date=datetime.now(),
                contracts=contracts,
                curve_shape=curve_shape,
                front_month_price=front_price,
                back_month_price=back_price,
                curve_slope=curve_slope,
                roll_yield=roll_yield
            )
            
        except Exception as e:
            print(f"[FuturesData] Error fetching curve for {symbol}: {e}")
            return None
    
    def _get_front_month_symbol(self, symbol: str) -> str:
        """Get front month contract symbol."""
        # This is a simplified implementation
        # In practice, you'd need to check actual expiry dates
        now = datetime.now()
        specs = self.contract_specs.get(symbol, {})
        months = specs.get('months', ['H', 'M', 'U', 'Z'])
        
        # Find next available month
        for month_code in months:
            month_num = self.month_codes[month_code]
            if month_num >= now.month:
                year_suffix = str(now.year)[-2:]
                return f"{symbol[1:]}{month_code}{year_suffix}"
        
        # If no month found this year, use first month of next year
        year_suffix = str(now.year + 1)[-2:]
        return f"{symbol[1:]}{months[0]}{year_suffix}"
    
    def _get_next_contract_months(self, symbol: str, count: int) -> List[str]:
        """Get next N contract months for a futures symbol."""
        contracts = []
        now = datetime.now()
        specs = self.contract_specs.get(symbol, {})
        months = specs.get('months', ['H', 'M', 'U', 'Z'])
        
        current_year = now.year
        current_month = now.month
        
        # Generate contract symbols
        for year_offset in range(2):  # Look at current and next year
            year = current_year + year_offset
            year_suffix = str(year)[-2:]
            
            for month_code in months:
                month_num = self.month_codes[month_code]
                
                # Skip past months in current year
                if year_offset == 0 and month_num < current_month:
                    continue
                
                contract_symbol = f"{symbol[1:]}{month_code}{year_suffix}"
                contracts.append(contract_symbol)
                
                if len(contracts) >= count:
                    return contracts
        
        return contracts
    
    def _get_yf_futures_symbol(self, symbol: str, contract_month: str) -> str:
        """Convert futures symbol to Yahoo Finance format."""
        # Yahoo Finance only supports continuous front-month contracts via the =F suffix.
        # Month-coded symbols (e.g. CLK26=F) are not supported and return no data.
        # Always use the continuous contract ticker (e.g. CL=F, GC=F, ES=F).
        if symbol.startswith('/'):
            base = symbol[1:]  # Remove leading slash
        else:
            # Strip trailing month code + year digits if present (e.g. CLK26 -> CL)
            base = re.sub(r'[FGHJKMNQUVXZ]\d{2}$', '', symbol)
        return f"{base}=F"
    
    def _calculate_expiry_date(self, symbol: str, contract_month: str) -> datetime:
        """Calculate expiry date for futures contract."""
        # This is simplified - actual expiry rules are complex
        # Each futures type has different expiry rules
        
        if len(contract_month) >= 3:
            month_code = contract_month[-3]
            year_suffix = contract_month[-2:]
            
            month_num = self.month_codes.get(month_code, 12)
            year = 2000 + int(year_suffix)
            
            # Most futures expire on third Friday of the month
            # This is a simplification
            third_friday = self._get_third_friday(year, month_num)
            return third_friday
        
        return datetime.now() + timedelta(days=30)  # Default
    
    def _get_third_friday(self, year: int, month: int) -> datetime:
        """Get third Friday of the month."""
        # Find first day of month
        first_day = datetime(year, month, 1)
        
        # Find first Friday
        days_to_friday = (4 - first_day.weekday()) % 7
        first_friday = first_day + timedelta(days=days_to_friday)
        
        # Third Friday is 14 days later
        third_friday = first_friday + timedelta(days=14)
        
        return third_friday
    
    def _get_default_currency(self, symbol: str) -> str:
        """Get default currency for futures contract based on symbol and market."""
        # Currency mapping for different futures markets
        currency_map = {
            # US Futures (CME, CBOT, NYMEX, COMEX)
            '/ES': 'USD', '/NQ': 'USD', '/RTY': 'USD', '/YM': 'USD',
            '/CL': 'USD', '/NG': 'USD', '/GC': 'USD', '/SI': 'USD',
            '/ZC': 'USD', '/ZS': 'USD', '/ZW': 'USD', '/ZN': 'USD',
            '/6E': 'USD', '/6B': 'USD', '/6J': 'USD', '/6A': 'USD',
            
            # European Futures
            '/FDAX': 'EUR', '/FESX': 'EUR', '/FGBL': 'EUR',
            
            # UK Futures  
            '/FTSE': 'GBP',
            
            # Asian Futures
            '/NK': 'JPY', '/HSI': 'HKD',
            
            # Indian Futures (NSE)
            'NIFTY': 'INR', 'BANKNIFTY': 'INR', 'SENSEX': 'INR',
        }
        
        # Check for Indian market symbols
        if '.NS' in symbol or 'NIFTY' in symbol or 'BANK' in symbol:
            return 'INR'
        
        # Check for European symbols
        if any(suffix in symbol for suffix in ['.DE', '.PA', '.MI', '.AS']):
            return 'EUR'
        
        # Check for UK symbols
        if '.L' in symbol:
            return 'GBP'
        
        # Check for Asian symbols
        if any(suffix in symbol for suffix in ['.T', '.HK', '.SS']):
            if '.T' in symbol:
                return 'JPY'
            elif '.HK' in symbol:
                return 'HKD'
            else:
                return 'CNY'
        
        return currency_map.get(symbol, 'USD')  # Default to USD
    
    def _get_futures_history(self, symbol: str, contract_month: str = None, period: str = "6mo") -> Optional[pd.DataFrame]:
        """Get historical data for futures contract."""
        yf_symbol = self._get_yf_futures_symbol(symbol, contract_month or self._get_front_month_symbol(symbol))
        
        try:
            ticker = yf.Ticker(yf_symbol)
            hist = ticker.history(period=period)
            return hist if not hist.empty else None
        except:
            return None
    
    def _get_cached_contract(self, symbol: str, contract_month: str = None) -> Optional[FuturesContract]:
        """Get cached futures contract."""
        # Placeholder - would implement Supabase caching
        return None
    
    def _get_cached_curve(self, symbol: str) -> Optional[FuturesCurve]:
        """Get cached futures curve."""
        # Placeholder - would implement Supabase caching
        return None
    
    def _cache_contract(self, contract: FuturesContract) -> bool:
        """Cache futures contract."""
        # Placeholder - would implement Supabase caching
        return True
    
    def _cache_curve(self, curve: FuturesCurve) -> bool:
        """Cache futures curve."""
        # Placeholder - would implement Supabase caching
        return True


# Convenience functions
def get_futures_contract(symbol: str, contract_month: str = None) -> Optional[FuturesContract]:
    """Quick function to get futures contract."""
    provider = FuturesDataProvider()
    return provider.get_futures_contract(symbol, contract_month)


def analyze_contango_backwardation(symbol: str) -> Dict[str, Any]:
    """Quick function to analyze futures curve."""
    provider = FuturesDataProvider()
    return provider.analyze_contango_backwardation(symbol)


def get_roll_strategy(symbol: str, strategy_type: str = 'front_month') -> Dict[str, Any]:
    """Quick function to get roll strategy."""
    provider = FuturesDataProvider()
    return provider.calculate_roll_strategy(symbol, strategy_type)


def analyze_commodity_spot(symbol: str) -> Dict[str, Any]:
    """
    Analyze commodity spot prices.
    
    Args:
        symbol: Commodity symbol (e.g., 'XAUUSD' for Gold, 'XTIUSD' for Oil)
        
    Returns:
        Commodity analysis with price, technicals, and market insights
    """
    try:
        # Map commodity symbols to Yahoo Finance format
        yf_symbol_map = {
            # Precious Metals
            'XAUUSD': 'GC=F',  # Gold
            'XAGUSD': 'SI=F',  # Silver
            'XPTUSD': 'PL=F',  # Platinum
            'XPDUSD': 'PA=F',  # Palladium
            
            # Energy
            'XTIUSD': 'CL=F',  # WTI Crude Oil
            'XBRUSD': 'BZ=F',  # Brent Crude
            'XNGUSD': 'NG=F',  # Natural Gas
            
            # Industrial Metals
            'XCOPUSD': 'HG=F', # Copper
            
            # Agricultural
            'XCORNUSD': 'ZC=F', # Corn
            'XWHEUSD': 'ZW=F',  # Wheat
            'XSOYUSD': 'ZS=F',  # Soybeans
            'XCOFUSD': 'KC=F',  # Coffee
            'XSUGUSD': 'SB=F',  # Sugar
        }
        
        yf_symbol = yf_symbol_map.get(symbol, symbol)
        
        # Get current price data
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info
        hist = ticker.history(period="1y")
        
        if hist.empty:
            return {'error': f'No data available for {symbol}'}
        
        current_price = info.get('regularMarketPrice') or hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2] if len(hist) >= 2 else current_price
        
        change = current_price - prev_close
        change_pct = (change / prev_close * 100) if prev_close != 0 else 0
        
        # Calculate technical indicators
        close = hist['Close']
        high = hist['High']
        low = hist['Low']
        
        # Moving averages
        sma20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else None
        sma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else None
        
        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = (100 - 100 / (1 + rs)).iloc[-1] if len(close) >= 14 else None
        
        # 52-week high/low
        high_52w = close.rolling(252).max().iloc[-1] if len(close) >= 252 else close.max()
        low_52w = close.rolling(252).min().iloc[-1] if len(close) >= 252 else close.min()
        
        # Determine commodity type and unit
        commodity_info = _get_commodity_info(symbol)
        
        return {
            'symbol': symbol,
            'name': commodity_info['name'],
            'type': commodity_info['type'],
            'unit': commodity_info['unit'],
            'current_price': float(current_price),
            'change': float(change),
            'change_pct': float(change_pct),
            'volume': info.get('regularMarketVolume', 0),
            'technicals': {
                'sma20': float(sma20) if sma20 and not pd.isna(sma20) else None,
                'sma50': float(sma50) if sma50 and not pd.isna(sma50) else None,
                'rsi': float(rsi) if rsi and not pd.isna(rsi) else None,
                'high_52w': float(high_52w) if not pd.isna(high_52w) else None,
                'low_52w': float(low_52w) if not pd.isna(low_52w) else None,
                'pct_from_52w_high': ((current_price - high_52w) / high_52w * 100) if high_52w else None,
                'pct_from_52w_low': ((current_price - low_52w) / low_52w * 100) if low_52w else None,
            },
            'market_insights': _get_commodity_insights(symbol, commodity_info['type']),
            'analysis_timestamp': datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        return {'error': f'Error analyzing {symbol}: {str(e)}'}


def _get_commodity_info(symbol: str) -> Dict[str, str]:
    """Get commodity information including name, type, and unit."""
    commodity_map = {
        # Precious Metals
        'XAUUSD': {'name': 'Gold', 'type': 'precious_metals', 'unit': 'USD/oz'},
        'XAGUSD': {'name': 'Silver', 'type': 'precious_metals', 'unit': 'USD/oz'},
        'XPTUSD': {'name': 'Platinum', 'type': 'precious_metals', 'unit': 'USD/oz'},
        'XPDUSD': {'name': 'Palladium', 'type': 'precious_metals', 'unit': 'USD/oz'},
        
        # Energy
        'XTIUSD': {'name': 'WTI Crude Oil', 'type': 'energy', 'unit': 'USD/bbl'},
        'XBRUSD': {'name': 'Brent Crude Oil', 'type': 'energy', 'unit': 'USD/bbl'},
        'XNGUSD': {'name': 'Natural Gas', 'type': 'energy', 'unit': 'USD/MMBtu'},
        
        # Industrial Metals
        'XCOPUSD': {'name': 'Copper', 'type': 'industrial_metals', 'unit': 'USD/lb'},
        
        # Agricultural
        'XCORNUSD': {'name': 'Corn', 'type': 'agricultural', 'unit': 'USD/bu'},
        'XWHEUSD': {'name': 'Wheat', 'type': 'agricultural', 'unit': 'USD/bu'},
        'XSOYUSD': {'name': 'Soybeans', 'type': 'agricultural', 'unit': 'USD/bu'},
        'XCOFUSD': {'name': 'Coffee', 'type': 'agricultural', 'unit': 'USD/lb'},
        'XSUGUSD': {'name': 'Sugar', 'type': 'agricultural', 'unit': 'USD/lb'},
    }
    
    return commodity_map.get(symbol, {'name': symbol, 'type': 'unknown', 'unit': 'USD'})


def _get_commodity_insights(symbol: str, commodity_type: str) -> List[str]:
    """Get market insights specific to commodity type."""
    insights = []
    
    if commodity_type == 'precious_metals':
        insights = [
            "Precious metals often act as safe-haven assets during market uncertainty",
            "Influenced by inflation expectations, currency strength, and geopolitical events",
            "Central bank policies and interest rates significantly impact precious metals prices"
        ]
    elif commodity_type == 'energy':
        insights = [
            "Energy commodities are sensitive to supply/demand dynamics and geopolitical tensions",
            "OPEC decisions, inventory levels, and seasonal demand patterns drive price movements",
            "Economic growth expectations and currency fluctuations impact energy prices"
        ]
    elif commodity_type == 'industrial_metals':
        insights = [
            "Industrial metals reflect global economic activity and manufacturing demand",
            "China's economic growth and infrastructure spending significantly influence prices",
            "Supply disruptions and mining production levels affect market dynamics"
        ]
    elif commodity_type == 'agricultural':
        insights = [
            "Agricultural commodities are influenced by weather patterns and seasonal cycles",
            "Global supply/demand balance, crop reports, and trade policies drive prices",
            "Currency fluctuations and biofuel demand impact agricultural markets"
        ]
    
    return insights
if __name__ == "__main__":
    provider = FuturesDataProvider()
    
    # Test futures contract
    contract = provider.get_futures_contract("/ES")
    if contract:
        print(f"E-mini S&P 500 Contract:")
        print(f"Symbol: {contract.symbol}")
        print(f"Price: ${contract.last_price:.2f}")
        print(f"Change: {contract.change:+.2f} ({contract.change_pct:+.2f}%)")
        print(f"Days to Expiry: {contract.days_to_expiry}")
    
    # Test contango/backwardation analysis
    curve_analysis = provider.analyze_contango_backwardation("/GC")
    print(f"\nGold Futures Curve Analysis:")
    print(f"Shape: {curve_analysis.get('curve_shape', 'Unknown')}")
    print(f"Roll Yield: {curve_analysis.get('roll_yield_estimate', 0):.2f}%")
    
    # Test roll strategy
    roll_strategy = provider.calculate_roll_strategy("/ES", "front_month")
    print(f"\nE-mini S&P 500 Roll Strategy:")
    print(f"Current: {roll_strategy.get('current_contract', 'Unknown')}")
    print(f"Target: {roll_strategy.get('target_contract', 'Unknown')}")
    print(f"Roll Recommended: {roll_strategy.get('roll_recommended', False)}")