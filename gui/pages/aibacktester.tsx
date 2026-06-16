import { useState } from "react";
import Head from "next/head";
import Link from "next/link";
import Header from "../components/Header";
import RelatedTools from "../components/RelatedTools";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  AreaChart, Area, BarChart, Bar, ReferenceLine, ResponsiveContainer,
} from "recharts";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ParsedStrategy {
  ticker: string;
  strategy_description: string;
  period_years?: number;
  period_days?: number;
  start_date?: string;
  end_date?: string;
  initial_capital: number;
  signal_code: string;
  timeframe?: string;
  fee_rate_pct?: number;
  fee_description?: string;
  position_sizing?: { mode: string; value?: number; stop_loss_pct?: number };
}

interface Metrics {
  initial_capital: number;
  final_value: number;
  total_return_pct: number;
  buy_hold_return_pct: number;
  annualized_return_pct: number;
  sharpe_ratio: number;
  sortino_ratio?: number;
  calmar_ratio?: number;
  max_drawdown_pct: number;
  total_trades: number;
  total_closed_trades?: number;
  win_rate_pct: number;
  wins: number;
  losses: number;
  profit_factor?: number;
  expectancy?: number;
  avg_win?: number;
  avg_loss?: number;
  gross_profit?: number;
  gross_loss?: number;
  total_fees?: number;
  fee_rate_pct?: number;
  fee_description?: string;
  slippage_rate_pct?: number;
  slippage_description?: string;
}

interface Trade {
  date: string;
  type: "BUY" | "SELL" | "SHORT" | "COVER";
  price: number;
  shares: number;
  value?: number;
  pnl?: number;
  pnl_pct?: number;
  days_held?: number;
  [key: string]: any; // dynamic indicator columns (H3, L3, rsi, etc.)
}

interface PricePoint {
  date: string;
  close: number;
  portfolio: number;
  [key: string]: any;
}

