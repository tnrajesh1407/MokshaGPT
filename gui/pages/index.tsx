import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Head from "next/head";
import Link from "next/link";
import Header from "../components/Header";
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
    AreaChart, Area, ResponsiveContainer, Legend,
} from "recharts";

// ── Types ─────────────────────────────────────────────────────────────────────

interface AnalysisResult  { type: "analysis";  content: string }
interface PriceResult     { type: "price";     content: string }
interface ForexResult     { type: "forex";     content: string }
interface FuturesResult   { type: "futures";   content: string }
interface OptionsResult   { type: "options";   content: string }
interface UnknownResult   { type: "unknown";   content: string }
interface BacktestMetrics {
    initial_capital: number; final_value: number;
    total_return_pct: number; buy_hold_return_pct: number;
    annualized_return_pct: number; sharpe_ratio: number;
    sortino_ratio?: number; calmar_ratio?: number;        // New VectorBT metrics
    max_drawdown_pct: number; total_trades: number;
    total_closed_trades?: number;                         // New VectorBT metric
    win_rate_pct: number; wins: number; losses: number;
    profit_factor?: number; expectancy?: number;          // New VectorBT metrics
    avg_win?: number; avg_loss?: number;                  // New VectorBT metrics
    gross_profit?: number; gross_loss?: number;           // New VectorBT metrics
    total_fees?: number; fee_rate_pct?: number;           // Fee information
    fee_description?: string;                             // Fee description
    slippage_rate_pct?: number;                           // Slippage information
    slippage_description?: string;                        // Slippage description
}
interface BacktestContent {
    parsed_strategy: {
        ticker: string; strategy_description: string;
        period_years?: number; period_days?: number;
        start_date?: string; end_date?: string;
        initial_capital: number; timeframe?: string;
        fee_description?: string;                         // Fee description
    };
    metrics: BacktestMetrics;
    chart_data: {
        price_series: { date: string; close: number; portfolio: number; [key: string]: any }[];
        drawdown_series: { date: string; drawdown: number }[];
        trades: { date: string; type: string; price: number; shares: number; value?: number; pnl?: number; pnl_pct?: number; days_held?: number; [key: string]: any }[];
    };
}
interface BacktestResult  { type: "backtest";  content: BacktestContent }

interface Stock {
    ticker: string;
    name: string;
    price: number;
    currency?: string;
    change_pct: number;
    market_cap: string;
    pe_ratio: number;
    volume: string;
    sector: string;
    match_reason: string;
    sma20?: number;
    rsi?: number;
    pct_from_52w_high?: number;
}
interface ScreenerContent {
    query: string;
    criteria: string[];
    stocks: Stock[];
    total_matches: number;
}
interface ScreenerResult  { type: "screen";  content: ScreenerContent }

// Portfolio types
interface StockScore {
    stock: string;
    financial_health: { score: number; reason: string };
    growth_potential: { score: number; reason: string };
    news_sentiment: { score: number; reason: string };
    news_impact: { score: number; reason: string };
    price_momentum: { score: number; reason: string };
    volatility_risk: { score: number; reason: string };
}
interface PortfolioContent {
    stock_overviews: any[];
    score_reports: StockScore[];
    portfolio: { selected_stocks: { stock_code: string; weight: number }[]; reasoning: string };
    current_strategy: string;
    new_strategy?: string;
    timestamp: string;
}
interface PortfolioResult { type: "portfolio"; content: PortfolioContent }
interface EnsembleResult  { type: "ensemble";  content: string }

type AgentResult = AnalysisResult | PriceResult | BacktestResult | ScreenerResult | PortfolioResult | ForexResult | FuturesResult | OptionsResult | EnsembleResult | UnknownResult | null;

// ── Helpers ───────────────────────────────────────────────────────────────────

const fmt = (n: number, d = 2) =>
    n?.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (n: number) => `${n >= 0 ? "+" : ""}${fmt(n)}%`;

