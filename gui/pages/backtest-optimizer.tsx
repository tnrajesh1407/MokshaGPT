import { useState } from "react";
import Head from "next/head";
import Link from "next/link";
import Header from "../components/Header";
import RelatedTools from "../components/RelatedTools";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  AreaChart, Area, ResponsiveContainer, Legend,
} from "recharts";

// ── Types ─────────────────────────────────────────────────────────────────────

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
  fee_description?: string;
}

interface IterationLog {
  iteration: number;
  strategy: string;
  metrics?: Metrics;
  is_best?: boolean;
  error?: string;
}

interface OptimizeResult {
  passed: boolean;
  iterations: number;
  best_result: {
    parsed_strategy: {
      ticker: string;
      strategy_description: string;
      period_years?: number;
      period_days?: number;
      initial_capital: number;
      timeframe?: string;
      start_date?: string;
      end_date?: string;
    };
    metrics: Metrics;
    chart_data: {
      price_series: { date: string; close: number; portfolio: number }[];
      drawdown_series: { date: string; drawdown: number }[];
      trades: any[];
    };
  } | null;
  best_metrics: Metrics | null;
  iterations_log: IterationLog[];
  final_strategy: string;
  summary: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const fmt = (n: number, d = 2) =>
  n?.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });

const pct = (n: number) => `${n >= 0 ? "+" : ""}${fmt(n)}%`;

const DEFAULT_THRESHOLDS = {
  min_sharpe: 0.8,
  max_drawdown_pct: -20.0,
  min_win_rate_pct: 45.0,
};

const EXAMPLE_STRATEGIES = [
  "SMA 10/50 crossover on AAPL for 3 years with $50,000",
  "RSI strategy on TSLA: buy when RSI < 30, sell when RSI > 70, 2 years, $100,000",
  "MACD crossover on MSFT for 2 years with $50,000",
  "Bollinger Bands mean reversion on NVDA, 20-period, 2 std dev, 3 years, $50,000",
  "EMA 9/21 crossover on TCS.NS for 3 years with ₹500,000",
  "RSI strategy on RELIANCE.NS: buy RSI < 35, sell RSI > 65, 2 years, ₹1,000,000",
];

// ── Sub-components ────────────────────────────────────────────────────────────

function MetricCard({
  label, value, sub, positive,
}: { label: string; value: string; sub?: string; positive?: boolean }) {
  const color =
    positive === undefined ? "text-white" : positive ? "text-emerald-400" : "text-red-400";
  return (
    <div className="bg-slate-800/60 border border-violet-500/20 rounded-xl p-4 flex flex-col gap-1">
      <span className="text-xs text-violet-300 uppercase tracking-wider">{label}</span>
      <span className={`text-2xl font-bold ${color}`}>{value}</span>
      {sub && <span className="text-xs text-slate-400">{sub}</span>}
    </div>
  );
}

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-slate-900 border border-violet-500/30 rounded-lg p-3 text-xs shadow-xl">
      <p className="text-violet-300 mb-1 font-semibold">{label}</p>
      {payload.map((p: any) => (
        <p key={p.dataKey} style={{ color: p.color }}>
          {p.name}: {typeof p.value === "number" ? fmt(p.value) : p.value}
        </p>
      ))}
    </div>
  );
}

