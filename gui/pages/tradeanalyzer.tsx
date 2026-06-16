import { useState, useRef, useCallback } from "react";
import Head from "next/head";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import Header from "../components/Header";
import RelatedTools from "../components/RelatedTools";

// ── Types ─────────────────────────────────────────────────────────────────────

interface MonthlyStat {
  month_label: string;
  year: number;
  month: number;
  total_pnl: number;
  trade_count: number;
  win_count: number;
  loss_count: number;
  win_rate: number;
  gross_profit: number;
  gross_loss: number;
  fees_paid: number;
  best_trade_pnl: number;
  worst_trade_pnl: number;
  avg_trade_pnl: number;
}

interface OvertradingFlag {
  month_label: string;
  trade_count: number;
  win_rate: number;
  total_pnl: number;
  reasons: string[];
}

interface ConsistencyScore {
  overall: number | null;
  win_rate_score: number | null;
  pnl_stability: number | null;
  sizing_consistency: number | null;
  improvement_trend: number | null;
  interpretation: string;
}

interface SymbolStat {
  symbol: string;
  total_pnl: number;
  trade_count: number;
  win_rate: number;
  best_trade: number;
  worst_trade: number;
}

interface HoldingAnalysis {
  avg_days_held_overall?: number;
  avg_days_winners?: number;
  avg_days_losers?: number;
  holding_ratio?: number;
  insight?: string;
}

interface DowStat {
  day: string;
  dow: number;
  trade_count: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl: number;
}

interface FeeDrag {
  total_fees: number;
  gross_profit: number;
  fee_pct_of_gross: number;
  fee_pct_of_net_pnl: number;
  insight: string;
}

interface Summary {
  broker: string;
  currency: string;
  date_range_start: string;
  date_range_end: string;
  total_trades: number;
  unique_symbols: number;
  total_pnl: number;
  gross_profit: number;
  gross_loss: number;
  win_rate: number;
  win_count: number;
  loss_count: number;
  profit_factor: number | null;
  avg_win: number;
  avg_loss: number;
  best_trade_pnl: number;
  worst_trade_pnl: number;
  total_fees: number;
  months_active: number;
}

interface ReviewResult {
  detected_broker: string;
  broker_display: string;
  trader_name: string;
  review_period: string;
  summary: Summary;
  monthly_breakdown: MonthlyStat[];
  overtrading_flags: OvertradingFlag[];
  consistency_score: ConsistencyScore;
  symbol_breakdown: SymbolStat[];
  holding_analysis: HoldingAnalysis;
  dow_pattern: DowStat[];
  fee_drag: FeeDrag;
  narrative: string;
  total_rows_parsed: number;
  closed_trades: number;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const fmt = (n: number, d = 2) =>
  n?.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });

const pct = (n: number) => `${n >= 0 ? "+" : ""}${fmt(n)}%`;

