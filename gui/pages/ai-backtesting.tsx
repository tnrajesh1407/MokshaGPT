import { useState } from "react";
import Head from "next/head";
import Link from "next/link";
import Header from "../components/Header";

// Structured Schema Markup for Search Engines (SoftwareApplication)
const schemaMarkup = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "MokshaGPT AI Backtesting & Quant Suite",
  "applicationCategory": "FinanceApplication",
  "operatingSystem": "All",
  "offers": {
    "@type": "Offer",
    "price": "0.00",
    "priceCurrency": "USD"
  },
  "description": "An institutional-grade, AI-powered quantitative backtesting and strategy optimization platform. Write strategy rules in plain English and validate instantly.",
  "featureList": [
    "Plain-English trading strategy compiler",
    "Autonomous parameter optimization loops using LangGraph",
    "Multi-strategy uncorrelated portfolio ensemble generator",
    "Vectorized backtest metrics including Sharpe Ratio, Profit Factor, and Maximum Drawdown"
  ]
};

export default function AiBacktestingLanding() {
  const [userQuery, setUserQuery] = useState("");
  const [routingRecommendation, setRoutingRecommendation] = useState<{
    toolName: string;
    path: string;
    description: string;
    badgeColor: string;
    icon: string;
  } | null>(null);

  // Dynamic AI Strategy Intent Router (UX engagement & Ads conversion booster)
  const handleQueryAnalyze = (e: React.FormEvent) => {
    e.preventDefault();
    if (!userQuery.trim()) return;

    const queryLower = userQuery.toLowerCase();
    
    if (
      queryLower.includes("optimize") ||
      queryLower.includes("refine") ||
      queryLower.includes("loop") ||
      queryLower.includes("sharpe target") ||
      queryLower.includes("target") ||
      queryLower.includes("iterative") ||
      queryLower.includes("tune")
    ) {
      setRoutingRecommendation({
        toolName: "Backtest Optimizer",
        path: `/backtest-optimizer?query=${encodeURIComponent(userQuery)}`,
        description: "Best for automatically refining strategy rules until win-rate or drawdown targets are met.",
        badgeColor: "bg-purple-900/60 border-purple-500/40 text-purple-200",
        icon: "⚡"
      });
    } else if (
      queryLower.includes("ensemble") ||
      queryLower.includes("combine") ||
      queryLower.includes("diversify") ||
      queryLower.includes("multi-strategy") ||
      queryLower.includes("three") ||
      queryLower.includes("portfolio")
    ) {
      setRoutingRecommendation({
        toolName: "Ensemble Builder",
        path: `/ensemble-builder?query=${encodeURIComponent(userQuery)}`,
        description: "Best for constructing 3 uncorrelated strategies concurrently to smooth drawdown and cushion risk.",
        badgeColor: "bg-fuchsia-900/60 border-fuchsia-500/40 text-fuchsia-200",
        icon: "🚀"
      });
    } else {
      setRoutingRecommendation({
        toolName: "AI Strategy Backtester",
        path: `/aibacktester?query=${encodeURIComponent(userQuery)}`,
        description: "Best for validating a simple trading idea instantly using historical market data.",
        badgeColor: "bg-blue-900/60 border-blue-500/40 text-blue-200",
        icon: "🔬"
      });
    }
  };

  const handlePresetClick = (preset: string) => {
    setUserQuery(preset);
    // Auto-analyze
    const queryLower = preset.toLowerCase();
    if (queryLower.includes("optimize") || queryLower.includes("refine")) {
      setRoutingRecommendation({
        toolName: "Backtest Optimizer",
        path: `/backtest-optimizer?query=${encodeURIComponent(preset)}`,
        description: "Best for automatically refining strategy rules until win-rate or drawdown targets are met.",
        badgeColor: "bg-purple-900/60 border-purple-500/40 text-purple-200",
        icon: "⚡"
      });
    } else if (queryLower.includes("ensemble") || queryLower.includes("combine")) {
      setRoutingRecommendation({
        toolName: "Ensemble Builder",
        path: `/ensemble-builder?query=${encodeURIComponent(preset)}`,
        description: "Best for constructing 3 uncorrelated strategies concurrently to smooth drawdown and cushion risk.",
        badgeColor: "bg-fuchsia-900/60 border-fuchsia-500/40 text-fuchsia-200",
        icon: "🚀"
      });
    } else {
      setRoutingRecommendation({
        toolName: "AI Strategy Backtester",
        path: `/aibacktester?query=${encodeURIComponent(preset)}`,
        description: "Best for validating a simple trading idea instantly using historical market data.",
        badgeColor: "bg-blue-900/60 border-blue-500/40 text-blue-200",
        icon: "🔬"
      });
    }
  };

  return (
    <>
      <Head>
        {/* On-Page SEO Meta Tags */}
        <title>AI Trading Backtester & Quant Strategy Optimizer | MokshaGPT</title>
        <meta
          name="description"
          content="Validate trading strategies instantly with AI. Run backtests in plain English, optimize entry parameters using autonomous LangGraph loops, or build diversified multi-strategy ensembles."
        />
        <meta
          name="keywords"
          content="ai trading backtester, ai backtesting software, backtest trading strategies, automated trading backtest, free backtesting tools, stock backtesting, quant strategy optimizer, Sharpe ratio calculator"
        />
        <link rel="canonical" href="https://mokshagpt.com/ai-backtesting" />

        {/* Open Graph Meta Tags (Social Sharing & Ads relevance) */}
        <meta property="og:title" content="AI Trading Backtester & Quant Strategy Optimizer" />
        <meta
          property="og:description"
          content="Validate trading strategies instantly with AI. Write rules in plain English, run vectorized backtests, and auto-optimize parameters in seconds."
        />
        <meta property="og:url" content="https://mokshagpt.com/ai-backtesting" />
        <meta property="og:type" content="website" />
        <meta property="og:image" content="/mokshagpt-logo.png" />

        {/* Structured Schema Markup Injection */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaMarkup) }}
        />
      </Head>

      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
        <Header />

        {/* ── HERO SECTION (Above-the-Fold Optimization) ── */}
        <header className="relative bg-gradient-to-b from-slate-900 via-slate-950 to-slate-950 pt-20 pb-16 overflow-hidden">
          {/* Decorative blur elements for premium dark mode feel */}
          <div className="absolute top-10 left-1/4 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl -z-10 animate-pulse" />
          <div className="absolute top-20 right-1/4 w-96 h-96 bg-violet-500/10 rounded-full blur-3xl -z-10 animate-pulse delay-1000" />

          <div className="max-w-6xl mx-auto px-6 text-center">
            <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold text-white tracking-tight mb-6 leading-tight">
              Validate, Optimize & Ensemble <br />
              <span className="bg-gradient-to-r from-cyan-400 via-violet-400 to-fuchsia-400 bg-clip-text text-transparent">
                Trading Strategies with AI
              </span>
            </h1>

            <p className="text-lg md:text-xl text-slate-300 max-w-3xl mx-auto mb-10 leading-relaxed">
              MokshaGPT brings institutional-grade quantitative backtesting tools to retail traders. 
              No coding. No complex indicators scripting. Formulate your ideas in plain English and let our AI do the work.
            </p>

            {/* Instant CTAs for paid ads landing */}
            <div className="flex flex-wrap justify-center gap-4 mb-16">
              <Link
                href="/aibacktester"
                className="px-8 py-4 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-700 hover:to-blue-700 text-white font-bold rounded-xl shadow-lg shadow-cyan-500/20 transform hover:-translate-y-0.5 transition-all duration-200"
                id="hero-cta-backtester"
              >
                Validate Strategy Instantly
              </Link>
              <Link
                href="/backtest-optimizer"
                className="px-8 py-4 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 text-white font-bold rounded-xl shadow-lg shadow-violet-500/20 transform hover:-translate-y-0.5 transition-all duration-200"
                id="hero-cta-optimizer"
              >
                Auto-Optimize Rules
              </Link>
              <Link
                href="/ensemble-builder"
                className="px-8 py-4 bg-gradient-to-r from-fuchsia-600 to-pink-600 hover:from-fuchsia-700 hover:to-pink-700 text-white font-bold rounded-xl shadow-lg shadow-fuchsia-500/20 transform hover:-translate-y-0.5 transition-all duration-200"
                id="hero-cta-ensemble"
              >
                Build Strategy Ensemble
              </Link>
            </div>

            {/* ── UX ENHANCEMENT: INTERACTIVE INTENT ROUTER FORM ── */}
            <div className="max-w-2xl mx-auto bg-slate-900/50 backdrop-blur-xl border border-cyan-500/20 rounded-3xl p-6 md:p-8 shadow-2xl relative">
              <div className="absolute top-0 right-0 w-24 h-24 bg-cyan-500/5 rounded-full blur-2xl" />
              <h2 className="text-xl font-bold text-white mb-2 flex items-center justify-center gap-2">
                <span className="text-2xl">🔮</span>
                Test Your Strategy Idea
              </h2>
              <p className="text-slate-400 text-sm mb-6">
                Type what you want to achieve. Our AI will analyze your query and route you to the correct tool prefilled!
              </p>

              <form onSubmit={handleQueryAnalyze} className="space-y-4">
                <div className="relative">
                  <input
                    type="text"
                    value={userQuery}
                    onChange={(e) => setUserQuery(e.target.value)}
                    placeholder="e.g., RSI crossover on TSLA for 1 year with $10000"
                    className="w-full px-5 py-4 rounded-xl bg-slate-950 border-2 border-cyan-500/30 focus:border-cyan-500 focus:outline-none text-white placeholder-slate-500 transition-all font-medium pr-12 shadow-inner"
                    id="intent-router-input"
                  />
                  <button
                    type="submit"
                    className="absolute right-2 top-2 bottom-2 px-4 bg-cyan-600 hover:bg-cyan-700 text-white rounded-lg transition-colors flex items-center justify-center text-lg"
                    id="intent-router-btn"
                  >
                    ➔
                  </button>
                </div>
                
                {/* Presets suggestions */}
                <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
                  <span className="text-xs text-slate-500">Quick templates:</span>
                  <button
                    type="button"
                    onClick={() => handlePresetClick("20/50 EMA Crossover on NVDA for 2 years")}
                    className="text-xs px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-full border border-slate-700 transition-all"
                  >
                    📈 EMA Crossover
                  </button>
                  <button
                    type="button"
                    onClick={() => handlePresetClick("Optimize RSI rule on AAPL to hit 60% win rate")}
                    className="text-xs px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-full border border-slate-700 transition-all"
                  >
                    ⚡ Auto-Optimize
                  </button>
                  <button
                    type="button"
                    onClick={() => handlePresetClick("Diversified ensemble for MSFT, gold, and treasury")}
                    className="text-xs px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-full border border-slate-700 transition-all"
                  >
                    🚀 Build Ensemble
                  </button>
                </div>
              </form>

              {/* Dynamic recommendation alert */}
              {routingRecommendation && (
                <div className={`mt-6 border rounded-2xl p-4 transition-all duration-300 ${routingRecommendation.badgeColor}`}>
                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-2xl">{routingRecommendation.icon}</span>
                    <div className="text-left">
                      <span className="text-xs font-semibold uppercase tracking-wider">Recommended Tool</span>
                      <h4 className="font-bold text-white text-base">{routingRecommendation.toolName}</h4>
                    </div>
                  </div>
                  <p className="text-slate-300 text-sm text-left mb-4">{routingRecommendation.description}</p>
                  <Link
                    href={routingRecommendation.path}
                    className="block w-full py-3 bg-white text-slate-950 font-bold rounded-xl text-center shadow-lg hover:bg-slate-200 transition-colors"
                  >
                    Go to {routingRecommendation.toolName} →
                  </Link>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* ── SECTION 2: THE THREE QUANT PILLARS (UX & ADS CONVERSION CARD DECK) ── */}
        <section className="py-20 bg-slate-950 border-t border-slate-900">
          <div className="max-w-6xl mx-auto px-6">
            <div className="text-center mb-16">
              <span className="text-xs font-semibold text-cyan-400 uppercase tracking-widest bg-cyan-950/40 border border-cyan-500/20 px-3 py-1.5 rounded-full inline-block mb-3">
                Trading Suite Ecosystem
              </span>
              <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
                Three Pillars of AI Quantitative Refinement
              </h2>
              <p className="text-slate-400 max-w-2xl mx-auto">
                MokshaGPT segments backtesting into three tailored execution layers. Find the exact fit for your strategy criteria.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              {/* Card 1: AI Strategy Backtester */}
              <div className="bg-slate-900/40 border border-blue-500/20 rounded-3xl p-8 hover:border-blue-500/50 hover:bg-slate-900/60 transition-all duration-300 flex flex-col group shadow-2xl relative">
                <div className="absolute top-0 right-0 w-24 h-24 bg-blue-500/5 rounded-full blur-2xl" />
                <div className="w-12 h-12 bg-blue-900/50 border border-blue-500/30 rounded-2xl flex items-center justify-center text-2xl shadow-lg shadow-blue-500/10 mb-6">
                  🔬
                </div>
                <h3 className="text-white font-extrabold text-xl mb-3 group-hover:text-blue-300 transition-colors">
                  AI Strategy Backtester
                </h3>
                <span className="text-xs font-bold text-blue-400 uppercase tracking-wider mb-4 block">
                  Pillar 1: Plain-English Validation
                </span>
                <p className="text-slate-300 text-sm leading-relaxed mb-6 flex-grow">
                  Describe strategy rules in natural English (e.g., indicators, stock tickers, timeline, transaction fees). 
                  Our backend translates your input, runs a vectorized mathematical simulation on historical market data, and delivers instant, readable reports.
                </p>
                <div className="pt-4 border-t border-slate-800">
                  <p className="text-xs text-slate-400 mb-4 font-mono">
                    ✓ Full trades logs & drawdown details<br />
                    ✓ Volatility, Sharpe, expectancies<br />
                    ✓ Vectorbt-backed high-speed engine
                  </p>
                  <Link
                    href="/aibacktester"
                    className="block w-full py-3 text-center bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-xl transition-colors shadow-lg shadow-blue-500/20"
                    id="pillar-cta-backtester"
                  >
                    Open Strategy Backtester
                  </Link>
                </div>
              </div>

              {/* Card 2: Autonomous Backtest Optimizer */}
              <div className="bg-slate-900/40 border border-purple-500/20 rounded-3xl p-8 hover:border-purple-500/50 hover:bg-slate-900/60 transition-all duration-300 flex flex-col group shadow-2xl relative">
                <div className="absolute top-0 right-0 w-24 h-24 bg-purple-500/5 rounded-full blur-2xl" />
                <div className="w-12 h-12 bg-purple-900/50 border border-purple-500/30 rounded-2xl flex items-center justify-center text-2xl shadow-lg shadow-purple-500/10 mb-6">
                  ⚡
                </div>
                <h3 className="text-white font-extrabold text-xl mb-3 group-hover:text-purple-300 transition-colors">
                  Backtest Optimizer
                </h3>
                <span className="text-xs font-bold text-purple-400 uppercase tracking-wider mb-4 block">
                  Pillar 2: Autonomous LangGraph Loops
                </span>
                <p className="text-slate-300 text-sm leading-relaxed mb-6 flex-grow">
                  Set target thresholds (e.g. Sharpe ratio &gt; 1.5, Win Rate &gt; 60%). 
                  An autonomous LangGraph loop will execute backtests, analyze the performance, adjust parameter rules, and run again—until your strategy objectives are fully met.
                </p>
                <div className="pt-4 border-t border-slate-800">
                  <p className="text-xs text-slate-400 mb-4 font-mono">
                    ✓ Continuous agentic execution loop<br />
                    ✓ Automatic stop-loss and trailing tuning<br />
                    ✓ Detailed parameter logs per iteration
                  </p>
                  <Link
                    href="/backtest-optimizer"
                    className="block w-full py-3 text-center bg-purple-600 hover:bg-purple-700 text-white font-semibold rounded-xl transition-colors shadow-lg shadow-purple-500/20"
                    id="pillar-cta-optimizer"
                  >
                    Open Backtest Optimizer
                  </Link>
                </div>
              </div>

              {/* Card 3: Multi-Strategy Ensemble Builder */}
              <div className="bg-slate-900/40 border border-fuchsia-500/20 rounded-3xl p-8 hover:border-fuchsia-500/50 hover:bg-slate-900/60 transition-all duration-300 flex flex-col group shadow-2xl relative">
                <div className="absolute top-0 right-0 w-24 h-24 bg-fuchsia-500/5 rounded-full blur-2xl" />
                <div className="w-12 h-12 bg-fuchsia-900/50 border border-fuchsia-500/30 rounded-2xl flex items-center justify-center text-2xl shadow-lg shadow-fuchsia-500/10 mb-6">
                  🚀
                </div>
                <h3 className="text-white font-extrabold text-xl mb-3 group-hover:text-fuchsia-300 transition-colors">
                  Ensemble Builder
                </h3>
                <span className="text-xs font-bold text-fuchsia-400 uppercase tracking-wider mb-4 block">
                  Pillar 3: Uncorrelated Diversification
                </span>
                <p className="text-slate-300 text-sm leading-relaxed mb-6 flex-grow">
                  Avoid single-strategy risk. Enter a single quant hypothesis, and the AI generates 3 distinct, uncorrelated models (Trend Following, Mean Reversion, Breakout). 
                  They run concurrently, aggregating their equity vectors to cushion max drawdowns.
                </p>
                <div className="pt-4 border-t border-slate-800">
                  <p className="text-xs text-slate-400 mb-4 font-mono">
                    ✓ 3 diverse quantitative strategies<br />
                    ✓ Mathematical daily equity summation<br />
                    ✓ Dramatically reduced portfolio drawdown
                  </p>
                  <Link
                    href="/ensemble-builder"
                    className="block w-full py-3 text-center bg-fuchsia-600 hover:bg-fuchsia-700 text-white font-semibold rounded-xl transition-colors shadow-lg shadow-fuchsia-500/20"
                    id="pillar-cta-ensemble"
                  >
                    Open Ensemble Builder
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── SECTION 3: WHY AI BACKTESTING? (COMPARISON GRID) ── */}
        <section className="py-20 bg-slate-900/30 border-t border-slate-900">
          <div className="max-w-6xl mx-auto px-6">
            <h2 className="text-3xl font-bold text-white text-center mb-16">
              Why Upgrade to AI-Powered Backtesting?
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
              <div className="p-6 bg-slate-900/50 rounded-2xl border border-slate-800">
                <span className="text-3xl mb-3 block">💨</span>
                <h4 className="text-white font-bold text-lg mb-2">Zero Coding Barrier</h4>
                <p className="text-slate-400 text-sm leading-relaxed">
                  Say goodbye to hours spent debugging complex PineScript, Python code, or MT5 strategy scripts. Formulate your logic naturally.
                </p>
              </div>

              <div className="p-6 bg-slate-900/50 rounded-2xl border border-slate-800">
                <span className="text-3xl mb-3 block">🎯</span>
                <h4 className="text-white font-bold text-lg mb-2">No Overfitting Biases</h4>
                <p className="text-slate-400 text-sm leading-relaxed">
                  Optimizing rules manually leads to curve-fitting. The Backtest Optimizer analyzes failures scientifically, preserving real-world edge.
                </p>
              </div>

              <div className="p-6 bg-slate-900/50 rounded-2xl border border-slate-800">
                <span className="text-3xl mb-3 block">📊</span>
                <h4 className="text-white font-bold text-lg mb-2">Institutional Metrics</h4>
                <p className="text-slate-400 text-sm leading-relaxed">
                  Evaluate strategies like a hedge fund. Access deep metrics: Sharpe ratios, Sortino ratios, Calmar drawdown multipliers, and expectations.
                </p>
              </div>

              <div className="p-6 bg-slate-900/50 rounded-2xl border border-slate-800">
                <span className="text-3xl mb-3 block">🔋</span>
                <h4 className="text-white font-bold text-lg mb-2">Global Data Sources</h4>
                <p className="text-slate-400 text-sm leading-relaxed">
                  Supports NYSE, NASDAQ, NSE (India), FTSE (London), DAX (Germany), Crypto pairs, Forex, and physical Commodity futures.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ── SECTION 4: QUANT GLOSSARY (SEO ENHANCEMENT) ── */}
        <section className="py-20 bg-slate-950 border-t border-slate-900">
          <div className="max-w-4xl mx-auto px-6">
            <h2 className="text-3xl font-bold text-white text-center mb-4">
              Understanding Quantitative Validation Metrics
            </h2>
            <p className="text-slate-400 text-center mb-12 max-w-2xl mx-auto">
              Our backtester computes institutional metrics. Here is a guide to what they mean and how they measure strategy performance:
            </p>

            <div className="space-y-6">
              <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-6">
                <h4 className="text-cyan-300 font-bold text-lg mb-2 flex items-center gap-2">
                  <span>📊</span> Sharpe Ratio
                </h4>
                <p className="text-slate-300 text-sm leading-relaxed">
                  Sharpe Ratio measures the risk-adjusted return of your strategy. It divides the excess returns of the portfolio above the risk-free rate by the daily standard deviation of those returns. 
                  A Sharpe ratio above <strong>1.0</strong> is considered decent, above <strong>2.0</strong> is excellent, and above <strong>3.0</strong> represents a world-class trading system.
                </p>
              </div>

              <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-6">
                <h4 className="text-violet-300 font-bold text-lg mb-2 flex items-center gap-2">
                  <span>📉</span> Maximum Drawdown (Max DD)
                </h4>
                <p className="text-slate-300 text-sm leading-relaxed">
                  Maximum drawdown measures the largest peak-to-trough decline in the value of the portfolio before a new peak is achieved. 
                  It is a critical gauge of historical downside risk. 
                  Most professional quants target keeping drawdown below <strong>15%</strong> to minimize capital impairment and behavioral stress.
                </p>
              </div>

              <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-6">
                <h4 className="text-fuchsia-300 font-bold text-lg mb-2 flex items-center gap-2">
                  <span>⚖️</span> Profit Factor
                </h4>
                <p className="text-slate-300 text-sm leading-relaxed">
                  Profit Factor is calculated as gross profit divided by gross loss for all executed trades during the backtesting duration. 
                  A Profit Factor of <strong>1.0</strong> means you broke even. 
                  Target a profit factor of <strong>1.5 to 2.5</strong> for a robust strategy that can absorb shifting market regimes.
                </p>
              </div>

              <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-6">
                <h4 className="text-emerald-300 font-bold text-lg mb-2 flex items-center gap-2">
                  <span>💎</span> Sortino Ratio
                </h4>
                <p className="text-slate-300 text-sm leading-relaxed">
                  Similar to the Sharpe Ratio, but the Sortino Ratio only penalizes negative volatility (downside risk). 
                  It isolates the variance of negative returns, giving a cleaner view of whether a strategy’s risk comes from actual losses or rapid positive surges.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ── SECTION 5: FAQ ACCORDION (TECHNICAL SEO SCHEMA BOOSTER) ── */}
        <section className="py-20 bg-slate-900/30 border-t border-slate-900">
          <div className="max-w-4xl mx-auto px-6">
            <h2 className="text-3xl font-bold text-white text-center mb-12">
              Frequently Asked Questions (FAQ)
            </h2>

            <div className="space-y-4">
              <div className="bg-slate-900/60 rounded-xl p-5 border border-slate-800">
                <h3 className="text-white font-bold text-base mb-2">
                  How do I backtest a stock trading strategy without coding?
                </h3>
                <p className="text-slate-300 text-sm leading-relaxed">
                  With MokshaGPT, you don't need any programming skills. You simply type your strategy parameters in natural English (e.g. "Buy AAPL when 20 EMA crosses above 50 EMA, hold for 1 year"). 
                  Our advanced AI compiler parses your rules, structures them into vectorized Python commands, and runs a comprehensive historical simulation on our institutional database.
                </p>
              </div>

              <div className="bg-slate-900/60 rounded-xl p-5 border border-slate-800">
                <h3 className="text-white font-bold text-base mb-2">
                  What is a LangGraph autonomous strategy optimizer?
                </h3>
                <p className="text-slate-300 text-sm leading-relaxed">
                  A LangGraph autonomous optimizer represents a state-of-the-art agentic loop. 
                  Instead of running a single backtest and guessing what parameters to tweak next, our agent iteratively executes simulations, reads Sharpe/drawdown metrics, analyzes the failures, adjusts thresholds autonomously, and repeats the loop until the strategy meets your desired performance benchmarks.
                </p>
              </div>

              <div className="bg-slate-900/60 rounded-xl p-5 border border-slate-800">
                <h3 className="text-white font-bold text-base mb-2">
                  How does the Ensemble Builder reduce maximum drawdown?
                </h3>
                <p className="text-slate-300 text-sm leading-relaxed">
                  The Ensemble Builder automatically constructs three distinct, uncorrelated strategies—typically combining a trend follower, a mean reversion model, and a volatility breakout engine. 
                  Because these strategies rely on different mathematical signals, their losing periods rarely overlap. When one model experiences a dip, the others cushion the total equity value, yielding a significantly smoother overall portfolio curve.
                </p>
              </div>

              <div className="bg-slate-900/60 rounded-xl p-5 border border-slate-800">
                <h3 className="text-white font-bold text-base mb-2">
                  Is backtesting historical data 100% accurate?
                </h3>
                <p className="text-slate-300 text-sm leading-relaxed">
                  Backtests simulate historical performance. While highly accurate for verifying if a strategy had an edge in the past, real-world execution contains slippage, transaction fees, liquidity constraints, and latency. 
                  MokshaGPT factors in standard transaction fees (approximated at 0.1% per trade) to ensure our simulations reflect realistic trading costs.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="bg-slate-900/80 backdrop-blur-xl border-t border-cyan-500/20 mt-0">
          <div className="max-w-7xl mx-auto px-6 py-10">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
              
              {/* About MokshaGPT */}
              <div>
                <h3 className="text-white font-bold text-lg mb-3">About MokshaGPT</h3>
                <p className="text-cyan-200 text-sm mb-4 leading-relaxed">
                  MokshaGPT is an advanced AI-powered platform for stock market analysis and trading strategy backtesting. We leverage cutting-edge language models and LangGraph agents to help traders and investors make data-driven decisions.
                </p>
                <p className="text-slate-400 text-xs mt-4">
                  Not financial advice. For educational and informational purposes only.
                </p>
              </div>

              {/* Product Tools */}
              <div>
                <h3 className="text-white font-bold text-lg mb-3">Product Tools</h3>
                <ul className="space-y-3">
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
                  <li className="pt-1">
                    <span className="text-slate-500 text-sm flex items-center gap-2">
                      <span className="text-lg">🚀</span>
                      <span>More tools coming soon...</span>
                    </span>
                  </li>
                </ul>
              </div>

              {/* Technology */}
              <div>
                <h3 className="text-white font-bold text-lg mb-3">Technology</h3>
                <ul className="space-y-3 text-sm text-cyan-200">
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
              <div className="flex gap-4 text-xs text-cyan-400">
                <Link href="/privacy" className="hover:text-white transition-colors">Privacy Policy</Link>
                <Link href="/terms" className="hover:text-white transition-colors">Terms of Service</Link>
                <Link href="/contact" className="hover:text-white transition-colors">Contact Support</Link>
              </div>
            </div>
          </div>
        </footer>
      </div>
    </>
  );
}
