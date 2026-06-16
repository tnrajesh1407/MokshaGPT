import { useState, useEffect } from "react";
import { useRouter } from "next/router";
import Head from "next/head";
import Link from "next/link";
import Header from "../components/Header";
import RelatedTools from "../components/RelatedTools";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer,
} from "recharts";

const fmt = (n: number, decimals = 2) =>
  n?.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

const pct = (n: number) => `${n >= 0 ? "+" : ""}${fmt(n)}%`;

function MetricCard({ label, value, sub, positive }: any) {
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

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-slate-900 border border-violet-500/30 rounded-lg p-3 text-xs shadow-xl">
      <p className="text-violet-300 mb-1 font-semibold">{label}</p>
      {payload.map((p: any) => (
        <p key={p.dataKey} style={{ color: p.color }}>
          {p.name}: {typeof p.value === "number" ? "$" + fmt(p.value) : p.value}
        </p>
      ))}
    </div>
  );
}

export default function EnsembleBuilderPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<any>(null);

  useEffect(() => {
    if (router.isReady) {
      const q = router.query.query || router.query.ticker;
      if (typeof q === "string" && q) {
        setQuery(q);
      }
    }
  }, [router.isReady, router.query]);

  const handleRun = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/ensemble-backtest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Ensemble build failed");
      }
      const data = await res.json();
      setResult(data);
    } catch (e: any) {
      setError(e.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const em = result?.ensemble_metrics;
  const cd = result?.ensemble_chart_data;

  return (
    <>
      <Head>
        <title>MokshaGPT – Multi-Strategy Ensemble Builder & Portfolio Optimizer</title>
        <meta name="description" content="Build, backtest, and optimize diversified multi-strategy trading portfolios. Combine trend following, breakout, and mean reversion strategies into a robust quant ensemble to maximize Sharpe ratio and minimize drawdown." />
        <meta name="keywords" content="ensemble backtester, multi-strategy portfolio builder, quantitative trading strategies, portfolio diversification tool, trading strategy ensemble, stock backtesting AI, MokshaGPT" />
        
        {/* Canonical Link */}
        <link rel="canonical" href="https://mokshagpt.com/ensemble-builder" />

        {/* OpenGraph Tags */}
        <meta property="og:title" content="Multi-Strategy Ensemble Builder & Portfolio Optimizer | MokshaGPT" />
        <meta property="og:description" content="Simulate, backtest, and optimize diversified algorithmic trading portfolios using advanced AI models." />
        <meta property="og:type" content="website" />
        <meta property="og:url" content="https://mokshagpt.com/ensemble-builder" />
        <meta property="og:image" content="https://mokshagpt.com/images/ensemble-og.jpg" />

        {/* Twitter Card Tags */}
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="Multi-Strategy Ensemble Builder & Portfolio Optimizer | MokshaGPT" />
        <meta name="twitter:description" content="Simulate, backtest, and optimize diversified algorithmic trading portfolios using advanced AI models." />
        <meta name="twitter:image" content="https://mokshagpt.com/images/ensemble-og.jpg" />

        {/* JSON-LD SoftwareApplication Structured Data */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "SoftwareApplication",
              "name": "MokshaGPT Multi-Strategy Ensemble Builder",
              "operatingSystem": "All",
              "applicationCategory": "FinanceApplication",
              "offers": {
                "@type": "Offer",
                "price": "0.00",
                "priceCurrency": "USD"
              },
              "description": "An advanced AI-powered quant builder for generating, backtesting, and aggregating multi-strategy portfolios."
            })
          }}
        />

        {/* JSON-LD FAQPage Structured Data */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "FAQPage",
              "mainEntity": [
                {
                  "@type": "Question",
                  "name": "What is a Multi-Strategy Ensemble in trading?",
                  "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "A multi-strategy ensemble is a trading portfolio that concurrently executes multiple independent algorithmic models (such as momentum, mean reversion, and gap breakouts) on the same asset to decrease regime-specific risk."
                  }
                },
                {
                  "@type": "Question",
                  "name": "How does AI generate these strategies?",
                  "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Our system uses a dual-engine architecture powered by advanced LLMs and LangGraph. The LLM designs mathematically rigorous, diverse parameter boundaries and codes three distinct technical rulesets."
                  }
                },
                {
                  "@type": "Question",
                  "name": "Why is the ensemble's max drawdown lower than individual strategies?",
                  "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Because different strategies thrive in different regimes, their variance-offset effect cushions the total equity value, yielding a significantly shallower drawdown profile."
                  }
                }
              ]
            })
          }}
        />
      </Head>
      <div className="min-h-screen bg-gradient-to-br from-indigo-950 via-slate-900 to-gray-900">
        <Header />
        
        <main className="max-w-7xl mx-auto px-6 py-10">
          <div className="text-center mb-10">
            <h1 className="text-4xl font-extrabold text-white mb-3">
              <span className="bg-gradient-to-r from-violet-400 via-fuchsia-400 to-violet-400 bg-clip-text text-transparent">
                Multi-Strategy Ensemble Builder
              </span>
            </h1>
            <p className="text-violet-200 max-w-2xl mx-auto mb-2 text-sm">
              Generate multiple diverse strategies for a single asset and combine them into a robust, diversified portfolio.
            </p>
          </div>

          {/* Input Area */}
          <div className="max-w-3xl mx-auto mb-8 bg-slate-800/60 backdrop-blur-xl rounded-2xl border border-violet-500/30 p-6 shadow-2xl">
            <label className="block text-violet-300 text-sm font-medium mb-2">
              Asset & Parameters
            </label>
            <textarea
              rows={2}
              placeholder="e.g., Build an ensemble for AAPL over the last 3 years with $30000"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleRun(); } }}
              className="w-full px-4 py-3 text-white bg-slate-900/70 border-2 border-violet-500/30 rounded-xl focus:outline-none focus:border-violet-500 transition-all placeholder:text-slate-400 resize-none"
            />
            <button
              onClick={handleRun}
              disabled={loading || !query.trim()}
              className="mt-4 w-full py-3 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white font-semibold rounded-xl hover:from-violet-700 hover:to-fuchsia-700 disabled:from-slate-600 disabled:to-slate-700 transition-all shadow-lg"
            >
              {loading ? "Generating Ensemble (approx 15-30s)..." : "Build Ensemble Portfolio"}
            </button>
            {error && <div className="mt-4 text-red-400 text-sm">{error}</div>}
          </div>

          {/* Results Area */}
          {result && em && cd && (
            <div className="space-y-8">
              
              {/* Ensemble Metrics */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricCard label="Ensemble Total Return" value={pct(em.total_return_pct)} positive={em.total_return_pct >= 0} />
                <MetricCard label="Ensemble Annualized" value={pct(em.annualized_return_pct)} positive={em.annualized_return_pct >= 0} />
                <MetricCard label="Ensemble Max Drawdown" value={pct(em.max_drawdown_pct)} positive={em.max_drawdown_pct >= -15} />
                <MetricCard label="Final Portfolio Value" value={`$${fmt(em.final_value)}`} sub={`Initial: $${fmt(em.initial_capital)}`} />
              </div>

              {/* Chart */}
              <div className="bg-slate-800/50 border border-violet-500/20 rounded-2xl p-6 h-96">
                <h3 className="text-white font-bold text-lg mb-4">Portfolio Equity Curves</h3>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={cd}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} />
                    <XAxis dataKey="date" stroke="#94a3b8" fontSize={12} tickMargin={10} minTickGap={30} />
                    <YAxis stroke="#94a3b8" fontSize={12} domain={['auto', 'auto']} tickFormatter={(val) => `$${(val/1000).toFixed(1)}k`} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend />
                    <Line type="monotone" name="Strategy 1" dataKey="strategy_1_portfolio" stroke="#3b82f6" strokeWidth={1} dot={false} />
                    <Line type="monotone" name="Strategy 2" dataKey="strategy_2_portfolio" stroke="#f59e0b" strokeWidth={1} dot={false} />
                    <Line type="monotone" name="Strategy 3" dataKey="strategy_3_portfolio" stroke="#10b981" strokeWidth={1} dot={false} />
                    <Line type="monotone" name="Combined Ensemble" dataKey="ensemble_portfolio" stroke="#c084fc" strokeWidth={3} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* AI Summary */}
              {result.ensemble_summary && (
                <div className="bg-slate-800/60 border border-fuchsia-500/30 rounded-2xl p-6 shadow-lg">
                  <div className="flex items-start gap-4">
                    <div className="text-3xl mt-1">🤖</div>
                    <div>
                      <h3 className="text-white font-bold text-lg mb-2">AI Ensemble Analysis</h3>
                      <p className="text-slate-300 leading-relaxed text-sm whitespace-pre-wrap">
                        {result.ensemble_summary}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Individual Strategies */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {result.results.map((res: any, idx: number) => {
                  const m = res.metrics;
                  const ps = res.parsed_strategy;
                  const colors = ["border-blue-500/40 bg-blue-950/20", "border-amber-500/40 bg-amber-950/20", "border-emerald-500/40 bg-emerald-950/20"];
                  const textColors = ["text-blue-400", "text-amber-400", "text-emerald-400"];
                  return (
                    <div key={idx} className={`border rounded-xl p-5 ${colors[idx]}`}>
                      <h4 className={`font-bold mb-2 ${textColors[idx]}`}>Strategy {idx + 1}</h4>
                      <p className="text-sm text-slate-300 mb-4 h-16 overflow-y-auto">
                        {ps.strategy_description}
                      </p>
                      <div className="space-y-2 text-xs">
                        <div className="flex justify-between">
                          <span className="text-slate-400">Total Return:</span>
                          <span className={m.total_return_pct >= 0 ? "text-emerald-400" : "text-red-400"}>
                            {pct(m.total_return_pct)}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Max Drawdown:</span>
                          <span className="text-red-400">{pct(m.max_drawdown_pct)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Win Rate:</span>
                          <span className="text-slate-200">{fmt(m.win_rate_pct)}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Total Trades:</span>
                          <span className="text-slate-200">{m.total_trades}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

            </div>
          )}

          {/* SEO Content & Educational Section */}
          <div className="mt-20 border-t border-violet-500/20 pt-16 flex flex-col gap-16">
            
            {/* How It Works Section */}
            <div className="max-w-4xl mx-auto w-full">
              <h2 className="text-3xl font-extrabold text-white mb-4 text-center">
                How Multi-Strategy Ensemble Backtesting Works
              </h2>
              <p className="text-violet-200 text-sm text-center max-w-2xl mx-auto mb-10">
                Diversification is the only free lunch in finance. Our advanced quantitative engine automates the process of strategy generation, concurrency testing, and mathematical aggregation.
              </p>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                <div className="bg-slate-800/40 border border-violet-500/20 rounded-2xl p-6 relative overflow-hidden group hover:border-violet-500/40 transition-all duration-300">
                  <div className="absolute -right-4 -bottom-4 text-8xl text-violet-500/5 select-none font-bold group-hover:scale-110 transition-transform duration-300">1</div>
                  <div className="w-12 h-12 bg-gradient-to-br from-violet-500 to-fuchsia-500 rounded-xl flex items-center justify-center text-xl mb-4 shadow-lg shadow-violet-500/20">
                    🤖
                  </div>
                  <h3 className="text-white font-bold text-lg mb-2">AI Strategy Synthesizer</h3>
                  <p className="text-slate-400 text-sm leading-relaxed">
                    Enter any ticker and target duration. The AI analyzes historical market conditions to construct exactly three uncorrelated, diverse strategy sets: Trend Following, Breakout, and Mean Reversion.
                  </p>
                </div>

                <div className="bg-slate-800/40 border border-violet-500/20 rounded-2xl p-6 relative overflow-hidden group hover:border-violet-500/40 transition-all duration-300">
                  <div className="absolute -right-4 -bottom-4 text-8xl text-violet-500/5 select-none font-bold group-hover:scale-110 transition-transform duration-300">2</div>
                  <div className="w-12 h-12 bg-gradient-to-br from-violet-500 to-fuchsia-500 rounded-xl flex items-center justify-center text-xl mb-4 shadow-lg shadow-violet-500/20">
                    ⚡
                  </div>
                  <h3 className="text-white font-bold text-lg mb-2">Concurrent Backtesting</h3>
                  <p className="text-slate-400 text-sm leading-relaxed">
                    The engine executes three individual backtests concurrently. Initial capital is mathematically divided equally across all three nodes, tracking standalone win rates, trade logs, and metrics.
                  </p>
                </div>

                <div className="bg-slate-800/40 border border-violet-500/20 rounded-2xl p-6 relative overflow-hidden group hover:border-violet-500/40 transition-all duration-300">
                  <div className="absolute -right-4 -bottom-4 text-8xl text-violet-500/5 select-none font-bold group-hover:scale-110 transition-transform duration-300">3</div>
                  <div className="w-12 h-12 bg-gradient-to-br from-violet-500 to-fuchsia-500 rounded-xl flex items-center justify-center text-xl mb-4 shadow-lg shadow-violet-500/20">
                    📊
                  </div>
                  <h3 className="text-white font-bold text-lg mb-2">Mathematical Synthesis</h3>
                  <p className="text-slate-400 text-sm leading-relaxed">
                    By merging daily price series and returns arrays, the system aggregates signal vectors to calculate a smoothed, high-performance **Combined Ensemble** curve, proving the power of diversification.
                  </p>
                </div>
              </div>
            </div>

            {/* Educational Content / Benefits */}
            <div className="max-w-4xl mx-auto w-full bg-slate-900/40 border border-violet-500/20 rounded-3xl p-8 md:p-10 relative overflow-hidden shadow-2xl">
              <div className="absolute top-0 right-0 w-80 h-80 bg-violet-500/5 rounded-full blur-3xl -z-10" />
              <div className="absolute bottom-0 left-0 w-80 h-80 bg-fuchsia-500/5 rounded-full blur-3xl -z-10" />
              
              <h2 className="text-2xl font-bold text-white mb-6">Why Professional Quants Use Strategy Ensembles</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-sm text-slate-300">
                <div className="space-y-4">
                  <div>
                    <h4 className="text-white font-semibold flex items-center gap-2 mb-1">
                      <span className="text-violet-400">🛡️</span> Max Drawdown Mitigation
                    </h4>
                    <p className="text-slate-400 leading-relaxed">
                      Single strategies often suffer from severe drawdowns in unfavorable regimes. Because different strategies thrive in different regimes (e.g. trend following in rallies, mean reversion in ranges), their combined equity curve exhibits significantly lower drawdowns.
                    </p>
                  </div>
                  <div>
                    <h4 className="text-white font-semibold flex items-center gap-2 mb-1">
                      <span className="text-violet-400">📈</span> Smoother Equity Curves
                    </h4>
                    <p className="text-slate-400 leading-relaxed">
                      An ensemble smooths out the peaks and troughs of individual trade profiles, giving you a steadier upward trajectory and reducing emotional trading impulses.
                    </p>
                  </div>
                </div>
                
                <div className="space-y-4">
                  <div>
                    <h4 className="text-white font-semibold flex items-center gap-2 mb-1">
                      <span className="text-violet-400">⚖️</span> Institutional Capital Allocation
                    </h4>
                    <p className="text-slate-400 leading-relaxed">
                      Splitting capital across non-correlated mathematical systems is a core technique used by high-frequency trading firms and multi-strat hedge funds to satisfy risk management mandates.
                    </p>
                  </div>
                  <div>
                    <h4 className="text-white font-semibold flex items-center gap-2 mb-1">
                      <span className="text-violet-400">🧠</span> Regime Adaptability
                    </h4>
                    <p className="text-slate-400 leading-relaxed">
                      Instead of manually switching strategies, the ensemble approach automatically balances your portfolio's beta, capturing alpha in bull markets while hedging losses during volatile sideways contractions.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* FAQ Section */}
            <div className="max-w-3xl mx-auto w-full mb-10">
              <h2 className="text-3xl font-extrabold text-white mb-4 text-center">Frequently Asked Questions</h2>
              <p className="text-violet-200 text-sm text-center max-w-xl mx-auto mb-8">
                Everything you need to know about multi-strategy portfolio ensembles and AI quantitative modeling.
              </p>
              
              <div className="space-y-4">
                <div className="bg-slate-800/40 border border-violet-500/20 rounded-2xl p-6 hover:border-violet-500/30 transition-all duration-300">
                  <h3 className="text-white font-bold text-base mb-2">What is a Multi-Strategy Ensemble in trading?</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    A multi-strategy ensemble is a trading portfolio that concurrently executes multiple independent algorithmic models (such as momentum, mean reversion, and gap breakouts) on the same asset. By combining the trades and returns of diverse rulesets, the overall system is less vulnerable to single-model failure.
                  </p>
                </div>
                
                <div className="bg-slate-800/40 border border-violet-500/20 rounded-2xl p-6 hover:border-violet-500/30 transition-all duration-300">
                  <h3 className="text-white font-bold text-base mb-2">How does AI generate these strategies?</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    Our system uses a dual-engine architecture powered by advanced LLMs and LangGraph. The LLM translates your asset query and analyzes the asset's historical behavior to design mathematically rigorous, diverse parameter boundaries. It then codes three distinct technical rulesets—each operating on non-overlapping mathematical concepts—to ensure low correlation.
                  </p>
                </div>

                <div className="bg-slate-800/40 border border-violet-500/20 rounded-2xl p-6 hover:border-violet-500/30 transition-all duration-300">
                  <h3 className="text-white font-bold text-base mb-2">How is initial capital distributed in the ensemble?</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    By default, the builder splits the total capital you request equally across the three generated strategies (33.3% each). During the backtesting simulation, the daily equity curves are computed independently for each branch and then mathematically summed on a date-matched timeline to represent the combined portfolio value.
                  </p>
                </div>

                <div className="bg-slate-800/40 border border-violet-500/20 rounded-2xl p-6 hover:border-violet-500/30 transition-all duration-300">
                  <h3 className="text-white font-bold text-base mb-2">Why is the ensemble's max drawdown lower than individual strategies?</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    Max drawdown is calculated as the peak-to-trough decline. When one strategy is losing capital (e.g. during a trend reversal), another strategy (e.g. an oversold mean reversion model) is often generating profitable trades. This variance-offset effect cushions the total equity value, yielding a significantly shallower drawdown profile.
                  </p>
                </div>
              </div>
            </div>

          </div>
        </main>

        <RelatedTools current="/ensemble-builder" />

        <footer className="mt-10 bg-slate-900/80 border-t border-violet-500/20">
          <div className="max-w-7xl mx-auto px-6 py-12">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
              {/* About Section */}
              <div>
                <h3 className="text-white font-bold text-lg mb-3 flex items-center gap-2">
                  <span className="text-2xl">📊</span>
                  About MokshaGPT
                </h3>
                <p className="text-violet-200 text-sm leading-relaxed">
                  MokshaGPT is an advanced AI-powered platform for stock market analysis and trading strategy backtesting. 
                  We leverage cutting-edge language models and LangGraph agents to help traders and investors make data-driven decisions.
                </p>
                <p className="text-violet-300/80 text-xs mt-3 italic">
                  Not financial advice. For educational and informational purposes only.
                </p>
              </div>

              {/* Product Tools */}
              <div>
                <h3 className="text-white font-bold text-lg mb-3">Product Tools</h3>
                <ul className="space-y-2">
                  <li>
                    <Link href="/" className="text-violet-300 hover:text-white transition-colors text-sm flex items-center gap-2">
                      <span className="text-lg">🏠</span>
                      <span>AI Stock Analysis</span>
                    </Link>
                    <p className="text-slate-400 text-xs ml-7">Get instant AI-powered stock insights</p>
                  </li>
                  <li>
                    <Link href="/aibacktester" className="text-violet-300 hover:text-white transition-colors text-sm flex items-center gap-2">
                      <span className="text-lg">🔬</span>
                      <span>AI Strategy Backtester</span>
                    </Link>
                    <p className="text-slate-400 text-xs ml-7">Test any trading strategy with AI</p>
                  </li>
                  <li>
                    <Link href="/backtest-optimizer" className="text-violet-300 hover:text-white transition-colors text-sm flex items-center gap-2">
                      <span className="text-lg">⚡</span>
                      <span>Backtest Optimizer</span>
                    </Link>
                    <p className="text-slate-400 text-xs ml-7">Auto-refine strategies to meet quality targets</p>
                  </li>
                  <li>
                    <Link href="/aiscreener" className="text-violet-300 hover:text-white transition-colors text-sm flex items-center gap-2">
                      <span className="text-lg">🔍</span>
                      <span>AI Stock Screener</span>
                    </Link>
                    <p className="text-slate-400 text-xs ml-7">Find stocks using natural language</p>
                  </li>
                  <li>
                    <Link href="/ensemble-builder" className="text-violet-300 hover:text-white transition-colors text-sm flex items-center gap-2">
                      <span className="text-lg">🚀</span>
                      <span>Ensemble Builder</span>
                    </Link>
                    <p className="text-slate-400 text-xs ml-7">Combine multiple trading strategies</p>
                  </li>
                  <li>
                    <Link href="/tradeanalyzer" className="text-violet-300 hover:text-white transition-colors text-sm flex items-center gap-2">
                      <span className="text-lg">📈</span>
                      <span>Trade Analyzer</span>
                    </Link>
                    <p className="text-slate-400 text-xs ml-7">Analyze your brokerage trade history</p>
                  </li>
                  <li>
                    <Link href="/aireporter" className="text-violet-300 hover:text-white transition-colors text-sm flex items-center gap-2">
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
                <ul className="space-y-2 text-sm text-violet-200">
                  <li className="flex items-start gap-2">
                    <span className="text-violet-400 mt-1">✓</span>
                    <span>Natural Language Processing</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-violet-400 mt-1">✓</span>
                    <span>Dynamic Code Generation</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-violet-400 mt-1">✓</span>
                    <span>Real-time Market Data</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-violet-400 mt-1">✓</span>
                    <span>Advanced Performance Metrics</span>
                  </li>
                </ul>
              </div>
            </div>

            {/* Bottom Bar */}
            <div className="pt-6 border-t border-violet-500/20 flex flex-col md:flex-row justify-between items-center gap-4">
              <p className="text-violet-300 text-sm">
                © 2026 MokshaGPT. All rights reserved.
              </p>
              <div className="flex gap-6 text-sm text-violet-300">
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