function currencySymbol(currency: string) {
  if (currency === "INR") return "₹";
  if (currency === "GBP") return "£";
  if (currency === "EUR") return "€";
  return "$";
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({
  label, value, positive, sub,
}: { label: string; value: string; positive?: boolean; sub?: string }) {
  const color =
    positive === undefined ? "text-white" :
    positive ? "text-emerald-400" : "text-red-400";
  return (
    <div className="bg-slate-800/60 border border-cyan-500/20 rounded-xl p-4">
      <p className="text-xs text-cyan-300 uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-xl font-bold ${color}`}>{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  );
}

function ScoreBar({ label, value }: { label: string; value: number | null }) {
  if (value === null) return null;
  const color =
    value >= 7 ? "bg-emerald-500" :
    value >= 5 ? "bg-cyan-500" :
    value >= 3 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-slate-300">{label}</span>
        <span className="text-white font-semibold">{value}/10</span>
      </div>
      <div className="w-full bg-slate-700 rounded-full h-2">
        <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${value * 10}%` }} />
      </div>
    </div>
  );
}
// ── Main Page ─────────────────────────────────────────────────────────────────

export default function TradeAnalyzerPage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const [file, setFile] = useState<File | null>(null);
  const [traderName, setTraderName] = useState("");
  const [reviewPeriod, setReviewPeriod] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => { e.preventDefault(); setDragOver(true); }, []);
  const handleDragLeave = useCallback(() => setDragOver(false), []);
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) setFile(f);
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) setFile(f);
  };

  const handleAnalyze = async () => {
    if (!file) { setError("Please upload your trade history file."); return; }
    setLoading(true); setError(""); setResult(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("trader_name", traderName || "Trader");
    formData.append("review_period", reviewPeriod);

    try {
      const res = await fetch(`${apiUrl}/tradeanalyzer/analyze`, { method: "POST", body: formData });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `Server error ${res.status}` }));
        throw new Error(err.detail || "Analysis failed");
      }
      const data: ReviewResult = await res.json();
      setResult(data);
    } catch (e: any) {
      setError(e.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const fileExt = file?.name.split(".").pop()?.toLowerCase() ?? "";
  const fileValid = ["xlsx", "xls", "xlsm", "csv"].includes(fileExt);
  const curr = result ? currencySymbol(result.summary.currency) : "";

  return (
    <>
      <Head>
        <title>MokshaGPT – Trade History Analyzer | Analyze My Trades & Trading Performance</title>
        <meta name="description" content="Upload your brokerage trade history and get an instant AI-powered trading performance analysis — P&L breakdown, overtrading detection, consistency score, and plain-English coaching. Works with Zerodha, Groww, Robinhood, and any broker CSV." />
        <meta name="keywords" content="trade history analyzer, trading performance analyzer, analyze my trades, brokerage account analysis, trading journal analyzer, zerodha trade history analysis, overtrading detector, trading p&l analysis, analyze zerodha trades, trading consistency score, retail trader analysis, trade review tool" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="robots" content="index, follow" />
        <link rel="canonical" href="https://mokshagpt.com/tradeanalyzer" />

        {/* Open Graph */}
        <meta property="og:type" content="website" />
        <meta property="og:url" content="https://mokshagpt.com/tradeanalyzer" />
        <meta property="og:title" content="MokshaGPT – Trade History Analyzer | Analyze My Trades Free" />
        <meta property="og:description" content="The smartest trade history analyzer for retail traders. Upload your brokerage CSV and get P&L analysis, overtrading detection, consistency score, and AI coaching — free, no sign-up." />
        <meta property="og:image" content="https://mokshagpt.com/og-tradeanalyzer.jpg" />

        {/* Twitter */}
        <meta property="twitter:card" content="summary_large_image" />
        <meta property="twitter:url" content="https://mokshagpt.com/tradeanalyzer" />
        <meta property="twitter:title" content="MokshaGPT – Trade History Analyzer | Trading Performance Analyzer" />
        <meta property="twitter:description" content="Analyze your trades with AI. Upload any broker CSV — Zerodha, Groww, Robinhood — and get instant P&L analysis, overtrading detection, and coaching. Free." />
        <meta property="twitter:image" content="https://mokshagpt.com/twitter-tradeanalyzer.jpg" />

        {/* Structured Data – SoftwareApplication */}
        <script type="application/ld+json">
          {JSON.stringify({
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": "MokshaGPT Trade History Analyzer",
            "applicationCategory": "FinanceApplication",
            "description": "AI-powered trade history analyzer that computes FIFO P&L, detects overtrading, scores trading consistency, and generates plain-English coaching for retail traders.",
            "url": "https://mokshagpt.com/tradeanalyzer",
            "offers": {
              "@type": "Offer",
              "price": "0",
              "priceCurrency": "USD"
            },
            "featureList": [
              "Trade history analyzer",
              "Trading performance analyzer",
              "Analyze my trades",
              "FIFO P&L calculation",
              "Overtrading detector",
              "Trading consistency score",
              "Monthly P&L breakdown",
              "Symbol-by-symbol analysis",
              "Holding period analysis",
              "Day-of-week win rate pattern",
              "Works with any broker CSV",
              "Zerodha, Groww, Robinhood, IBKR support"
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
                "name": "What is a trade history analyzer?",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "A trade history analyzer processes your brokerage trade export CSV and computes realized P&L for every closed trade using FIFO matching, then generates a full performance report including win rate, profit factor, monthly breakdown, and overtrading detection. MokshaGPT's trade history analyzer works with any broker."
                }
              },
              {
                "@type": "Question",
                "name": "How do I analyze my trades from Zerodha or Groww?",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "Export your trade history from Zerodha Console (Reports → Tradebook → Download CSV) or Groww (Profile → Reports → Trade History → Export), then upload the CSV to MokshaGPT's trade history analyzer. The broker is auto-detected and you get an instant trading performance analysis."
                }
              },
              {
                "@type": "Question",
                "name": "What is overtrading and how is it detected?",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "Overtrading means placing too many trades, often driven by emotion after losses. MokshaGPT detects it using three signals: a volume spike (trade count more than 1.5× your rolling average), revenge trading (extra trades placed on the same day as a loss), and win-rate collapse (win rate below 40% in a high-volume month)."
                }
              },
              {
                "@type": "Question",
                "name": "What is a trading consistency score?",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "The trading consistency score (0–10) measures how repeatable and disciplined your trading is. It combines four sub-scores: win rate, P&L stability month-to-month, position sizing consistency, and improvement trend over time. A score above 7 indicates excellent consistency."
                }
              },
              {
                "@type": "Question",
                "name": "Does this work with any broker?",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "Yes. MokshaGPT's trade history analyzer works with any broker CSV. Known brokers (Zerodha, Groww, Angel One, Robinhood, IBKR, Fidelity) are auto-detected. For other brokers, the system auto-detects columns by keyword — any CSV with date, symbol, side (buy/sell), quantity, and price columns will work."
                }
              }
            ]
          })}
        </script>
      </Head>

      <div className="min-h-screen bg-gradient-to-br from-indigo-950 via-slate-900 to-gray-900">
        <Header />

        <main className="max-w-6xl mx-auto px-6 py-12">
          {/* Hero */}
          <div className="text-center mb-10">
            <div className="inline-flex items-center gap-2 px-3 py-1 bg-cyan-900/40 border border-cyan-500/30 rounded-full text-cyan-300 text-xs mb-4">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
              Free Trade History Analyzer — No Sign-up Required
            </div>
            <h1 className="text-4xl font-extrabold text-white mb-4 leading-tight">
              <span className="bg-gradient-to-r from-cyan-400 via-blue-400 to-cyan-400 bg-clip-text text-transparent">
                Trade History Analyzer
              </span>
            </h1>
            <p className="text-cyan-100 max-w-2xl mx-auto mb-2">
              The smartest way to <span className="text-white font-semibold">analyze your trades</span>. Upload your brokerage trade history and get an instant <span className="text-white font-semibold">trading performance analysis</span> — P&L breakdown, overtrading detection, consistency score, and plain-English coaching.
            </p>
            <p className="text-cyan-200 max-w-xl mx-auto text-sm mb-3">
              Works with <span className="text-white font-semibold">any broker</span> — known brokers are auto-detected, and any CSV with date, symbol, side, quantity, and price columns is supported.
            </p>
            <div className="mt-3 flex flex-wrap justify-center gap-2 text-xs text-slate-400">
              {["Zerodha", "Groww", "Angel One", "Robinhood", "IBKR", "Fidelity", "Upstox", "5paisa", "Dhan", "Any Broker CSV"].map((b) => (
                <span key={b} className={`px-2 py-1 rounded-full border ${b === "Any Broker CSV" ? "bg-cyan-900/40 border-cyan-500/30 text-cyan-300" : "bg-slate-800/60 border-slate-600/30"}`}>{b}</span>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
            {/* ── Left: Upload Panel ── */}
            <div className="lg:col-span-2 space-y-5">
              {/* Disclaimer */}
              <div className="bg-amber-950/30 border border-amber-500/30 rounded-xl px-5 py-4 flex gap-3 text-xs text-amber-200/80">
                <span className="text-amber-400 text-base shrink-0 mt-0.5">⚠️</span>
                <span>
                  <span className="font-semibold text-amber-300">Research tool only — not financial advice. </span>
                  Trade analysis is for educational and informational purposes only. Results are based on your uploaded data and do not constitute investment advice. Always consult a licensed financial advisor before making trading decisions.
                </span>
              </div>
              <div className="bg-slate-800/60 backdrop-blur-xl rounded-2xl border border-cyan-500/30 p-5">
                <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                  <span className="text-cyan-400">📂</span> Upload Trade History
                </h3>
                <div
                  onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${
                    dragOver ? "border-cyan-400 bg-cyan-900/20" :
                    file && fileValid ? "border-emerald-500/50 bg-emerald-900/10" :
                    file && !fileValid ? "border-red-500/50 bg-red-900/10" :
                    "border-slate-600/50 hover:border-cyan-500/50 hover:bg-slate-700/20"
                  }`}
                >
                  <input ref={fileInputRef} type="file" accept=".xlsx,.xls,.xlsm,.csv" onChange={handleFileChange} className="hidden" />
                  {file ? (
                    <div>
                      <p className={`font-medium text-sm ${fileValid ? "text-emerald-300" : "text-red-300"}`}>
                        {fileValid ? "✓" : "✗"} {file.name}
                      </p>
                      <p className="text-slate-400 text-xs mt-1">{(file.size / 1024).toFixed(1)} KB{!fileValid && " — unsupported format"}</p>
                      <button onClick={(e) => { e.stopPropagation(); setFile(null); }} className="mt-2 text-xs text-slate-400 hover:text-red-400 transition-colors">Remove</button>
                    </div>
                  ) : (
                    <div>
                      <p className="text-slate-300 text-sm">Drop your trade history CSV here</p>
                      <p className="text-slate-500 text-xs mt-1">Any broker · .csv, .xlsx, .xls · max 10 MB</p>
                    </div>
                  )}
                </div>

                <div className="mt-4 space-y-3">
                  <div>
                    <label className="block text-cyan-300 text-xs font-medium mb-1.5 uppercase tracking-wider">Your Name <span className="text-slate-500 normal-case">(optional)</span></label>
                    <input type="text" placeholder="e.g. Rahul Sharma" value={traderName} onChange={(e) => setTraderName(e.target.value)}
                      className="w-full px-3 py-2 text-white bg-slate-900/70 border border-slate-600/40 rounded-lg focus:outline-none focus:border-cyan-500 text-sm placeholder:text-slate-500 transition-colors" />
                  </div>
                  <div>
                    <label className="block text-cyan-300 text-xs font-medium mb-1.5 uppercase tracking-wider">Review Period <span className="text-slate-500 normal-case">(optional — auto-detected)</span></label>
                    <input type="text" placeholder="e.g. Jan–Mar 2026" value={reviewPeriod} onChange={(e) => setReviewPeriod(e.target.value)}
                      className="w-full px-3 py-2 text-white bg-slate-900/70 border border-slate-600/40 rounded-lg focus:outline-none focus:border-cyan-500 text-sm placeholder:text-slate-500 transition-colors" />
                  </div>
                </div>

                <button onClick={handleAnalyze} disabled={loading || !file || !fileValid}
                  className="mt-4 w-full py-3 bg-gradient-to-r from-cyan-600 to-blue-600 text-white font-semibold rounded-xl hover:from-cyan-700 hover:to-blue-700 disabled:from-slate-600 disabled:to-slate-700 disabled:cursor-not-allowed transition-all shadow-lg shadow-cyan-500/20">
                  {loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Analyzing your trades…
                    </span>
                  ) : "Analyze My Trades"}
                </button>

                {error && <div className="mt-4 bg-red-900/40 border-l-4 border-red-500 text-red-200 px-4 py-3 rounded text-sm">{error}</div>}
              </div>

              {/* How it works */}
              <div className="bg-slate-800/40 border border-slate-600/20 rounded-2xl p-5">
                <h3 className="text-slate-300 font-semibold mb-3 text-sm">How it works</h3>
                <ol className="space-y-2 text-xs text-slate-400">
                  {[
                    "Export your trade history from your broker as CSV",
                    "Upload it here — broker is auto-detected",
                    "FIFO P&L is computed for every closed trade",
                    "Overtrading, consistency, and patterns are analysed",
                    "AI writes a plain-English coaching summary",
                  ].map((step, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="w-5 h-5 rounded-full bg-cyan-900/50 border border-cyan-500/30 flex items-center justify-center text-cyan-400 font-bold shrink-0 mt-0.5">{i + 1}</span>
                      {step}
                    </li>
                  ))}
                </ol>
                <div className="mt-4 pt-4 border-t border-slate-700/50">
                  <p className="text-xs text-slate-500 font-medium mb-2">How to export from your broker:</p>
                  <ul className="text-xs text-slate-500 space-y-1">
                    <li>• <span className="text-slate-400">Zerodha:</span> Console → Reports → Tradebook → Download CSV</li>
                    <li>• <span className="text-slate-400">Groww:</span> Profile → Reports → Trade History → Export</li>
                    <li>• <span className="text-slate-400">Robinhood:</span> Account → Statements → Download CSV</li>
                    <li>• <span className="text-slate-400">IBKR:</span> Reports → Activity → Trades → CSV</li>
                  </ul>
                  <div className="mt-3 p-3 bg-slate-700/30 rounded-lg border border-slate-600/30">
                    <p className="text-xs text-cyan-300 font-medium mb-1">🔧 Using a different broker?</p>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Any CSV with columns for <span className="text-slate-300">date, symbol, side (buy/sell), quantity,</span> and <span className="text-slate-300">price</span> will work — column names don&apos;t need to match exactly. The system auto-detects them.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* ── Right: Results Panel ── */}
            <div className="lg:col-span-3">
              {!result && !loading && (
                <div className="h-full flex items-center justify-center">
                  <div className="text-center text-slate-500 py-20">
                    <div className="text-6xl mb-4">📊</div>
                    <p className="text-lg font-medium text-slate-400">Your review will appear here</p>
                    <p className="text-sm mt-2">Upload your trade history CSV and click Analyze My Trades</p>
                  </div>
                </div>
              )}

              {loading && (
                <div className="h-full flex items-center justify-center">
                  <div className="text-center py-20">
                    <div className="relative w-16 h-16 mx-auto mb-6">
                      <div className="absolute inset-0 rounded-full border-4 border-cyan-500/20"></div>
                      <div className="absolute inset-0 rounded-full border-4 border-t-cyan-500 animate-spin"></div>
                    </div>
                    <p className="text-cyan-300 font-medium">Analysing your trades…</p>
                    <p className="text-slate-400 text-sm mt-2">Computing P&L, detecting patterns, writing review</p>
                  </div>
                </div>
              )}

              {result && !loading && (
                <div className="space-y-6">

                  {/* Report Header */}
                  <div className="bg-gradient-to-r from-slate-800/80 to-slate-700/60 border border-cyan-500/30 rounded-2xl p-6">
                    <div className="flex items-start justify-between gap-4 flex-wrap">
                      <div>
                        <h2 className="text-xl font-bold text-white mb-1">
                          📊 {result.trader_name}&apos;s Trade Review
                        </h2>
                        <div className="flex flex-wrap gap-3 text-xs text-slate-400 mt-2">
                          <span>📅 {result.review_period}</span>
                          <span>🏦 {result.broker_display}</span>
                          <span>💱 {result.summary.currency}</span>
                          <span>{result.summary.date_range_start} → {result.summary.date_range_end}</span>
                          <span className="text-slate-500">{result.closed_trades} closed trades analysed</span>
                        </div>
                      </div>
                      <span className="px-3 py-1 bg-cyan-900/40 border border-cyan-500/30 rounded-full text-cyan-300 text-xs">
                        {result.detected_broker === "generic"
                          ? "✓ Format auto-detected"
                          : `✓ ${result.broker_display} detected`}
                      </span>
                    </div>
                  </div>

                  {/* Summary Cards */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <StatCard label="Total P&L" value={`${curr}${fmt(Math.abs(result.summary.total_pnl))}`} positive={result.summary.total_pnl >= 0} sub={result.summary.total_pnl >= 0 ? "Profit" : "Loss"} />
                    <StatCard label="Win Rate" value={`${result.summary.win_rate}%`} positive={result.summary.win_rate >= 50} sub={`${result.summary.win_count}W / ${result.summary.loss_count}L`} />
                    <StatCard label="Profit Factor" value={result.summary.profit_factor !== null ? fmt(result.summary.profit_factor) : "N/A"} positive={result.summary.profit_factor !== null ? result.summary.profit_factor >= 1.5 : undefined} />
                    <StatCard label="Total Trades" value={String(result.summary.total_trades)} sub={`${result.summary.unique_symbols} symbols`} />
                    <StatCard label="Avg Win" value={`${curr}${fmt(result.summary.avg_win)}`} positive={true} />
                    <StatCard label="Avg Loss" value={`${curr}${fmt(Math.abs(result.summary.avg_loss))}`} positive={false} />
                    <StatCard label="Best Trade" value={`${curr}${fmt(result.summary.best_trade_pnl)}`} positive={true} />
                    <StatCard label="Worst Trade" value={`${curr}${fmt(Math.abs(result.summary.worst_trade_pnl))}`} positive={false} />
                  </div>

                  {/* Overtrading Alerts */}
                  {result.overtrading_flags.length > 0 && (
                    <div className="bg-red-950/50 border border-red-500/30 rounded-2xl p-5">
                      <h3 className="text-red-300 font-bold mb-3 flex items-center gap-2">
                        <span>⚠️</span> Overtrading Detected
                      </h3>
                      <div className="space-y-3">
                        {result.overtrading_flags.map((flag, i) => (
                          <div key={i} className="bg-red-900/20 rounded-xl p-4">
                            <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
                              <span className="text-red-200 font-semibold text-sm">{flag.month_label}</span>
                              <div className="flex gap-3 text-xs text-slate-400">
                                <span>{flag.trade_count} trades</span>
                                <span>{flag.win_rate}% win rate</span>
                                <span className={flag.total_pnl >= 0 ? "text-emerald-400" : "text-red-400"}>
                                  {curr}{fmt(Math.abs(flag.total_pnl))} {flag.total_pnl >= 0 ? "profit" : "loss"}
                                </span>
                              </div>
                            </div>
                            <ul className="space-y-1">
                              {flag.reasons.map((r, j) => (
                                <li key={j} className="text-red-200 text-xs flex items-start gap-2">
                                  <span className="text-red-400 shrink-0 mt-0.5">•</span>{r}
                                </li>
                              ))}
                            </ul>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* AI Narrative */}
                  <div className="bg-slate-800/60 border border-blue-500/30 rounded-2xl p-6">
                    <h3 className="text-blue-300 font-bold text-sm uppercase tracking-wider mb-4 flex items-center gap-2">
                      <span>🤖</span> AI Coaching Summary
                    </h3>
                    <div className="prose prose-invert prose-sm max-w-none">
                      <ReactMarkdown components={{
                        h2: ({ children }) => <h2 className="text-lg font-bold text-cyan-200 mt-5 mb-2 first:mt-0">{children}</h2>,
                        p:  ({ children }) => <p className="text-slate-200 leading-relaxed mb-3">{children}</p>,
                        ul: ({ children }) => <ul className="list-disc list-inside text-slate-300 space-y-1 mb-3">{children}</ul>,
                        li: ({ children }) => <li className="text-slate-300">{children}</li>,
                        strong: ({ children }) => <strong className="text-white font-semibold">{children}</strong>,
                      }}>
                        {result.narrative}
                      </ReactMarkdown>
                    </div>
                  </div>

                  {/* Monthly Breakdown */}
                  {result.monthly_breakdown.length > 0 && (
                    <div className="bg-slate-800/40 border border-cyan-500/20 rounded-2xl p-5">
                      <h3 className="text-white font-bold mb-4">📅 Monthly Breakdown</h3>
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="text-xs text-cyan-300 uppercase tracking-wider border-b border-slate-700/50">
                              <th className="text-left pb-2 pr-4">Month</th>
                              <th className="text-right pb-2 pr-4">P&amp;L</th>
                              <th className="text-right pb-2 pr-4">Trades</th>
                              <th className="text-right pb-2 pr-4">Win Rate</th>
                              <th className="text-right pb-2 pr-4">Best</th>
                              <th className="text-right pb-2">Worst</th>
                            </tr>
                          </thead>
                          <tbody>
                            {result.monthly_breakdown.map((m, i) => {
                              const isOT = result.overtrading_flags.some(f => f.month_label === m.month_label);
                              return (
                                <tr key={i} className={`border-b border-slate-700/30 ${isOT ? "bg-red-950/20" : ""}`}>
                                  <td className="py-2 pr-4 text-slate-300 font-medium">
                                    {m.month_label}
                                    {isOT && <span className="ml-2 text-xs text-red-400">⚠️</span>}
                                  </td>
                                  <td className={`py-2 pr-4 text-right font-semibold ${m.total_pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                                    {m.total_pnl >= 0 ? "+" : ""}{curr}{fmt(Math.abs(m.total_pnl))}
                                  </td>
                                  <td className="py-2 pr-4 text-right text-slate-300">{m.trade_count}</td>
                                  <td className={`py-2 pr-4 text-right font-medium ${m.win_rate >= 50 ? "text-emerald-400" : "text-red-400"}`}>
                                    {m.win_rate}%
                                  </td>
                                  <td className="py-2 pr-4 text-right text-emerald-400 text-xs">{curr}{fmt(m.best_trade_pnl)}</td>
                                  <td className="py-2 text-right text-red-400 text-xs">{curr}{fmt(m.worst_trade_pnl)}</td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Consistency Score */}
                  {result.consistency_score.overall !== null && (
                    <div className="bg-slate-800/40 border border-purple-500/20 rounded-2xl p-5">
                      <div className="flex items-center justify-between mb-4">
                        <h3 className="text-white font-bold">🎯 Consistency Score</h3>
                        <div className="text-right">
                          <span className={`text-3xl font-bold ${
                            result.consistency_score.overall >= 7 ? "text-emerald-400" :
                            result.consistency_score.overall >= 5 ? "text-cyan-400" :
                            result.consistency_score.overall >= 3 ? "text-yellow-400" : "text-red-400"
                          }`}>{result.consistency_score.overall}</span>
                          <span className="text-slate-400 text-lg">/10</span>
                        </div>
                      </div>
                      <p className="text-slate-300 text-sm mb-4">{result.consistency_score.interpretation}</p>
                      <div className="space-y-3">
                        <ScoreBar label="Win Rate Score" value={result.consistency_score.win_rate_score} />
                        <ScoreBar label="P&L Stability" value={result.consistency_score.pnl_stability} />
                        <ScoreBar label="Position Sizing Consistency" value={result.consistency_score.sizing_consistency} />
                        <ScoreBar label="Improvement Trend" value={result.consistency_score.improvement_trend} />
                      </div>
                    </div>
                  )}

                  {/* Symbol Breakdown */}
                  {result.symbol_breakdown.length > 0 && (
                    <div className="bg-slate-800/40 border border-cyan-500/20 rounded-2xl p-5">
                      <h3 className="text-white font-bold mb-4">📈 Symbol Breakdown</h3>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {result.symbol_breakdown.slice(0, 10).map((s, i) => (
                          <div key={i} className="bg-slate-700/30 rounded-xl p-3 flex items-center justify-between">
                            <div>
                              <p className="text-white font-semibold text-sm">{s.symbol}</p>
                              <p className="text-slate-400 text-xs">{s.trade_count} trades · {s.win_rate}% win rate</p>
                            </div>
                            <span className={`font-bold text-sm ${s.total_pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                              {s.total_pnl >= 0 ? "+" : ""}{curr}{fmt(Math.abs(s.total_pnl))}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Holding Period + Fee Drag */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {result.holding_analysis.insight && (
                      <div className="bg-slate-800/40 border border-yellow-500/20 rounded-2xl p-5">
                        <h3 className="text-white font-bold mb-3">⏱️ Holding Period</h3>
                        <div className="space-y-2 text-sm mb-3">
                          {result.holding_analysis.avg_days_winners !== undefined && (
                            <div className="flex justify-between">
                              <span className="text-slate-400">Avg days — winners</span>
                              <span className="text-emerald-400 font-medium">{result.holding_analysis.avg_days_winners}d</span>
                            </div>
                          )}
                          {result.holding_analysis.avg_days_losers !== undefined && (
                            <div className="flex justify-between">
                              <span className="text-slate-400">Avg days — losers</span>
                              <span className="text-red-400 font-medium">{result.holding_analysis.avg_days_losers}d</span>
                            </div>
                          )}
                        </div>
                        <p className="text-slate-300 text-xs leading-relaxed">{result.holding_analysis.insight}</p>
                      </div>
                    )}
                    {result.fee_drag.total_fees > 0 && (
                      <div className="bg-slate-800/40 border border-orange-500/20 rounded-2xl p-5">
                        <h3 className="text-white font-bold mb-3">💸 Fee Drag</h3>
                        <div className="space-y-2 text-sm mb-3">
                          <div className="flex justify-between">
                            <span className="text-slate-400">Total fees paid</span>
                            <span className="text-orange-400 font-medium">{curr}{fmt(result.fee_drag.total_fees)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-400">% of gross profit</span>
                            <span className="text-orange-400 font-medium">{result.fee_drag.fee_pct_of_gross}%</span>
                          </div>
                        </div>
                        <p className="text-slate-300 text-xs leading-relaxed">{result.fee_drag.insight}</p>
                      </div>
                    )}
                  </div>

                  {/* Day-of-Week Pattern */}
                  {result.dow_pattern.length > 0 && (
                    <div className="bg-slate-800/40 border border-cyan-500/20 rounded-2xl p-5">
                      <h3 className="text-white font-bold mb-4">📆 Day-of-Week Win Rate</h3>
                      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                        {result.dow_pattern.filter(d => d.dow < 5).map((d, i) => (
                          <div key={i} className="bg-slate-700/30 rounded-xl p-3 text-center">
                            <p className="text-slate-400 text-xs mb-1">{d.day.slice(0, 3)}</p>
                            <p className={`text-lg font-bold ${d.win_rate >= 50 ? "text-emerald-400" : "text-red-400"}`}>{d.win_rate}%</p>
                            <p className="text-slate-500 text-xs">{d.trade_count} trades</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Disclaimer */}
                  <div className="bg-slate-800/30 border border-slate-600/20 rounded-xl px-5 py-4 text-xs text-slate-500">
                    <span className="text-slate-400 font-semibold">Disclaimer: </span>
                    This review is generated by AI based on the trade data you provided. P&L calculations use FIFO matching and may differ from your broker&apos;s official statements. For informational and educational purposes only. Not financial advice.
                  </div>
                </div>
              )}
            </div>
          </div>
        </main>

        {/* ── SEO Content: Features + FAQ ── */}
        <section className="bg-slate-900/60 border-t border-cyan-500/10 py-16">
          <div className="max-w-6xl mx-auto px-6">

            {/* Intro */}
            <div className="text-center mb-12">
              <h2 className="text-3xl font-bold text-white mb-3">
                Analyze Your Trades — Know If You&apos;re Actually Improving
              </h2>
              <p className="text-cyan-200 max-w-2xl mx-auto">
                Most retail traders never review their own performance. MokshaGPT&apos;s trade history analyzer gives you the same data-driven feedback a professional trading coach would — for free, in seconds.
              </p>
            </div>

            {/* Feature cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-14">
              <div className="bg-slate-800/50 border border-cyan-500/20 rounded-2xl p-6 hover:border-cyan-500/40 transition-all">
                <div className="text-3xl mb-3">📊</div>
                <h3 className="text-white font-bold text-lg mb-2">Trading Performance Analyzer</h3>
                <p className="text-slate-300 text-sm leading-relaxed">
                  Get a complete trading performance analysis — total P&L, win rate, profit factor, average win vs loss, best and worst trades — computed from your actual trade history.
                </p>
              </div>
              <div className="bg-slate-800/50 border border-red-500/20 rounded-2xl p-6 hover:border-red-500/40 transition-all">
                <div className="text-3xl mb-3">⚠️</div>
                <h3 className="text-white font-bold text-lg mb-2">Overtrading Detector</h3>
                <p className="text-slate-300 text-sm leading-relaxed">
                  Automatically flags months where you traded too much — volume spikes, revenge trading after losses, and win-rate collapse. One of the most common and costly retail trader mistakes.
                </p>
              </div>
              <div className="bg-slate-800/50 border border-purple-500/20 rounded-2xl p-6 hover:border-purple-500/40 transition-all">
                <div className="text-3xl mb-3">🎯</div>
                <h3 className="text-white font-bold text-lg mb-2">Consistency Score</h3>
                <p className="text-slate-300 text-sm leading-relaxed">
                  A 0–10 trading consistency score built from win rate, P&L stability, position sizing discipline, and improvement trend. Know exactly where your edge is breaking down.
                </p>
              </div>
              <div className="bg-slate-800/50 border border-emerald-500/20 rounded-2xl p-6 hover:border-emerald-500/40 transition-all">
                <div className="text-3xl mb-3">🤖</div>
                <h3 className="text-white font-bold text-lg mb-2">AI Coaching Summary</h3>
                <p className="text-slate-300 text-sm leading-relaxed">
                  Plain-English coaching written by AI based on your actual numbers — not generic advice. Specific to your symbols, your months, your patterns.
                </p>
              </div>
            </div>

            {/* What you get */}
            <div className="bg-slate-800/30 border border-cyan-500/15 rounded-2xl p-8 mb-14">
              <h2 className="text-2xl font-bold text-white mb-6 text-center">What You Get When You Analyze Your Trades</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {[
                  { icon: "📅", name: "Monthly P&L Breakdown", desc: "See exactly which months were profitable and which weren't — with trade count, win rate, and best/worst trade per month." },
                  { icon: "📈", name: "Symbol-by-Symbol Analysis", desc: "Which stocks made you money and which cost you? Ranked by total P&L with win rate per symbol." },
                  { icon: "⏱️", name: "Holding Period Insight", desc: "Are you holding losers too long and cutting winners too early? The most common retail trader mistake, detected automatically." },
                  { icon: "📆", name: "Day-of-Week Pattern", desc: "Your win rate by day of the week — some traders consistently underperform on Mondays or Fridays without realising it." },
                  { icon: "💸", name: "Fee Drag Analysis", desc: "Total fees paid and their impact as a percentage of your gross profit. High fee drag can turn a winning strategy into a losing one." },
                  { icon: "🏦", name: "Any Broker Supported", desc: "Zerodha, Groww, Angel One, Robinhood, IBKR, Fidelity, Upstox, or any custom CSV — broker is auto-detected from column names." },
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
              <h2 className="text-2xl font-bold text-white mb-6 text-center">Trade Analyzer FAQ</h2>
              <div className="space-y-4">
                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                  <h3 className="text-white font-semibold mb-2">What is a trade history analyzer?</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    A trade history analyzer processes your brokerage trade export and computes realized P&L for every closed trade using FIFO matching. It then generates a full performance report — win rate, profit factor, monthly breakdown, overtrading flags, and consistency score — so you can see exactly how you&apos;re performing as a trader.
                  </p>
                </div>
                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                  <h3 className="text-white font-semibold mb-2">How do I analyze my Zerodha trades?</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    Go to Zerodha Console → Reports → Tradebook → Download CSV. Upload that file here. The analyzer auto-detects the Zerodha format and computes your full trading performance analysis — P&L, win rate, overtrading detection, and more.
                  </p>
                </div>
                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                  <h3 className="text-white font-semibold mb-2">What is overtrading and how is it detected?</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    Overtrading means placing too many trades — often driven by emotion after a loss. The analyzer detects it using three signals: a volume spike (trade count more than 1.5× your rolling average), revenge trading (extra trades placed on the same day as a loss), and win-rate collapse (win rate below 40% in a high-volume month).
                  </p>
                </div>
                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                  <h3 className="text-white font-semibold mb-2">How is this different from a trading journal?</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    A trading journal requires you to manually log every trade. This trade history analyzer works from your broker&apos;s existing export — no manual entry. Upload once and get instant analysis. Tools like Edgewonk or TraderSync require subscriptions; this is free.
                  </p>
                </div>
                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                  <h3 className="text-white font-semibold mb-2">Is this free to use?</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    Yes — completely free, no sign-up required. Upload your trade history CSV from any broker and get your full trading performance analysis instantly.
                  </p>
                </div>
              </div>
            </div>

          </div>
        </section>

        <RelatedTools current="/tradeanalyzer" />

        {/* Footer */}
        <footer className="mt-0 bg-slate-900/80 border-t border-cyan-500/20">
          <div className="max-w-7xl mx-auto px-6 py-12">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
              <div>
                <h3 className="text-white font-bold text-lg mb-3 flex items-center gap-2">
                  <span className="text-2xl">📊</span> About MokshaGPT
                </h3>
                <p className="text-cyan-200 text-sm leading-relaxed">
                  MokshaGPT is an AI-powered platform for retail traders — stock analysis, strategy backtesting, stock screening, and brokerage account reviews.
                </p>
                <p className="text-cyan-300 text-xs mt-3 italic">Not financial advice. For educational purposes only.</p>
              </div>
              <div>
                <h3 className="text-white font-bold text-lg mb-3">Tools</h3>
                <ul className="space-y-2 text-sm">
                  <li><Link href="/" className="text-cyan-300 hover:text-white transition-colors">🏠 AI Stock Analyzer</Link></li>
                  <li><Link href="/aibacktester" className="text-cyan-300 hover:text-white transition-colors">🔬 AI Backtester</Link></li>
                  <li><Link href="/backtest-optimizer" className="text-cyan-300 hover:text-white transition-colors">⚡ Backtest Optimizer</Link></li>
                  <li><Link href="/aiscreener" className="text-cyan-300 hover:text-white transition-colors">🔍 AI Stock Screener</Link></li>
                  <li><Link href="/aireporter" className="text-cyan-300 hover:text-white transition-colors">📋 AI Reporter</Link></li>
                  <li><Link href="/tradeanalyzer" className="text-white font-semibold">📈 Trade Analyzer</Link></li>
                </ul>
              </div>
              <div>
                <h3 className="text-white font-bold text-lg mb-3">Technology</h3>
                <ul className="space-y-2 text-sm text-cyan-200">
                  {["FIFO P&L Engine", "Broker Auto-Detection", "Overtrading Detection", "Consistency Scoring", "LLM Coaching Narrative"].map(t => (
                    <li key={t} className="flex items-start gap-2"><span className="text-cyan-400 mt-1">✓</span><span>{t}</span></li>
                  ))}
                </ul>
              </div>
            </div>
            <div className="pt-6 border-t border-cyan-500/20 flex flex-col md:flex-row justify-between items-center gap-4">
              <p className="text-cyan-300 text-sm">© 2026 MokshaGPT. All rights reserved.</p>
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