// Download trades as CSV
const downloadTradesCSV = (trades: any[], ticker: string) => {
    const fixedCols = new Set(["date", "type", "price", "shares", "value", "pnl", "pnl_pct", "days_held"]);
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
    const csvContent = [headers.join(","), ...rows.map(row => row.join(","))].join("\n");
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

function MetricCard({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
    const color = positive === undefined ? "text-white" : positive ? "text-emerald-400" : "text-red-400";
    return (
        <div className="bg-slate-800/60 border border-cyan-500/20 rounded-xl p-4">
            <p className="text-xs text-cyan-300 uppercase tracking-wider mb-1">{label}</p>
            <p className={`text-xl font-bold ${color}`}>{value}</p>
        </div>
    );
}

function ChartTooltip({ active, payload, label }: any) {
    if (!active || !payload?.length) return null;
    return (
        <div className="bg-slate-900 border border-cyan-500/30 rounded-lg p-3 text-xs shadow-xl">
            <p className="text-cyan-300 mb-1 font-semibold">{label}</p>
            {payload.map((p: any) => (
                <p key={p.dataKey} style={{ color: p.color }}>{p.name}: {fmt(p.value)}</p>
            ))}
        </div>
    );
}

// ── Intent Badge config ───────────────────────────────────────────────────────

const INTENT_META: Record<string, { label: string; icon: string; color: string }> = {
    price:     { label: "Live Price",          icon: "💹", color: "bg-emerald-900/50 border-emerald-500/40 text-emerald-200" },
    analysis:  { label: "Stock Analysis",      icon: "📈", color: "bg-cyan-900/50 border-cyan-500/40 text-cyan-200" },
    backtest:  { label: "Strategy Backtest",   icon: "🔬", color: "bg-blue-900/50 border-blue-500/40 text-blue-200" },
    screen:    { label: "Stock Screener",      icon: "🔍", color: "bg-purple-900/50 border-purple-500/40 text-purple-200" },
    portfolio: { label: "Portfolio Optimizer", icon: "📊", color: "bg-yellow-900/50 border-yellow-500/40 text-yellow-200" },
    forex:     { label: "Forex Analysis",      icon: "💱", color: "bg-pink-900/50 border-pink-500/40 text-pink-200" },
    futures:   { label: "Futures Analysis",    icon: "📦", color: "bg-orange-900/50 border-orange-500/40 text-orange-200" },
    options:   { label: "Options Analysis",    icon: "📋", color: "bg-indigo-900/50 border-indigo-500/40 text-indigo-200" },
    ensemble:  { label: "Ensemble Builder",    icon: "🚀", color: "bg-fuchsia-900/50 border-fuchsia-500/40 text-fuchsia-200" },
    unknown:   { label: "General Response",    icon: "💬", color: "bg-slate-700/50 border-slate-500/40 text-slate-300" },
};

const EXAMPLE_PROMPTS = [
    "How is AAPL looking for tomorrow?",
    "Analyse NVDA fundamentals",
    "Backtest a 10/50 SMA crossover on TSLA for 2 years with $50,000",
    "RSI strategy on MSFT: buy < 30, sell > 70, 2 years, $100,000",
    "S&P 500 stocks below 20 moving average",
    "US tech stocks with RSI below 30",
    "Analyze EUR/USD forex pair",
    "Gold futures /GC analysis",
    "NIFTY 50 stocks below 20 moving average",
];

// Detect if the message is a portfolio optimization request
// Portfolio optimizer is currently disabled from the public UI
const detectPortfolioIntent = (_msg: string): { tickers?: string; strategy?: string } | null => null;

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function Home() {
    const [message, setMessage] = useState("");
    const [result, setResult]   = useState<AgentResult>(null);
    const [intent, setIntent]   = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError]     = useState("");

    // Persistent anonymous user ID (survives page reloads) + per-session ID
    // Both are sent to the backend so Langfuse can group traces by user and session.
    const userIdRef    = useRef<string>("");
    const sessionIdRef = useRef<string>("");
    useEffect(() => {
        // userId: persisted in localStorage so the same browser always maps to the same user
        let uid = localStorage.getItem("mokshaUserId");
        if (!uid) {
            uid = `anon-${crypto.randomUUID()}`;
            localStorage.setItem("mokshaUserId", uid);
        }
        userIdRef.current = uid;
        // sessionId: persisted in sessionStorage so it resets on new tab/window
        let sid = sessionStorage.getItem("mokshaSessionId");
        if (!sid) {
            sid = `sess-${crypto.randomUUID()}`;
            sessionStorage.setItem("mokshaSessionId", sid);
        }
        sessionIdRef.current = sid;
    }, []);

    // Streaming state
    const [streamSteps, setStreamSteps] = useState<{ tool: string; label: string; step: number }[]>([]);

    // Pagination state for trade log
    const [tradesPerPage, setTradesPerPage] = useState(50);
    const [currentPage, setCurrentPage] = useState(1);

    const handleSubmit = async () => {
        if (!message.trim()) return;
        setLoading(true);
        setError("");
        setResult(null);
        setIntent("");
        setStreamSteps([]);
        
        // Reset pagination when new query is submitted
        setCurrentPage(1);

        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

        try {
            // Portfolio intent — call /3s-trader directly (no streaming needed)
            const portfolioIntent = detectPortfolioIntent(message);
            if (portfolioIntent) {
                const tickerList = portfolioIntent.tickers
                    ? portfolioIntent.tickers.split(",").map(t => t.trim()).filter(Boolean)
                    : ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"];
                const res = await fetch(`${apiUrl}/3s-trader`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        tickers: tickerList,
                        initial_strategy: portfolioIntent.strategy || undefined,
                    }),
                });
                if (!res.ok) {
                    const contentType = res.headers.get("content-type") || "";
                    if (contentType.includes("application/json")) {
                        const err = await res.json();
                        throw new Error(err.detail || "Request failed");
                    }
                    throw new Error(`Server error: ${res.status} ${res.statusText}`);
                }
                const data = await res.json();
                setIntent("portfolio");
                setResult({ type: "portfolio", content: data });
                return;
            }

            // All other intents — call /research/stream (SSE)
            const res = await fetch(`${apiUrl}/research/stream`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message,
                    session_id: sessionIdRef.current || undefined,
                    user_id:    userIdRef.current    || undefined,
                }),
            });

            if (!res.ok || !res.body) {
                const contentType = res.headers.get("content-type") || "";
                if (contentType.includes("application/json")) {
                    const err = await res.json();
                    throw new Error(err.detail || "Request failed");
                }
                throw new Error(`Server error: ${res.status} ${res.statusText}`);
            }

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n\n");
                buffer = lines.pop() ?? "";

                for (const line of lines) {
                    const trimmed = line.trim();
                    if (!trimmed.startsWith("data:")) continue;
                    const jsonStr = trimmed.slice(5).trim();
                    if (!jsonStr) continue;

                    try {
                        const evt = JSON.parse(jsonStr);

                        if (evt.event === "step") {
                            setStreamSteps(prev => [...prev, {
                                tool: evt.tool,
                                label: evt.label,
                                step: evt.step,
                            }]);
                        } else if (evt.event === "result") {
                            setIntent(evt.type);
                            // Mirror the shape /research returns so all existing
                            // result renderers work without changes.
                            if (evt.type === "backtest") {
                                setResult({ type: "backtest", content: evt.content });
                            } else if (evt.type === "screen") {
                                setResult({ type: "screen", content: evt.content });
                            } else {
                                setResult({ type: evt.type as any, content: evt.answer || evt.content });
                            }
                        } else if (evt.event === "error") {
                            throw new Error(evt.message || "Agent error");
                        }
                    } catch (parseErr: any) {
                        // Skip malformed SSE lines
                        if (parseErr.message !== "Agent error") continue;
                        throw parseErr;
                    }
                }
            }
        } catch (e: any) {
            setError(e.message || "Something went wrong");
        } finally {
            setLoading(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSubmit(); }
    };

    const bt = result?.type === "backtest" ? (result as BacktestResult).content : null;
    const m  = bt?.metrics;

    return (
        <>
            <Head>
                <title>MokshaGPT – AI Stock Analyzer | Stock Analysis AI, Backtesting & Screener</title>
                <meta name="description" content="MokshaGPT is the most powerful AI stock analyzer — get instant stock analysis with AI, backtest trading strategies, and screen global markets in plain English. Try the #1 stock market AI free." />
                <meta name="keywords" content="ai stock analyzer, stock analysis ai, ai for stock analysis, stockmarket ai, ai stock analysis tool, stock analyzer ai, ai stock screener, ai backtesting, trading strategy backtester, stock market ai, ai trading assistant, technical analysis ai, algorithmic trading, quantitative analysis, stock screener ai, portfolio optimizer ai" />
                <meta name="viewport" content="width=device-width, initial-scale=1" />
                <meta name="robots" content="index, follow" />
                <link rel="canonical" href="https://mokshagpt.com" />

                {/* Open Graph */}
                <meta property="og:type" content="website" />
                <meta property="og:url" content="https://mokshagpt.com" />
                <meta property="og:title" content="MokshaGPT – AI Stock Analyzer | Stock Analysis AI Free" />
                <meta property="og:description" content="The smartest AI stock analyzer on the web. Analyze any stock with AI, backtest strategies, screen global markets, and optimize your portfolio — all in plain English. Free to use." />
                <meta property="og:image" content="https://mokshagpt.com/og-home.jpg" />

                {/* Twitter */}
                <meta property="twitter:card" content="summary_large_image" />
                <meta property="twitter:url" content="https://mokshagpt.com" />
                <meta property="twitter:title" content="MokshaGPT – AI Stock Analyzer | Stock Analysis AI" />
                <meta property="twitter:description" content="Analyze stocks with AI, backtest trading strategies, and screen global markets in plain English. The best free AI stock analysis tool." />
                <meta property="twitter:image" content="https://mokshagpt.com/twitter-home.jpg" />

                {/* Structured Data – WebApplication */}
                <script type="application/ld+json">
                    {JSON.stringify({
                        "@context": "https://schema.org",
                        "@type": "WebApplication",
                        "name": "MokshaGPT – AI Stock Analyzer",
                        "applicationCategory": "FinanceApplication",
                        "description": "AI stock analyzer that provides instant stock analysis with AI, strategy backtesting, AI stock screener, and portfolio optimization for global markets.",
                        "url": "https://mokshagpt.com",
                        "offers": {
                            "@type": "Offer",
                            "price": "0",
                            "priceCurrency": "USD"
                        },
                        "featureList": [
                            "AI stock analyzer",
                            "Stock analysis AI",
                            "AI for stock analysis",
                            "Stock market AI",
                            "AI strategy backtesting",
                            "AI stock screener",
                            "Portfolio optimizer",
                            "Forex & futures analysis",
                            "Natural language queries",
                            "Global market coverage"
                        ],
                        "aggregateRating": {
                            "@type": "AggregateRating",
                            "ratingValue": "4.8",
                            "ratingCount": "1250"
                        }
                    })}
                </script>

                {/* Structured Data – FAQPage for SEO */}
                <script type="application/ld+json">
                    {JSON.stringify({
                        "@context": "https://schema.org",
                        "@type": "FAQPage",
                        "mainEntity": [
                            {
                                "@type": "Question",
                                "name": "What is an AI stock analyzer?",
                                "acceptedAnswer": {
                                    "@type": "Answer",
                                    "text": "An AI stock analyzer uses artificial intelligence and large language models to evaluate stocks, interpret financial data, and generate actionable insights — all in plain English. MokshaGPT is a free AI stock analyzer covering US, Indian, and global markets."
                                }
                            },
                            {
                                "@type": "Question",
                                "name": "How does stock analysis AI work?",
                                "acceptedAnswer": {
                                    "@type": "Answer",
                                    "text": "Stock analysis AI processes real-time price data, technical indicators (RSI, MACD, SMA), and fundamental metrics to generate a comprehensive analysis report. MokshaGPT's AI agent automatically routes your query to the right analysis tool."
                                }
                            },
                            {
                                "@type": "Question",
                                "name": "Can I backtest trading strategies with AI?",
                                "acceptedAnswer": {
                                    "@type": "Answer",
                                    "text": "Yes. MokshaGPT's AI backtester lets you describe any trading strategy in plain English — such as 'RSI buy below 30, sell above 70 on AAPL for 2 years' — and instantly get detailed performance metrics including Sharpe ratio, win rate, max drawdown, and an interactive chart."
                                }
                            },
                            {
                                "@type": "Question",
                                "name": "Is MokshaGPT free to use?",
                                "acceptedAnswer": {
                                    "@type": "Answer",
                                    "text": "Yes, MokshaGPT's AI stock analyzer, backtester, screener, and portfolio optimizer are free to use for educational and informational purposes."
                                }
                            }
                        ]
                    })}
                </script>
            </Head>

            <div className="min-h-screen bg-gradient-to-br from-indigo-950 via-slate-900 to-gray-900">

                <Header />

                <main className="max-w-5xl mx-auto px-6 py-12">

                    {/* Hero */}
                    <div className="text-center mb-10">
                        <div className="inline-flex items-center gap-2 px-3 py-1 bg-cyan-900/40 border border-cyan-500/30 rounded-full text-cyan-300 text-xs mb-4">
                            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
                            Free AI Stock Analyzer — No Sign-up Required
                        </div>
                        <h1 className="text-5xl font-extrabold text-white mb-4 leading-tight drop-shadow-lg">
                            Your AI Stock Market <br />
                            <span className="bg-gradient-to-r from-cyan-400 via-blue-400 to-cyan-400 bg-clip-text text-transparent">
                                Research Agent
                            </span>
                        </h1>
                        <p className="text-cyan-200 text-base font-medium mb-3 tracking-wide">
                            Powered by the Smartest <span className="text-white font-semibold">AI Stock Analyzer</span>
                        </p>
                        <p className="text-cyan-100 max-w-2xl mx-auto text-lg mb-3">
                            Ask anything in plain English — the agent researches, analyzes, backtests, and screens global markets in real time, then delivers a complete answer.
                        </p>
                        <p className="text-cyan-200 max-w-xl mx-auto text-sm mb-2">
                            Multi-step ReAct agent that chains tools automatically — stock analyzer, backtester, screener, forex, futures, and more.
                        </p>
                        <p className="text-cyan-300 text-sm mt-2 max-w-2xl mx-auto">
                            🌍 Global Markets • US • India • UK • Germany • Japan • HK • Australia • Canada • Crypto • Forex • Futures
                        </p>
                    </div>

                    {/* LangGraph flow diagram */}
                    <div className="max-w-3xl mx-auto mb-8">
                        <div className="bg-slate-800/30 border border-cyan-500/20 rounded-xl p-4 flex items-center justify-center gap-2 text-xs text-slate-400 flex-wrap">
                            <span className="px-2 py-1 bg-slate-700/50 rounded">Your Prompt</span>
                            <span>→</span>
                            <span className="px-2 py-1 bg-cyan-900/50 border border-cyan-500/30 rounded text-cyan-300">classify node</span>
                            <span>→</span>
                            <span className="px-2 py-1 bg-blue-900/50 border border-blue-500/30 rounded text-blue-300">analyze</span>
                            <span className="text-slate-600">|</span>
                            <span className="px-2 py-1 bg-emerald-900/50 border border-emerald-500/30 rounded text-emerald-300">backtest</span>
                            <span className="text-slate-600">|</span>
                            <span className="px-2 py-1 bg-purple-900/50 border border-purple-500/30 rounded text-purple-300">screen</span>
                            <span className="text-slate-600">|</span>
                            <span className="px-2 py-1 bg-pink-900/50 border border-pink-500/30 rounded text-pink-300">forex</span>
                            <span className="text-slate-600">|</span>
                            <span className="px-2 py-1 bg-orange-900/50 border border-orange-500/30 rounded text-orange-300">futures</span>
                            <span className="text-slate-600">|</span>
                            <span className="px-2 py-1 bg-fuchsia-900/50 border border-fuchsia-500/30 rounded text-fuchsia-300">ensemble</span>
                            <span>→</span>
                            <span className="px-2 py-1 bg-slate-700/50 rounded">Result</span>
                        </div>
                    </div>

                    {/* Input */}
                    <div className="max-w-3xl mx-auto mb-10">
                        <div className="bg-slate-800/60 backdrop-blur-xl rounded-2xl shadow-2xl border border-cyan-500/30 p-6">
                            <textarea
                                rows={3}
                                placeholder={`Ask anything — e.g. "How is RELIANCE.NS looking?" or "Find Indian IT stocks with P/E < 20" or "Backtest RSI on TCS.NS"`}
                                value={message}
                                onChange={(e) => setMessage(e.target.value)}
                                onKeyDown={handleKeyDown}
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
                                    🇮🇳 India (TCS.NS, RELIANCE.NS)
                                </span>
                                <span className="text-slate-600">•</span>
                                <span className="flex items-center gap-1">
                                    <span className="w-2 h-2 rounded-full bg-yellow-500"></span>
                                    💱 Forex (EUR/USD, GBP/JPY)
                                </span>
                                <span className="text-slate-600">•</span>
                                <span className="text-slate-500">🇬🇧 UK • 🇩🇪 DE • 🇯🇵 JP • ₿ Crypto • 📦 Futures</span>
                            </div>

                            {/* Example chips */}
                            <div className="mt-3 flex flex-wrap gap-2">
                                {EXAMPLE_PROMPTS.map((ex) => (
                                    <button key={ex} onClick={() => setMessage(ex)}
                                        className="text-xs px-3 py-1 bg-cyan-900/40 border border-cyan-500/30 text-cyan-300 rounded-full hover:bg-cyan-800/50 hover:text-white transition-all">
                                        {ex.length > 50 ? ex.slice(0, 50) + "…" : ex}
                                    </button>
                                ))}
                            </div>

                            <div className="mt-4 flex gap-3">
                                <button onClick={handleSubmit} disabled={loading || !message.trim()}
                                    className="flex-1 py-3 bg-gradient-to-r from-cyan-600 to-blue-600 text-white font-semibold rounded-xl hover:from-cyan-700 hover:to-blue-700 disabled:from-slate-600 disabled:to-slate-700 disabled:cursor-not-allowed transition-all shadow-lg shadow-cyan-500/30">
                                    {loading ? (
                                        <span className="flex items-center justify-center gap-2">
                                            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                            </svg>
                                            Agent thinking…
                                        </span>
                                    ) : "Ask Agent"}
                                </button>
                            </div>

                            {error && (
                                <div className="mt-4 bg-red-900/40 border-l-4 border-red-500 text-red-200 px-4 py-3 rounded text-sm">{error}</div>
                            )}
                        </div>
                    </div>

                    {/* ── Streaming Steps Panel ── */}
                    {(loading || streamSteps.length > 0) && !result && (
                        <div className="max-w-3xl mx-auto mb-8">
                            <div className="bg-slate-800/50 border border-cyan-500/20 rounded-2xl p-5">
                                <div className="flex items-center gap-2 mb-4">
                                    <svg className="animate-spin h-4 w-4 text-cyan-400 shrink-0" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                    </svg>
                                    <span className="text-cyan-300 text-sm font-medium">Agent working…</span>
                                </div>
                                <div className="space-y-2">
                                    {streamSteps.length === 0 && (
                                        <div className="flex items-center gap-3 text-slate-400 text-sm">
                                            <span className="w-5 h-5 rounded-full border border-slate-600 flex items-center justify-center text-xs shrink-0">1</span>
                                            <span className="text-slate-500">Routing your query…</span>
                                        </div>
                                    )}
                                    {streamSteps.map((s, i) => {
                                        const toolIcons: Record<string, string> = {
                                            price: "💹", indicators: "📐", analyze: "📈",
                                            forex: "💱", options: "📋", futures: "📦",
                                            backtest: "🔬", screen: "🔍", general: "💬",
                                            final_answer: "✍️",
                                        };
                                        const isLast = i === streamSteps.length - 1;
                                        return (
                                            <div key={i} className={`flex items-center gap-3 text-sm transition-all ${isLast ? "text-cyan-200" : "text-slate-400"}`}>
                                                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs shrink-0 ${isLast ? "bg-cyan-900/60 border border-cyan-500/40" : "bg-slate-700/60 border border-slate-600/40"}`}>
                                                    {toolIcons[s.tool] || "⚙️"}
                                                </span>
                                                <span>{s.label}</span>
                                                {isLast && loading && (
                                                    <span className="flex gap-0.5 ml-1">
                                                        <span className="w-1 h-1 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                                                        <span className="w-1 h-1 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                                                        <span className="w-1 h-1 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                                                    </span>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>
                    )}

                    {/* ── Dedicated Tools Strip ── */}
                    <div className="max-w-3xl mx-auto mb-10">
                        <p className="text-slate-500 text-xs uppercase tracking-wider text-center mb-3">Or go directly to a dedicated tool</p>
                        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                            <Link href="/aibacktester"
                                className="flex flex-col items-center gap-2 px-4 py-3 bg-slate-800/60 border border-blue-500/20 rounded-xl hover:border-blue-500/50 hover:bg-slate-700/60 transition-all group">
                                <span className="text-2xl">🔬</span>
                                <span className="text-xs text-blue-300 group-hover:text-white transition-colors font-medium text-center">AI Backtester</span>
                                <span className="text-xs text-slate-500 text-center leading-tight">Test any strategy</span>
                            </Link>
                            <Link href="/backtest-optimizer"
                                className="flex flex-col items-center gap-2 px-4 py-3 bg-slate-800/60 border border-violet-500/20 rounded-xl hover:border-violet-500/50 hover:bg-slate-700/60 transition-all group">
                                <span className="text-2xl">⚡</span>
                                <span className="text-xs text-violet-300 group-hover:text-white transition-colors font-medium text-center">Backtest Optimizer</span>
                                <span className="text-xs text-slate-500 text-center leading-tight">Auto-refine strategy</span>
                            </Link>
                            <Link href="/aiscreener"
                                className="flex flex-col items-center gap-2 px-4 py-3 bg-slate-800/60 border border-purple-500/20 rounded-xl hover:border-purple-500/50 hover:bg-slate-700/60 transition-all group">
                                <span className="text-2xl">🔍</span>
                                <span className="text-xs text-purple-300 group-hover:text-white transition-colors font-medium text-center">AI Screener</span>
                                <span className="text-xs text-slate-500 text-center leading-tight">Find stocks</span>
                            </Link>
                            <Link href="/ensemble-builder"
                                className="flex flex-col items-center gap-2 px-4 py-3 bg-slate-800/60 border border-fuchsia-500/20 rounded-xl hover:border-fuchsia-500/50 hover:bg-slate-700/60 transition-all group">
                                <span className="text-2xl">🚀</span>
                                <span className="text-xs text-fuchsia-300 group-hover:text-white transition-colors font-medium text-center">Ensemble Builder</span>
                                <span className="text-xs text-slate-500 text-center leading-tight">Combine strategies</span>
                            </Link>
                            <Link href="/aireporter"
                                className="flex flex-col items-center gap-2 px-4 py-3 bg-slate-800/60 border border-indigo-500/20 rounded-xl hover:border-indigo-500/50 hover:bg-slate-700/60 transition-all group">
                                <span className="text-2xl">📋</span>
                                <span className="text-xs text-indigo-300 group-hover:text-white transition-colors font-medium text-center">AI Reporter</span>
                                <span className="text-xs text-slate-500 text-center leading-tight">Generate reports</span>
                            </Link>
                            <Link href="/tradeanalyzer"
                                className="flex flex-col items-center gap-2 px-4 py-3 bg-slate-800/60 border border-emerald-500/20 rounded-xl hover:border-emerald-500/50 hover:bg-slate-700/60 transition-all group">
                                <span className="text-2xl">📊</span>
                                <span className="text-xs text-emerald-300 group-hover:text-white transition-colors font-medium text-center">Trade Analyzer</span>
                                <span className="text-xs text-slate-500 text-center leading-tight">Analyze your trades</span>
                            </Link>
                        </div>
                    </div>

                    {/* ── Global Disclaimer ── */}
                    <div className="max-w-3xl mx-auto mb-8">
                        <div className="bg-amber-950/30 border border-amber-500/30 rounded-xl px-5 py-4 flex gap-3 text-xs text-amber-200/80">
                            <span className="text-amber-400 text-base shrink-0 mt-0.5">⚠️</span>
                            <span>
                                <span className="font-semibold text-amber-300">Disclaimer: </span>
                                MokshaGPT is a research and educational platform. All analysis, backtest results, and screener outputs are for informational purposes only and do <strong className="text-amber-200">not</strong> constitute financial or investment advice. Past performance is not indicative of future results. Always conduct your own research and consult a licensed financial advisor before making investment decisions.
                            </span>
                        </div>
                    </div>

                    {/* Intent badge — shows which node was activated */}
                    {intent && !loading && (
                        <div className="max-w-3xl mx-auto mb-6 flex items-center gap-3">
                            <span className="text-slate-400 text-sm">Agent routed to:</span>
                            <span className={`px-3 py-1 border rounded-full text-sm font-medium ${INTENT_META[intent]?.color}`}>
                                {INTENT_META[intent]?.icon} {INTENT_META[intent]?.label}
                            </span>
                        </div>
                    )}

                    {/* ── Price Result ── */}
                    {result?.type === "price" && !loading && (
                        <article className="max-w-2xl mx-auto">
                            <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl shadow-2xl border border-emerald-500/30 overflow-hidden">
                                <div className="bg-gradient-to-r from-emerald-600 to-teal-600 px-8 py-5 flex items-center gap-3">
                                    <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center text-xl">💹</div>
                                    <div>
                                        <h3 className="text-white font-bold text-lg">Live Stock Price</h3>
                                        <p className="text-emerald-100 text-xs">Real-time data via Yahoo Finance</p>
                                    </div>
                                </div>
                                <div className="px-8 py-8">
                                    <ReactMarkdown 
                                        remarkPlugins={[remarkGfm]}
                                        components={{
                                        p:      ({ children }) => <p className="text-slate-300 leading-relaxed mb-3">{children}</p>,
                                        strong: ({ children }) => <strong className="font-bold text-white text-2xl">{children}</strong>,
                                        em:     ({ children }) => <em className="text-slate-400 text-xs not-italic">{children}</em>,
                                    }}>
                                        {(result as PriceResult).content}
                                    </ReactMarkdown>
                                </div>
                            </div>
                        </article>
                    )}

                    {/* ── Analysis Result ── */}
                    {result?.type === "analysis" && !loading && (
                        <article className="max-w-4xl mx-auto">
                            <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl shadow-2xl border border-purple-500/30 overflow-hidden">
                                <div className="bg-gradient-to-r from-purple-600 to-pink-600 px-8 py-5 flex items-center gap-3">
                                    <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center text-xl">📈</div>
                                    <div>
                                        <h3 className="text-white font-bold text-lg">Analysis Report</h3>
                                        <p className="text-purple-100 text-xs">AI-generated · not financial advice</p>
                                    </div>
                                </div>
                                <div className="px-8 py-8">
                                    <ReactMarkdown 
                                        remarkPlugins={[remarkGfm]}
                                        components={{
                                        h1: ({ children }) => <h1 className="text-2xl font-bold text-white mt-6 mb-3 pb-2 border-b border-purple-500/30">{children}</h1>,
                                        h2: ({ children }) => <h2 className="text-xl font-bold text-purple-200 mt-6 mb-2">{children}</h2>,
                                        h3: ({ children }) => <h3 className="text-lg font-semibold text-purple-300 mt-4 mb-2">{children}</h3>,
                                        p:  ({ children }) => <p className="text-slate-300 leading-relaxed mb-4">{children}</p>,
                                        ul: ({ children }) => <ul className="space-y-2 mb-4 ml-2">{children}</ul>,
                                        li: ({ children }) => (
                                            <li className="flex items-start gap-2 text-slate-300">
                                                <span className="mt-2 w-1.5 h-1.5 rounded-full bg-purple-500 flex-shrink-0" />
                                                <span>{children}</span>
                                            </li>
                                        ),
                                        strong: ({ children }) => <strong className="font-bold text-white">{children}</strong>,
                                        code:   ({ children }) => <code className="bg-purple-900/50 text-purple-200 px-2 py-0.5 rounded text-sm font-mono">{children}</code>,
                                        table: ({ children }) => (
                                            <div className="overflow-x-auto my-4">
                                                <table className="w-full text-sm border-collapse">{children}</table>
                                            </div>
                                        ),
                                        thead: ({ children }) => <thead className="bg-purple-900/40">{children}</thead>,
                                        tbody: ({ children }) => <tbody className="divide-y divide-purple-500/10">{children}</tbody>,
                                        tr:   ({ children }) => <tr className="hover:bg-purple-900/20 transition-colors">{children}</tr>,
                                        th:   ({ children }) => <th className="px-3 py-2 text-left text-purple-300 font-semibold border-b border-purple-500/30 whitespace-nowrap">{children}</th>,
                                        td:   ({ children }) => <td className="px-3 py-2 text-slate-300 border-b border-purple-500/10">{children}</td>,
                                    }}>
                                        {(result as AnalysisResult).content}
                                    </ReactMarkdown>
                                </div>
                                <div className="bg-slate-900/50 px-8 py-4 border-t border-purple-500/30 flex items-center justify-between text-xs">
                                    <span className="text-purple-300">Not financial advice. For informational purposes only.</span>
                                    <span className="text-purple-400">Generated by AI · {new Date().toLocaleDateString()}</span>
                                </div>
                            </div>
                        </article>
                    )}

                    {/* ── Forex Result ── */}
                    {result?.type === "forex" && !loading && (
                        <article className="max-w-4xl mx-auto">
                            <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl shadow-2xl border border-pink-500/30 overflow-hidden">
                                <div className="bg-gradient-to-r from-pink-600 to-rose-600 px-8 py-5 flex items-center gap-3">
                                    <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center text-xl">💱</div>
                                    <div>
                                        <h3 className="text-white font-bold text-lg">Forex Analysis</h3>
                                        <p className="text-pink-100 text-xs">Technical & fundamental analysis</p>
                                    </div>
                                </div>
                                <div className="px-8 py-8">
                                    <ReactMarkdown 
                                        remarkPlugins={[remarkGfm]}
                                        components={{
                                        h1: ({ children }) => <h1 className="text-2xl font-bold text-white mt-6 mb-3 pb-2 border-b border-pink-500/30">{children}</h1>,
                                        h2: ({ children }) => <h2 className="text-xl font-bold text-pink-200 mt-6 mb-2">{children}</h2>,
                                        h3: ({ children }) => <h3 className="text-lg font-semibold text-pink-300 mt-4 mb-2">{children}</h3>,
                                        p:  ({ children }) => <p className="text-slate-300 leading-relaxed mb-4">{children}</p>,
                                        ul: ({ children }) => <ul className="space-y-2 mb-4 ml-2">{children}</ul>,
                                        li: ({ children }) => (
                                            <li className="flex items-start gap-2 text-slate-300">
                                                <span className="mt-2 w-1.5 h-1.5 rounded-full bg-pink-500 flex-shrink-0" />
                                                <span>{children}</span>
                                            </li>
                                        ),
                                        strong: ({ children }) => <strong className="font-bold text-white">{children}</strong>,
                                        code:   ({ children }) => <code className="bg-pink-900/50 text-pink-200 px-2 py-0.5 rounded text-sm font-mono">{children}</code>,
                                        table: ({ children }) => (
                                            <div className="overflow-x-auto my-4">
                                                <table className="w-full text-sm border-collapse">{children}</table>
                                            </div>
                                        ),
                                        thead: ({ children }) => <thead className="bg-pink-900/40">{children}</thead>,
                                        tbody: ({ children }) => <tbody className="divide-y divide-pink-500/10">{children}</tbody>,
                                        tr:   ({ children }) => <tr className="hover:bg-pink-900/20 transition-colors">{children}</tr>,
                                        th:   ({ children }) => <th className="px-3 py-2 text-left text-pink-300 font-semibold border-b border-pink-500/30 whitespace-nowrap">{children}</th>,
                                        td:   ({ children }) => <td className="px-3 py-2 text-slate-300 border-b border-pink-500/10">{children}</td>,
                                    }}>
                                        {(result as ForexResult).content}
                                    </ReactMarkdown>
                                </div>
                                <div className="bg-slate-900/50 px-8 py-4 border-t border-pink-500/30 flex items-center justify-between text-xs">
                                    <span className="text-pink-300">Not financial advice. For informational purposes only.</span>
                                    <span className="text-pink-400">Generated by AI · {new Date().toLocaleDateString()}</span>
                                </div>
                            </div>
                        </article>
                    )}

                    {/* ── Futures Result ── */}
                    {result?.type === "futures" && !loading && (
                        <article className="max-w-4xl mx-auto">
                            <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl shadow-2xl border border-orange-500/30 overflow-hidden">
                                <div className="bg-gradient-to-r from-orange-600 to-amber-600 px-8 py-5 flex items-center gap-3">
                                    <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center text-xl">📦</div>
                                    <div>
                                        <h3 className="text-white font-bold text-lg">Futures Analysis</h3>
                                        <p className="text-orange-100 text-xs">Commodities, indices & currencies</p>
                                    </div>
                                </div>
                                <div className="px-8 py-8">
                                    <ReactMarkdown 
                                        remarkPlugins={[remarkGfm]}
                                        components={{
                                        h1: ({ children }) => <h1 className="text-2xl font-bold text-white mt-6 mb-3 pb-2 border-b border-orange-500/30">{children}</h1>,
                                        h2: ({ children }) => <h2 className="text-xl font-bold text-orange-200 mt-6 mb-2">{children}</h2>,
                                        h3: ({ children }) => <h3 className="text-lg font-semibold text-orange-300 mt-4 mb-2">{children}</h3>,
                                        p:  ({ children }) => <p className="text-slate-300 leading-relaxed mb-4">{children}</p>,
                                        ul: ({ children }) => <ul className="space-y-2 mb-4 ml-2">{children}</ul>,
                                        li: ({ children }) => (
                                            <li className="flex items-start gap-2 text-slate-300">
                                                <span className="mt-2 w-1.5 h-1.5 rounded-full bg-orange-500 flex-shrink-0" />
                                                <span>{children}</span>
                                            </li>
                                        ),
                                        strong: ({ children }) => <strong className="font-bold text-white">{children}</strong>,
                                        code:   ({ children }) => <code className="bg-orange-900/50 text-orange-200 px-2 py-0.5 rounded text-sm font-mono">{children}</code>,
                                        table: ({ children }) => (
                                            <div className="overflow-x-auto my-4">
                                                <table className="w-full text-sm border-collapse">{children}</table>
                                            </div>
                                        ),
                                        thead: ({ children }) => <thead className="bg-orange-900/40">{children}</thead>,
                                        tbody: ({ children }) => <tbody className="divide-y divide-orange-500/10">{children}</tbody>,
                                        tr:   ({ children }) => <tr className="hover:bg-orange-900/20 transition-colors">{children}</tr>,
                                        th:   ({ children }) => <th className="px-3 py-2 text-left text-orange-300 font-semibold border-b border-orange-500/30 whitespace-nowrap">{children}</th>,
                                        td:   ({ children }) => <td className="px-3 py-2 text-slate-300 border-b border-orange-500/10">{children}</td>,
                                    }}>
                                        {(result as FuturesResult).content}
                                    </ReactMarkdown>
                                </div>
                                <div className="bg-slate-900/50 px-8 py-4 border-t border-orange-500/30 flex items-center justify-between text-xs">
                                    <span className="text-orange-300">Not financial advice. For informational purposes only.</span>
                                    <span className="text-orange-400">Generated by AI · {new Date().toLocaleDateString()}</span>
                                </div>
                            </div>
                        </article>
                    )}

                    {/* ── Options Result ── */}
                    {result?.type === "options" && !loading && (
                        <article className="max-w-4xl mx-auto">
                            <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl shadow-2xl border border-indigo-500/30 overflow-hidden">
                                <div className="bg-gradient-to-r from-indigo-600 to-violet-600 px-8 py-5 flex items-center gap-3">
                                    <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center text-xl">📋</div>
                                    <div>
                                        <h3 className="text-white font-bold text-lg">Options Analysis</h3>
                                        <p className="text-indigo-100 text-xs">Greeks, volatility & pricing</p>
                                    </div>
                                </div>
                                <div className="px-8 py-8">
                                    <ReactMarkdown 
                                        remarkPlugins={[remarkGfm]}
                                        components={{
                                        h1: ({ children }) => <h1 className="text-2xl font-bold text-white mt-6 mb-3 pb-2 border-b border-indigo-500/30">{children}</h1>,
                                        h2: ({ children }) => <h2 className="text-xl font-bold text-indigo-200 mt-6 mb-2">{children}</h2>,
                                        h3: ({ children }) => <h3 className="text-lg font-semibold text-indigo-300 mt-4 mb-2">{children}</h3>,
                                        p:  ({ children }) => <p className="text-slate-300 leading-relaxed mb-4">{children}</p>,
                                        ul: ({ children }) => <ul className="space-y-2 mb-4 ml-2">{children}</ul>,
                                        li: ({ children }) => (
                                            <li className="flex items-start gap-2 text-slate-300">
                                                <span className="mt-2 w-1.5 h-1.5 rounded-full bg-indigo-500 flex-shrink-0" />
                                                <span>{children}</span>
                                            </li>
                                        ),
                                        strong: ({ children }) => <strong className="font-bold text-white">{children}</strong>,
                                        code:   ({ children }) => <code className="bg-indigo-900/50 text-indigo-200 px-2 py-0.5 rounded text-sm font-mono">{children}</code>,
                                        table: ({ children }) => (
                                            <div className="overflow-x-auto my-4">
                                                <table className="w-full text-sm border-collapse">{children}</table>
                                            </div>
                                        ),
                                        thead: ({ children }) => <thead className="bg-indigo-900/40">{children}</thead>,
                                        tbody: ({ children }) => <tbody className="divide-y divide-indigo-500/10">{children}</tbody>,
                                        tr:   ({ children }) => <tr className="hover:bg-indigo-900/20 transition-colors">{children}</tr>,
                                        th:   ({ children }) => <th className="px-3 py-2 text-left text-indigo-300 font-semibold border-b border-indigo-500/30 whitespace-nowrap">{children}</th>,
                                        td:   ({ children }) => <td className="px-3 py-2 text-slate-300 border-b border-indigo-500/10">{children}</td>,
                                    }}>
                                        {(result as OptionsResult).content}
                                    </ReactMarkdown>
                                </div>
                                <div className="bg-slate-900/50 px-8 py-4 border-t border-indigo-500/30 flex items-center justify-between text-xs">
                                    <span className="text-indigo-300">Not financial advice. For informational purposes only.</span>
                                    <span className="text-indigo-400">Generated by AI · {new Date().toLocaleDateString()}</span>
                                </div>
                            </div>
                        </article>
                    )}

                    {/* ── Backtest Result ── */}
                    {result?.type === "backtest" && bt && m && !loading && (
                        <div className="space-y-6">
                            {/* Strategy summary */}
                            <div className="bg-slate-800/40 border border-purple-500/20 rounded-2xl p-5">
                                <h3 className="text-white font-bold text-lg mb-2">Parsed Strategy</h3>
                                <p className="text-purple-200 text-sm mb-3">{bt.parsed_strategy.strategy_description}</p>
                                <div className="flex flex-wrap gap-2 text-sm">
                                    {[
                                        `📌 ${bt.parsed_strategy.ticker}`,
                                        bt.parsed_strategy.timeframe && bt.parsed_strategy.timeframe !== "1d"
                                            ? `⏱️ ${bt.parsed_strategy.timeframe} (${bt.parsed_strategy.period_days} days)`
                                            : bt.parsed_strategy.start_date && bt.parsed_strategy.end_date
                                                ? `📅 ${bt.parsed_strategy.start_date} → ${bt.parsed_strategy.end_date}`
                                                : bt.parsed_strategy.period_years
                                                    ? `📅 ${bt.parsed_strategy.period_years}y`
                                                    : `📅 ${bt.parsed_strategy.period_days ?? "—"} days`,
                                        `💰 ${bt.parsed_strategy.initial_capital.toLocaleString()}`,
                                    ].map(tag => (
                                        <span key={tag} className="px-3 py-1 bg-purple-900/50 border border-purple-500/30 rounded-full text-purple-200">{tag}</span>
                                    ))}
                                </div>
                            </div>

                            {/* Backtest Disclaimer */}
                            <div className="flex gap-3 bg-slate-700/30 border border-slate-500/30 rounded-xl px-4 py-3 text-xs text-slate-400">
                                <span className="shrink-0 mt-0.5">⚠️</span>
                                <span>
                                    <span className="text-slate-300 font-semibold">Backtest disclaimer: </span>
                                    Trades execute at bar close. Real fills may differ by 1–2 bars due to market impact and latency.
                                    Results include estimated fees ({m.fee_description || bt.parsed_strategy.fee_description || "0.1% per trade"})
                                    {m.slippage_description ? ` and slippage (${m.slippage_description})` : ""}.
                                    Taxes, borrowing costs, and liquidity constraints are excluded.
                                    Past performance does not guarantee future results.
                                </span>
                            </div>

                            {/* Strategy Verdict */}
                            {(() => {
                                // Score the strategy across 6 dimensions
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

                            {/* Fee notice */}
                            <div className="flex gap-3 bg-slate-700/40 border border-slate-500/30 rounded-xl px-4 py-3 text-sm text-slate-300">
                                <span className="text-slate-400 text-base mt-0.5 shrink-0">💸</span>
                                <div>
                                    <span className="font-semibold text-slate-200">Results include trading fees:</span>{" "}
                                    {m.fee_description || bt.parsed_strategy.fee_description || "0.1% per trade"}.
                                    {bt.parsed_strategy.ticker?.endsWith(".NS") || bt.parsed_strategy.ticker?.endsWith(".BO") ? (
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

                            {/* Metrics grid */}
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                                <MetricCard label="Total Return"      value={pct(m.total_return_pct)}        positive={m.total_return_pct >= 0} />
                                <MetricCard label="Buy & Hold"        value={pct(m.buy_hold_return_pct)}     positive={m.buy_hold_return_pct >= 0} />
                                <MetricCard label="Sharpe Ratio"      value={fmt(m.sharpe_ratio, 3)}         positive={m.sharpe_ratio >= 1} />
                                <MetricCard label="Max Drawdown"      value={`${fmt(m.max_drawdown_pct)}%`}  positive={m.max_drawdown_pct > -10} />
                                <MetricCard label="Annualised Return" value={pct(m.annualized_return_pct)}   positive={m.annualized_return_pct >= 0} />
                                <MetricCard label="Win Rate"          value={`${fmt(m.win_rate_pct)}%`}      positive={m.win_rate_pct >= 50} />
                                <MetricCard label="Total Trades"      value={String(m.total_trades)} />
                                <MetricCard label="Alpha vs B&H"      value={pct(m.total_return_pct - m.buy_hold_return_pct)} positive={m.total_return_pct >= m.buy_hold_return_pct} />
                                
                                {/* Enhanced VectorBT Metrics */}
                                {m.sortino_ratio !== undefined && (
                                    <MetricCard label="Sortino Ratio" value={fmt(m.sortino_ratio, 3)} positive={m.sortino_ratio >= 1} />
                                )}
                                {m.calmar_ratio !== undefined && (
                                    <MetricCard label="Calmar Ratio" value={fmt(m.calmar_ratio, 3)} positive={m.calmar_ratio >= 1} />
                                )}
                                {m.profit_factor !== undefined && (
                                    <MetricCard label="Profit Factor" value={fmt(m.profit_factor, 2)} positive={m.profit_factor >= 1.5} />
                                )}
                                {m.expectancy !== undefined && (
                                    <MetricCard label="Expectancy" value={fmt(m.expectancy, 2)} positive={m.expectancy >= 0} />
                                )}
                            </div>

                            {/* Portfolio chart */}
                            <div className="bg-slate-800/40 border border-purple-500/20 rounded-2xl p-6">
                                <h3 className="text-white font-bold mb-4">Portfolio Value vs Price</h3>
                                <ResponsiveContainer width="100%" height={280}>
                                    <LineChart data={bt.chart_data.price_series} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                                        <XAxis dataKey="date" tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} interval="preserveStartEnd" />
                                        <YAxis yAxisId="l" tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} tickFormatter={v => `${(v/1000).toFixed(0)}k`} />
                                        <YAxis yAxisId="r" orientation="right" tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} tickFormatter={v => `${(v/1000).toFixed(0)}k`} />
                                        <Tooltip content={<ChartTooltip />} />
                                        <Legend wrapperStyle={{ color: "#cbd5e1", fontSize: 12 }} />
                                        <Line yAxisId="r" type="monotone" dataKey="close"     name="Price"     stroke="#818cf8" dot={false} strokeWidth={1.5} />
                                        <Line yAxisId="l" type="monotone" dataKey="portfolio" name="Portfolio" stroke="#34d399" dot={false} strokeWidth={2} />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>

                            {/* Drawdown chart */}
                            <div className="bg-slate-800/40 border border-purple-500/20 rounded-2xl p-6">
                                <h3 className="text-white font-bold mb-4">Drawdown</h3>
                                <ResponsiveContainer width="100%" height={180}>
                                    <AreaChart data={bt.chart_data.drawdown_series} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                                        <XAxis dataKey="date" tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} interval="preserveStartEnd" />
                                        <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} tickFormatter={v => `${v}%`} />
                                        <Tooltip content={<ChartTooltip />} />
                                        <Area type="monotone" dataKey="drawdown" name="Drawdown %" stroke="#ef4444" fill="#ef444430" strokeWidth={1.5} />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>

                            {/* Trade Log */}
                            {bt.chart_data.trades.length > 0 && (
                                <div className="bg-slate-800/40 border border-purple-500/20 rounded-2xl p-6">
                                    <div className="flex items-center justify-between mb-4">
                                        <h3 className="text-white font-bold text-lg">
                                            Trade Log ({bt.chart_data.trades.length} trades)
                                        </h3>
                                        <button
                                            onClick={() => downloadTradesCSV(bt.chart_data.trades, bt.parsed_strategy.ticker)}
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
                                            Entries and exits use the <strong>closing price</strong> of the signal bar ({bt.parsed_strategy.timeframe || "1d"} candle).
                                            Real orders would fill at the next bar&apos;s open.
                                        </div>
                                    </div>

                                    {(() => {
                                        const fixedCols = new Set(["date", "type", "price", "shares", "value", "pnl", "pnl_pct", "days_held", "_timestamp"]);
                                        const tradeIndicatorCols = Array.from(
                                            new Set(bt.chart_data.trades.flatMap(t => Object.keys(t).filter(k => !fixedCols.has(k))))
                                        );
                                        
                                        // Calculate pagination
                                        const totalPages = Math.ceil(bt.chart_data.trades.length / tradesPerPage);
                                        const startIdx = (currentPage - 1) * tradesPerPage;
                                        const endIdx = startIdx + tradesPerPage;
                                        const paginatedTrades = bt.chart_data.trades.slice(startIdx, endIdx);
                                        
                                        return (
                                            <div className="overflow-x-auto">
                                                <table className="w-full text-sm">
                                                    <thead>
                                                        <tr className="text-purple-300 border-b border-purple-500/20">
                                                            <th className="text-left py-2 pr-4">#</th>
                                                            <th className="text-left py-2 pr-4">Date</th>
                                                            <th className="text-left py-2 pr-4">Type</th>
                                                            <th className="text-right py-2 pr-4">Price</th>
                                                            <th className="text-right py-2 pr-4">Shares</th>
                                                            <th className="text-right py-2 pr-4">Trade Value</th>
                                                            {tradeIndicatorCols.map(col => (
                                                                <th key={col} className="text-right py-2 pr-4 text-amber-300">{col.toUpperCase()}</th>
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
                                                                className="bg-slate-700 text-white text-sm px-2 py-1 rounded border border-slate-600 hover:border-purple-500/50"
                                                            >
                                                                <option value={25}>25</option>
                                                                <option value={50}>50</option>
                                                                <option value={100}>100</option>
                                                                <option value={200}>200</option>
                                                            </select>
                                                        </div>
                                                        
                                                        <div className="text-slate-400 text-sm">
                                                            Page {currentPage} of {totalPages} ({startIdx + 1}-{Math.min(endIdx, bt.chart_data.trades.length)} of {bt.chart_data.trades.length})
                                                        </div>
                                                        
                                                        <div className="flex gap-2">
                                                            <button
                                                                onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                                                                disabled={currentPage === 1}
                                                                className="px-3 py-1 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm rounded border border-slate-600 transition-colors"
                                                            >
                                                                Previous
                                                            </button>
                                                            <button
                                                                onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                                                                disabled={currentPage === totalPages}
                                                                className="px-3 py-1 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm rounded border border-slate-600 transition-colors"
                                                            >
                                                                Next
                                                            </button>
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    })()}
                                </div>
                            )}

                            <p className="text-center text-slate-500 text-xs pb-4">
                                Past performance is not indicative of future results. For educational purposes only.
                            </p>
                        </div>
                    )}

                    {/* ── Screener Result ── */}
                    {result?.type === "screen" && !loading && (() => {
                        const sc = (result as ScreenerResult).content;
                        return (
                            <div className="space-y-6">
                                {/* Summary */}
                                <div className="bg-slate-800/40 border border-purple-500/20 rounded-2xl p-5">
                                    <div className="flex items-start justify-between mb-3">
                                        <div>
                                            <h3 className="text-white font-bold text-lg mb-2">Search Results</h3>
                                            <p className="text-purple-200 text-sm mb-3">{sc.query}</p>
                                        </div>
                                        <div className="text-right">
                                            <p className="text-3xl font-bold text-purple-400">{sc.total_matches}</p>
                                            <p className="text-xs text-slate-400">stocks found</p>
                                        </div>
                                    </div>
                                    
                                    {(sc.criteria ?? []).length > 0 && (
                                        <div>
                                            <p className="text-slate-400 text-xs mb-2">Applied Criteria:</p>
                                            <div className="flex flex-wrap gap-2">
                                                {(sc.criteria ?? []).map((criterion, i) => (
                                                    <span key={i} className="px-3 py-1 bg-purple-900/50 border border-purple-500/30 rounded-full text-purple-200 text-xs">
                                                        {criterion}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>

                                {/* Stock Grid */}
                                {(sc.stocks ?? []).length > 0 ? (
                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                        {(sc.stocks ?? []).map((stock) => {
                                            const isPositive = stock.change_pct >= 0;
                                            return (
                                                <div key={stock.ticker} className="bg-slate-800/60 border border-purple-500/20 rounded-xl p-5 hover:border-purple-500/40 transition-all hover:shadow-lg hover:shadow-purple-500/10">
                                                    <div className="flex items-start justify-between mb-3">
                                                        <div>
                                                            <h3 className="text-white font-bold text-lg">{stock.ticker}</h3>
                                                            <p className="text-slate-400 text-sm">{stock.name}</p>
                                                        </div>
                                                        <div className="text-right">
                                                            <p className="text-white font-bold text-lg">{stock.currency ?? "$"}{fmt(stock.price)}</p>
                                                            <p className={`text-sm font-semibold ${isPositive ? "text-emerald-400" : "text-red-400"}`}>
                                                                {pct(stock.change_pct)}
                                                            </p>
                                                        </div>
                                                    </div>

                                                    <div className="grid grid-cols-2 gap-3 mb-3 text-sm">
                                                        <div>
                                                            <p className="text-slate-500 text-xs">Market Cap</p>
                                                            <p className="text-purple-300 font-medium">{stock.market_cap}</p>
                                                        </div>
                                                        <div>
                                                            <p className="text-slate-500 text-xs">P/E Ratio</p>
                                                            <p className="text-purple-300 font-medium">{stock.pe_ratio > 0 ? fmt(stock.pe_ratio) : "N/A"}</p>
                                                        </div>
                                                        <div>
                                                            <p className="text-slate-500 text-xs">Volume</p>
                                                            <p className="text-purple-300 font-medium">{stock.volume}</p>
                                                        </div>
                                                        <div>
                                                            <p className="text-slate-500 text-xs">Sector</p>
                                                            <p className="text-purple-300 font-medium">{stock.sector}</p>
                                                        </div>
                                                        {/* Technical indicators if available */}
                                                        {stock.sma20 && (
                                                            <div>
                                                                <p className="text-slate-500 text-xs">20-day MA</p>
                                                                <p className="text-purple-300 font-medium">{stock.currency ?? "$"}{fmt(stock.sma20)}</p>
                                                            </div>
                                                        )}
                                                        {stock.rsi && (
                                                            <div>
                                                                <p className="text-slate-500 text-xs">RSI</p>
                                                                <p className={`font-medium ${stock.rsi < 30 ? "text-green-400" : stock.rsi > 70 ? "text-red-400" : "text-purple-300"}`}>
                                                                    {fmt(stock.rsi, 1)}
                                                                </p>
                                                            </div>
                                                        )}
                                                        {stock.pct_from_52w_high !== undefined && (
                                                            <div>
                                                                <p className="text-slate-500 text-xs">From 52W High</p>
                                                                <p className={`font-medium ${stock.pct_from_52w_high > -10 ? "text-yellow-400" : "text-purple-300"}`}>
                                                                    {stock.pct_from_52w_high.toFixed(1)}%
                                                                </p>
                                                            </div>
                                                        )}
                                                    </div>

                                                    <div className="pt-3 border-t border-slate-700/50">
                                                        <p className="text-xs text-slate-400 mb-1">Match Reason:</p>
                                                        <p className="text-sm text-slate-300">{stock.match_reason}</p>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                ) : (
                                    <div className="bg-slate-800/40 border border-yellow-500/20 rounded-2xl p-8 text-center">
                                        <p className="text-yellow-300 text-lg mb-2">No stocks found</p>
                                        <p className="text-slate-400 text-sm">Try adjusting your criteria or using different search terms.</p>
                                    </div>
                                )}

                                {/* Disclaimer */}
                                <div className="bg-amber-950/30 border border-amber-500/30 rounded-xl px-5 py-4 flex gap-3 text-xs text-amber-200/80">
                                    <span className="text-amber-400 text-base shrink-0 mt-0.5">⚠️</span>
                                    <span>
                                        <span className="font-semibold text-amber-300">Research tool only — not financial advice. </span>
                                        Stock data is for informational purposes only. Data may be delayed. Always do your own research before investing.
                                    </span>
                                </div>
                            </div>
                        );
                    })()}

                    {/* ── Portfolio Result ── */}
                    {result?.type === "portfolio" && !loading && (() => {
                        const po = (result as PortfolioResult).content;
                        const getScoreColor = (s: number) => s >= 8 ? "text-emerald-400 font-bold" : s >= 6 ? "text-blue-400" : s >= 4 ? "text-yellow-400" : "text-red-400";
                        const getBarColor   = (s: number) => s >= 8 ? "bg-emerald-500" : s >= 6 ? "bg-blue-500" : s >= 4 ? "bg-yellow-500" : "bg-red-500";
                        const scoreKeys: (keyof StockScore)[] = ["financial_health","growth_potential","news_sentiment","news_impact","price_momentum","volatility_risk"];
                        const scoreLabels: Record<string, string> = {
                            financial_health: "Financial Health", growth_potential: "Growth Potential",
                            news_sentiment: "News Sentiment", news_impact: "News Impact",
                            price_momentum: "Price Momentum", volatility_risk: "Volatility Risk",
                        };
                        return (
                            <div className="space-y-6">
                                {/* Portfolio Allocation */}
                                <div className="bg-slate-800/40 border border-yellow-500/20 rounded-2xl p-6">
                                    <h3 className="text-white font-bold text-xl mb-4">📊 Portfolio Allocation</h3>

                                    {/* Summary bar */}
                                    {(() => {
                                        const totalInvested = po.portfolio.selected_stocks.reduce((sum, s) => sum + s.weight, 0);
                                        const cash = Math.max(0, 1 - totalInvested);
                                        return (
                                            <div className="mb-4 bg-white/5 rounded-xl p-3 flex flex-wrap gap-4 items-center">
                                                <div className="flex items-center gap-2">
                                                    <span className="w-3 h-3 rounded-full bg-gradient-to-r from-yellow-500 to-orange-500 inline-block"></span>
                                                    <span className="text-slate-300 text-sm">Invested</span>
                                                    <span className="text-white font-bold">{(totalInvested * 100).toFixed(1)}%</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <span className="w-3 h-3 rounded-full bg-slate-500 inline-block"></span>
                                                    <span className="text-slate-300 text-sm">Cash / Unallocated</span>
                                                    <span className="text-yellow-300 font-bold">{(cash * 100).toFixed(1)}%</span>
                                                </div>
                                                {cash > 0.01 && (
                                                    <span className="text-slate-400 text-xs italic">
                                                        The AI kept {(cash * 100).toFixed(0)}% in cash — remaining stocks didn't meet the strategy criteria.
                                                    </span>
                                                )}
                                            </div>
                                        );
                                    })()}

                                    <div className="space-y-3 mb-5">
                                        {po.portfolio.selected_stocks.map((s, i) => (
                                            <div key={i} className="bg-white/5 rounded-lg p-4">
                                                <div className="flex justify-between items-center mb-2">
                                                    <span className="text-white font-bold">{s.stock_code}</span>
                                                    <span className="text-yellow-300 font-bold">{(s.weight * 100).toFixed(1)}% of portfolio</span>
                                                </div>
                                                <div className="w-full bg-slate-700 rounded-full h-3">
                                                    <div className="bg-gradient-to-r from-yellow-500 to-orange-500 h-3 rounded-full" style={{ width: `${s.weight * 100}%` }} />
                                                </div>
                                            </div>
                                        ))}

                                        {/* Cash row */}
                                        {(() => {
                                            const cash = Math.max(0, 1 - po.portfolio.selected_stocks.reduce((sum, s) => sum + s.weight, 0));
                                            return cash > 0.005 ? (
                                                <div className="bg-white/5 rounded-lg p-4 border border-yellow-500/20">
                                                    <div className="flex justify-between items-center mb-2">
                                                        <span className="text-yellow-300 font-bold flex items-center gap-2">💵 Cash / Unallocated</span>
                                                        <span className="text-yellow-300 font-bold">{(cash * 100).toFixed(1)}% of portfolio</span>
                                                    </div>
                                                    <div className="w-full bg-slate-700 rounded-full h-3">
                                                        <div className="bg-yellow-500/50 h-3 rounded-full" style={{ width: `${cash * 100}%` }} />
                                                    </div>
                                                    <p className="text-slate-400 text-xs mt-2">
                                                        The AI deliberately left this portion uninvested — remaining stocks didn't meet the strategy criteria.
                                                    </p>
                                                </div>
                                            ) : null;
                                        })()}
                                    </div>

                                    <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
                                        <p className="text-xs text-yellow-300 uppercase tracking-wider mb-1">Selection Reasoning</p>
                                        <p className="text-slate-200 text-sm">{po.portfolio.reasoning}</p>
                                    </div>
                                </div>

                                {/* Strategy */}
                                <div className="bg-slate-800/40 border border-yellow-500/20 rounded-2xl p-6">
                                    <h3 className="text-white font-bold text-xl mb-3">🎯 Investment Strategy</h3>
                                    <div className="bg-cyan-500/10 border border-cyan-500/30 rounded-lg p-4 mb-3">
                                        <p className="text-slate-200 text-sm">{po.current_strategy}</p>
                                    </div>
                                    {po.new_strategy && (
                                        <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-4">
                                            <p className="text-xs text-emerald-300 uppercase tracking-wider mb-1">Updated Strategy</p>
                                            <p className="text-slate-200 text-sm">{po.new_strategy}</p>
                                        </div>
                                    )}
                                </div>

                                {/* Stock Scores */}
                                <div className="bg-slate-800/40 border border-yellow-500/20 rounded-2xl p-6">
                                    <h3 className="text-white font-bold text-xl mb-4">📈 Multi-Dimensional Stock Scores</h3>
                                    <div className="space-y-5">
                                        {po.score_reports.map((report, i) => (
                                            <div key={i} className="bg-white/5 rounded-xl p-5">
                                                <h4 className="text-white font-bold text-lg mb-4">{report.stock}</h4>
                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                                    {scoreKeys.map(key => {
                                                        const dim = report[key] as { score: number; reason: string };
                                                        return (
                                                            <div key={key} className="bg-white/5 rounded-lg p-3">
                                                                <div className="flex justify-between items-center mb-1">
                                                                    <span className="text-slate-300 text-sm font-medium">{scoreLabels[key]}</span>
                                                                    <span className={`text-sm ${getScoreColor(dim.score)}`}>{dim.score}/10</span>
                                                                </div>
                                                                <div className="w-full bg-slate-700 rounded-full h-2 mb-2">
                                                                    <div className={`${getBarColor(dim.score)} h-2 rounded-full`} style={{ width: `${dim.score * 10}%` }} />
                                                                </div>
                                                                <p className="text-slate-400 text-xs">{dim.reason}</p>
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                                <p className="text-center text-slate-500 text-xs pb-4">Not financial advice. For informational purposes only.</p>
                            </div>
                        );
                    })()}

                    {/* ── Ensemble Builder Redirect ── */}
                    {result?.type === "ensemble" && !loading && (
                        <div className="max-w-2xl mx-auto">
                            <div className="bg-slate-800/60 backdrop-blur-xl border border-fuchsia-500/40 rounded-2xl p-8 shadow-2xl relative overflow-hidden">
                                <div className="absolute top-0 right-0 w-48 h-48 bg-fuchsia-500/10 rounded-full blur-3xl -z-10" />
                                <div className="absolute bottom-0 left-0 w-48 h-48 bg-indigo-500/10 rounded-full blur-3xl -z-10" />
                                
                                <div className="flex items-center gap-4 mb-6">
                                    <div className="w-14 h-14 bg-gradient-to-br from-fuchsia-500 to-indigo-500 rounded-2xl flex items-center justify-center text-3xl shadow-lg shadow-fuchsia-500/20">
                                        🚀
                                    </div>
                                    <div>
                                        <h3 className="text-white font-extrabold text-xl">Multi-Strategy Ensemble Builder</h3>
                                        <p className="text-fuchsia-300 text-xs font-semibold uppercase tracking-wider">Institutional Quant Suite</p>
                                    </div>
                                </div>

                                <p className="text-slate-200 text-base leading-relaxed mb-6">
                                    I detected that you want to build a diversified, multi-strategy portfolio. Our dedicated <strong>Ensemble Builder</strong> can automatically generate 3 diverse strategies, test them concurrently, aggregate daily return vectors, and calculate combined portfolio metrics with interactive charts!
                                </p>

                                <div className="bg-slate-900/60 rounded-xl p-4 border border-fuchsia-500/20 mb-6 flex items-start gap-3">
                                    <span className="text-fuchsia-400 mt-0.5">ℹ️</span>
                                    <div>
                                        <p className="text-xs text-slate-400 uppercase font-semibold">Your Query</p>
                                        <p className="text-white text-sm font-mono mt-1">"{message}"</p>
                                    </div>
                                </div>

                                <Link 
                                    href={`/ensemble-builder?query=${encodeURIComponent(message)}`}
                                    className="block w-full py-4 text-center bg-gradient-to-r from-fuchsia-600 to-indigo-600 hover:from-fuchsia-700 hover:to-indigo-700 text-white font-bold rounded-xl transition-all shadow-lg shadow-fuchsia-500/30 transform hover:-translate-y-0.5 active:translate-y-0"
                                >
                                    Open Ensemble Builder Dashboard & Run Analysis →
                                </Link>
                            </div>
                        </div>
                    )}

                    {/* ── Unknown / fallback ── */}
                    {result?.type === "unknown" && !loading && (
                        <div className="max-w-2xl mx-auto">
                            <div className="bg-slate-800/40 border border-purple-500/20 rounded-2xl p-6">
                                <ReactMarkdown components={{
                                    h1: ({ children }) => <h1 className="text-2xl font-bold text-white mt-4 mb-3">{children}</h1>,
                                    h2: ({ children }) => <h2 className="text-xl font-bold text-purple-200 mt-4 mb-2">{children}</h2>,
                                    h3: ({ children }) => <h3 className="text-lg font-semibold text-purple-300 mt-3 mb-2">{children}</h3>,
                                    p:      ({ children }) => <p className="text-slate-300 mb-3">{children}</p>,
                                    li:     ({ children }) => <li className="flex items-start gap-2 text-slate-300 mb-1"><span className="mt-2 w-1.5 h-1.5 rounded-full bg-purple-500 flex-shrink-0" /><span>{children}</span></li>,
                                    ul:     ({ children }) => <ul className="ml-2 space-y-1">{children}</ul>,
                                    strong: ({ children }) => <strong className="text-white font-semibold">{children}</strong>,
                                    table: ({ children }) => (
                                        <div className="overflow-x-auto my-4">
                                            <table className="w-full text-sm border-collapse">{children}</table>
                                        </div>
                                    ),
                                    thead: ({ children }) => <thead className="bg-purple-900/40">{children}</thead>,
                                    tbody: ({ children }) => <tbody className="divide-y divide-purple-500/10">{children}</tbody>,
                                    tr:   ({ children }) => <tr className="hover:bg-purple-900/20 transition-colors">{children}</tr>,
                                    th:   ({ children }) => <th className="px-3 py-2 text-left text-purple-300 font-semibold border-b border-purple-500/30 whitespace-nowrap">{children}</th>,
                                    td:   ({ children }) => <td className="px-3 py-2 text-slate-300 border-b border-purple-500/10">{children}</td>,
                                }}>
                                    {(result as UnknownResult).content}
                                </ReactMarkdown>
                            </div>
                        </div>
                    )}

                </main>

                {/* ── SEO Content: Features Section ── */}
                <section className="bg-slate-900/60 border-t border-cyan-500/10 py-16">
                    <div className="max-w-6xl mx-auto px-6">
                        <div className="text-center mb-12">
                            <h2 className="text-3xl font-bold text-white mb-3">
                                AI for Stock Analysis — Everything You Need
                            </h2>
                            <p className="text-cyan-200 max-w-2xl mx-auto">
                                MokshaGPT is a full-featured stock market AI platform. Whether you need a quick stock analysis, want to backtest a strategy, screen thousands of stocks, or analyze your own trade history — our AI handles it all.
                            </p>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-14">
                            {/* Feature 1 */}
                            <Link href="/" className="bg-slate-800/50 border border-cyan-500/20 rounded-2xl p-6 hover:border-cyan-500/50 hover:bg-slate-700/50 transition-all group">
                                <div className="text-3xl mb-3">📈</div>
                                <h3 className="text-white font-bold text-lg mb-2 group-hover:text-cyan-300 transition-colors">AI Stock Analyzer</h3>
                                <p className="text-slate-300 text-sm leading-relaxed">
                                    Get a comprehensive AI stock analysis in seconds. Our stock analysis AI covers technical indicators, fundamentals, price momentum, and market sentiment for any ticker worldwide.
                                </p>
                                <span className="inline-block mt-3 text-xs text-cyan-400 group-hover:text-cyan-300 transition-colors">Analyze a stock →</span>
                            </Link>
                            {/* Feature 2 */}
                            <Link href="/aibacktester" className="bg-slate-800/50 border border-blue-500/20 rounded-2xl p-6 hover:border-blue-500/50 hover:bg-slate-700/50 transition-all group">
                                <div className="text-3xl mb-3">🔬</div>
                                <h3 className="text-white font-bold text-lg mb-2 group-hover:text-blue-300 transition-colors">AI Strategy Backtester</h3>
                                <p className="text-slate-300 text-sm leading-relaxed">
                                    Describe any trading strategy in plain English and backtest it instantly. Get Sharpe ratio, win rate, max drawdown, profit factor, and a full trade log — powered by AI backtesting.
                                </p>
                                <span className="inline-block mt-3 text-xs text-blue-400 group-hover:text-blue-300 transition-colors">Backtest a strategy →</span>
                            </Link>
                            {/* Feature 3: Backtest Optimizer */}
                            <Link href="/backtest-optimizer" className="bg-slate-800/50 border border-purple-500/20 rounded-2xl p-6 hover:border-purple-500/50 hover:bg-slate-700/50 transition-all group">
                                <div className="text-3xl mb-3">⚡</div>
                                <h3 className="text-white font-bold text-lg mb-2 group-hover:text-purple-300 transition-colors">Backtest Optimizer</h3>
                                <p className="text-slate-300 text-sm leading-relaxed">
                                    Autonomous LangGraph loop that iteratively refines your strategy until Sharpe, drawdown, and win-rate targets are met.
                                </p>
                                <span className="inline-block mt-3 text-xs text-purple-400 group-hover:text-purple-300 transition-colors">Optimize strategy →</span>
                            </Link>
                            {/* Feature 4 */}
                            <Link href="/aiscreener" className="bg-slate-800/50 border border-purple-500/20 rounded-2xl p-6 hover:border-purple-500/50 hover:bg-slate-700/50 transition-all group">
                                <div className="text-3xl mb-3">🔍</div>
                                <h3 className="text-white font-bold text-lg mb-2 group-hover:text-purple-300 transition-colors">AI Stock Screener</h3>
                                <p className="text-slate-300 text-sm leading-relaxed">
                                    Screen thousands of stocks using natural language. Ask for "US tech stocks with RSI below 30" or "NIFTY 50 stocks below 20-day moving average" — the AI stock screener does the rest.
                                </p>
                                <span className="inline-block mt-3 text-xs text-purple-400 group-hover:text-purple-300 transition-colors">Screen stocks →</span>
                            </Link>
                            {/* Feature 5: Ensemble Builder */}
                            <Link href="/ensemble-builder" className="bg-slate-800/50 border border-fuchsia-500/20 rounded-2xl p-6 hover:border-fuchsia-500/50 hover:bg-slate-700/50 transition-all group">
                                <div className="text-3xl mb-3">🚀</div>
                                <h3 className="text-white font-bold text-lg mb-2 group-hover:text-fuchsia-300 transition-colors">Ensemble Builder</h3>
                                <p className="text-slate-300 text-sm leading-relaxed">
                                    Combine multiple uncorrelated trading strategies into a single robust portfolio with mathematically aggregated risk and diversified returns.
                                </p>
                                <span className="inline-block mt-3 text-xs text-fuchsia-400 group-hover:text-fuchsia-300 transition-colors">Build ensemble →</span>
                            </Link>
                            {/* Feature 6 */}
                            <Link href="/tradeanalyzer" className="bg-slate-800/50 border border-emerald-500/20 rounded-2xl p-6 hover:border-emerald-500/50 hover:bg-slate-700/50 transition-all group">
                                <div className="text-3xl mb-3">📋</div>
                                <h3 className="text-white font-bold text-lg mb-2 group-hover:text-emerald-300 transition-colors">Trade History Analyzer</h3>
                                <p className="text-slate-300 text-sm leading-relaxed">
                                    Upload your brokerage trade history CSV and get an instant trading performance analysis — P&L breakdown, overtrading detection, consistency score, and AI coaching. Works with any broker.
                                </p>
                                <span className="inline-block mt-3 text-xs text-emerald-400 group-hover:text-emerald-300 transition-colors">Analyze my trades →</span>
                            </Link>
                            {/* Feature 7 */}
                            <Link href="/aireporter" className="bg-slate-800/50 border border-orange-500/20 rounded-2xl p-6 hover:border-orange-500/50 hover:bg-slate-700/50 transition-all group">
                                <div className="text-3xl mb-3">📰</div>
                                <h3 className="text-white font-bold text-lg mb-2 group-hover:text-orange-300 transition-colors">AI Reporter</h3>
                                <p className="text-slate-300 text-sm leading-relaxed">
                                    Generate professional financial research reports for any stock. Deep-dive analysis with AI-written commentary on technicals, fundamentals, and market outlook.
                                </p>
                                <span className="inline-block mt-3 text-xs text-orange-400 group-hover:text-orange-300 transition-colors">Generate a report →</span>
                            </Link>
                            {/* Feature 8 */}
                            <div className="bg-slate-800/50 border border-slate-600/20 rounded-2xl p-6">
                                <div className="text-3xl mb-3">🚀</div>
                                <h3 className="text-white font-bold text-lg mb-2">More Coming Soon</h3>
                                <p className="text-slate-400 text-sm leading-relaxed">
                                    Options analyzer, earnings calendar, sector rotation tracker, and more AI-powered tools in development.
                                </p>
                            </div>
                        </div>

                        {/* How it works */}
                        <div className="bg-slate-800/30 border border-cyan-500/15 rounded-2xl p-8 mb-14">
                            <h2 className="text-2xl font-bold text-white mb-6 text-center">How Our Stock Market AI Works</h2>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                                <div className="text-center">
                                    <div className="w-12 h-12 bg-cyan-900/60 border border-cyan-500/40 rounded-full flex items-center justify-center text-xl mx-auto mb-3">1</div>
                                    <h3 className="text-white font-semibold mb-2">Ask in Plain English</h3>
                                    <p className="text-slate-400 text-sm">Type your question naturally — "Analyze AAPL", "Backtest RSI on TSLA for 2 years", or "Find oversold Indian tech stocks".</p>
                                </div>
                                <div className="text-center">
                                    <div className="w-12 h-12 bg-cyan-900/60 border border-cyan-500/40 rounded-full flex items-center justify-center text-xl mx-auto mb-3">2</div>
                                    <h3 className="text-white font-semibold mb-2">AI Routes to the Right Tool</h3>
                                    <p className="text-slate-400 text-sm">The AI agent classifies your intent and automatically routes to the stock analyzer, backtester, screener, or portfolio optimizer.</p>
                                </div>
                                <div className="text-center">
                                    <div className="w-12 h-12 bg-cyan-900/60 border border-cyan-500/40 rounded-full flex items-center justify-center text-xl mx-auto mb-3">3</div>
                                    <h3 className="text-white font-semibold mb-2">Get Actionable Insights</h3>
                                    <p className="text-slate-400 text-sm">Receive a detailed AI stock analysis report with charts, metrics, and plain-English explanations — ready in seconds.</p>
                                </div>
                            </div>
                        </div>

                        {/* FAQ Section */}
                        <div className="max-w-3xl mx-auto">
                            <h2 className="text-2xl font-bold text-white mb-6 text-center">Frequently Asked Questions</h2>
                            <div className="space-y-4">
                                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                                    <h3 className="text-white font-semibold mb-2">What is an AI stock analyzer?</h3>
                                    <p className="text-slate-300 text-sm leading-relaxed">
                                        An AI stock analyzer uses artificial intelligence to evaluate stocks by processing real-time price data, technical indicators, and fundamental metrics. MokshaGPT's stock analysis AI generates comprehensive reports in plain English — covering RSI, MACD, moving averages, support/resistance levels, and more.
                                    </p>
                                </div>
                                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                                    <h3 className="text-white font-semibold mb-2">How is AI for stock analysis better than traditional tools?</h3>
                                    <p className="text-slate-300 text-sm leading-relaxed">
                                        Traditional stock analysis tools require you to manually set up charts and interpret indicators. AI for stock analysis understands natural language, automatically selects the right indicators, and explains findings in plain English — making professional-grade analysis accessible to everyone.
                                    </p>
                                </div>
                                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                                    <h3 className="text-white font-semibold mb-2">Which markets does the stock market AI cover?</h3>
                                    <p className="text-slate-300 text-sm leading-relaxed">
                                        MokshaGPT's stock market AI covers US (NYSE, NASDAQ), Indian (NSE, BSE), UK, Germany, Japan, Hong Kong, Australia, Canada, Crypto, Forex pairs, and Futures contracts — all from a single interface.
                                    </p>
                                </div>
                                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                                    <h3 className="text-white font-semibold mb-2">Can I backtest any trading strategy with AI?</h3>
                                    <p className="text-slate-300 text-sm leading-relaxed">
                                        Yes. Describe your strategy in plain English — e.g. "10/50 SMA crossover on NVDA for 3 years with $50,000" — and the AI backtester will run it and return full performance metrics including Sharpe ratio, Sortino ratio, max drawdown, win rate, profit factor, and an interactive portfolio chart.
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

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
                                        <Link href="/ensemble-builder" className="text-cyan-300 hover:text-white transition-colors text-sm flex items-center gap-2">
                                            <span className="text-lg">🚀</span>
                                            <span>Ensemble Builder</span>
                                        </Link>
                                        <p className="text-slate-400 text-xs ml-7">Combine multiple trading strategies</p>
                                    </li>
                                    <li>
                                        <Link href="/tradeanalyzer" className="text-cyan-300 hover:text-white transition-colors text-sm flex items-center gap-2">
                                            <span className="text-lg">📈</span>
                                            <span>Trade Analyzer</span>
                                        </Link>
                                        <p className="text-slate-400 text-xs ml-7">Analyze your brokerage trade history</p>
                                    </li>
                                    <li>
                                        <Link href="/aireporter" className="text-cyan-300 hover:text-white transition-colors text-sm flex items-center gap-2">
                                            <span className="text-lg">📋</span>
                                            <span>AI Reporter</span>
                                        </Link>
                                        <p className="text-slate-400 text-xs ml-7">Generate professional financial reports</p>
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