interface BacktestResult {
  parsed_strategy: ParsedStrategy;
  metrics: Metrics;
  chart_data: {
    price_series: PricePoint[];
    drawdown_series: { date: string; drawdown: number }[];
    trades: Trade[];
  };
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const fmt = (n: number, decimals = 2) =>
  n?.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

const pct = (n: number) => `${n >= 0 ? "+" : ""}${fmt(n)}%`;

// Download trades as CSV
const downloadTradesCSV = (trades: any[], ticker: string) => {
  // Collect all indicator columns from trades (keys beyond the fixed ones)
  const fixedCols = new Set(["date", "type", "price", "shares", "value", "pnl", "pnl_pct", "days_held", "_timestamp"]);
  const indicatorKeys = Array.from(
    new Set(trades.flatMap(t => Object.keys(t).filter(k => !fixedCols.has(k))))
  );

  const headers = ["#", "Date", "Type", "Price", "Shares", "Trade Value", "P&L", "P&L %", "Days Held", ...indicatorKeys.map(k => k.toUpperCase())];
  const rows = trades.map((t, i) => [
    i + 1,
    t.date,
    t.type,
    t.price.toFixed(2),
    t.shares,
    (t.value ?? 0).toFixed(2),
    (t.pnl ?? 0).toFixed(2),
    (t.pnl_pct ?? 0).toFixed(2),
    t.days_held ?? 0,
    ...indicatorKeys.map(k => t[k] != null ? t[k] : ""),
  ]);
  
  const csvContent = [
    headers.join(","),
    ...rows.map(row => row.join(","))
  ].join("\n");
  
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  const url = URL.createObjectURL(blob);
  link.setAttribute("href", url);
  link.setAttribute("download", `${ticker}_trades_${new Date().toISOString().split('T')[0]}.csv`);
  link.style.visibility = "hidden";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

const STRATEGY_EXAMPLES = [
  "Backtest a 10/50 SMA crossover on AAPL for 3 years with $50,000 capital",
  "RSI strategy on TSLA: buy when RSI < 30, sell when RSI > 70, 2 years, $100,000",
  "MACD crossover on MSFT for 2 years with $50,000 capital",
  "Bollinger Bands mean reversion on NVDA, 20-period, 2 std dev, 3 years",
  "EMA 9/21 crossover on SPY (S&P 500 ETF) for 3 years with $100,000",
  "Backtest a 10/50 SMA crossover strategy on TCS.NS for the last 3 years with ₹500,000 capital",
];

// ── Popular Strategies ────────────────────────────────────────────────────────

const POPULAR_STRATEGIES: { category: string; color: string; items: { label: string; prompt: string }[] }[] = [
  {
    category: "Moving Average",
    color: "cyan",
    items: [
      { label: "SMA 10/50 Crossover", prompt: "Backtest a 10/50 SMA crossover on AAPL for 3 years with $50,000" },
      { label: "EMA 10/20 Crossover", prompt: "EMA 10/20 crossover on MSFT for 2 years with $50,000" },
      { label: "Golden Cross (50/200 SMA)", prompt: "Golden cross strategy: buy when 50 SMA crosses above 200 SMA on SPY, 5 years, $100,000" },
      { label: "Triple EMA (5/10/20)", prompt: "Triple EMA crossover on NVDA: buy when 5 EMA > 10 EMA > 20 EMA, 2 years, $50,000" },
    ],
  },
  {
    category: "Momentum / RSI",
    color: "purple",
    items: [
      { label: "RSI Oversold/Overbought", prompt: "RSI strategy on TSLA: buy when RSI < 30, sell when RSI > 70, 2 years, $100,000" },
      { label: "RSI Divergence", prompt: "RSI mean reversion on GOOGL: buy RSI < 35, sell RSI > 65, 3 years, $50,000" },
      { label: "Stochastic Oscillator", prompt: "Stochastic oscillator strategy on AMZN: buy when %K crosses above %D below 20, sell above 80, 2 years, $50,000" },
      { label: "RSI + SMA Filter", prompt: "RSI strategy with SMA filter on AAPL: buy when RSI < 30 and price above 200 SMA, sell RSI > 70, 3 years, $50,000" },
    ],
  },
  {
    category: "MACD",
    color: "blue",
    items: [
      { label: "MACD Signal Crossover", prompt: "MACD crossover on MSFT: buy when MACD crosses above signal line, sell when crosses below, 3 years, $50,000" },
      { label: "MACD Zero Line Cross", prompt: "MACD zero line crossover on SPY: buy when MACD crosses above zero, sell below zero, 2 years, $100,000" },
      { label: "MACD Histogram", prompt: "MACD histogram strategy on NVDA: buy when histogram turns positive, sell when negative, 2 years, $50,000" },
    ],
  },
  {
    category: "Bollinger Bands",
    color: "emerald",
    items: [
      { label: "BB Mean Reversion", prompt: "Bollinger Bands mean reversion on AAPL: buy at lower band, sell at upper band, 20-period 2 std dev, 3 years, $50,000" },
      { label: "BB Breakout", prompt: "Bollinger Bands breakout on TSLA: buy when price breaks above upper band, sell below middle band, 2 years, $100,000" },
      { label: "BB Squeeze", prompt: "Bollinger Bands squeeze strategy on QQQ: buy when bands expand after squeeze, 2 years, $100,000" },
    ],
  },
  {
    category: "🇺🇸 US Market",
    color: "blue",
    items: [
      { label: "AAPL SMA Crossover", prompt: "10/50 SMA crossover on AAPL for 3 years with $50,000" },
      { label: "TSLA RSI Strategy", prompt: "RSI strategy on TSLA: buy RSI < 30, sell RSI > 70, 2 years, $100,000" },
      { label: "SPY Golden Cross", prompt: "Golden cross strategy: buy when 50 SMA crosses above 200 SMA on SPY, 5 years, $100,000" },
      { label: "NVDA MACD", prompt: "MACD crossover on NVDA for 2 years with $50,000" },
      { label: "QQQ Bollinger Bands", prompt: "Bollinger Bands mean reversion on QQQ for 2 years with $50,000" },
      { label: "MSFT EMA Crossover", prompt: "EMA 10/20 crossover on MSFT for 2 years with $50,000" },
    ],
  },
  {
    category: "🇮🇳 Indian Market (NSE)",
    color: "orange",
    items: [
      { label: "TCS SMA Crossover", prompt: "10/50 SMA crossover on TCS.NS for 3 years with ₹500,000" },
      { label: "Reliance RSI Strategy", prompt: "RSI strategy on RELIANCE.NS: buy RSI < 30, sell RSI > 70, 2 years, ₹1,000,000" },
      { label: "NIFTY EMA Strategy", prompt: "EMA 20/50 crossover on ^NSEI (NIFTY 50) for 3 years with ₹500,000" },
      { label: "Infosys MACD", prompt: "MACD crossover on INFY.NS for 2 years with ₹500,000" },
    ],
  },
  {
    category: "🌍 International Markets",
    color: "emerald",
    items: [
      { label: "SHEL.L (UK) SMA", prompt: "10/50 SMA crossover on SHEL.L for 3 years with £50,000" },
      { label: "SAP.DE (Germany) RSI", prompt: "RSI strategy on SAP.DE: buy RSI < 30, sell RSI > 70, 2 years, €50,000" },
      { label: "7203.T (Toyota) EMA", prompt: "EMA 20/50 crossover on 7203.T for 3 years with ¥5,000,000" },
      { label: "BHP.AX (Australia)", prompt: "MACD crossover on BHP.AX for 2 years with A$50,000" },
      { label: "0700.HK (Tencent)", prompt: "Bollinger Bands on 0700.HK for 2 years with HK$500,000" },
      { label: "SHOP.TO (Canada)", prompt: "EMA 10/20 crossover on SHOP.TO for 2 years with C$50,000" },
    ],
  },
  {
    category: "₿ Crypto",
    color: "purple",
    items: [
      { label: "BTC-USD SMA", prompt: "10/50 SMA crossover on BTC-USD for 2 years with $50,000" },
      { label: "ETH-USD RSI", prompt: "RSI strategy on ETH-USD: buy RSI < 30, sell RSI > 70, 2 years, $50,000" },
      { label: "SOL-USD MACD", prompt: "MACD crossover on SOL-USD for 1 year with $20,000" },
    ],
  },
  {
    category: "⏱️ Intraday",
    color: "pink",
    items: [
      { label: "5-min RSI (AAPL)", prompt: "Intraday 5-minute RSI scalping on AAPL: buy RSI < 30, sell RSI > 70, last 30 days, $50,000" },
      { label: "15-min EMA (SPY)", prompt: "15-minute EMA 9/21 crossover on SPY for last 45 days with $50,000" },
      { label: "1-hour RSI (RELIANCE.NS)", prompt: "1-hour RSI strategy on RELIANCE.NS: buy RSI < 35, sell RSI > 65, last 60 days, ₹500,000" },
    ],
  },
];

// ── Metric Card ───────────────────────────────────────────────────────────────

function MetricCard({
  label, value, sub, positive,
}: { label: string; value: string; sub?: string; positive?: boolean }) {
  const color =
    positive === undefined
      ? "text-white"
      : positive
      ? "text-emerald-400"
      : "text-red-400";
  return (
    <div className="bg-slate-800/60 border border-cyan-500/20 rounded-xl p-4 flex flex-col gap-1">
      <span className="text-xs text-cyan-300 uppercase tracking-wider">{label}</span>
      <span className={`text-2xl font-bold ${color}`}>{value}</span>
      {sub && <span className="text-xs text-slate-400">{sub}</span>}
    </div>
  );
}

// ── Custom Tooltip ────────────────────────────────────────────────────────────

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-slate-900 border border-cyan-500/30 rounded-lg p-3 text-xs shadow-xl">
      <p className="text-cyan-300 mb-1 font-semibold">{label}</p>
      {payload.map((p: any) => (
        <p key={p.dataKey} style={{ color: p.color }}>
          {p.name}: {typeof p.value === "number" ? fmt(p.value) : p.value}
        </p>
      ))}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function BacktestPage() {
  const [strategy, setStrategy]     = useState("");
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState("");
  const [result, setResult]         = useState<BacktestResult | null>(null);
  const [tradesPerPage, setTradesPerPage] = useState(50);
  const [currentPage, setCurrentPage]    = useState(1);

  const handleBacktest = async () => {
    if (!strategy.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    setCurrentPage(1);

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/backtest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Backtest failed");
      }
      const data: BacktestResult = await res.json();
      setResult(data);
    } catch (e: any) {
      setError(e.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const m = result?.metrics;
  const ps = result?.parsed_strategy;
  const cd = result?.chart_data;
  
  // Auto-detect indicator types from chart data columns
  const samplePoint = cd?.price_series?.[0] || {};
  const hasMA = "fast_ma" in samplePoint || "slow_ma" in samplePoint || "sma_10" in samplePoint || "sma_20" in samplePoint || "sma_50" in samplePoint || "ema_10" in samplePoint || "ema_20" in samplePoint;
  const hasRSI = "rsi" in samplePoint;
  const hasMACD = "macd" in samplePoint;
  const hasBB = "bb_upper" in samplePoint;
  
  // Extract all indicator column names (excluding base columns)
  const indicatorCols = Object.keys(samplePoint).filter(k => 
    !["date", "close", "portfolio"].includes(k)
  );

  return (
    <>
      <Head>
        <title>MokshaGPT – AI Backtester | Backtesting Trading Strategies in Plain English</title>
        <meta name="description" content="The best free AI backtester — describe any trading strategy in plain English and get instant backtest results. Backtest SMA, RSI, MACD, Bollinger Bands strategies across US, Indian, and global markets with detailed metrics and charts." />
        <meta name="keywords" content="ai backtester, backtester, backtesting trading strategies, trading strategy backtester, ai backtesting, backtest trading strategies, algorithmic trading backtester, RSI backtester, MACD backtester, SMA crossover backtest, strategy backtesting tool, free backtester, stock backtester" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="robots" content="index, follow" />
        <link rel="canonical" href="https://mokshagpt.com/aibacktester" />

        {/* Open Graph */}
        <meta property="og:type" content="website" />
        <meta property="og:url" content="https://mokshagpt.com/aibacktester" />
        <meta property="og:title" content="MokshaGPT – AI Backtester | Backtest Trading Strategies Free" />
        <meta property="og:description" content="Describe any trading strategy in plain English and backtest it instantly. Get Sharpe ratio, win rate, max drawdown, profit factor, and a full trade log. The smartest AI backtester — free to use." />
        <meta property="og:image" content="https://mokshagpt.com/og-backtest.jpg" />

        {/* Twitter */}
        <meta property="twitter:card" content="summary_large_image" />
        <meta property="twitter:url" content="https://mokshagpt.com/aibacktester" />
        <meta property="twitter:title" content="MokshaGPT – AI Backtester | Backtesting Trading Strategies" />
        <meta property="twitter:description" content="The best free AI backtester. Describe any strategy in plain English — SMA, RSI, MACD, Bollinger Bands — and get instant backtest results with charts and metrics." />
        <meta property="twitter:image" content="https://mokshagpt.com/twitter-backtest.jpg" />

        {/* Structured Data – SoftwareApplication */}
        <script type="application/ld+json">
          {JSON.stringify({
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": "MokshaGPT AI Backtester",
            "applicationCategory": "FinanceApplication",
            "description": "AI backtester for backtesting trading strategies in plain English. Supports SMA, EMA, RSI, MACD, Bollinger Bands, and custom strategies across global markets.",
            "url": "https://mokshagpt.com/aibacktester",
            "offers": {
              "@type": "Offer",
              "price": "0",
              "priceCurrency": "USD"
            },
            "featureList": [
              "AI backtester",
              "Backtesting trading strategies in plain English",
              "SMA crossover backtester",
              "RSI strategy backtester",
              "MACD backtester",
              "Bollinger Bands backtester",
              "Sharpe ratio, Sortino ratio, Calmar ratio",
              "Max drawdown analysis",
              "Win rate and profit factor",
              "Interactive portfolio charts",
              "Full trade log with CSV export",
              "Global market coverage"
            ]
          })}
        </script>

        {/* Structured Data – FAQPage */}
        <script type="application/ld+json">
          {JSON.stringify({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
              {
                "@type": "Question",
                "name": "What is an AI backtester?",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "An AI backtester lets you describe a trading strategy in plain English and automatically runs a historical backtest on real market data. MokshaGPT's AI backtester parses your strategy, generates the signal code, and returns full performance metrics including Sharpe ratio, win rate, max drawdown, and profit factor."
                }
              },
              {
                "@type": "Question",
                "name": "How do I backtest a trading strategy with AI?",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "Simply describe your strategy in plain English — for example, 'RSI strategy on AAPL: buy when RSI < 30, sell when RSI > 70, 2 years, $50,000'. The AI backtester will parse it, run the backtest, and return detailed results with charts."
                }
              },
              {
                "@type": "Question",
                "name": "Which strategies can I backtest?",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "You can backtest any strategy including SMA crossovers, EMA crossovers, RSI mean reversion, MACD signal crossovers, Bollinger Bands breakouts, Golden Cross, and custom multi-indicator strategies. The AI backtester supports US, Indian, UK, German, Japanese, Australian, Canadian, Crypto, Forex, and Futures markets."
                }
              },
              {
                "@type": "Question",
                "name": "What metrics does the backtester provide?",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "The AI backtester provides total return, annualized return, Sharpe ratio, Sortino ratio, Calmar ratio, max drawdown, win rate, profit factor, expectancy, average win/loss, gross profit/loss, total fees, and a complete trade-by-trade log downloadable as CSV."
                }
              }
            ]
          })}
        </script>
      </Head>

