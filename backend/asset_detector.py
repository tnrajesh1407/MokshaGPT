"""
Multi-Asset Type Detection
─────────────────────────
Detects asset types (stocks, forex, options, futures) from user input
and extracts relevant symbols and metadata.
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum


class AssetType(Enum):
    STOCK = "stock"
    FOREX = "forex"
    OPTIONS = "options"
    FUTURES = "futures"
    CRYPTO = "crypto"
    UNKNOWN = "unknown"


@dataclass
class AssetInfo:
    asset_type: AssetType
    symbol: str
    exchange: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AssetDetector:
    """Detects asset types and extracts symbols from user queries."""
    
    def __init__(self):
        # Forex patterns
        self.forex_pairs = {
            # Major pairs
            'EURUSD', 'EUR/USD', 'GBPUSD', 'GBP/USD', 'USDJPY', 'USD/JPY',
            'AUDUSD', 'AUD/USD', 'USDCAD', 'USD/CAD', 'USDCHF', 'USD/CHF',
            'NZDUSD', 'NZD/USD',
            # Minor pairs
            'EURGBP', 'EUR/GBP', 'EURJPY', 'EUR/JPY', 'GBPJPY', 'GBP/JPY',
            'EURCHF', 'EUR/CHF', 'EURAUD', 'EUR/AUD', 'GBPAUD', 'GBP/AUD',
            'AUDJPY', 'AUD/JPY', 'CADJPY', 'CAD/JPY', 'CHFJPY', 'CHF/JPY',
            # Exotic pairs
            'USDTRY', 'USD/TRY', 'USDZAR', 'USD/ZAR', 'USDMXN', 'USD/MXN',
            'USDBRL', 'USD/BRL', 'USDINR', 'USD/INR', 'USDCNY', 'USD/CNY',
        }
        
        # Futures symbols
        self.futures_symbols = {
            # Indices
            '/ES', '/NQ', '/RTY', '/YM',  # US indices
            '/NK', '/FDAX', '/FTSE',      # International indices
            # Commodities
            '/GC', '/SI', '/CL', '/NG', '/HG',  # Metals & Energy
            '/ZC', '/ZS', '/ZW', '/KC', '/SB',  # Agriculture
            # Currencies
            '/6E', '/6B', '/6J', '/6A', '/6C', '/6S',  # Currency futures
            # Bonds
            '/ZN', '/ZB', '/ZF', '/ZT',   # Treasury futures
        }
        
        # Currency codes for forex detection
        self.currency_codes = {
            'USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'NZD',
            'SEK', 'NOK', 'DKK', 'PLN', 'CZK', 'HUF', 'TRY', 'ZAR',
            'BRL', 'MXN', 'INR', 'CNY', 'KRW', 'SGD', 'HKD', 'THB'
        }
        
        # Stock exchange suffixes
        self.stock_suffixes = {
            '.NS': 'NSE',     # India
            '.BO': 'BSE',     # India
            '.L': 'LSE',      # London
            '.DE': 'XETRA',   # Germany
            '.T': 'TSE',      # Tokyo
            '.HK': 'HKEX',    # Hong Kong
            '.AX': 'ASX',     # Australia
            '.TO': 'TSX',     # Toronto
            '.PA': 'EPA',     # Paris
            '.MI': 'BIT',     # Milan
        }
        
        # Forex keywords
        self.forex_keywords = {
            'forex', 'fx', 'currency', 'exchange rate', 'central bank',
            'fed', 'ecb', 'boe', 'boj', 'rba', 'boc', 'snb',
            'interest rate', 'monetary policy', 'inflation',
            'carry trade', 'currency pair', 'cross rate'
        }
        
        # Options keywords
        self.options_keywords = {
            'call', 'put', 'option', 'options', 'strike', 'expiry', 'expiration',
            'delta', 'gamma', 'theta', 'vega', 'rho', 'greeks',
            'implied volatility', 'iv', 'time decay', 'intrinsic value',
            'straddle', 'strangle', 'spread', 'covered call', 'protective put'
        }
        
        # Futures keywords
        self.futures_keywords = {
            'futures', 'future', 'commodity', 'commodities', 'contango',
            'backwardation', 'roll', 'expiry', 'settlement', 'margin',
            'crude oil', 'gold', 'silver', 'natural gas', 'copper',
            'corn', 'wheat', 'soybeans', 'coffee', 'sugar', 'spot price'
        }
        
        # Crypto keywords and symbols
        self.crypto_keywords = {
            'bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'cryptocurrency',
            'blockchain', 'defi', 'nft', 'altcoin', 'stablecoin'
        }
        
        self.crypto_symbols = {
            'BTC', 'ETH', 'ADA', 'DOT', 'LINK', 'LTC', 'XRP', 'BCH',
            'BNB', 'SOL', 'AVAX', 'MATIC', 'ATOM', 'ALGO', 'VET'
        }
        
        # Commodities symbols and keywords
        self.commodities_symbols = {
            # Precious Metals
            'XAU', 'XAUUSD', 'GC=F', 'GOLD',
            'XAG', 'XAGUSD', 'SI=F', 'SILVER',
            'XPT', 'XPTUSD', 'PL=F', 'PLATINUM',
            'XPD', 'XPDUSD', 'PA=F', 'PALLADIUM',
            # Energy
            'CL=F', 'CRUDE', 'WTI', 'XTIUSD',
            'BZ=F', 'BRENT', 'XBRUSD',
            'NG=F', 'NATGAS', 'XNGUSD',
            # Industrial Metals
            'HG=F', 'COPPER', 'XCOPUSD',
            # Agricultural
            'ZC=F', 'CORN', 'XCORNUSD',
            'ZW=F', 'WHEAT', 'XWHEUSD',
            'ZS=F', 'SOYBEANS', 'XSOYUSD',
            'KC=F', 'COFFEE', 'XCOFUSD',
            'SB=F', 'SUGAR', 'XSUGUSD',
        }
        
        self.commodities_keywords = {
            'commodity', 'commodities', 'spot price', 'gold', 'silver', 'platinum', 'palladium',
            'crude oil', 'oil', 'brent', 'wti', 'natural gas', 'copper', 'aluminum',
            'corn', 'wheat', 'soybeans', 'coffee', 'sugar', 'cocoa', 'cotton'
        }

    def detect_asset_type(self, query: str) -> List[AssetInfo]:
        """
        Detect asset types and extract symbols from user query.
        Returns list of AssetInfo objects for all detected assets.
        """
        query_upper = query.upper()
        query_lower = query.lower()
        detected_assets = []
        
        # 1. Check for forex pairs
        forex_assets = self._detect_forex(query_upper, query_lower)
        detected_assets.extend(forex_assets)
        
        # 2. Check for options symbols
        options_assets = self._detect_options(query_upper, query_lower)
        detected_assets.extend(options_assets)
        
        # 3. Check for futures symbols
        futures_assets = self._detect_futures(query_upper, query_lower)
        detected_assets.extend(futures_assets)
        
        # 4. Check for crypto symbols
        crypto_assets = self._detect_crypto(query_upper, query_lower)
        detected_assets.extend(crypto_assets)
        
        # 5. Check for commodities (integrated with futures)
        commodities_assets = self._detect_commodities(query_upper, query_lower)
        detected_assets.extend(commodities_assets)
        
        # 6. Check for stock symbols (fallback)
        if not detected_assets:
            stock_assets = self._detect_stocks(query_upper, query_lower)
            detected_assets.extend(stock_assets)
        
        return detected_assets if detected_assets else [AssetInfo(AssetType.UNKNOWN, "")]

    def _detect_forex(self, query_upper: str, query_lower: str) -> List[AssetInfo]:
        """Detect forex pairs and currency-related queries."""
        assets = []
        
        # Check for explicit forex pairs
        for pair in self.forex_pairs:
            if pair in query_upper:
                # Normalize to standard format (e.g., EUR/USD)
                normalized = self._normalize_forex_pair(pair)
                assets.append(AssetInfo(
                    asset_type=AssetType.FOREX,
                    symbol=normalized,
                    exchange="FOREX",
                    metadata={"base_currency": normalized[:3], "quote_currency": normalized[4:]}
                ))
        
        # Check for currency codes pattern (XXX/YYY or XXXYYY)
        currency_pattern = r'\b([A-Z]{3})[/]?([A-Z]{3})\b'
        matches = re.findall(currency_pattern, query_upper)
        for base, quote in matches:
            if base in self.currency_codes and quote in self.currency_codes:
                pair = f"{base}/{quote}"
                if pair not in [a.symbol for a in assets]:  # Avoid duplicates
                    assets.append(AssetInfo(
                        asset_type=AssetType.FOREX,
                        symbol=pair,
                        exchange="FOREX",
                        metadata={"base_currency": base, "quote_currency": quote}
                    ))
        
        # Check for forex keywords
        if any(keyword in query_lower for keyword in self.forex_keywords):
            if not assets:  # If no specific pair found, default to major pairs
                assets.append(AssetInfo(
                    asset_type=AssetType.FOREX,
                    symbol="EUR/USD",
                    exchange="FOREX",
                    metadata={"base_currency": "EUR", "quote_currency": "USD", "is_default": True}
                ))
        
        return assets

    def _detect_options(self, query_upper: str, query_lower: str) -> List[AssetInfo]:
        """Detect options symbols and options-related queries."""
        assets = []
        
        # Options symbol pattern: AAPL240315C150 (Stock + Date + C/P + Strike)
        options_pattern = r'\b([A-Z]{1,5})(\d{6})([CP])(\d+(?:\.\d+)?)\b'
        matches = re.findall(options_pattern, query_upper)
        
        for symbol, date, option_type, strike in matches:
            # Parse date (YYMMDD format)
            year = 2000 + int(date[:2])
            month = int(date[2:4])
            day = int(date[4:6])
            
            assets.append(AssetInfo(
                asset_type=AssetType.OPTIONS,
                symbol=f"{symbol}{date}{option_type}{strike}",
                exchange="OPTIONS",
                metadata={
                    "underlying": symbol,
                    "expiry_date": f"{year}-{month:02d}-{day:02d}",
                    "option_type": "call" if option_type == "C" else "put",
                    "strike_price": float(strike)
                }
            ))
        
        # Check for options keywords with stock symbols
        if any(keyword in query_lower for keyword in self.options_keywords):
            # Look for stock symbols in the query
            stock_pattern = r'\b([A-Z]{1,5}(?:\.[A-Z]{1,3})?)\b'
            stock_matches = re.findall(stock_pattern, query_upper)
            
            for stock in stock_matches:
                if stock not in [a.metadata.get("underlying", "") for a in assets]:
                    assets.append(AssetInfo(
                        asset_type=AssetType.OPTIONS,
                        symbol=stock,
                        exchange="OPTIONS",
                        metadata={"underlying": stock, "is_chain_request": True}
                    ))
        
        return assets

    def _detect_futures(self, query_upper: str, query_lower: str) -> List[AssetInfo]:
        """Detect futures symbols and futures-related queries."""
        assets = []
        
        # Check for explicit futures symbols
        for symbol in self.futures_symbols:
            if symbol in query_upper:
                assets.append(AssetInfo(
                    asset_type=AssetType.FUTURES,
                    symbol=symbol,
                    exchange="FUTURES",
                    metadata={"contract_type": self._get_futures_type(symbol)}
                ))
        
        # Check for futures contract notation (ESM23, GCZ23, etc.)
        futures_contract_pattern = r'\b([A-Z]{1,3})([FGHJKMNQUVXZ])(\d{2})\b'
        matches = re.findall(futures_contract_pattern, query_upper)
        
        for root, month_code, year in matches:
            symbol = f"{root}{month_code}{year}"
            assets.append(AssetInfo(
                asset_type=AssetType.FUTURES,
                symbol=symbol,
                exchange="FUTURES",
                metadata={
                    "root_symbol": root,
                    "month_code": month_code,
                    "year": f"20{year}",
                    "contract_type": self._get_futures_type(root)
                }
            ))
        
        # Check for futures keywords
        if any(keyword in query_lower for keyword in self.futures_keywords):
            if not assets:  # Default to popular futures
                assets.append(AssetInfo(
                    asset_type=AssetType.FUTURES,
                    symbol="/ES",
                    exchange="FUTURES",
                    metadata={"contract_type": "index", "is_default": True}
                ))
        
        return assets

    def _detect_crypto(self, query_upper: str, query_lower: str) -> List[AssetInfo]:
        """Detect cryptocurrency symbols and crypto-related queries."""
        assets = []
        
        # Check for crypto symbols
        for symbol in self.crypto_symbols:
            if symbol in query_upper:
                assets.append(AssetInfo(
                    asset_type=AssetType.CRYPTO,
                    symbol=f"{symbol}-USD",
                    exchange="CRYPTO",
                    metadata={"base_currency": symbol, "quote_currency": "USD"}
                ))
        
        # Check for crypto keywords
        if any(keyword in query_lower for keyword in self.crypto_keywords):
            if not assets:  # Default to Bitcoin
                assets.append(AssetInfo(
                    asset_type=AssetType.CRYPTO,
                    symbol="BTC-USD",
                    exchange="CRYPTO",
                    metadata={"base_currency": "BTC", "quote_currency": "USD", "is_default": True}
                ))
        
        return assets

    def _detect_commodities(self, query_upper: str, query_lower: str) -> List[AssetInfo]:
        """Detect commodity symbols and commodity-related queries."""
        assets = []
        
        # Check for explicit commodity symbols
        for symbol in self.commodities_symbols:
            if symbol in query_upper:
                # Determine commodity type
                commodity_type = self._get_commodity_type(symbol)
                normalized_symbol = self._normalize_commodity_symbol(symbol)
                
                assets.append(AssetInfo(
                    asset_type=AssetType.FUTURES,  # Commodities handled through futures system
                    symbol=normalized_symbol,
                    exchange="SPOT",
                    metadata={
                        "commodity_type": commodity_type,
                        "original_symbol": symbol,
                        "unit": self._get_commodity_unit(symbol),
                        "is_spot_commodity": True
                    }
                ))
        
        # Check for commodity keywords
        if any(keyword in query_lower for keyword in self.commodities_keywords):
            if not assets:  # If no specific commodity found, try to infer from keywords
                # Map keywords to symbols
                keyword_mappings = {
                    'gold': 'XAUUSD',
                    'silver': 'XAGUSD', 
                    'oil': 'XTIUSD',
                    'crude': 'XTIUSD',
                    'copper': 'XCOPUSD',
                    'natural gas': 'XNGUSD',
                    'corn': 'XCORNUSD',
                    'wheat': 'XWHEUSD',
                    'coffee': 'XCOFUSD',
                    'sugar': 'XSUGUSD'
                }
                
                for keyword, symbol in keyword_mappings.items():
                    if keyword in query_lower:
                        commodity_type = self._get_commodity_type(symbol)
                        assets.append(AssetInfo(
                            asset_type=AssetType.FUTURES,  # Commodities handled through futures system
                            symbol=symbol,
                            exchange="SPOT",
                            metadata={
                                "commodity_type": commodity_type,
                                "is_keyword_match": True,
                                "unit": self._get_commodity_unit(symbol),
                                "is_spot_commodity": True
                            }
                        ))
                        break  # Take first match
        
        return assets

    def _detect_stocks(self, query_upper: str, query_lower: str) -> List[AssetInfo]:
        """Detect stock symbols (fallback detection)."""
        assets = []
        
        # Stock symbol pattern with optional exchange suffix
        stock_pattern = r'\b([A-Z]{1,5}(?:\.[A-Z]{1,3})?)\b'
        matches = re.findall(stock_pattern, query_upper)
        
        for symbol in matches:
            # Skip if it's a currency code, futures symbol, or crypto
            if (symbol in self.currency_codes or 
                symbol in self.futures_symbols or 
                symbol in self.crypto_symbols or
                symbol in self.commodities_symbols):
                continue
            
            # Determine exchange from suffix
            exchange = "NYSE"  # Default
            for suffix, exch in self.stock_suffixes.items():
                if symbol.endswith(suffix):
                    exchange = exch
                    break
            
            assets.append(AssetInfo(
                asset_type=AssetType.STOCK,
                symbol=symbol,
                exchange=exchange,
                metadata={"is_stock": True}
            ))
        
        return assets

    def _get_commodity_type(self, symbol: str) -> str:
        """Get commodity type from symbol."""
        precious_metals = ['XAU', 'XAUUSD', 'GC=F', 'GOLD', 'XAG', 'XAGUSD', 'SI=F', 'SILVER', 
                          'XPT', 'XPTUSD', 'PL=F', 'PLATINUM', 'XPD', 'XPDUSD', 'PA=F', 'PALLADIUM']
        
        industrial_metals = ['HG=F', 'COPPER', 'XCOPUSD', 'ALI=F', 'ALUMINUM', 'XALUUSD',
                           'ZN=F', 'ZINC', 'XZNCUSD', 'NI=F', 'NICKEL', 'XNICUSD']
        
        energy = ['CL=F', 'CRUDE', 'WTI', 'XTIUSD', 'BZ=F', 'BRENT', 'XBRUSD',
                 'NG=F', 'NATGAS', 'XNGUSD', 'RB=F', 'GASOLINE', 'XGSUSD', 'HO=F', 'HEATING', 'XHOUSD']
        
        agricultural = ['ZC=F', 'CORN', 'XCORNUSD', 'ZW=F', 'WHEAT', 'XWHEUSD', 'ZS=F', 'SOYBEANS', 'XSOYUSD',
                       'KC=F', 'COFFEE', 'XCOFUSD', 'SB=F', 'SUGAR', 'XSUGUSD', 'CC=F', 'COCOA', 'XCOCUSD',
                       'CT=F', 'COTTON', 'XCTNUSD']
        
        if symbol in precious_metals:
            return 'precious_metals'
        elif symbol in industrial_metals:
            return 'industrial_metals'
        elif symbol in energy:
            return 'energy'
        elif symbol in agricultural:
            return 'agricultural'
        else:
            return 'other'

    def _normalize_commodity_symbol(self, symbol: str) -> str:
        """Normalize commodity symbol to standard format."""
        # Map various formats to standardized symbols
        symbol_map = {
            # Gold
            'XAU': 'XAUUSD', 'GC=F': 'XAUUSD', 'GOLD': 'XAUUSD',
            # Silver  
            'XAG': 'XAGUSD', 'SI=F': 'XAGUSD', 'SILVER': 'XAGUSD',
            # Platinum
            'XPT': 'XPTUSD', 'PL=F': 'XPTUSD', 'PLATINUM': 'XPTUSD',
            # Palladium
            'XPD': 'XPDUSD', 'PA=F': 'XPDUSD', 'PALLADIUM': 'XPDUSD',
            # Copper
            'HG=F': 'XCOPUSD', 'COPPER': 'XCOPUSD',
            # Oil
            'CL=F': 'XTIUSD', 'CRUDE': 'XTIUSD', 'WTI': 'XTIUSD',
            'BZ=F': 'XBRUSD', 'BRENT': 'XBRUSD',
            # Natural Gas
            'NG=F': 'XNGUSD', 'NATGAS': 'XNGUSD',
            # Agricultural
            'ZC=F': 'XCORNUSD', 'CORN': 'XCORNUSD',
            'ZW=F': 'XWHEUSD', 'WHEAT': 'XWHEUSD',
            'ZS=F': 'XSOYUSD', 'SOYBEANS': 'XSOYUSD',
            'KC=F': 'XCOFUSD', 'COFFEE': 'XCOFUSD',
            'SB=F': 'XSUGUSD', 'SUGAR': 'XSUGUSD',
        }
        
        return symbol_map.get(symbol, symbol)

    def _get_commodity_unit(self, symbol: str) -> str:
        """Get trading unit for commodity."""
        units = {
            # Precious metals (troy ounces)
            'XAUUSD': 'USD/oz', 'XAGUSD': 'USD/oz', 'XPTUSD': 'USD/oz', 'XPDUSD': 'USD/oz',
            # Industrial metals (per pound/ton)
            'XCOPUSD': 'USD/lb', 'XALUUSD': 'USD/ton', 'XZNCUSD': 'USD/ton', 'XNICUSD': 'USD/ton',
            # Energy (per barrel/MMBtu)
            'XTIUSD': 'USD/bbl', 'XBRUSD': 'USD/bbl', 'XNGUSD': 'USD/MMBtu', 
            'XGSUSD': 'USD/gal', 'XHOUSD': 'USD/gal',
            # Agricultural (per bushel/pound)
            'XCORNUSD': 'USD/bu', 'XWHEUSD': 'USD/bu', 'XSOYUSD': 'USD/bu',
            'XCOFUSD': 'USD/lb', 'XSUGUSD': 'USD/lb', 'XCOCUSD': 'USD/ton', 'XCTNUSD': 'USD/lb',
        }
        
        return units.get(symbol, 'USD')

    def _normalize_forex_pair(self, pair: str) -> str:
        """Normalize forex pair to standard format (XXX/YYY)."""
        # Remove any existing slashes and spaces
        clean_pair = pair.replace("/", "").replace(" ", "")
        
        # Insert slash after first 3 characters
        if len(clean_pair) == 6:
            return f"{clean_pair[:3]}/{clean_pair[3:]}"
        
        return pair  # Return as-is if not standard format

    def _get_futures_type(self, symbol: str) -> str:
        """Get futures contract type from symbol."""
        futures_types = {
            # Indices
            '/ES': 'index', '/NQ': 'index', '/RTY': 'index', '/YM': 'index',
            # Commodities - Energy
            '/CL': 'energy', '/NG': 'energy', '/RB': 'energy', '/HO': 'energy',
            # Commodities - Metals
            '/GC': 'metals', '/SI': 'metals', '/HG': 'metals', '/PA': 'metals',
            # Commodities - Agriculture
            '/ZC': 'agriculture', '/ZS': 'agriculture', '/ZW': 'agriculture',
            '/KC': 'agriculture', '/SB': 'agriculture', '/CT': 'agriculture',
            # Currencies
            '/6E': 'currency', '/6B': 'currency', '/6J': 'currency',
            '/6A': 'currency', '/6C': 'currency', '/6S': 'currency',
            # Bonds
            '/ZN': 'bonds', '/ZB': 'bonds', '/ZF': 'bonds', '/ZT': 'bonds',
        }
        
        return futures_types.get(symbol, 'unknown')

    def get_primary_asset(self, assets: List[AssetInfo]) -> AssetInfo:
        """Get the primary asset from a list of detected assets."""
        if not assets:
            return AssetInfo(AssetType.UNKNOWN, "")
        
        # Priority: explicit symbols > keyword-based defaults
        explicit_assets = [a for a in assets if not a.metadata.get("is_default", False)]
        if explicit_assets:
            return explicit_assets[0]
        
        return assets[0]

    def format_asset_for_query(self, asset: AssetInfo) -> str:
        """Format asset info for use in downstream queries."""
        if asset.asset_type == AssetType.FOREX:
            return asset.symbol.replace("/", "")  # EURUSD format for yfinance
        elif asset.asset_type == AssetType.CRYPTO:
            return asset.symbol  # BTC-USD format
        elif asset.asset_type == AssetType.FUTURES:
            return asset.symbol  # /ES or ESM23 format
        elif asset.asset_type == AssetType.OPTIONS:
            return asset.symbol  # Full options symbol
        else:
            return asset.symbol  # Stock symbol as-is


# Convenience function for quick detection
def detect_assets(query: str) -> List[AssetInfo]:
    """Quick function to detect assets from a query string."""
    detector = AssetDetector()
    return detector.detect_asset_type(query)


def get_primary_asset_type(query: str) -> AssetType:
    """Get the primary asset type from a query string."""
    detector = AssetDetector()
    assets = detector.detect_asset_type(query)
    primary = detector.get_primary_asset(assets)
    return primary.asset_type


# Example usage and testing
if __name__ == "__main__":
    detector = AssetDetector()
    
    test_queries = [
        "How is EUR/USD looking today?",
        "Analyze AAPL call options expiring next week",
        "Show me /ES futures trend",
        "What's the price of Bitcoin?",
        "RELIANCE.NS stock analysis",
        "GBP/JPY forex analysis with RSI",
        "TSLA240315C250 options Greeks",
        "/GC gold futures contango analysis"
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        assets = detector.detect_asset_type(query)
        for asset in assets:
            print(f"  Asset: {asset.asset_type.value} | Symbol: {asset.symbol} | Exchange: {asset.exchange}")
            if asset.metadata:
                print(f"    Metadata: {asset.metadata}")