function ThresholdBadge({
  label, value, pass,
}: { label: string; value: string; pass: boolean }) {
  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs
      ${pass
        ? "bg-emerald-900/30 border-emerald-500/30 text-emerald-300"
        : "bg-red-900/30 border-red-500/30 text-red-300"}`}>
      <span>{pass ? "✓" : "✗"}</span>
      <span className="font-medium">{label}</span>
      <span className="text-slate-400">{value}</span>
    </div>
  );
}

function IterationCard({ log, index, isFinalBest }: { log: IterationLog; index: number; isFinalBest: boolean }) {
  const [open, setOpen] = useState(false);
  const m = log.metrics;
  const hasError = !!log.error;

  return (
    <div className={`rounded-xl border p-4 transition-all
      ${isFinalBest
        ? "bg-violet-900/20 border-violet-500/40"
        : hasError
        ? "bg-red-900/10 border-red-500/20"
        : "bg-slate-800/40 border-slate-600/30"}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold
            ${isFinalBest ? "bg-violet-600 text-white" : "bg-slate-700 text-slate-300"}`}>
            {index + 1}
          </span>
          <div>
            <p className="text-sm text-white font-medium truncate max-w-xs md:max-w-lg">
              {log.strategy.length > 90 ? log.strategy.slice(0, 90) + "…" : log.strategy}
            </p>
            {isFinalBest && (
              <span className="text-xs text-violet-400 font-semibold">⭐ Best result</span>
            )}
            {hasError && (
              <span className="text-xs text-red-400">Error: {log.error}</span>
            )}
          </div>
        </div>
        {m && (
          <button
            onClick={() => setOpen(!open)}
            className="text-xs text-slate-400 hover:text-white transition-colors ml-4 shrink-0"
          >
            {open ? "▲ Hide" : "▼ Metrics"}
          </button>
        )}
      </div>

      {m && (
        <div className="mt-3 flex flex-wrap gap-3 text-xs">
          <span className={`px-2 py-1 rounded ${m.sharpe_ratio >= 0.8 ? "bg-emerald-900/40 text-emerald-300" : "bg-red-900/40 text-red-300"}`}>
            Sharpe {fmt(m.sharpe_ratio, 3)}
          </span>
          <span className={`px-2 py-1 rounded ${m.max_drawdown_pct >= -20 ? "bg-emerald-900/40 text-emerald-300" : "bg-red-900/40 text-red-300"}`}>
            DD {fmt(m.max_drawdown_pct)}%
          </span>
          <span className={`px-2 py-1 rounded ${m.win_rate_pct >= 45 ? "bg-emerald-900/40 text-emerald-300" : "bg-red-900/40 text-red-300"}`}>
            WR {fmt(m.win_rate_pct)}%
          </span>
          <span className="px-2 py-1 rounded bg-slate-700/50 text-slate-300">
            Return {pct(m.total_return_pct)}
          </span>
          <span className="px-2 py-1 rounded bg-slate-700/50 text-slate-300">
            {m.total_trades} trades
          </span>
        </div>
      )}

      {open && m && (
        <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs border-t border-slate-700/50 pt-3">
          {[
            ["Total Return", pct(m.total_return_pct)],
            ["B&H Return", pct(m.buy_hold_return_pct)],
            ["Ann. Return", pct(m.annualized_return_pct)],
            ["Sharpe", fmt(m.sharpe_ratio, 3)],
            ["Sortino", m.sortino_ratio != null ? fmt(m.sortino_ratio, 3) : "—"],
            ["Max DD", `${fmt(m.max_drawdown_pct)}%`],
            ["Win Rate", `${fmt(m.win_rate_pct)}%`],
            ["Profit Factor", m.profit_factor != null ? fmt(m.profit_factor, 3) : "—"],
          ].map(([lbl, val]) => (
            <div key={lbl} className="bg-slate-900/50 rounded p-2">
              <p className="text-slate-500 mb-0.5">{lbl}</p>
              <p className="text-white font-semibold">{val}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function BacktestOptimizerPage() {
  const [strategy, setStrategy]   = useState("");
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState("");
  const [result, setResult]       = useState<OptimizeResult | null>(null);
  const [activeTab, setActiveTab] = useState<"chart" | "trades" | "log">("chart");

  // Threshold overrides
  const [showThresholds, setShowThresholds] = useState(false);
  const [minSharpe, setMinSharpe]           = useState(String(DEFAULT_THRESHOLDS.min_sharpe));
  const [maxDrawdown, setMaxDrawdown]       = useState(String(DEFAULT_THRESHOLDS.max_drawdown_pct));
  const [minWinRate, setMinWinRate]         = useState(String(DEFAULT_THRESHOLDS.min_win_rate_pct));
  const [maxIter, setMaxIter]               = useState("5");

  // Live iteration progress while loading
  const [liveIter, setLiveIter] = useState(0);

  const handleOptimize = async () => {
    if (!strategy.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    setLiveIter(0);
    setActiveTab("chart");

    // Simulate iteration counter while waiting (backend is synchronous)
    const iterMax = Math.min(parseInt(maxIter) || 5, 10);
    let tick = 0;
    const timer = setInterval(() => {
      tick++;
      setLiveIter(Math.min(tick, iterMax));
    }, 8000); // rough 8s per iteration estimate

    try {
      const thresholds: Record<string, number> = {};
      const s = parseFloat(minSharpe);
      const d = parseFloat(maxDrawdown);
      const w = parseFloat(minWinRate);
      if (!isNaN(s)) thresholds.min_sharpe = s;
      if (!isNaN(d)) thresholds.max_drawdown_pct = d;
      if (!isNaN(w)) thresholds.min_win_rate_pct = w;

      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/backtest/optimize`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            strategy,
            thresholds: Object.keys(thresholds).length ? thresholds : undefined,
            max_iterations: iterMax,
          }),
        }
      );

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Optimization failed");
      }

      const data: OptimizeResult = await res.json();
      setResult(data);
      setLiveIter(data.iterations);
    } catch (e: any) {
      setError(e.message || "Something went wrong");
    } finally {
      clearInterval(timer);
      setLoading(false);
    }
  };

  const br = result?.best_result;
  const m  = result?.best_metrics;
  const cd = br?.chart_data;
  const ps = br?.parsed_strategy;

  // Threshold pass/fail for best result
  const resolvedThresholds = {
    min_sharpe:       parseFloat(minSharpe)   || DEFAULT_THRESHOLDS.min_sharpe,
    max_drawdown_pct: parseFloat(maxDrawdown) || DEFAULT_THRESHOLDS.max_drawdown_pct,
    min_win_rate_pct: parseFloat(minWinRate)  || DEFAULT_THRESHOLDS.min_win_rate_pct,
  };

  return (
    <>
      <Head>
        <title>MokshaGPT – AI Backtest Optimizer | Auto-Optimize Trading Strategies</title>
        <meta name="description" content="The smartest AI backtest optimizer — describe any trading strategy, set Sharpe, drawdown, and win-rate targets, and let the AI automatically refine it across multiple iterations until it passes. Powered by LangGraph." />
        <meta name="keywords" content="backtest optimizer, ai backtest optimizer, trading strategy optimizer, auto optimize trading strategy, sharpe ratio optimizer, strategy refinement ai, backtesting optimization, algorithmic trading optimizer, ai trading strategy, backtest automation, langgraph trading, strategy parameter optimization" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="robots" content="index, follow" />
        <link rel="canonical" href="https://mokshagpt.com/backtest-optimizer" />

        {/* Open Graph */}
        <meta property="og:type" content="website" />
        <meta property="og:url" content="https://mokshagpt.com/backtest-optimizer" />
        <meta property="og:title" content="MokshaGPT – AI Backtest Optimizer | Auto-Optimize Trading Strategies" />
        <meta property="og:site_name" content="MokshaGPT" />
        <meta property="og:description" content="Describe a trading strategy in plain English. The AI backtests it, checks Sharpe ratio, drawdown, and win rate, then automatically refines and re-runs — up to 10 times — until your quality targets are met." />
        <meta property="og:image" content="https://mokshagpt.com/og-backtest-optimizer.jpg" />

        {/* Twitter */}
        <meta property="twitter:card" content="summary_large_image" />
        <meta property="twitter:url" content="https://mokshagpt.com/backtest-optimizer" />
        <meta property="twitter:title" content="MokshaGPT – AI Backtest Optimizer | Auto-Optimize Trading Strategies" />
        <meta property="twitter:description" content="Let AI automatically refine your trading strategy until it meets your Sharpe, drawdown, and win-rate targets. Powered by LangGraph autonomous optimization loop." />
        <meta property="twitter:image" content="https://mokshagpt.com/og-backtest-optimizer.jpg" />
        {/* Structured Data – SoftwareApplication */}
        <script type="application/ld+json">
          {JSON.stringify({
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": "MokshaGPT AI Backtest Optimizer",
            "applicationCategory": "FinanceApplication",
            "description": "Autonomous AI backtest optimizer powered by LangGraph. Describe a trading strategy, set Sharpe, drawdown, and win-rate targets, and the AI iteratively refines it until all quality thresholds are met.",
            "url": "https://mokshagpt.com/backtest-optimizer",
            "offers": {
              "@type": "Offer",
              "price": "0",
              "priceCurrency": "USD"
            },
            "featureList": [
              "Autonomous strategy optimization loop",
              "LangGraph multi-step refinement",
              "Sharpe ratio threshold enforcement",
              "Max drawdown quality gate",
              "Win rate optimization",
              "Up to 10 automatic refinement iterations",
              "Full iteration history and audit trail",
              "Best strategy selection by composite score",
              "Global market coverage",
              "Plain English strategy input"
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
                "name": "What is an AI backtest optimizer?",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "An AI backtest optimizer automatically runs a backtest on your trading strategy, evaluates the results against quality thresholds (Sharpe ratio, max drawdown, win rate), and if they are not met, asks the AI to refine the strategy and re-runs — repeating this loop until the strategy passes or the iteration limit is reached."
                }
              },
              {
                "@type": "Question",
                "name": "How many iterations does the optimizer run?",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "The optimizer runs up to 10 iterations by default (configurable). Each iteration backtests a refined version of your strategy. It stops early if all quality thresholds are met. The best result across all iterations is always returned, even if the thresholds are never fully met."
                }
              },
              {
                "@type": "Question",
                "name": "What quality thresholds does the optimizer check?",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "By default the optimizer checks three thresholds: Sharpe ratio ≥ 0.8, max drawdown ≤ -20%, and win rate ≥ 45%. All three thresholds are customizable before you run the optimizer."
                }
              },
              {
                "@type": "Question",
                "name": "What happens if the strategy never meets the thresholds?",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "The optimizer returns the best result found across all iterations along with a full audit trail showing every strategy variation tried and its metrics. This helps you understand which thresholds could not be met and why, so you can decide whether to adjust the thresholds or try a different strategy concept."
                }
              },
              {
                "@type": "Question",
                "name": "Does the optimizer switch to a completely different strategy?",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "No. The optimizer refines your original strategy concept — adjusting indicator periods, adding filters (like RSI or volume), or adding stop-loss and take-profit rules. It keeps the same ticker and capital. It will not switch from an SMA strategy to a Camarilla strategy, for example."
                }
              },
              {
                "@type": "Question",
                "name": "Is the backtest optimizer free to use?",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "Yes. MokshaGPT's AI Backtest Optimizer is completely free to use for educational and informational purposes. No sign-up required."
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
            <div className="inline-flex items-center gap-2 px-3 py-1 bg-violet-900/40 border border-violet-500/30 rounded-full text-violet-300 text-xs mb-4">
              <span className="w-2 h-2 rounded-full bg-violet-400 animate-pulse"></span>
              Powered by LangGraph — Autonomous Optimization Loop
            </div>
            <h1 className="text-4xl font-extrabold text-white mb-3">
              <span className="bg-gradient-to-r from-violet-400 via-purple-400 to-violet-400 bg-clip-text text-transparent">
                AI Backtest Optimizer
              </span>
            </h1>
            <p className="text-slate-300 max-w-2xl mx-auto mb-3">
              Describe a strategy in plain English. The AI runs a backtest, checks Sharpe ratio, drawdown, and win rate against your targets, then automatically refines the strategy and re-runs — up to 5 times — until it passes.
            </p>

            {/* LangGraph flow diagram */}
            <div className="max-w-3xl mx-auto mt-4">
              <div className="bg-slate-800/30 border border-violet-500/20 rounded-xl p-4 flex items-center justify-center gap-2 text-xs text-slate-400 flex-wrap">
                <span className="px-2 py-1 bg-slate-700/50 rounded">Your Strategy</span>
                <span>→</span>
                <span className="px-2 py-1 bg-violet-900/50 border border-violet-500/30 rounded text-violet-300">run_backtest</span>
                <span>→</span>
                <span className="px-2 py-1 bg-blue-900/50 border border-blue-500/30 rounded text-blue-300">evaluate</span>
                <span>→</span>
                <span className="text-emerald-400 font-semibold">pass → END</span>
                <span className="text-slate-600">|</span>
                <span className="text-red-400">fail →</span>
                <span className="px-2 py-1 bg-orange-900/50 border border-orange-500/30 rounded text-orange-300">refine_strategy</span>
                <span>→ loop</span>
              </div>
            </div>
          </div>

          {/* Input card */}
          <div className="max-w-3xl mx-auto mb-8">
            <div className="mb-4 bg-amber-950/30 border border-amber-500/30 rounded-xl px-5 py-4 flex gap-3 text-xs text-amber-200/80">
              <span className="text-amber-400 text-base shrink-0 mt-0.5">⚠️</span>
              <span>
                <span className="font-semibold text-amber-300">Research tool only — not financial advice. </span>
                Optimization targets historical metrics only. Past performance does not guarantee future results.
              </span>
            </div>

            <div className="bg-slate-800/60 backdrop-blur-xl rounded-2xl border border-violet-500/30 p-6 shadow-2xl">
              <label className="block text-violet-300 text-sm font-medium mb-2">
                Describe your base strategy
              </label>
              <textarea
                rows={3}
                placeholder="e.g. SMA 10/50 crossover on AAPL for 3 years with $50,000"
                value={strategy}
                onChange={(e) => setStrategy(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleOptimize(); } }}
                className="w-full px-4 py-3 text-white bg-slate-900/70 border-2 border-violet-500/30 rounded-xl focus:outline-none focus:border-violet-500 transition-all placeholder:text-slate-400 resize-none"
              />

              {/* Example chips */}
              <div className="mt-3 flex flex-wrap gap-2">
                {EXAMPLE_STRATEGIES.map((ex) => (
                  <button
                    key={ex}
                    onClick={() => setStrategy(ex)}
                    className="text-xs px-3 py-1 bg-violet-900/40 border border-violet-500/30 text-violet-300 rounded-full hover:bg-violet-800/50 hover:text-white transition-all"
                  >
                    {ex.length > 55 ? ex.slice(0, 55) + "…" : ex}
                  </button>
                ))}
              </div>

              {/* Threshold controls */}
              <div className="mt-4">
                <button
                  onClick={() => setShowThresholds(!showThresholds)}
                  className="text-xs text-slate-400 hover:text-violet-300 transition-colors flex items-center gap-1"
                >
                  ⚙️ {showThresholds ? "Hide" : "Customize"} quality thresholds &amp; iterations
                </button>

                {showThresholds && (
                  <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {[
                      { label: "Min Sharpe", value: minSharpe, set: setMinSharpe, placeholder: "0.8" },
                      { label: "Max Drawdown %", value: maxDrawdown, set: setMaxDrawdown, placeholder: "-20" },
                      { label: "Min Win Rate %", value: minWinRate, set: setMinWinRate, placeholder: "45" },
                      { label: "Max Iterations", value: maxIter, set: setMaxIter, placeholder: "5" },
                    ].map(({ label, value, set, placeholder }) => (
                      <div key={label}>
                        <label className="block text-xs text-slate-400 mb-1">{label}</label>
                        <input
                          type="number"
                          value={value}
                          onChange={(e) => set(e.target.value)}
                          placeholder={placeholder}
                          className="w-full px-3 py-2 text-sm text-white bg-slate-900/70 border border-violet-500/30 rounded-lg focus:outline-none focus:border-violet-500 transition-all"
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <button
                onClick={handleOptimize}
                disabled={loading || !strategy.trim()}
                className="mt-5 w-full py-3 bg-gradient-to-r from-violet-600 to-purple-600 text-white font-semibold rounded-xl hover:from-violet-700 hover:to-purple-700 disabled:from-slate-600 disabled:to-slate-700 disabled:cursor-not-allowed transition-all shadow-lg shadow-violet-500/30"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Optimizing… iteration {liveIter}/{Math.min(parseInt(maxIter) || 5, 10)}
                  </span>
                ) : (
                  "🚀 Run Backtest Optimizer"
                )}
              </button>

              {error && (
                <div className="mt-4 bg-red-900/40 border-l-4 border-red-500 text-red-200 px-4 py-3 rounded text-sm">
                  {error}
                </div>
              )}
            </div>
          </div>

          {/* ── Results ── */}
          {result && (
            <div className="space-y-8">

              {/* Summary banner */}
              <div className={`rounded-2xl border p-5 flex items-start gap-4
                ${result.passed
                  ? "bg-emerald-900/20 border-emerald-500/40"
                  : "bg-amber-900/20 border-amber-500/40"}`}>
                <span className="text-3xl">{result.passed ? "✅" : "⚠️"}</span>
                <div>
                  <p className={`font-bold text-lg ${result.passed ? "text-emerald-300" : "text-amber-300"}`}>
                    {result.passed ? "Optimization Successful" : "Best Result After Max Iterations"}
                  </p>
                  <p className="text-slate-300 text-sm mt-1">{result.summary}</p>
                  <p className="text-slate-400 text-xs mt-1">
                    Final strategy: <span className="text-white">{result.final_strategy}</span>
                  </p>
                </div>
              </div>

              {/* Threshold pass/fail row */}
              {m && (
                <div className="flex flex-wrap gap-3">
                  <ThresholdBadge
                    label="Sharpe"
                    value={`${fmt(m.sharpe_ratio, 3)} (target ≥ ${resolvedThresholds.min_sharpe})`}
                    pass={m.sharpe_ratio >= resolvedThresholds.min_sharpe}
                  />
                  <ThresholdBadge
                    label="Max Drawdown"
                    value={`${fmt(m.max_drawdown_pct)}% (limit ${resolvedThresholds.max_drawdown_pct}%)`}
                    pass={m.max_drawdown_pct >= resolvedThresholds.max_drawdown_pct}
                  />
                  <ThresholdBadge
                    label="Win Rate"
                    value={`${fmt(m.win_rate_pct)}% (target ≥ ${resolvedThresholds.min_win_rate_pct}%)`}
                    pass={m.win_rate_pct >= resolvedThresholds.min_win_rate_pct}
                  />
                </div>
              )}

              {/* Strategy info */}
              {ps && (
                <div className="bg-slate-800/40 border border-violet-500/20 rounded-2xl p-5">
                  <h3 className="text-white font-bold text-lg mb-2">Best Strategy Found</h3>
                  <p className="text-violet-200 mb-3 text-sm">{ps.strategy_description}</p>
                  <div className="flex flex-wrap gap-3 text-sm">
                    <span className="px-3 py-1 bg-violet-900/50 border border-violet-500/30 rounded-full text-violet-200">
                      📌 {ps.ticker}
                    </span>
                    <span className="px-3 py-1 bg-violet-900/50 border border-violet-500/30 rounded-full text-violet-200">
                      {ps.start_date && ps.end_date
                        ? `📅 ${ps.start_date} → ${ps.end_date}`
                        : ps.timeframe && ps.timeframe !== "1d"
                        ? `⏱️ ${ps.timeframe} (${ps.period_days} days)`
                        : ps.period_years
                        ? `📅 ${ps.period_years} year${ps.period_years !== 1 ? "s" : ""}`
                        : `📅 ${ps.period_days ?? ps.period_years ?? "—"} days`}
                    </span>
                    <span className="px-3 py-1 bg-violet-900/50 border border-violet-500/30 rounded-full text-violet-200">
                      💰 {ps.initial_capital.toLocaleString()} capital
                    </span>
                    <span className="px-3 py-1 bg-violet-900/50 border border-violet-500/30 rounded-full text-violet-200">
                      🔁 {result.iterations} iteration{result.iterations !== 1 ? "s" : ""}
                    </span>
                  </div>
                </div>
              )}

              {/* Metrics grid */}
              {m && (
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                  <MetricCard label="Total Return"    value={pct(m.total_return_pct)}       positive={m.total_return_pct >= 0} />
                  <MetricCard label="Sharpe Ratio"    value={fmt(m.sharpe_ratio, 3)}         positive={m.sharpe_ratio >= 1} />
                  <MetricCard label="Max Drawdown"    value={`${fmt(m.max_drawdown_pct)}%`}  positive={m.max_drawdown_pct >= -15} />
                  <MetricCard label="Win Rate"        value={`${fmt(m.win_rate_pct)}%`}      positive={m.win_rate_pct >= 50} />
                  <MetricCard label="Profit Factor"   value={m.profit_factor != null ? fmt(m.profit_factor, 3) : "—"} positive={m.profit_factor != null ? m.profit_factor >= 1.5 : undefined} />
                  <MetricCard label="Total Trades"    value={String(m.total_trades)} />
                </div>
              )}

              {/* Secondary metrics */}
              {m && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <MetricCard label="B&H Return"      value={pct(m.buy_hold_return_pct)}     positive={m.total_return_pct >= m.buy_hold_return_pct} />
                  <MetricCard label="Ann. Return"     value={pct(m.annualized_return_pct)}   positive={m.annualized_return_pct >= 0} />
                  <MetricCard label="Sortino"         value={m.sortino_ratio != null ? fmt(m.sortino_ratio, 3) : "—"} />
                  <MetricCard label="Expectancy"      value={m.expectancy != null ? `$${fmt(m.expectancy)}` : "—"} positive={m.expectancy != null ? m.expectancy >= 0 : undefined} />
                </div>
              )}

              {/* Tabs */}
              {cd && (
                <div>
                  <div className="flex gap-2 mb-4">
                    {(["chart", "trades", "log"] as const).map((tab) => (
                      <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-all
                          ${activeTab === tab
                            ? "bg-violet-600 text-white"
                            : "bg-slate-800/60 text-slate-400 hover:text-white border border-slate-600/40"}`}
                      >
                        {tab === "chart" ? "📈 Charts" : tab === "trades" ? "📋 Trades" : "🔁 Iterations"}
                      </button>
                    ))}
                  </div>

                  {/* Charts tab */}
                  {activeTab === "chart" && (
                    <div className="space-y-6">
                      {/* Portfolio vs Price */}
                      <div className="bg-slate-800/40 border border-violet-500/20 rounded-2xl p-5">
                        <h3 className="text-white font-semibold mb-4">Portfolio Value vs Price</h3>
                        <ResponsiveContainer width="100%" height={300}>
                          <LineChart data={cd.price_series}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                            <XAxis dataKey="date" tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} interval="preserveStartEnd" />
                            <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                            <Tooltip content={<ChartTooltip />} />
                            <Legend wrapperStyle={{ color: "#94a3b8", fontSize: 12 }} />
                            <Line type="monotone" dataKey="portfolio" name="Portfolio" stroke="#a78bfa" strokeWidth={2} dot={false} />
                            <Line type="monotone" dataKey="close" name="Price" stroke="#38bdf8" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>

                      {/* Drawdown */}
                      <div className="bg-slate-800/40 border border-violet-500/20 rounded-2xl p-5">
                        <h3 className="text-white font-semibold mb-4">Drawdown</h3>
                        <ResponsiveContainer width="100%" height={180}>
                          <AreaChart data={cd.drawdown_series}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                            <XAxis dataKey="date" tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} interval="preserveStartEnd" />
                            <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} tickFormatter={(v) => `${v.toFixed(0)}%`} />
                            <Tooltip content={<ChartTooltip />} />
                            <Area type="monotone" dataKey="drawdown" name="Drawdown %" stroke="#f87171" fill="#f87171" fillOpacity={0.2} strokeWidth={1.5} />
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  )}

                  {/* Trades tab */}
                  {activeTab === "trades" && (
                    <div className="bg-slate-800/40 border border-violet-500/20 rounded-2xl p-5">
                      <div className="flex items-center justify-between mb-4">
                        <h3 className="text-white font-semibold">Trade Log ({cd.trades.length} trades)</h3>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs text-left">
                          <thead>
                            <tr className="text-violet-300 border-b border-slate-700">
                              <th className="pb-2 pr-4">#</th>
                              <th className="pb-2 pr-4">Date</th>
                              <th className="pb-2 pr-4">Type</th>
                              <th className="pb-2 pr-4">Price</th>
                              <th className="pb-2 pr-4">Shares</th>
                              <th className="pb-2 pr-4">P&amp;L</th>
                              <th className="pb-2 pr-4">P&amp;L %</th>
                              <th className="pb-2">Days</th>
                            </tr>
                          </thead>
                          <tbody>
                            {cd.trades.slice(0, 100).map((t, i) => (
                              <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-700/20">
                                <td className="py-1.5 pr-4 text-slate-500">{i + 1}</td>
                                <td className="py-1.5 pr-4 text-slate-300">{t.date}</td>
                                <td className={`py-1.5 pr-4 font-semibold ${t.type === "BUY" || t.type === "SHORT" ? "text-emerald-400" : "text-red-400"}`}>{t.type}</td>
                                <td className="py-1.5 pr-4 text-white">{fmt(t.price)}</td>
                                <td className="py-1.5 pr-4 text-slate-300">{t.shares}</td>
                                <td className={`py-1.5 pr-4 ${(t.pnl ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}>{t.pnl != null ? `$${fmt(t.pnl)}` : "—"}</td>
                                <td className={`py-1.5 pr-4 ${(t.pnl_pct ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}>{t.pnl_pct != null ? pct(t.pnl_pct) : "—"}</td>
                                <td className="py-1.5 text-slate-400">{t.days_held ?? "—"}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {cd.trades.length > 100 && (
                          <p className="text-slate-500 text-xs mt-2">Showing first 100 of {cd.trades.length} trades.</p>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Iterations log tab */}
                  {activeTab === "log" && (
                    <div className="space-y-3">
                      <p className="text-slate-400 text-sm">
                        {result.iterations_log.length} iteration{result.iterations_log.length !== 1 ? "s" : ""} run.
                        The optimizer refined the strategy each time thresholds were not met.
                      </p>
                      {(() => {
                        // Find the single iteration with the highest composite score
                        // score = sharpe - |drawdown|/10 + win_rate/100
                        const compositeScore = (m?: Metrics) =>
                          m ? (m.sharpe_ratio ?? 0) - Math.abs(m.max_drawdown_pct ?? 100) / 10 + (m.win_rate_pct ?? 0) / 100 : -Infinity;
                        const bestIdx = result.iterations_log.reduce(
                          (best, log, i) =>
                            compositeScore(log.metrics) > compositeScore(result.iterations_log[best]?.metrics)
                              ? i
                              : best,
                          0
                        );
                        return result.iterations_log.map((log, i) => (
                          <IterationCard key={i} log={log} index={i} isFinalBest={i === bestIdx} />
                        ));
                      })()}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </main>

        {/* ── SEO Content: Features + FAQ ── */}
        <section className="bg-slate-900/60 border-t border-cyan-500/10 py-16">
          <div className="max-w-6xl mx-auto px-6">

            {/* What is a Backtest Optimizer */}
            <div className="text-center mb-12">
              <h2 className="text-3xl font-bold text-white mb-3">
                What is an AI Backtest Optimizer?
              </h2>
              <p className="text-cyan-200 max-w-2xl mx-auto">
                A backtest optimizer goes beyond a single backtest run. It automatically evaluates your strategy against quality targets — Sharpe ratio, drawdown, win rate — and keeps refining it until it passes or the iteration limit is reached. No manual parameter tuning needed.
              </p>
            </div>

            {/* Feature cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-14">
              <div className="bg-slate-800/50 border border-violet-500/20 rounded-2xl p-6 hover:border-violet-500/40 transition-all">
                <div className="text-3xl mb-3">🔁</div>
                <h3 className="text-white font-bold text-lg mb-2">Autonomous Loop</h3>
                <p className="text-slate-300 text-sm leading-relaxed">
                  Powered by LangGraph. The optimizer runs backtest → evaluate → refine in a loop — up to 10 iterations — without any manual intervention from you.
                </p>
              </div>
              <div className="bg-slate-800/50 border border-blue-500/20 rounded-2xl p-6 hover:border-blue-500/40 transition-all">
                <div className="text-3xl mb-3">🎯</div>
                <h3 className="text-white font-bold text-lg mb-2">Quality Thresholds</h3>
                <p className="text-slate-300 text-sm leading-relaxed">
                  Set your own Sharpe ratio, max drawdown, and win rate targets. The optimizer won't stop until all three are met — or it has exhausted all iterations.
                </p>
              </div>
              <div className="bg-slate-800/50 border border-purple-500/20 rounded-2xl p-6 hover:border-purple-500/40 transition-all">
                <div className="text-3xl mb-3">📋</div>
                <h3 className="text-white font-bold text-lg mb-2">Full Audit Trail</h3>
                <p className="text-slate-300 text-sm leading-relaxed">
                  Every iteration is logged — strategy text, Sharpe, drawdown, win rate. You see exactly what was tried and how each refinement improved the metrics.
                </p>
              </div>
              <div className="bg-slate-800/50 border border-emerald-500/20 rounded-2xl p-6 hover:border-emerald-500/40 transition-all">
                <div className="text-3xl mb-3">⭐</div>
                <h3 className="text-white font-bold text-lg mb-2">Best Result Always Returned</h3>
                <p className="text-slate-300 text-sm leading-relaxed">
                  Even if thresholds are never fully met, the optimizer returns the single best strategy found — ranked by a composite score of Sharpe, drawdown, and win rate.
                </p>
              </div>
            </div>

            {/* How it works step-by-step */}
            <div className="bg-slate-800/30 border border-violet-500/15 rounded-2xl p-8 mb-14">
              <h2 className="text-2xl font-bold text-white mb-6 text-center">How the Backtest Optimizer Works</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                {[
                  { step: "1", icon: "💬", title: "Describe Your Strategy", desc: "Type any strategy in plain English — SMA crossover, RSI mean reversion, MACD, or custom multi-indicator logic." },
                  { step: "2", icon: "🔬", title: "AI Runs Backtest", desc: "The AI parses your strategy, generates signal code, and runs a full vectorbt backtest on real historical data." },
                  { step: "3", icon: "📊", title: "Evaluate vs Thresholds", desc: "Sharpe ratio, max drawdown, and win rate are checked against your targets. If all pass, the loop ends." },
                  { step: "4", icon: "🔧", title: "Refine & Repeat", desc: "If any threshold fails, the AI refines the strategy — adjusting periods, adding filters or stop-losses — and re-runs." },
                ].map((s) => (
                  <div key={s.step} className="flex flex-col items-center text-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-violet-600 flex items-center justify-center text-white font-bold text-lg">{s.step}</div>
                    <div className="text-3xl">{s.icon}</div>
                    <p className="text-white font-semibold text-sm">{s.title}</p>
                    <p className="text-slate-400 text-xs leading-relaxed">{s.desc}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* What the optimizer can refine */}
            <div className="bg-slate-800/30 border border-cyan-500/15 rounded-2xl p-8 mb-14">
              <h2 className="text-2xl font-bold text-white mb-6 text-center">What the Optimizer Refines</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {[
                  { icon: "📐", name: "Indicator Periods", desc: "Adjusts SMA/EMA/RSI/MACD periods to reduce noise and improve signal quality." },
                  { icon: "🔍", name: "Entry Filters", desc: "Adds RSI, volume, or trend filters to the entry condition to improve win rate." },
                  { icon: "🛡️", name: "Stop-Loss Rules", desc: "Introduces percentage or points-based stop-losses to control max drawdown." },
                  { icon: "🎯", name: "Take-Profit Targets", desc: "Adds profit targets to lock in gains and improve the profit factor." },
                  { icon: "⏱️", name: "Timeframe Tuning", desc: "Suggests slower timeframes when intraday noise is hurting performance." },
                  { icon: "📊", name: "Position Sizing", desc: "Recommends risk-based or Kelly Criterion sizing to improve Sharpe ratio." },
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
              <h2 className="text-2xl font-bold text-white mb-6 text-center">Backtest Optimizer FAQ</h2>
              <div className="space-y-4">
                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                  <h3 className="text-white font-semibold mb-2">What is a backtest optimizer?</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    A backtest optimizer automatically runs multiple backtest iterations on variations of your strategy, evaluating each against quality thresholds like Sharpe ratio, max drawdown, and win rate. It keeps refining until the strategy passes all targets or the iteration limit is reached — saving you hours of manual parameter tuning.
                  </p>
                </div>
                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                  <h3 className="text-white font-semibold mb-2">How is this different from the AI Backtester?</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    The AI Backtester runs your strategy once and returns the result. The Backtest Optimizer runs it multiple times, automatically refining the strategy between iterations until it meets your quality targets. Use the Backtester to test a specific strategy; use the Optimizer when you want the AI to find the best version of a strategy concept.
                  </p>
                </div>
                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                  <h3 className="text-white font-semibold mb-2">Will the optimizer switch to a completely different strategy?</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    No. The optimizer refines your original strategy concept — adjusting periods, adding filters, or introducing stop-loss rules. It keeps the same ticker and capital. If you describe an SMA crossover, it will try variations of SMA crossovers, not switch to Camarilla pivots or a completely unrelated approach.
                  </p>
                </div>
                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                  <h3 className="text-white font-semibold mb-2">What if the strategy never meets all thresholds?</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    The optimizer always returns the best result found — even if no iteration fully passed. The iteration log shows every variation tried and its metrics, so you can see which threshold was hardest to meet. This is a signal that the strategy concept may not suit the asset or timeframe, and a different approach should be considered.
                  </p>
                </div>
                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                  <h3 className="text-white font-semibold mb-2">Can I customize the quality thresholds?</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    Yes. Click "Customize quality thresholds" before running to set your own Sharpe ratio minimum, max drawdown limit, win rate target, and maximum number of iterations (up to 10). The defaults are Sharpe ≥ 0.8, drawdown ≤ -20%, win rate ≥ 45%.
                  </p>
                </div>
                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                  <h3 className="text-white font-semibold mb-2">Is the Backtest Optimizer free?</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    Yes. MokshaGPT's AI Backtest Optimizer is completely free to use for educational and informational purposes. No sign-up, no credit card required.
                  </p>
                </div>
              </div>
            </div>

          </div>
        </section>

        <RelatedTools current="/backtest-optimizer" />

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
