import { useState } from 'react';

export interface Market {
  id: string;
  name: string;
  flag: string;
  currency: string;
  timezone: string;
  examples: string[];
  popular_assets: string[];
  suffix?: string;
}

export const MARKETS: Market[] = [
  {
    id: 'us',
    name: 'United States',
    flag: '🇺🇸',
    currency: 'USD',
    timezone: 'America/New_York',
    examples: ['AAPL', 'TSLA', 'MSFT', 'GOOGL', 'AMZN'],
    popular_assets: ['S&P 500', 'NASDAQ 100', 'Dow Jones', 'US Options', 'US Futures'],
    suffix: ''
  },
  {
    id: 'india',
    name: 'India (NSE/BSE)',
    flag: '🇮🇳',
    currency: 'INR',
    timezone: 'Asia/Kolkata',
    examples: ['RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'WIPRO.NS'],
    popular_assets: ['NIFTY 50', 'NIFTY 100', 'Indian IT', 'Banking', 'Pharma'],
    suffix: '.NS'
  },
  {
    id: 'uk',
    name: 'United Kingdom',
    flag: '🇬🇧',
    currency: 'GBP',
    timezone: 'Europe/London',
    examples: ['SHEL.L', 'AZN.L', 'HSBA.L', 'ULVR.L', 'BP.L'],
    popular_assets: ['FTSE 100', 'UK Banking', 'Oil & Gas', 'Pharmaceuticals'],
    suffix: '.L'
  },
  {
    id: 'germany',
    name: 'Germany',
    flag: '🇩🇪',
    currency: 'EUR',
    timezone: 'Europe/Berlin',
    examples: ['SAP.DE', 'SIE.DE', 'ALV.DE', 'BMW.DE', 'BAS.DE'],
    popular_assets: ['DAX 40', 'German Tech', 'Automotive', 'Industrials'],
    suffix: '.DE'
  },
  {
    id: 'japan',
    name: 'Japan',
    flag: '🇯🇵',
    currency: 'JPY',
    timezone: 'Asia/Tokyo',
    examples: ['7203.T', '6758.T', '9984.T', '6861.T', '8306.T'],
    popular_assets: ['Nikkei 225', 'Japanese Tech', 'Automotive', 'Electronics'],
    suffix: '.T'
  },
  {
    id: 'hongkong',
    name: 'Hong Kong',
    flag: '🇭🇰',
    currency: 'HKD',
    timezone: 'Asia/Hong_Kong',
    examples: ['0700.HK', '9988.HK', '0941.HK', '1299.HK', '0388.HK'],
    popular_assets: ['Hang Seng', 'Chinese Tech', 'Banking', 'Real Estate'],
    suffix: '.HK'
  },
  {
    id: 'australia',
    name: 'Australia',
    flag: '🇦🇺',
    currency: 'AUD',
    timezone: 'Australia/Sydney',
    examples: ['CBA.AX', 'BHP.AX', 'CSL.AX', 'NAB.AX', 'WBC.AX'],
    popular_assets: ['ASX 200', 'Banking', 'Mining', 'Healthcare'],
    suffix: '.AX'
  },
  {
    id: 'canada',
    name: 'Canada',
    flag: '🇨🇦',
    currency: 'CAD',
    timezone: 'America/Toronto',
    examples: ['SHOP.TO', 'RY.TO', 'TD.TO', 'ENB.TO', 'CNQ.TO'],
    popular_assets: ['TSX', 'Banking', 'Energy', 'Technology'],
    suffix: '.TO'
  }
];

export const FOREX_PAIRS = [
  { pair: 'EUR/USD', name: 'Euro / US Dollar', category: 'Major' },
  { pair: 'GBP/USD', name: 'British Pound / US Dollar', category: 'Major' },
  { pair: 'USD/JPY', name: 'US Dollar / Japanese Yen', category: 'Major' },
  { pair: 'AUD/USD', name: 'Australian Dollar / US Dollar', category: 'Major' },
  { pair: 'USD/CAD', name: 'US Dollar / Canadian Dollar', category: 'Major' },
  { pair: 'USD/CHF', name: 'US Dollar / Swiss Franc', category: 'Major' },
  { pair: 'NZD/USD', name: 'New Zealand Dollar / US Dollar', category: 'Major' },
  { pair: 'EUR/GBP', name: 'Euro / British Pound', category: 'Minor' },
  { pair: 'EUR/JPY', name: 'Euro / Japanese Yen', category: 'Minor' },
  { pair: 'GBP/JPY', name: 'British Pound / Japanese Yen', category: 'Minor' },
  { pair: 'USD/INR', name: 'US Dollar / Indian Rupee', category: 'Exotic' },
  { pair: 'USD/CNY', name: 'US Dollar / Chinese Yuan', category: 'Exotic' }
];

export const FUTURES_CONTRACTS = [
  { symbol: '/ES', name: 'E-mini S&P 500', category: 'Index' },
  { symbol: '/NQ', name: 'E-mini NASDAQ 100', category: 'Index' },
  { symbol: '/RTY', name: 'E-mini Russell 2000', category: 'Index' },
  { symbol: '/GC', name: 'Gold Futures', category: 'Metals' },
  { symbol: '/SI', name: 'Silver Futures', category: 'Metals' },
  { symbol: '/CL', name: 'Crude Oil Futures', category: 'Energy' },
  { symbol: '/NG', name: 'Natural Gas Futures', category: 'Energy' },
  { symbol: '/ZC', name: 'Corn Futures', category: 'Agriculture' },
  { symbol: '/ZS', name: 'Soybean Futures', category: 'Agriculture' },
  { symbol: '/ZW', name: 'Wheat Futures', category: 'Agriculture' }
];

interface MarketSelectorProps {
  selectedMarket: Market;
  onMarketChange: (market: Market) => void;
}

export const MarketSelector = ({ selectedMarket, onMarketChange }: MarketSelectorProps) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg hover:border-cyan-500 transition-all"
      >
        <span className="text-lg">{selectedMarket.flag}</span>
        <span className="text-white font-medium">{selectedMarket.name}</span>
        <span className="text-slate-400 text-sm">({selectedMarket.currency})</span>
        <svg className={`w-4 h-4 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-2 w-80 bg-slate-800 border border-slate-600 rounded-lg shadow-xl z-50">
          <div className="p-2">
            <div className="text-xs text-slate-400 uppercase tracking-wider mb-2 px-2">Select Market</div>
            {MARKETS.map((market) => (
              <button
                key={market.id}
                onClick={() => {
                  onMarketChange(market);
                  setIsOpen(false);
                }}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-all ${
                  selectedMarket.id === market.id
                    ? 'bg-cyan-600 text-white'
                    : 'hover:bg-slate-700 text-slate-300'
                }`}
              >
                <span className="text-lg">{market.flag}</span>
                <div className="flex-1 text-left">
                  <div className="font-medium">{market.name}</div>
                  <div className="text-xs text-slate-400">{market.currency} • {market.popular_assets.slice(0, 2).join(', ')}</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export const formatCurrency = (amount: number, currency: string): string => {
  const currencySymbols: Record<string, string> = {
    'USD': '$',
    'EUR': '€',
    'GBP': '£',
    'JPY': '¥',
    'INR': '₹',
    'CAD': 'C$',
    'AUD': 'A$',
    'HKD': 'HK$',
    'CHF': 'CHF'
  };
  
  const symbol = currencySymbols[currency] || currency;
  
  // Format based on currency
  if (currency === 'JPY') {
    return `${symbol}${Math.round(amount).toLocaleString()}`;
  } else {
    return `${symbol}${amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
};

export const isMarketOpen = (market: Market, currentTime: Date): boolean => {
  // Simplified market hours check
  const hour = currentTime.getHours();
  
  switch (market.id) {
    case 'us':
      return hour >= 9 && hour < 16; // 9:30 AM - 4:00 PM EST (simplified)
    case 'india':
      return hour >= 9 && hour < 15; // 9:15 AM - 3:30 PM IST (simplified)
    case 'uk':
      return hour >= 8 && hour < 16; // 8:00 AM - 4:30 PM GMT (simplified)
    case 'germany':
      return hour >= 9 && hour < 17; // 9:00 AM - 5:30 PM CET (simplified)
    case 'japan':
      return hour >= 9 && hour < 15; // 9:00 AM - 3:00 PM JST (simplified)
    case 'hongkong':
      return hour >= 9 && hour < 16; // 9:30 AM - 4:00 PM HKT (simplified)
    case 'australia':
      return hour >= 10 && hour < 16; // 10:00 AM - 4:00 PM AEST (simplified)
    case 'canada':
      return hour >= 9 && hour < 16; // 9:30 AM - 4:00 PM EST (simplified)
    default:
      return false;
  }
};