      <div className="min-h-screen bg-gradient-to-br from-indigo-950 via-slate-900 to-gray-900">
        <Header />

        <main className="max-w-7xl mx-auto px-6 py-10">
          {/* Hero */}
          <div className="text-center mb-10">
            <div className="inline-flex items-center gap-2 px-3 py-1 bg-cyan-900/40 border border-cyan-500/30 rounded-full text-cyan-300 text-xs mb-4">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
              Free AI Backtester — No Sign-up Required
            </div>
            <h1 className="text-4xl font-extrabold text-white mb-3">
              <span className="bg-gradient-to-r from-cyan-400 via-blue-400 to-cyan-400 bg-clip-text text-transparent">
                AI Backtester for Trading Strategies
              </span>
            </h1>
            <p className="text-cyan-100 max-w-2xl mx-auto mb-2">
              The smartest <span className="text-white font-semibold">backtester</span> powered by AI. Describe any trading strategy in plain English — the AI parses it, runs a full historical backtest, and returns detailed performance metrics including Sharpe ratio, drawdown, win rate, and profit factor.
            </p>
            <p className="text-cyan-200 max-w-xl mx-auto text-sm">
              Backtesting trading strategies has never been easier. No code. No spreadsheets. Just plain English.
            </p>
            <p className="text-cyan-300 text-sm mt-2">
              🌍 Global Markets • US, India, UK, Germany, Japan, HK, Australia, Canada • Crypto • Forex • Futures
            </p>
            {/* Optimizer CTA */}
            <div className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-violet-900/30 border border-violet-500/30 rounded-full text-violet-300 text-xs hover:bg-violet-900/50 transition-all">
              <span>🚀</span>
              <span>Want the AI to auto-refine your strategy?</span>
              <Link href="/backtest-optimizer" className="text-violet-200 font-semibold underline underline-offset-2 hover:text-white">
                Try the Backtest Optimizer →
              </Link>
            </div>
          </div>

