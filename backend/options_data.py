"""
Options Data Module
───────────────────
Handles options data fetching, Greeks calculation, and strategy analysis.
Supports options chains, implied volatility, and common options strategies.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from scipy.stats import norm
import math

from supabase_cache import _get_client


@dataclass
class OptionContract:
    symbol: str
    underlying: str
    expiry: datetime
    strike: float
    option_type: str  # 'call' or 'put'
    bid: float
    ask: float
    last: float
    change: float
    change_pct: float
    volume: int
    open_interest: int
    implied_volatility: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    intrinsic_value: float
    time_value: float
    moneyness: float  # strike / spot
    days_to_expiry: int
    currency: str  # Market-specific currency
    exchange: str  # Exchange information


@dataclass
class OptionsChain:
    underlying: str
    spot_price: float
    expiry_dates: List[datetime]
    calls: List[OptionContract]
    puts: List[OptionContract]
    iv_rank: float  # Current IV percentile
    iv_30d_avg: float
    currency: str  # Market-specific currency
    exchange: str  # Exchange information


class BlackScholesCalculator:
    """Black-Scholes options pricing and Greeks calculator."""
    
    @staticmethod
    def calculate_option_price(spot: float, strike: float, time_to_expiry: float, 
                             risk_free_rate: float, volatility: float, 
                             option_type: str = 'call') -> float:
        """
        Calculate Black-Scholes option price.
        
        Args:
            spot: Current stock price
            strike: Strike price
            time_to_expiry: Time to expiry in years
            risk_free_rate: Risk-free interest rate
            volatility: Implied volatility
            option_type: 'call' or 'put'
        """
        if time_to_expiry <= 0:
            if option_type == 'call':
                return max(spot - strike, 0)
            else:
                return max(strike - spot, 0)
        
        d1 = (np.log(spot / strike) + (risk_free_rate + 0.5 * volatility**2) * time_to_expiry) / (volatility * np.sqrt(time_to_expiry))
        d2 = d1 - volatility * np.sqrt(time_to_expiry)
        
        if option_type == 'call':
            price = spot * norm.cdf(d1) - strike * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2)
        else:
            price = strike * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2) - spot * norm.cdf(-d1)
        
        return max(price, 0)
    
    @staticmethod
    def calculate_greeks(spot: float, strike: float, time_to_expiry: float,
                        risk_free_rate: float, volatility: float,
                        option_type: str = 'call') -> Dict[str, float]:
        """Calculate all Greeks for an option."""
        if time_to_expiry <= 0:
            return {
                'delta': 1.0 if (option_type == 'call' and spot > strike) else 0.0,
                'gamma': 0.0,
                'theta': 0.0,
                'vega': 0.0,
                'rho': 0.0
            }
        
        d1 = (np.log(spot / strike) + (risk_free_rate + 0.5 * volatility**2) * time_to_expiry) / (volatility * np.sqrt(time_to_expiry))
        d2 = d1 - volatility * np.sqrt(time_to_expiry)
        
        # Delta
        if option_type == 'call':
            delta = norm.cdf(d1)
        else:
            delta = norm.cdf(d1) - 1
        
        # Gamma (same for calls and puts)
        gamma = norm.pdf(d1) / (spot * volatility * np.sqrt(time_to_expiry))
        
        # Theta
        theta_part1 = -(spot * norm.pdf(d1) * volatility) / (2 * np.sqrt(time_to_expiry))
        if option_type == 'call':
            theta_part2 = -risk_free_rate * strike * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2)
            theta = (theta_part1 + theta_part2) / 365  # Per day
        else:
            theta_part2 = risk_free_rate * strike * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2)
            theta = (theta_part1 + theta_part2) / 365  # Per day
        
        # Vega (same for calls and puts)
        vega = spot * norm.pdf(d1) * np.sqrt(time_to_expiry) / 100  # Per 1% change in volatility
        
        # Rho
        if option_type == 'call':
            rho = strike * time_to_expiry * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2) / 100
        else:
            rho = -strike * time_to_expiry * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2) / 100
        
        return {
            'delta': delta,
            'gamma': gamma,
            'theta': theta,
            'vega': vega,
            'rho': rho
        }


class OptionsDataProvider:
    """Options data provider with Greeks calculation and strategy analysis."""
    
    def __init__(self):
        self.risk_free_rate = 0.05  # Default 5% risk-free rate
        self.bs_calculator = BlackScholesCalculator()
    
    def get_options_chain(self, symbol: str, use_cache: bool = True) -> Optional[OptionsChain]:
        """
        Get complete options chain for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL', 'TSLA')
            use_cache: Whether to use cached data
            
        Returns:
            OptionsChain object or None
        """
        if use_cache:
            cached_chain = self._get_cached_chain(symbol)
            if cached_chain:
                return cached_chain
        
        # Fetch from yfinance
        chain = self._fetch_chain_yfinance(symbol)
        if chain:
            self._cache_chain(chain)
            return chain
        
        return None
    
    def get_option_contract(self, option_symbol: str) -> Optional[OptionContract]:
        """
        Get specific option contract data.
        
        Args:
            option_symbol: Full option symbol (e.g., 'AAPL240315C150')
            
        Returns:
            OptionContract object or None
        """
        # Parse option symbol
        parsed = self._parse_option_symbol(option_symbol)
        if not parsed:
            return None
        
        underlying, expiry_date, option_type, strike = parsed
        
        # Get options chain for the underlying
        chain = self.get_options_chain(underlying)
        if not chain:
            return None
        
        # Find the specific contract
        contracts = chain.calls if option_type == 'call' else chain.puts
        
        for contract in contracts:
            if (contract.expiry.date() == expiry_date.date() and 
                abs(contract.strike - strike) < 0.01):
                return contract
        
        return None
    
    def calculate_implied_volatility(self, spot: float, strike: float, time_to_expiry: float,
                                   risk_free_rate: float, option_price: float,
                                   option_type: str = 'call') -> float:
        """
        Calculate implied volatility using Newton-Raphson method.
        """
        if time_to_expiry <= 0 or option_price <= 0:
            return 0.0
        
        # Initial guess
        iv = 0.3
        
        for _ in range(100):  # Max iterations
            try:
                # Calculate option price with current IV
                calculated_price = self.bs_calculator.calculate_option_price(
                    spot, strike, time_to_expiry, risk_free_rate, iv, option_type
                )
                
                # Calculate vega for Newton-Raphson
                greeks = self.bs_calculator.calculate_greeks(
                    spot, strike, time_to_expiry, risk_free_rate, iv, option_type
                )
                vega = greeks['vega'] * 100  # Convert back to per unit change
                
                if abs(vega) < 1e-6:
                    break
                
                # Newton-Raphson update
                price_diff = calculated_price - option_price
                iv_new = iv - price_diff / vega
                
                if abs(iv_new - iv) < 1e-6:
                    break
                
                iv = max(iv_new, 0.01)  # Keep IV positive
                
            except:
                break
        
        return max(iv, 0.01)
    
    def analyze_options_strategy(self, strategy_name: str, legs: List[Dict[str, Any]],
                               spot_price: float) -> Dict[str, Any]:
        """
        Analyze options strategy payoff and Greeks.
        
        Args:
            strategy_name: Name of the strategy
            legs: List of option legs with contract details
            spot_price: Current underlying price
            
        Returns:
            Strategy analysis with payoff diagram and Greeks
        """
        total_cost = 0
        total_delta = 0
        total_gamma = 0
        total_theta = 0
        total_vega = 0
        
        # Calculate strategy Greeks and cost
        for leg in legs:
            contract = leg.get('contract')
            quantity = leg.get('quantity', 1)
            action = leg.get('action', 'buy')  # 'buy' or 'sell'
            
            if not contract:
                continue
            
            multiplier = quantity * (1 if action == 'buy' else -1)
            
            # Add to totals
            if action == 'buy':
                total_cost += contract.ask * quantity * 100  # Options are per 100 shares
            else:
                total_cost -= contract.bid * quantity * 100
            
            total_delta += contract.delta * multiplier
            total_gamma += contract.gamma * multiplier
            total_theta += contract.theta * multiplier
            total_vega += contract.vega * multiplier
        
        # Generate payoff diagram
        price_range = np.linspace(spot_price * 0.7, spot_price * 1.3, 100)
        payoffs = []
        
        for price in price_range:
            payoff = -total_cost  # Start with initial cost
            
            for leg in legs:
                contract = leg.get('contract')
                quantity = leg.get('quantity', 1)
                action = leg.get('action', 'buy')
                
                if not contract:
                    continue
                
                # Calculate intrinsic value at expiry
                if contract.option_type == 'call':
                    intrinsic = max(price - contract.strike, 0)
                else:
                    intrinsic = max(contract.strike - price, 0)
                
                if action == 'buy':
                    payoff += intrinsic * quantity * 100
                else:
                    payoff -= intrinsic * quantity * 100
            
            payoffs.append(payoff)
        
        # Find breakeven points
        breakevens = []
        for i in range(len(payoffs) - 1):
            if payoffs[i] * payoffs[i + 1] <= 0:  # Sign change
                # Linear interpolation to find exact breakeven
                x1, y1 = price_range[i], payoffs[i]
                x2, y2 = price_range[i + 1], payoffs[i + 1]
                if y2 != y1:
                    breakeven = x1 - y1 * (x2 - x1) / (y2 - y1)
                    breakevens.append(breakeven)
        
        # Calculate max profit/loss
        max_profit = max(payoffs) if payoffs else 0
        max_loss = min(payoffs) if payoffs else 0
        
        return {
            'strategy_name': strategy_name,
            'total_cost': total_cost,
            'max_profit': max_profit if max_profit != float('inf') else None,
            'max_loss': max_loss if max_loss != float('-inf') else None,
            'breakeven_points': breakevens,
            'greeks': {
                'delta': total_delta,
                'gamma': total_gamma,
                'theta': total_theta,
                'vega': total_vega
            },
            'payoff_diagram': {
                'prices': price_range.tolist(),
                'payoffs': payoffs
            },
            'current_pnl': 0,  # Would need current option prices to calculate
            'analysis_timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def screen_options(self, criteria: Dict[str, Any]) -> List[OptionContract]:
        """
        Screen options based on criteria.
        
        Args:
            criteria: Screening criteria (IV rank, delta range, etc.)
            
        Returns:
            List of matching option contracts
        """
        # This would implement options screening logic
        # For now, return empty list as placeholder
        return []
    
    def _fetch_chain_yfinance(self, symbol: str) -> Optional[OptionsChain]:
        """Fetch options chain from Yahoo Finance."""
        try:
            ticker = yf.Ticker(symbol)
            
            # Get current stock price and currency info
            info = ticker.info
            spot_price = info.get('regularMarketPrice') or info.get('currentPrice')
            currency = info.get('currency', 'USD')  # Get market-specific currency
            exchange = info.get('exchange', 'Unknown')  # Get exchange info
            
            if not spot_price:
                return None
            
            # Get options expiry dates
            expiry_dates = ticker.options
            if not expiry_dates:
                return None
            
            all_calls = []
            all_puts = []
            
            # Fetch options for each expiry
            for expiry_str in expiry_dates[:6]:  # Limit to first 6 expiries
                try:
                    expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d')
                    options_data = ticker.option_chain(expiry_str)
                    
                    calls_df = options_data.calls
                    puts_df = options_data.puts
                    
                    # Process calls
                    for _, row in calls_df.iterrows():
                        contract = self._create_option_contract(
                            symbol, expiry_date, row, 'call', spot_price, currency, exchange
                        )
                        if contract:
                            all_calls.append(contract)
                    
                    # Process puts
                    for _, row in puts_df.iterrows():
                        contract = self._create_option_contract(
                            symbol, expiry_date, row, 'put', spot_price, currency, exchange
                        )
                        if contract:
                            all_puts.append(contract)
                            
                except Exception as e:
                    print(f"[OptionsData] Error processing expiry {expiry_str}: {e}")
                    continue
            
            # Calculate IV rank (placeholder)
            iv_values = [c.implied_volatility for c in all_calls + all_puts if c.implied_volatility > 0]
            iv_rank = 50.0  # Placeholder
            iv_30d_avg = np.mean(iv_values) if iv_values else 0.3
            
            return OptionsChain(
                underlying=symbol,
                spot_price=spot_price,
                expiry_dates=[datetime.strptime(d, '%Y-%m-%d') for d in expiry_dates],
                calls=all_calls,
                puts=all_puts,
                iv_rank=iv_rank,
                iv_30d_avg=iv_30d_avg,
                currency=currency,
                exchange=exchange
            )
            
        except Exception as e:
            print(f"[OptionsData] Error fetching chain for {symbol}: {e}")
            return None
    
    def _create_option_contract(self, underlying: str, expiry: datetime, 
                              row: pd.Series, option_type: str, spot_price: float,
                              currency: str, exchange: str) -> Optional[OptionContract]:
        """Create OptionContract from DataFrame row."""
        try:
            strike = float(row['strike'])
            bid = float(row.get('bid', 0))
            ask = float(row.get('ask', 0))
            last = float(row.get('lastPrice', 0))
            volume = int(row.get('volume', 0)) if not pd.isna(row.get('volume', 0)) else 0
            open_interest = int(row.get('openInterest', 0)) if not pd.isna(row.get('openInterest', 0)) else 0
            
            # Calculate time to expiry
            now = datetime.now()
            time_to_expiry = (expiry - now).days / 365.0
            days_to_expiry = (expiry - now).days
            
            # Calculate implied volatility
            mid_price = (bid + ask) / 2 if bid > 0 and ask > 0 else last
            if mid_price > 0:
                iv = self.calculate_implied_volatility(
                    spot_price, strike, time_to_expiry, self.risk_free_rate, mid_price, option_type
                )
            else:
                iv = 0.3  # Default IV
            
            # Calculate Greeks
            greeks = self.bs_calculator.calculate_greeks(
                spot_price, strike, time_to_expiry, self.risk_free_rate, iv, option_type
            )
            
            # Calculate intrinsic and time value
            if option_type == 'call':
                intrinsic_value = max(spot_price - strike, 0)
            else:
                intrinsic_value = max(strike - spot_price, 0)
            
            time_value = max(mid_price - intrinsic_value, 0)
            moneyness = strike / spot_price
            
            # Create option symbol
            expiry_str = expiry.strftime('%y%m%d')
            option_symbol = f"{underlying}{expiry_str}{'C' if option_type == 'call' else 'P'}{int(strike)}"
            
            return OptionContract(
                symbol=option_symbol,
                underlying=underlying,
                expiry=expiry,
                strike=strike,
                option_type=option_type,
                bid=bid,
                ask=ask,
                last=last,
                change=float(row.get('change', 0)),
                change_pct=float(row.get('percentChange', 0)),
                volume=volume,
                open_interest=open_interest,
                implied_volatility=iv,
                delta=greeks['delta'],
                gamma=greeks['gamma'],
                theta=greeks['theta'],
                vega=greeks['vega'],
                rho=greeks['rho'],
                intrinsic_value=intrinsic_value,
                time_value=time_value,
                moneyness=moneyness,
                days_to_expiry=days_to_expiry,
                currency=currency,
                exchange=exchange
            )
            
        except Exception as e:
            print(f"[OptionsData] Error creating contract: {e}")
            return None
    
    def _parse_option_symbol(self, option_symbol: str) -> Optional[Tuple[str, datetime, str, float]]:
        """
        Parse option symbol into components.
        
        Format: AAPL240315C150 -> (AAPL, 2024-03-15, call, 150.0)
        """
        import re
        
        # Pattern: SYMBOL + YYMMDD + C/P + STRIKE
        pattern = r'^([A-Z]+)(\d{6})([CP])(\d+(?:\.\d+)?)$'
        match = re.match(pattern, option_symbol.upper())
        
        if not match:
            return None
        
        symbol, date_str, option_type_char, strike_str = match.groups()
        
        # Parse date
        year = 2000 + int(date_str[:2])
        month = int(date_str[2:4])
        day = int(date_str[4:6])
        expiry_date = datetime(year, month, day)
        
        # Parse option type
        option_type = 'call' if option_type_char == 'C' else 'put'
        
        # Parse strike
        strike = float(strike_str)
        
        return symbol, expiry_date, option_type, strike
    
    def _get_cached_chain(self, symbol: str) -> Optional[OptionsChain]:
        """Get cached options chain from Supabase."""
        # Implementation would fetch from options_chains table
        # For now, return None to always fetch fresh data
        return None
    
    def _cache_chain(self, chain: OptionsChain) -> bool:
        """Cache options chain to Supabase."""
        client = _get_client()
        if not client:
            return False
        
        try:
            # Cache all contracts
            contracts_data = []
            
            for contract in chain.calls + chain.puts:
                contracts_data.append({
                    'underlying': contract.underlying,
                    'expiry': contract.expiry.date().isoformat(),
                    'strike': contract.strike,
                    'option_type': contract.option_type,
                    'bid': contract.bid,
                    'ask': contract.ask,
                    'last': contract.last,
                    'change': contract.change,
                    'change_pct': contract.change_pct,
                    'volume': contract.volume,
                    'open_interest': contract.open_interest,
                    'implied_volatility': contract.implied_volatility,
                    'delta': contract.delta,
                    'gamma': contract.gamma,
                    'theta': contract.theta,
                    'vega': contract.vega,
                    'rho': contract.rho,
                    'intrinsic_value': contract.intrinsic_value,
                    'time_value': contract.time_value,
                    'updated_at': datetime.now(timezone.utc).isoformat()
                })
            
            # Batch upsert
            if contracts_data:
                client.table('options_chains').upsert(
                    contracts_data, 
                    on_conflict='underlying,expiry,strike,option_type'
                ).execute()
            
            return True
            
        except Exception as e:
            print(f"[OptionsData] Cache write error for {chain.underlying}: {e}")
            return False


# Convenience functions
def get_options_chain(symbol: str) -> Optional[OptionsChain]:
    """Quick function to get options chain."""
    provider = OptionsDataProvider()
    return provider.get_options_chain(symbol)


def get_option_contract(option_symbol: str) -> Optional[OptionContract]:
    """Quick function to get specific option contract."""
    provider = OptionsDataProvider()
    return provider.get_option_contract(option_symbol)


def analyze_covered_call(underlying: str, call_strike: float, expiry_date: str) -> Dict[str, Any]:
    """Analyze a covered call strategy."""
    provider = OptionsDataProvider()
    
    # Get options chain
    chain = provider.get_options_chain(underlying)
    if not chain:
        return {'error': f'Could not fetch options chain for {underlying}'}
    
    # Find the call option
    target_expiry = datetime.strptime(expiry_date, '%Y-%m-%d')
    call_contract = None
    
    for call in chain.calls:
        if (call.expiry.date() == target_expiry.date() and 
            abs(call.strike - call_strike) < 0.01):
            call_contract = call
            break
    
    if not call_contract:
        return {'error': f'Could not find call option {call_strike} expiring {expiry_date}'}
    
    # Analyze covered call
    legs = [
        {
            'contract': call_contract,
            'quantity': 1,
            'action': 'sell'
        }
    ]
    
    strategy_analysis = provider.analyze_options_strategy(
        'Covered Call', legs, chain.spot_price
    )
    
    # Add covered call specific metrics
    max_profit = (call_strike - chain.spot_price) * 100 + strategy_analysis['total_cost']
    assignment_prob = call_contract.delta  # Approximate probability
    
    strategy_analysis.update({
        'max_profit_if_assigned': max_profit,
        'assignment_probability': assignment_prob,
        'income_generated': strategy_analysis['total_cost'],
        'protection_level': strategy_analysis['total_cost'] / (chain.spot_price * 100) * 100
    })
    
    return strategy_analysis


# Example usage
if __name__ == "__main__":
    provider = OptionsDataProvider()
    
    # Test options chain
    chain = provider.get_options_chain("AAPL")
    if chain:
        print(f"AAPL Options Chain:")
        print(f"Spot Price: ${chain.spot_price:.2f}")
        print(f"Expiry Dates: {len(chain.expiry_dates)}")
        print(f"Calls: {len(chain.calls)}")
        print(f"Puts: {len(chain.puts)}")
        
        # Show first few calls
        print("\nFirst 5 Calls:")
        for call in chain.calls[:5]:
            print(f"  {call.strike} Call: ${call.last:.2f} (IV: {call.implied_volatility:.1%}, Δ: {call.delta:.3f})")
    
    # Test covered call analysis
    covered_call = analyze_covered_call("AAPL", 150.0, "2024-03-15")
    print(f"\nCovered Call Analysis: {covered_call.get('strategy_name', 'Error')}")