          {/* Input */}
          <div className="max-w-3xl mx-auto mb-8">
            {/* Disclaimer */}
            <div className="mb-4 bg-amber-950/30 border border-amber-500/30 rounded-xl px-5 py-4 flex gap-3 text-xs text-amber-200/80">
              <span className="text-amber-400 text-base shrink-0 mt-0.5">⚠️</span>
              <span>
                <span className="font-semibold text-amber-300">Research tool only — not financial advice. </span>
                Backtest results are based on historical data and do not guarantee future performance. Results include estimated fees and slippage but exclude taxes, borrowing costs, and liquidity constraints. Always paper trade before risking real capital.
              </span>
            </div>
            <div className="bg-slate-800/60 backdrop-blur-xl rounded-2xl border border-cyan-500/30 p-6 shadow-2xl">
              <label className="block text-cyan-300 text-sm font-medium mb-2">
                Describe your strategy
              </label>
              <textarea
                rows={3}
                placeholder="e.g. Backtest a 10/50 SMA crossover on TCS.NS for 3 years with ₹500,000 capital"
                value={strategy}
                onChange={(e) => setStrategy(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleBacktest(); } }}
                className="w-full px-4 py-3 text-white bg-slate-900/70 border-2 border-cyan-500/30 rounded-xl focus:outline-none focus:border-cyan-500 transition-all placeholder:text-slate-400 resize-none"
              />

              {/* Market indicators */}
              <div className="mt-2 flex items-center gap-2 text-xs text-slate-400 flex-wrap">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                  🇺🇸 US (AAPL, TSLA, SPY)
                </span>
                <span className="text-slate-600">•</span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-orange-500"></span>
                  🇮🇳 India (.NS suffix)
                </span>
                <span className="text-slate-600">•</span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-purple-500"></span>
                  ₿ Crypto (BTC-USD)
                </span>
                <span className="text-slate-600">•</span>
                <span className="text-slate-500">UK (.L) • Germany (.DE) • Japan (.T) • HK (.HK) • AU (.AX)</span>
              </div>

              {/* Popular strategies picker */}
              <div className="mt-4">
                <p className="text-slate-400 text-xs mb-2 uppercase tracking-wider">Popular Strategies</p>
                <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                  {POPULAR_STRATEGIES.map((group) => (
                    <div key={group.category}>
                      <p className="text-xs text-slate-500 mb-1">{group.category}</p>
                      <div className="flex flex-wrap gap-1.5">
                        {group.items.map((item) => (
                          <button
                            key={item.label}
                            onClick={() => setStrategy(item.prompt)}
                            className={`text-xs px-3 py-1 rounded-full border transition-all
                              ${group.color === "cyan"    ? "bg-cyan-900/40 border-cyan-500/30 text-cyan-300 hover:bg-cyan-800/50 hover:text-white" : ""}
                              ${group.color === "purple"  ? "bg-purple-900/40 border-purple-500/30 text-purple-300 hover:bg-purple-800/50 hover:text-white" : ""}
                              ${group.color === "blue"    ? "bg-blue-900/40 border-blue-500/30 text-blue-300 hover:bg-blue-800/50 hover:text-white" : ""}
                              ${group.color === "emerald" ? "bg-emerald-900/40 border-emerald-500/30 text-emerald-300 hover:bg-emerald-800/50 hover:text-white" : ""}
                              ${group.color === "orange"  ? "bg-orange-900/40 border-orange-500/30 text-orange-300 hover:bg-orange-800/50 hover:text-white" : ""}
                              ${group.color === "pink"    ? "bg-pink-900/40 border-pink-500/30 text-pink-300 hover:bg-pink-800/50 hover:text-white" : ""}
                            `}
                          >
                            {item.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <button
                onClick={handleBacktest}
                disabled={loading || !strategy.trim()}
                className="mt-4 w-full py-3 bg-gradient-to-r from-cyan-600 to-blue-600 text-white font-semibold rounded-xl hover:from-cyan-700 hover:to-blue-700 disabled:from-slate-600 disabled:to-slate-700 disabled:cursor-not-allowed transition-all shadow-lg shadow-cyan-500/30"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Running Backtest…
                  </span>
                ) : (
                  "Run Backtest"
                )}
              </button>

              {error && (
                <div className="mt-4 bg-red-900/40 border-l-4 border-red-500 text-red-200 px-4 py-3 rounded text-sm">
                  {error}
                </div>
              )}
            </div>
          </div>

          {/* Results — always shows the latest turn's result */}
          {result && m && ps && cd && (
            <div className="space-y-8">
              {/* Strategy Summary */}
              <div className="bg-slate-800/40 border border-cyan-500/20 rounded-2xl p-5">
                <h3 className="text-white font-bold text-lg mb-2">Parsed Strategy</h3>
                <p className="text-cyan-200 mb-3 text-sm">{ps.strategy_description}</p>
                <div className="flex flex-wrap gap-3 text-sm">
                  <span className="px-3 py-1 bg-cyan-900/50 border border-cyan-500/30 rounded-full text-cyan-200">
                    📌 {ps.ticker}
                  </span>
                  <span className="px-3 py-1 bg-cyan-900/50 border border-cyan-500/30 rounded-full text-cyan-200">
                    {ps.start_date && ps.end_date
                      ? `📅 ${ps.start_date} to ${ps.end_date}`
                      : ps.timeframe && ps.timeframe !== "1d" 
                      ? `⏱️ ${ps.timeframe} (${ps.period_days} days)`
                      : ps.period_years
                      ? `📅 ${ps.period_years} year${ps.period_years !== 1 ? "s" : ""}`
                      : `📅 ${ps.period_days ?? "—"} days`
                    }
                  </span>
                  <span className="px-3 py-1 bg-cyan-900/50 border border-cyan-500/30 rounded-full text-cyan-200">
                    💰 {ps.initial_capital.toLocaleString()} capital
                  </span>
                  {indicatorCols.length > 0 && (
                    <span className="px-3 py-1 bg-slate-700/50 border border-slate-500/30 rounded-full text-slate-300">
                      📊 {indicatorCols.length} indicator{indicatorCols.length !== 1 ? "s" : ""}: {indicatorCols.slice(0, 3).join(", ")}{indicatorCols.length > 3 ? "..." : ""}
                    </span>
                  )}
                  {/* Position sizing tag */}
                  {(() => {
                    const ps_mode = ps.position_sizing?.mode ?? "all_in";
                    const ps_val  = ps.position_sizing?.value;
                    const kelly_pct = (ps.position_sizing as any)?.computed_kelly_pct;
                    const label =
                      ps_mode === "fixed_shares" ? `📦 ${ps_val} shares/trade` :
                      ps_mode === "fixed_amount" ? `📦 ${(ps_val ?? 0).toLocaleString()} per trade` :
                      ps_mode === "pct_capital"  ? `📦 ${ps_val}% of capital/trade` :
                      ps_mode === "risk_pct"     ? `📦 Risk ${ps_val}% per trade` :
                      ps_mode === "half_kelly"   ? `📦 Half-Kelly${kelly_pct != null ? ` (${kelly_pct}%)` : ""}` :
                      ps_mode === "kelly"        ? `📦 Full Kelly${kelly_pct != null ? ` (${kelly_pct}%)` : ""}` :
                                                   "📦 All-in per trade";
                    return (
                      <span className="px-3 py-1 bg-slate-700/50 border border-slate-500/30 rounded-full text-slate-300">
                        {label}
                      </span>
                    );
                  })()}
                </div>
              </div>

              {/* Backtest Disclaimer */}
              <div className="flex gap-3 bg-slate-700/30 border border-slate-500/30 rounded-xl px-4 py-3 text-xs text-slate-400">
                <span className="shrink-0 mt-0.5">⚠️</span>
                <span>
                  <span className="text-slate-300 font-semibold">Backtest disclaimer: </span>
                  Trades execute at bar close. Real fills may differ by 1–2 bars due to market impact and latency.
                  Results include estimated fees ({m.fee_description || ps.fee_description || "0.1% per trade"})
                  {m.slippage_description ? ` and slippage (${m.slippage_description})` : ""}.
                  Taxes, borrowing costs, and liquidity constraints are excluded.
                  Past performance does not guarantee future results.
                </span>
              </div>

              {/* Plain-English Strategy Verdict */}
              {(() => {
                // Score the strategy across 6 dimensions, each worth 1 point
                const totalReturn   = m.total_return_pct ?? 0;
                const alpha         = totalReturn - (m.buy_hold_return_pct ?? 0);
                const winRate       = m.win_rate_pct ?? 0;
                const profitFactor  = m.profit_factor ?? 0;
                const maxDD         = Math.abs(m.max_drawdown_pct ?? 0);
                const sharpe        = m.sharpe_ratio ?? 0;
                const expectancy    = m.expectancy ?? 0;
                const totalTrades   = m.total_trades ?? 0;

                // Special case: No trades executed
                if (totalTrades === 0) {
                  return (
                    <div className="bg-slate-800/50 border border-slate-600/40 rounded-2xl p-5">
                      <div className="flex items-center gap-3 mb-4">
                        <span className="text-3xl">⚠️</span>
                        <div>
                          <h3 className="text-white font-bold text-lg">Strategy Verdict</h3>
                          <span className="text-yellow-300 text-xl font-bold">No Trading Activity</span>
                        </div>
                      </div>
                      <ul className="space-y-2">
                        <li className="flex items-start gap-2 text-sm">
                          <span className="mt-0.5 shrink-0 text-yellow-400">⚠</span>
                          <span className="text-slate-200">
                            No trades were executed during this period — the strategy conditions were never met.
                          </span>
                        </li>
                        <li className="flex items-start gap-2 text-sm">
                          <span className="mt-0.5 shrink-0 text-slate-500">•</span>
                          <span className="text-slate-400">
                            This could mean: (1) the backtest period was too short, (2) the market didn't move in a way that triggered your entry conditions, or (3) the strategy parameters need adjustment.
                          </span>
                        </li>
                        <li className="flex items-start gap-2 text-sm">
                          <span className="mt-0.5 shrink-0 text-cyan-400">💡</span>
                          <span className="text-slate-300">
                            Try: extending the backtest period (e.g., 6 months or 1 year instead of 1 month), adjusting strategy parameters, or testing on a different asset.
                          </span>
                        </li>
                      </ul>
                    </div>
                  );
                }

                let score = 0;
                if (totalReturn > 0)      score++;
                if (alpha > 0)            score++;
                if (winRate >= 50)        score++;
                if (profitFactor >= 1.5)  score++;
                if (sharpe >= 1)          score++;
                if (expectancy > 0)       score++;

                // Overall verdict
                type Verdict = { label: string; color: string; bg: string; border: string; icon: string };
                const verdict: Verdict =
                  score >= 5 ? { label: "Strong Edge",    color: "text-emerald-300", bg: "bg-emerald-950/50", border: "border-emerald-500/40", icon: "🚀" } :
                  score >= 4 ? { label: "Decent Edge",    color: "text-cyan-300",    bg: "bg-cyan-950/50",    border: "border-cyan-500/40",    icon: "✅" } :
                  score >= 3 ? { label: "Marginal Edge",  color: "text-yellow-300",  bg: "bg-yellow-950/50",  border: "border-yellow-500/40",  icon: "⚠️" } :
                               { label: "No Edge",        color: "text-red-300",     bg: "bg-red-950/50",     border: "border-red-500/40",     icon: "❌" };

                // Build plain-English bullet points
                const bullets: { text: string; good: boolean }[] = [];

                // 1. Profitability
                if (totalReturn > 20)
                  bullets.push({ text: `Strong profit of ${totalReturn.toFixed(1)}% over the period — the strategy made good money.`, good: true });
                else if (totalReturn > 0)
                  bullets.push({ text: `Modest profit of ${totalReturn.toFixed(1)}% — the strategy made money but not a lot.`, good: true });
                else
                  bullets.push({ text: `Lost ${Math.abs(totalReturn).toFixed(1)}% overall — the strategy lost money.`, good: false });

                // 2. vs Buy & Hold
                if (alpha > 5)
                  bullets.push({ text: `Outperformed simply holding the asset by ${alpha.toFixed(1)}% — active trading added real value here.`, good: true });
                else if (alpha > 0)
                  bullets.push({ text: `Slightly beat buy-and-hold by ${alpha.toFixed(1)}% — marginal advantage over doing nothing.`, good: true });
                else
                  bullets.push({ text: `Underperformed buy-and-hold by ${Math.abs(alpha).toFixed(1)}% — you'd have done better just holding the asset.`, good: false });

                // 3. Win rate
                if (winRate >= 65)
                  bullets.push({ text: `Won ${winRate.toFixed(0)}% of trades — the strategy was right more often than not.`, good: true });
                else if (winRate >= 50)
                  bullets.push({ text: `Won ${winRate.toFixed(0)}% of trades — slightly more winners than losers.`, good: true });
                else
                  bullets.push({ text: `Only won ${winRate.toFixed(0)}% of trades — more losing trades than winning ones.`, good: false });

                // 4. Risk (drawdown)
                if (maxDD < 10)
                  bullets.push({ text: `Maximum loss from peak was only ${maxDD.toFixed(1)}% — low risk, the portfolio stayed relatively stable.`, good: true });
                else if (maxDD < 20)
                  bullets.push({ text: `Maximum loss from peak was ${maxDD.toFixed(1)}% — moderate risk, expect some uncomfortable dips.`, good: true });
                else
                  bullets.push({ text: `Maximum loss from peak was ${maxDD.toFixed(1)}% — high risk, the portfolio dropped significantly at some point.`, good: false });

                // 5. Profit factor
                if (profitFactor >= 2)
                  bullets.push({ text: `For every dollar lost, the strategy made ${profitFactor.toFixed(1)} dollars — a strong reward-to-risk ratio.`, good: true });
                else if (profitFactor >= 1.5)
                  bullets.push({ text: `For every dollar lost, the strategy made ${profitFactor.toFixed(1)} dollars — a decent reward-to-risk ratio.`, good: true });
                else if (profitFactor >= 1)
                  bullets.push({ text: `For every dollar lost, the strategy made ${profitFactor.toFixed(1)} dollars — barely profitable, thin margin.`, good: false });
                else if (profitFactor > 0)
                  bullets.push({ text: `For every dollar made, the strategy lost ${(1/profitFactor).toFixed(1)} dollars — losses outweigh gains.`, good: false });

                // 6. Trade count warning
                if (totalTrades < 5)
                  bullets.push({ text: `Only ${totalTrades} trade${totalTrades !== 1 ? "s" : ""} in the period — too few to draw reliable conclusions. Results may be luck.`, good: false });
                else if (totalTrades >= 20)
                  bullets.push({ text: `${totalTrades} trades over the period — enough data to have reasonable confidence in the results.`, good: true });

                return (
                  <div className={`${verdict.bg} border ${verdict.border} rounded-2xl p-5`}>
                    <div className="flex items-center gap-3 mb-4">
                      <span className="text-3xl">{verdict.icon}</span>
                      <div>
                        <h3 className="text-white font-bold text-lg">Strategy Verdict</h3>
                        <span className={`text-xl font-bold ${verdict.color}`}>{verdict.label}</span>
                        <span className="text-slate-400 text-sm ml-2">({score}/6 criteria met)</span>
                      </div>
                    </div>
                    <ul className="space-y-2">
                      {bullets.map((b, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm">
                          <span className={`mt-0.5 shrink-0 ${b.good ? "text-emerald-400" : "text-red-400"}`}>
                            {b.good ? "✓" : "✗"}
                          </span>
                          <span className={b.good ? "text-slate-200" : "text-slate-400"}>{b.text}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })()}

              {/* Metrics Grid */}
              <div>
                <h3 className="text-white font-bold text-lg mb-3">Performance Metrics</h3>

                {/* Fee notice — always shown so users know results are after fees */}
                <div className="mb-4 flex gap-3 bg-slate-700/40 border border-slate-500/30 rounded-xl px-4 py-3 text-sm text-slate-300">
                  <span className="text-slate-400 text-base mt-0.5 shrink-0">💸</span>
                  <div>
                    <span className="font-semibold text-slate-200">Results include trading fees:</span>{" "}
                    {m.fee_description || ps.fee_description || "0.1% per trade"}.
                    {ps.ticker?.endsWith(".NS") || ps.ticker?.endsWith(".BO") ? (
                      <span className="text-slate-400">
                        {" "}Indian brokers (Zerodha, Groww, etc.) charge a flat ₹20 per order — approximated here as 0.03%.
                        For smaller trade sizes the actual fee will be higher.
                      </span>
                    ) : (
                      <span className="text-slate-400">
                        {" "}Actual fees vary by broker. Adjust your strategy query to include a custom fee if needed.
                      </span>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
                  <MetricCard
                    label="Total Return"
                    value={pct(m.total_return_pct)}
                    sub={`Final: ${fmt(m.final_value)}`}
                    positive={m.total_return_pct >= 0}
                  />
                  <MetricCard
                    label="Buy & Hold Return"
                    value={pct(m.buy_hold_return_pct)}
                    positive={m.buy_hold_return_pct >= 0}
                  />
                  <MetricCard
                    label="Annualized Return"
                    value={pct(m.annualized_return_pct)}
                    positive={m.annualized_return_pct >= 0}
                  />
                  <MetricCard
                    label="Sharpe Ratio"
                    value={fmt(m.sharpe_ratio, 3)}
                    positive={m.sharpe_ratio >= 1}
                  />
                  <MetricCard
                    label="Max Drawdown"
                    value={`${fmt(m.max_drawdown_pct)}%`}
                    positive={m.max_drawdown_pct > -10}
                  />
                  <MetricCard
                    label="Win Rate"
                    value={`${fmt(m.win_rate_pct)}%`}
                    sub={`${m.wins}W / ${m.losses}L`}
                    positive={m.win_rate_pct >= 50}
                  />
                  <MetricCard
                    label="Total Trades"
                    value={String(m.total_trades)}
                  />
                  <MetricCard
                    label="Alpha vs B&H"
                    value={pct(m.total_return_pct - m.buy_hold_return_pct)}
                    positive={m.total_return_pct >= m.buy_hold_return_pct}
                  />
                  
                  {/* Enhanced VectorBT Metrics */}
                  {m.sortino_ratio !== undefined && (
                    <MetricCard
                      label="Sortino Ratio"
                      value={fmt(m.sortino_ratio, 3)}
                      sub="Downside risk-adjusted"
                      positive={m.sortino_ratio >= 1}
                    />
                  )}
                  {m.calmar_ratio !== undefined && (
                    <MetricCard
                      label="Calmar Ratio"
                      value={fmt(m.calmar_ratio, 3)}
                      sub="Return/Max Drawdown"
                      positive={m.calmar_ratio >= 1}
                    />
                  )}
                  {m.profit_factor !== undefined && (
                    <MetricCard
                      label="Profit Factor"
                      value={fmt(m.profit_factor, 2)}
                      sub="Gross Profit/Loss"
                      positive={m.profit_factor >= 1.5}
                    />
                  )}
                  {m.expectancy !== undefined && (
                    <MetricCard
                      label="Expectancy"
                      value={fmt(m.expectancy, 2)}
                      sub="Expected $ per trade"
                      positive={m.expectancy >= 0}
                    />
                  )}
                  {m.avg_win !== undefined && m.avg_loss !== undefined && (
                    <MetricCard
                      label="Avg Win/Loss"
                      value={`${fmt(m.avg_win, 0)} / ${fmt(Math.abs(m.avg_loss), 0)}`}
                      sub="Average trade P&L"
                      positive={m.avg_win > Math.abs(m.avg_loss)}
                    />
                  )}
                  {m.total_fees !== undefined && m.total_fees > 0 && (
                    <MetricCard
                      label="Total Fees Paid"
                      value={fmt(m.total_fees, 2)}
                      sub={`${m.fee_rate_pct ?? 0}% per trade`}
                      positive={false}
                    />
                  )}
                </div>
              </div>

              {/* Portfolio Value Chart */}
              <div className="bg-slate-800/40 border border-cyan-500/20 rounded-2xl p-6">
                <h3 className="text-white font-bold text-lg mb-4">Portfolio Value vs Price</h3>
                <ResponsiveContainer width="100%" height={320}>
                  <LineChart data={cd.price_series} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="date" tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} interval="preserveStartEnd" />
                    <YAxis yAxisId="left" tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                    <YAxis yAxisId="right" orientation="right" tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                    <Tooltip content={<ChartTooltip />} />
                    <Legend wrapperStyle={{ color: "#cbd5e1", fontSize: 12 }} />
                    <Line yAxisId="right" type="monotone" dataKey="close" name="Price" stroke="#818cf8" dot={false} strokeWidth={1.5} />
                    <Line yAxisId="left" type="monotone" dataKey="portfolio" name="Portfolio" stroke="#34d399" dot={false} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Indicator Chart */}
              {(hasMA || hasBB) && (
                <div className="bg-slate-800/40 border border-cyan-500/20 rounded-2xl p-6">
                  <h3 className="text-white font-bold text-lg mb-4">
                    {hasBB ? "Bollinger Bands" : "Moving Averages"}
                  </h3>
                  <ResponsiveContainer width="100%" height={280}>
                    <LineChart data={cd.price_series} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis dataKey="date" tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} interval="preserveStartEnd" />
                      <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} />
                      <Tooltip content={<ChartTooltip />} />
                      <Legend wrapperStyle={{ color: "#cbd5e1", fontSize: 12 }} />
                      <Line type="monotone" dataKey="close" name="Price" stroke="#818cf8" dot={false} strokeWidth={1.5} />
                      {/* Dynamically render MA lines */}
                      {indicatorCols.filter(c => c.includes("ma") || c.includes("sma") || c.includes("ema")).map((col, i) => (
                        <Line key={col} type="monotone" dataKey={col} name={col.toUpperCase()} stroke={["#f59e0b", "#ef4444", "#10b981", "#06b6d4"][i % 4]} dot={false} strokeWidth={1.5} />
                      ))}
                      {/* Bollinger Bands */}
                      {hasBB && <Line type="monotone" dataKey="bb_upper" name="Upper Band" stroke="#f59e0b" dot={false} strokeWidth={1} strokeDasharray="4 2" />}
                      {hasBB && <Line type="monotone" dataKey="bb_mid" name="Middle Band" stroke="#94a3b8" dot={false} strokeWidth={1} />}
                      {hasBB && <Line type="monotone" dataKey="bb_lower" name="Lower Band" stroke="#f59e0b" dot={false} strokeWidth={1} strokeDasharray="4 2" />}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {hasRSI && (
                <div className="bg-slate-800/40 border border-cyan-500/20 rounded-2xl p-6">
                  <h3 className="text-white font-bold text-lg mb-4">RSI Indicator</h3>
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart data={cd.price_series} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis dataKey="date" tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} interval="preserveStartEnd" />
                      <YAxis domain={[0, 100]} tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} />
                      <Tooltip content={<ChartTooltip />} />
                      <ReferenceLine y={70} stroke="#ef4444" strokeDasharray="4 2" label={{ value: "Overbought 70", fill: "#ef4444", fontSize: 10 }} />
                      <ReferenceLine y={30} stroke="#34d399" strokeDasharray="4 2" label={{ value: "Oversold 30", fill: "#34d399", fontSize: 10 }} />
                      <Line type="monotone" dataKey="rsi" name="RSI" stroke="#a78bfa" dot={false} strokeWidth={2} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {hasMACD && (
                <div className="bg-slate-800/40 border border-cyan-500/20 rounded-2xl p-6">
                  <h3 className="text-white font-bold text-lg mb-4">MACD</h3>
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={cd.price_series} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis dataKey="date" tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} interval="preserveStartEnd" />
                      <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} />
                      <Tooltip content={<ChartTooltip />} />
                      <Legend wrapperStyle={{ color: "#cbd5e1", fontSize: 12 }} />
                      <ReferenceLine y={0} stroke="#475569" />
                      <Bar dataKey="macd_hist" name="Histogram" fill="#818cf8" opacity={0.7} />
                      <Line type="monotone" dataKey="macd" name="MACD" stroke="#34d399" dot={false} strokeWidth={1.5} />
                      <Line type="monotone" dataKey="macd_signal" name="Signal" stroke="#f59e0b" dot={false} strokeWidth={1.5} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Drawdown Chart */}
              <div className="bg-slate-800/40 border border-cyan-500/20 rounded-2xl p-6">
                <h3 className="text-white font-bold text-lg mb-4">Drawdown</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <AreaChart data={cd.drawdown_series} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="date" tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} interval="preserveStartEnd" />
                    <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} tickFormatter={(v) => `${v}%`} />
                    <Tooltip content={<ChartTooltip />} />
                    <Area type="monotone" dataKey="drawdown" name="Drawdown %" stroke="#ef4444" fill="#ef444430" strokeWidth={1.5} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              {/* Trade Log */}
              {cd.trades.length > 0 && (
                <div className="bg-slate-800/40 border border-cyan-500/20 rounded-2xl p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-white font-bold text-lg">
                      Trade Log ({cd.trades.length} trades)
                    </h3>
                    <button
                      onClick={() => downloadTradesCSV(cd.trades, ps.ticker)}
                      className="px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      Download CSV
                    </button>
                  </div>

                  {/* Execution Price Note */}
                  <div className="mb-4 flex gap-3 bg-blue-950/40 border border-blue-500/30 rounded-xl px-4 py-3 text-sm text-blue-200">
                    <span className="text-blue-400 text-base mt-0.5 shrink-0">ℹ️</span>
                    <div>
                      <span className="font-semibold text-blue-300">Execution price:</span>{" "}
                      Entries and exits use the <strong>closing price</strong> of the signal bar ({ps.timeframe || "1d"} candle).
                      Real orders would fill at the next bar&apos;s open.
                    </div>
                  </div>

                  {/* Daily-bar SL/TP fill note — shown only when stop-loss or take-profit is active */}
                  {(() => {
                    const slTpKeys = new Set(["stop_loss_usd", "take_profit_usd", "stop_loss_pct", "take_profit_pct", "stop_loss_pts", "take_profit_pts"]);
                    const hasSlTp = cd.trades.some(t => Object.keys(t).some(k => slTpKeys.has(k)));
                    if (!hasSlTp) return null;
                    const isIntraday = ps.timeframe && ps.timeframe !== "1d";
                    return (
                      <div className="mb-4 flex gap-3 bg-amber-950/40 border border-amber-500/30 rounded-xl px-4 py-3 text-sm text-amber-200">
                        <span className="text-amber-400 text-base mt-0.5 shrink-0">⚠️</span>
                        <div>
                          <span className="font-semibold text-amber-300">
                            {isIntraday ? "Intraday" : "Daily"}-bar fill note:
                          </span>{" "}
                          {isIntraday
                            ? "Stop-loss and take-profit levels are checked at each bar's close. The actual fill executes at the next bar's open, so the realized P&L may differ slightly from the exact threshold."
                            : "Stop-loss and take-profit levels are checked at each day's closing price. The actual fill executes at the next trading day's open price. Because the market can move significantly overnight or intraday before the close, the realized P&L may overshoot the target — this is standard behavior in all daily-bar backtesting systems and reflects realistic execution constraints."
                          }
                        </div>
                      </div>
                    );
                  })()}
                  {(() => {
                    // Derive indicator columns from the first trade that has extras
                    const fixedCols = new Set(["date", "type", "price", "shares", "value", "pnl", "pnl_pct", "days_held", "_timestamp"]);
                    const tradeIndicatorCols = Array.from(
                      new Set(cd.trades.flatMap(t => Object.keys(t).filter(k => !fixedCols.has(k))))
                    );
                    
                    // Calculate pagination
                    const totalPages = Math.ceil(cd.trades.length / tradesPerPage);
                    const startIdx = (currentPage - 1) * tradesPerPage;
                    const endIdx = startIdx + tradesPerPage;
                    const paginatedTrades = cd.trades.slice(startIdx, endIdx);
                    
                    return (
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="text-cyan-300 border-b border-cyan-500/20">
                              <th className="text-left py-2 pr-4">#</th>
                              <th className="text-left py-2 pr-4">Date</th>
                              <th className="text-left py-2 pr-4">Type</th>
                              <th className="text-right py-2 pr-4">Price</th>
                              <th className="text-right py-2 pr-4">Shares</th>
                              <th className="text-right py-2 pr-4">Trade Value</th>
                              {/* Dynamic indicator columns */}
                              {tradeIndicatorCols.map(col => (
                                <th key={col} className="text-right py-2 pr-4 text-amber-300">
                                  {col.toUpperCase()}
                                </th>
                              ))}
                              <th className="text-right py-2 pr-4">P&L</th>
                              <th className="text-right py-2 pr-4">P&L %</th>
                              <th className="text-right py-2">Days Held</th>
                            </tr>
                          </thead>
                          <tbody>
                            {paginatedTrades.map((t, i) => (
                              <tr key={startIdx + i} className="border-b border-slate-700/40 hover:bg-slate-700/20 transition-colors">
                                <td className="py-2 pr-4 text-slate-400">{startIdx + i + 1}</td>
                                <td className="py-2 pr-4 text-slate-300 font-mono">{t.date}</td>
                                <td className="py-2 pr-4">
                                  <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                                    t.type === "BUY" || t.type === "SHORT" 
                                      ? "bg-emerald-900/50 text-emerald-400" 
                                      : "bg-red-900/50 text-red-400"
                                  }`}>
                                    {t.type}
                                  </span>
                                </td>
                                <td className="py-2 pr-4 text-right text-slate-300 font-mono">{fmt(t.price)}</td>
                                <td className="py-2 pr-4 text-right text-slate-300 font-mono">{typeof t.shares === 'number' ? (Number.isInteger(t.shares) ? t.shares.toLocaleString() : fmt(t.shares, 6).replace(/\.?0+$/, '')) : t.shares}</td>
                                <td className="py-2 pr-4 text-right text-slate-300 font-mono">{fmt(t.value ?? 0)}</td>
                                {/* Dynamic indicator values */}
                                {tradeIndicatorCols.map(col => (
                                  <td key={col} className="py-2 pr-4 text-right font-mono text-amber-200">
                                    {t[col] != null ? fmt(t[col]) : "-"}
                                  </td>
                                ))}
                                <td className={`py-2 pr-4 text-right font-mono font-semibold ${(t.pnl ?? 0) > 0 ? "text-emerald-400" : (t.pnl ?? 0) < 0 ? "text-red-400" : "text-slate-400"}`}>
                                  {(t.type === "SELL" || t.type === "COVER") ? ((t.pnl ?? 0) >= 0 ? "+" : "") + fmt(t.pnl ?? 0) : "-"}
                                </td>
                                <td className={`py-2 pr-4 text-right font-mono font-semibold ${(t.pnl_pct ?? 0) > 0 ? "text-emerald-400" : (t.pnl_pct ?? 0) < 0 ? "text-red-400" : "text-slate-400"}`}>
                                  {(t.type === "SELL" || t.type === "COVER") ? ((t.pnl_pct ?? 0) >= 0 ? "+" : "") + fmt(t.pnl_pct ?? 0) + "%" : "-"}
                                </td>
                                <td className="py-2 text-right text-slate-300">
                                  {(t.type === "SELL" || t.type === "COVER") ? `${t.days_held} days` : "-"}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        
                        {/* Pagination Controls */}
                        {totalPages > 1 && (
                          <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-700/40">
                            <div className="flex items-center gap-2">
                              <label className="text-slate-400 text-sm">Trades per page:</label>
                              <select
                                value={tradesPerPage}
                                onChange={(e) => {
                                  setTradesPerPage(Number(e.target.value));
                                  setCurrentPage(1);
                                }}
                                className="bg-slate-700 text-white text-sm px-2 py-1 rounded border border-slate-600 hover:border-cyan-500/50"
                              >
                                <option value={25}>25</option>
                                <option value={50}>50</option>
                                <option value={100}>100</option>
                                <option value={200}>200</option>
                              </select>
                            </div>
                            
                            <div className="text-slate-400 text-sm">
                              Page {currentPage} of {totalPages} ({startIdx + 1}-{Math.min(endIdx, cd.trades.length)} of {cd.trades.length})
                            </div>
                            
                            <div className="flex gap-2">
                              <button
                                onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                                disabled={currentPage === 1}
                                className="px-3 py-1 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm rounded border border-slate-600 transition-colors"
                              >
                                ← Prev
                              </button>
                              <button
                                onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                                disabled={currentPage === totalPages}
                                className="px-3 py-1 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm rounded border border-slate-600 transition-colors"
                              >
                                Next →
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>
              )}

              {/* Disclaimer */}
              <p className="text-center text-slate-500 text-xs pb-4">
                Past performance is not indicative of future results. This is for educational purposes only and not financial advice.
              </p>
            </div>
          )}
        </main>

        {/* ── SEO Content: Features + FAQ ── */}
        <section className="bg-slate-900/60 border-t border-cyan-500/10 py-16">
          <div className="max-w-6xl mx-auto px-6">

            {/* What is an AI Backtester */}
            <div className="text-center mb-12">
              <h2 className="text-3xl font-bold text-white mb-3">
                What is an AI Backtester?
              </h2>
              <p className="text-cyan-200 max-w-2xl mx-auto">
                An AI backtester combines artificial intelligence with historical market data to let you test any trading strategy without writing a single line of code. Just describe your strategy in plain English and get institutional-grade backtest results in seconds.
              </p>
            </div>

            {/* Feature cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-14">
              <div className="bg-slate-800/50 border border-cyan-500/20 rounded-2xl p-6 hover:border-cyan-500/40 transition-all">
                <div className="text-3xl mb-3">💬</div>
                <h3 className="text-white font-bold text-lg mb-2">Plain English Input</h3>
                <p className="text-slate-300 text-sm leading-relaxed">
                  No code required. Describe your strategy naturally — "RSI buy below 30, sell above 70 on AAPL for 2 years" — and the AI backtester handles the rest.
                </p>
              </div>
              <div className="bg-slate-800/50 border border-blue-500/20 rounded-2xl p-6 hover:border-blue-500/40 transition-all">
                <div className="text-3xl mb-3">📊</div>
                <h3 className="text-white font-bold text-lg mb-2">Full Performance Metrics</h3>
                <p className="text-slate-300 text-sm leading-relaxed">
                  Every backtest returns Sharpe ratio, Sortino ratio, Calmar ratio, max drawdown, win rate, profit factor, expectancy, and a complete trade-by-trade log.
                </p>
              </div>
              <div className="bg-slate-800/50 border border-purple-500/20 rounded-2xl p-6 hover:border-purple-500/40 transition-all">
                <div className="text-3xl mb-3">🌍</div>
                <h3 className="text-white font-bold text-lg mb-2">Global Markets</h3>
                <p className="text-slate-300 text-sm leading-relaxed">
                  Backtest trading strategies on US, Indian (NSE/BSE), UK, German, Japanese, Australian, Canadian, Crypto, Forex, and Futures markets — all from one backtester.
                </p>
              </div>
              <div className="bg-slate-800/50 border border-emerald-500/20 rounded-2xl p-6 hover:border-emerald-500/40 transition-all">
                <div className="text-3xl mb-3">⏱️</div>
                <h3 className="text-white font-bold text-lg mb-2">Intraday Backtesting</h3>
                <p className="text-slate-300 text-sm leading-relaxed">
                  Not just daily — backtest intraday strategies on 1-min, 5-min, 15-min, and 1-hour timeframes. Perfect for scalping and day trading strategy validation.
                </p>
              </div>
            </div>

            {/* Strategies you can backtest */}
            <div className="bg-slate-800/30 border border-cyan-500/15 rounded-2xl p-8 mb-14">
              <h2 className="text-2xl font-bold text-white mb-6 text-center">Strategies You Can Backtest</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {[
                  { icon: "📈", name: "SMA / EMA Crossovers", desc: "Golden Cross, 10/50 SMA, EMA 9/21 — any moving average crossover strategy." },
                  { icon: "📉", name: "RSI Mean Reversion", desc: "Buy oversold (RSI < 30), sell overbought (RSI > 70) — classic momentum backtesting." },
                  { icon: "🔀", name: "MACD Strategies", desc: "Signal line crossovers, zero-line crosses, and MACD histogram strategies." },
                  { icon: "📏", name: "Bollinger Bands", desc: "Mean reversion at the bands, breakout strategies, and BB squeeze setups." },
                  { icon: "🔢", name: "Multi-Indicator", desc: "Combine RSI + SMA filter, MACD + Bollinger Bands, or any custom indicator mix." },
                  { icon: "📦", name: "Futures & Forex", desc: "Backtest commodity futures (/GC, /CL), index futures, and Forex pairs like EUR/USD." },
                ].map((s) => (
                  <div key={s.name} className="flex items-start gap-3 bg-slate-700/30 rounded-xl p-4">
                    <span className="text-2xl">{s.icon}</span>
                    <div>
                      <p className="text-white font-semibold text-sm mb-1">{s.name}</p>
                      <p className="text-slate-400 text-xs leading-relaxed">{s.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* FAQ */}
            <div className="max-w-3xl mx-auto">
              <h2 className="text-2xl font-bold text-white mb-6 text-center">Backtesting FAQ</h2>
              <div className="space-y-4">
                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                  <h3 className="text-white font-semibold mb-2">What is backtesting trading strategies?</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    Backtesting trading strategies means applying a set of trading rules to historical market data to see how the strategy would have performed in the past. It helps traders validate ideas, measure risk-adjusted returns, and refine entry/exit rules before risking real capital.
                  </p>
                </div>
                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                  <h3 className="text-white font-semibold mb-2">How is an AI backtester different from traditional backtesting tools?</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    Traditional backtesting tools like TradingView Pine Script or Python require you to write code. An AI backtester understands plain English — you describe the strategy and the AI generates the signal logic, runs the backtest, and explains the results. No coding knowledge needed.
                  </p>
                </div>
                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                  <h3 className="text-white font-semibold mb-2">Does the backtester account for trading fees and slippage?</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    Yes. MokshaGPT's AI backtester includes realistic trading fees (default 0.1% per trade, adjustable) and slippage estimates. Indian market backtests use NSE-appropriate fee structures. All metrics — total return, Sharpe ratio, profit factor — are calculated after fees.
                  </p>
                </div>
                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                  <h3 className="text-white font-semibold mb-2">Is this backtester free to use?</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    Yes. MokshaGPT's AI backtester is completely free to use for educational and informational purposes. Backtest any strategy across global markets with no sign-up required.
                  </p>
                </div>
              </div>
            </div>

          </div>
        </section>

        <RelatedTools current="/aibacktester" />

        {/* Footer */}
        <footer className="mt-0 bg-slate-900/80 border-t border-cyan-500/20">
          <div className="max-w-7xl mx-auto px-6 py-12">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
              {/* About Section */}
              <div>
                <h3 className="text-white font-bold text-lg mb-3 flex items-center gap-2">
                  <span className="text-2xl">📊</span>
                  About MokshaGPT
                </h3>
                <p className="text-cyan-200 text-sm leading-relaxed">
                  MokshaGPT is an advanced AI-powered platform for stock market analysis and trading strategy backtesting. 
                  We leverage cutting-edge language models and LangGraph agents to help traders and investors make data-driven decisions.
                </p>
                <p className="text-cyan-300 text-xs mt-3 italic">
                  Not financial advice. For educational and informational purposes only.
                </p>
              </div>

              {/* Product Tools */}
              <div>
                <h3 className="text-white font-bold text-lg mb-3">Product Tools</h3>
                <ul className="space-y-2">
                  <li>
                    <Link href="/" className="text-cyan-300 hover:text-white transition-colors text-sm flex items-center gap-2">
                      <span className="text-lg">🏠</span>
                      <span>AI Stock Analysis</span>
                    </Link>
                    <p className="text-slate-400 text-xs ml-7">Get instant AI-powered stock insights</p>
                  </li>
                  <li>
                    <Link href="/aibacktester" className="text-cyan-300 hover:text-white transition-colors text-sm flex items-center gap-2">
                      <span className="text-lg">🔬</span>
                      <span>AI Strategy Backtester</span>
                    </Link>
                    <p className="text-slate-400 text-xs ml-7">Test any trading strategy with AI</p>
                  </li>
                  <li>
                    <Link href="/backtest-optimizer" className="text-cyan-300 hover:text-white transition-colors text-sm flex items-center gap-2">
                      <span className="text-lg">⚡</span>
                      <span>Backtest Optimizer</span>
                    </Link>
                    <p className="text-slate-400 text-xs ml-7">Auto-refine strategies to meet quality targets</p>
                  </li>
                  <li>
                    <Link href="/aiscreener" className="text-cyan-300 hover:text-white transition-colors text-sm flex items-center gap-2">
                      <span className="text-lg">🔍</span>
                      <span>AI Stock Screener</span>
                    </Link>
                    <p className="text-slate-400 text-xs ml-7">Find stocks using natural language</p>
                  </li>
                  <li>
                    <Link href="/aireporter" className="text-cyan-300 hover:text-white transition-colors text-sm flex items-center gap-2">
                      <span className="text-lg">📋</span>
                      <span>AI Reporter</span>
                    </Link>
                    <p className="text-slate-400 text-xs ml-7">Generate professional financial reports</p>
                  </li>
                  <li>
                    <Link href="/tradeanalyzer" className="text-cyan-300 hover:text-white transition-colors text-sm flex items-center gap-2">
                      <span className="text-lg">📈</span>
                      <span>Trade Analyzer</span>
                    </Link>
                    <p className="text-slate-400 text-xs ml-7">Analyze your brokerage trade history</p>
                  </li>
                  <li className="pt-2">
                    <span className="text-slate-500 text-sm flex items-center gap-2">
                      <span className="text-lg">🚀</span>
                      <span>More tools coming soon...</span>
                    </span>
                  </li>
                </ul>
              </div>

              {/* Technology & Features */}
              <div>
                <h3 className="text-white font-bold text-lg mb-3">Technology</h3>
                <ul className="space-y-2 text-sm text-cyan-200">
                  <li className="flex items-start gap-2">
                    <span className="text-cyan-400 mt-1">✓</span>
                    <span>Natural Language Processing</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-cyan-400 mt-1">✓</span>
                    <span>Dynamic Code Generation</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-cyan-400 mt-1">✓</span>
                    <span>Real-time Market Data</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-cyan-400 mt-1">✓</span>
                    <span>Advanced Performance Metrics</span>
                  </li>
                </ul>
              </div>
            </div>

            {/* Bottom Bar */}
            <div className="pt-6 border-t border-cyan-500/20 flex flex-col md:flex-row justify-between items-center gap-4">
              <p className="text-cyan-300 text-sm">
                © 2026 MokshaGPT. All rights reserved.
              </p>
              <div className="flex gap-6 text-sm text-cyan-300">
                <Link href="/privacy" className="hover:text-white transition-colors">Privacy Policy</Link>
                <Link href="/terms" className="hover:text-white transition-colors">Terms of Service</Link>
                <Link href="/contact" className="hover:text-white transition-colors">Contact</Link>
              </div>
            </div>
          </div>
        </footer>
      </div>
    </>
  );
}
