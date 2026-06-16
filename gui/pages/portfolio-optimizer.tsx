import { useState, useEffect } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import Header from '../components/Header';
import RelatedTools from '../components/RelatedTools';
import { useRouter } from 'next/router';

interface StockScore {
  stock: string;
  financial_health: { score: number; reason: string };
  growth_potential: { score: number; reason: string };
  news_sentiment: { score: number; reason: string };
  news_impact: { score: number; reason: string };
  price_momentum: { score: number; reason: string };
  volatility_risk: { score: number; reason: string };
}

interface SelectedStock {
  stock_code: string;
  weight: number;
}

interface Portfolio {
  selected_stocks: SelectedStock[];
  reasoning: string;
}

interface ThreeSTraderResult {
  stock_overviews: any[];
  score_reports: StockScore[];
  portfolio: Portfolio;
  current_strategy: string;
  new_strategy?: string;
  timestamp: string;
}

export default function ThreeSTrader() {
  const router = useRouter();
  const [tickers, setTickers] = useState<string>('AAPL,MSFT,GOOGL,AMZN,TSLA,NVDA,META');
  const [initialStrategy, setInitialStrategy] = useState<string>(
    'Balanced approach: favor financially healthy stocks with positive momentum and moderate volatility'
  );
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ThreeSTraderResult | null>(null);
  const [error, setError] = useState<string>('');

  // Pre-fill from URL params (when redirected from home page chat)
  useEffect(() => {
    if (!router.isReady) return;
    const { tickers: t, strategy: s, autorun } = router.query;
    if (t) setTickers(t as string);
    if (s) setInitialStrategy(s as string);
    if (autorun === '1' && t) {
      // Trigger submit after state is set
      setTimeout(() => {
        document.getElementById('portfolio-submit-btn')?.click();
      }, 100);
    }
  }, [router.isReady, router.query]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setResult(null);

    try {
      const tickerList = tickers.split(',').map(t => t.trim()).filter(t => t);
      
      if (tickerList.length === 0) {
        throw new Error('Please enter at least one ticker');
      }

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/3s-trader`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tickers: tickerList,
          initial_strategy: initialStrategy || undefined,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to run 3S-Trader');
      }

      const data = await response.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const getScoreColor = (score: number): string => {
    if (score >= 8) return 'text-green-600 font-bold';
    if (score >= 6) return 'text-blue-600';
    if (score >= 4) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getScoreBarColor = (score: number): string => {
    if (score >= 8) return 'bg-green-500';
    if (score >= 6) return 'bg-blue-500';
    if (score >= 4) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  return (
    <>
      <Head>
        <title>AI Portfolio Optimizer - Multi-Agent Stock Analysis | MokshaGPT</title>
        <meta name="description" content="Advanced multi-agent portfolio optimization with adaptive stock scoring and strategy selection" />
        <link rel="canonical" href="https://mokshagpt.com/portfolio-optimizer" />
      </Head>

      <div className="min-h-screen bg-gradient-to-br from-indigo-950 via-slate-900 to-gray-900">
        
        <Header />

        <main className="max-w-7xl mx-auto px-6 py-10">
          {/* Hero */}
          <div className="text-center mb-10">
            <h2 className="text-4xl font-extrabold text-white mb-3">
              AI Portfolio Optimizer
            </h2>
            <p className="text-cyan-100 text-lg">
              Multi-Agent Framework for Adaptive Stock Scoring, Strategy, and Selection
            </p>
          </div>

          {/* How It Works */}
          <div className="max-w-4xl mx-auto mb-8">
            <div className="bg-cyan-900/20 border border-cyan-500/30 rounded-xl p-4">
              <h3 className="text-white font-semibold mb-2 flex items-center gap-2">
                <span className="text-xl">💡</span>
                How It Works
              </h3>
              <p className="text-cyan-100 text-sm">
                Our AI analyzes each stock across <strong>6 dimensions</strong> (Financial Health, Growth Potential, News Sentiment, 
                News Impact, Price Momentum, Volatility Risk). Your strategy guides which stocks to select and how to weight them. 
                The system constructs an optimized portfolio of up to 5 stocks based on your preferences.
              </p>
            </div>
          </div>

          {/* Input Form */}
          <div className="max-w-3xl mx-auto mb-8">
            <div className="bg-slate-800/60 backdrop-blur-xl rounded-2xl shadow-2xl border border-cyan-500/30 p-6">
              <form onSubmit={handleSubmit}>
                <div className="mb-4">
                  <label className="block text-cyan-300 font-medium mb-2">
                    Stock Tickers (comma-separated)
                  </label>
                  <input
                    type="text"
                    value={tickers}
                    onChange={(e) => setTickers(e.target.value)}
                    placeholder="AAPL,MSFT,GOOGL,AMZN,TSLA"
                    className="w-full px-4 py-2 rounded-lg bg-slate-900/70 text-white placeholder-slate-400 border-2 border-cyan-500/30 focus:outline-none focus:border-cyan-500 transition-all"
                    disabled={loading}
                  />
                  <p className="text-slate-400 text-sm mt-1">
                    Enter 5-10 stock tickers for optimal portfolio construction. Mix markets: US (AAPL), India (TCS.NS), UK (SHEL.L), Crypto (BTC-USD)
                  </p>
                  {/* Market presets */}
                  <div className="flex flex-wrap gap-2 mt-2">
                    <button type="button" onClick={() => setTickers('AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA')}
                      className="text-xs px-3 py-1 bg-blue-900/40 border border-blue-500/30 text-blue-300 rounded-full hover:bg-blue-800/50 hover:text-white transition-all" disabled={loading}>
                      🇺🇸 US Tech
                    </button>
                    <button type="button" onClick={() => setTickers('JPM,BAC,GS,MS,WFC,C,BLK')}
                      className="text-xs px-3 py-1 bg-blue-900/40 border border-blue-500/30 text-blue-300 rounded-full hover:bg-blue-800/50 hover:text-white transition-all" disabled={loading}>
                      🇺🇸 US Finance
                    </button>
                    <button type="button" onClick={() => setTickers('RELIANCE.NS,TCS.NS,INFY.NS,HDFCBANK.NS,ICICIBANK.NS,WIPRO.NS')}
                      className="text-xs px-3 py-1 bg-orange-900/40 border border-orange-500/30 text-orange-300 rounded-full hover:bg-orange-800/50 hover:text-white transition-all" disabled={loading}>
                      🇮🇳 India NIFTY
                    </button>
                    <button type="button" onClick={() => setTickers('SHEL.L,AZN.L,HSBA.L,BP.L,GSK.L')}
                      className="text-xs px-3 py-1 bg-emerald-900/40 border border-emerald-500/30 text-emerald-300 rounded-full hover:bg-emerald-800/50 hover:text-white transition-all" disabled={loading}>
                      🇬🇧 UK FTSE
                    </button>
                    <button type="button" onClick={() => setTickers('SAP.DE,SIE.DE,ALV.DE,BMW.DE,BAS.DE')}
                      className="text-xs px-3 py-1 bg-emerald-900/40 border border-emerald-500/30 text-emerald-300 rounded-full hover:bg-emerald-800/50 hover:text-white transition-all" disabled={loading}>
                      🇩🇪 Germany DAX
                    </button>
                    <button type="button" onClick={() => setTickers('BTC-USD,ETH-USD,SOL-USD,BNB-USD,ADA-USD')}
                      className="text-xs px-3 py-1 bg-purple-900/40 border border-purple-500/30 text-purple-300 rounded-full hover:bg-purple-800/50 hover:text-white transition-all" disabled={loading}>
                      ₿ Crypto
                    </button>
                    <button type="button" onClick={() => setTickers('AAPL,TCS.NS,SHEL.L,BTC-USD,GC=F')}
                      className="text-xs px-3 py-1 bg-cyan-900/40 border border-cyan-500/30 text-cyan-300 rounded-full hover:bg-cyan-800/50 hover:text-white transition-all" disabled={loading}>
                      🌍 Global Mix
                    </button>
                  </div>
                </div>

                <div className="mb-6">
                  <label className="block text-cyan-300 font-medium mb-2">
                    Initial Strategy (optional)
                  </label>
                  <textarea
                    value={initialStrategy}
                    onChange={(e) => setInitialStrategy(e.target.value)}
                    placeholder="Describe your investment strategy..."
                    rows={3}
                    className="w-full px-4 py-2 rounded-lg bg-slate-900/70 text-white placeholder-slate-400 border-2 border-cyan-500/30 focus:outline-none focus:border-cyan-500 transition-all resize-none"
                    disabled={loading}
                  />
                  <p className="text-slate-400 text-sm mt-1 mb-2">
                    Describe your investment goals and risk tolerance to guide stock selection
                  </p>
                  
                  {/* Strategy Examples */}
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => setInitialStrategy('Prioritize financial health and low volatility. Focus on established companies with stable earnings and minimal price fluctuations. Avoid high-risk, high-growth stocks.')}
                      className="text-xs px-3 py-1 bg-cyan-900/40 border border-cyan-500/30 text-cyan-300 rounded-full hover:bg-cyan-800/50 hover:text-white transition-all"
                      disabled={loading}
                    >
                      🛡️ Conservative
                    </button>
                    <button
                      type="button"
                      onClick={() => setInitialStrategy('Balanced approach: favor financially healthy stocks with positive momentum and moderate volatility. Balance growth potential with risk management.')}
                      className="text-xs px-3 py-1 bg-cyan-900/40 border border-cyan-500/30 text-cyan-300 rounded-full hover:bg-cyan-800/50 hover:text-white transition-all"
                      disabled={loading}
                    >
                      ⚖️ Balanced
                    </button>
                    <button
                      type="button"
                      onClick={() => setInitialStrategy('Focus on growth potential and positive momentum. Seek companies with strong revenue growth, expanding markets, and positive news sentiment. Accept higher volatility for potential gains.')}
                      className="text-xs px-3 py-1 bg-cyan-900/40 border border-cyan-500/30 text-cyan-300 rounded-full hover:bg-cyan-800/50 hover:text-white transition-all"
                      disabled={loading}
                    >
                      🚀 Growth
                    </button>
                    <button
                      type="button"
                      onClick={() => setInitialStrategy('Focus on undervalued stocks with strong fundamentals. Prioritize financial health and low price-to-earnings ratios. Look for stocks trading below intrinsic value with solid balance sheets.')}
                      className="text-xs px-3 py-1 bg-cyan-900/40 border border-cyan-500/30 text-cyan-300 rounded-full hover:bg-cyan-800/50 hover:text-white transition-all"
                      disabled={loading}
                    >
                      💎 Value
                    </button>
                    <button
                      type="button"
                      onClick={() => setInitialStrategy('Emphasize price momentum and positive news sentiment. Focus on stocks with strong upward trends and favorable market perception. Ride the momentum wave.')}
                      className="text-xs px-3 py-1 bg-cyan-900/40 border border-cyan-500/30 text-cyan-300 rounded-full hover:bg-cyan-800/50 hover:text-white transition-all"
                      disabled={loading}
                    >
                      📈 Momentum
                    </button>
                    <button
                      type="button"
                      onClick={() => setInitialStrategy('Focus on dividend-paying stocks with strong financial health and stable cash flows. Prioritize companies with consistent dividend history and low volatility.')}
                      className="text-xs px-3 py-1 bg-cyan-900/40 border border-cyan-500/30 text-cyan-300 rounded-full hover:bg-cyan-800/50 hover:text-white transition-all"
                      disabled={loading}
                    >
                      💰 Income
                    </button>
                  </div>
                </div>

                <button
                  id="portfolio-submit-btn"
                  type="submit"
                  disabled={loading}
                  className="w-full bg-gradient-to-r from-cyan-600 to-blue-600 text-white font-semibold py-3 px-6 rounded-xl hover:from-cyan-700 hover:to-blue-700 disabled:from-slate-600 disabled:to-slate-700 disabled:cursor-not-allowed transition-all shadow-lg shadow-cyan-500/30"
                >
                  {loading ? 'Analyzing Portfolio...' : 'Run Portfolio Analysis'}
                </button>
              </form>
            </div>
          </div>

          {/* Error Display */}
          {error && (
            <div className="max-w-3xl mx-auto mb-8">
              <div className="bg-red-900/40 border-l-4 border-red-500 text-red-200 px-4 py-3 rounded text-sm">
                {error}
              </div>
            </div>
          )}

          {/* Results Display */}
          {result && (
            <div className="max-w-7xl mx-auto space-y-6">
              {/* Portfolio Summary */}
              <div className="bg-slate-800/40 border border-cyan-500/20 rounded-2xl p-6 shadow-xl">
                <h2 className="text-2xl font-bold text-white mb-4">📊 Portfolio Allocation</h2>

                {/* Summary bar */}
                {(() => {
                  const totalInvested = result.portfolio.selected_stocks.reduce((sum, s) => sum + s.weight, 0);
                  const cash = Math.max(0, 1 - totalInvested);
                  return (
                    <div className="mb-5 bg-white/5 rounded-xl p-4 flex flex-wrap gap-4 items-center">
                      <div className="flex items-center gap-2">
                        <span className="w-3 h-3 rounded-full bg-gradient-to-r from-purple-500 to-blue-500 inline-block"></span>
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
                          The AI chose to keep {(cash * 100).toFixed(0)}% in cash — it didn't find enough conviction to deploy all capital.
                        </span>
                      )}
                    </div>
                  );
                })()}
                
                <div className="mb-6">
                  <h3 className="text-lg font-semibold text-white mb-2">Selected Stocks</h3>
                  <div className="space-y-3">
                    {result.portfolio.selected_stocks.map((stock, idx) => (
                      <div key={idx} className="bg-white/5 rounded-lg p-4">
                        <div className="flex justify-between items-center mb-2">
                          <span className="text-white font-bold text-lg">{stock.stock_code}</span>
                          <span className="text-purple-300 font-bold text-lg">
                            {(stock.weight * 100).toFixed(1)}% of portfolio
                          </span>
                        </div>
                        <div className="w-full bg-gray-700 rounded-full h-3">
                          <div
                            className="bg-gradient-to-r from-purple-500 to-blue-500 h-3 rounded-full transition-all"
                            style={{ width: `${stock.weight * 100}%` }}
                          />
                        </div>
                      </div>
                    ))}

                    {/* Cash row */}
                    {(() => {
                      const cash = Math.max(0, 1 - result.portfolio.selected_stocks.reduce((sum, s) => sum + s.weight, 0));
                      return cash > 0.005 ? (
                        <div className="bg-white/5 rounded-lg p-4 border border-yellow-500/20">
                          <div className="flex justify-between items-center mb-2">
                            <span className="text-yellow-300 font-bold text-lg flex items-center gap-2">
                              💵 Cash / Unallocated
                            </span>
                            <span className="text-yellow-300 font-bold text-lg">
                              {(cash * 100).toFixed(1)}% of portfolio
                            </span>
                          </div>
                          <div className="w-full bg-gray-700 rounded-full h-3">
                            <div
                              className="bg-yellow-500/60 h-3 rounded-full transition-all"
                              style={{ width: `${cash * 100}%` }}
                            />
                          </div>
                          <p className="text-slate-400 text-xs mt-2">
                            The AI deliberately left this portion uninvested — remaining stocks from your list didn't meet the strategy criteria.
                          </p>
                        </div>
                      ) : null;
                    })()}
                  </div>
                </div>

                <div className="bg-cyan-500/20 border border-cyan-500/50 rounded-lg p-4">
                  <h3 className="text-lg font-semibold text-white mb-2">Selection Reasoning</h3>
                  <p className="text-slate-200">{result.portfolio.reasoning}</p>
                </div>
              </div>

              {/* Strategy */}
              <div className="bg-slate-800/40 border border-cyan-500/20 rounded-2xl p-6 shadow-xl">
                <h2 className="text-2xl font-bold text-white mb-4">🎯 Investment Strategy</h2>
                <div className="bg-cyan-500/20 border border-cyan-500/50 rounded-lg p-4">
                  <p className="text-slate-200">{result.current_strategy}</p>
                </div>
                {result.new_strategy && (
                  <div className="mt-4 bg-emerald-500/20 border border-emerald-500/50 rounded-lg p-4">
                    <h3 className="text-lg font-semibold text-white mb-2">Updated Strategy</h3>
                    <p className="text-slate-200">{result.new_strategy}</p>
                  </div>
                )}
              </div>

              {/* Stock Scores */}
              <div className="bg-slate-800/40 border border-cyan-500/20 rounded-2xl p-6 shadow-xl">
                <h2 className="text-2xl font-bold text-white mb-4">📈 Multi-Dimensional Stock Scores</h2>
                
                <div className="space-y-6">
                  {result.score_reports.map((report, idx) => (
                    <div key={idx} className="bg-white/5 rounded-lg p-5">
                      <h3 className="text-xl font-bold text-white mb-4">{report.stock}</h3>
                      
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Financial Health */}
                        <div className="bg-white/5 rounded p-3">
                          <div className="flex justify-between items-center mb-2">
                            <span className="text-gray-300 font-semibold">Financial Health</span>
                            <span className={getScoreColor(report.financial_health.score)}>
                              {report.financial_health.score}/10
                            </span>
                          </div>
                          <div className="w-full bg-gray-700 rounded-full h-2 mb-2">
                            <div
                              className={`${getScoreBarColor(report.financial_health.score)} h-2 rounded-full`}
                              style={{ width: `${report.financial_health.score * 10}%` }}
                            />
                          </div>
                          <p className="text-gray-400 text-sm">{report.financial_health.reason}</p>
                        </div>

                        {/* Growth Potential */}
                        <div className="bg-white/5 rounded p-3">
                          <div className="flex justify-between items-center mb-2">
                            <span className="text-gray-300 font-semibold">Growth Potential</span>
                            <span className={getScoreColor(report.growth_potential.score)}>
                              {report.growth_potential.score}/10
                            </span>
                          </div>
                          <div className="w-full bg-gray-700 rounded-full h-2 mb-2">
                            <div
                              className={`${getScoreBarColor(report.growth_potential.score)} h-2 rounded-full`}
                              style={{ width: `${report.growth_potential.score * 10}%` }}
                            />
                          </div>
                          <p className="text-gray-400 text-sm">{report.growth_potential.reason}</p>
                        </div>

                        {/* News Sentiment */}
                        <div className="bg-white/5 rounded p-3">
                          <div className="flex justify-between items-center mb-2">
                            <span className="text-gray-300 font-semibold">News Sentiment</span>
                            <span className={getScoreColor(report.news_sentiment.score)}>
                              {report.news_sentiment.score}/10
                            </span>
                          </div>
                          <div className="w-full bg-gray-700 rounded-full h-2 mb-2">
                            <div
                              className={`${getScoreBarColor(report.news_sentiment.score)} h-2 rounded-full`}
                              style={{ width: `${report.news_sentiment.score * 10}%` }}
                            />
                          </div>
                          <p className="text-gray-400 text-sm">{report.news_sentiment.reason}</p>
                        </div>

                        {/* News Impact */}
                        <div className="bg-white/5 rounded p-3">
                          <div className="flex justify-between items-center mb-2">
                            <span className="text-gray-300 font-semibold">News Impact</span>
                            <span className={getScoreColor(report.news_impact.score)}>
                              {report.news_impact.score}/10
                            </span>
                          </div>
                          <div className="w-full bg-gray-700 rounded-full h-2 mb-2">
                            <div
                              className={`${getScoreBarColor(report.news_impact.score)} h-2 rounded-full`}
                              style={{ width: `${report.news_impact.score * 10}%` }}
                            />
                          </div>
                          <p className="text-gray-400 text-sm">{report.news_impact.reason}</p>
                        </div>

                        {/* Price Momentum */}
                        <div className="bg-white/5 rounded p-3">
                          <div className="flex justify-between items-center mb-2">
                            <span className="text-gray-300 font-semibold">Price Momentum</span>
                            <span className={getScoreColor(report.price_momentum.score)}>
                              {report.price_momentum.score}/10
                            </span>
                          </div>
                          <div className="w-full bg-gray-700 rounded-full h-2 mb-2">
                            <div
                              className={`${getScoreBarColor(report.price_momentum.score)} h-2 rounded-full`}
                              style={{ width: `${report.price_momentum.score * 10}%` }}
                            />
                          </div>
                          <p className="text-gray-400 text-sm">{report.price_momentum.reason}</p>
                        </div>

                        {/* Volatility Risk */}
                        <div className="bg-white/5 rounded p-3">
                          <div className="flex justify-between items-center mb-2">
                            <span className="text-gray-300 font-semibold">Volatility Risk</span>
                            <span className={getScoreColor(report.volatility_risk.score)}>
                              {report.volatility_risk.score}/10
                            </span>
                          </div>
                          <div className="w-full bg-gray-700 rounded-full h-2 mb-2">
                            <div
                              className={`${getScoreBarColor(report.volatility_risk.score)} h-2 rounded-full`}
                              style={{ width: `${report.volatility_risk.score * 10}%` }}
                            />
                          </div>
                          <p className="text-gray-400 text-sm">{report.volatility_risk.reason}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Framework Info */}
              <div className="bg-slate-800/40 border border-cyan-500/20 rounded-2xl p-6 shadow-xl">
                <h2 className="text-2xl font-bold text-white mb-4">ℹ️ About AI Portfolio Optimizer</h2>
                <div className="text-cyan-100 space-y-3">
                  <p>
                    Our <strong className="text-white">AI Portfolio Optimizer</strong> is a training-free multi-agent framework for portfolio optimization
                    that incorporates <strong>Scoring</strong>, <strong>Strategy</strong>, and <strong>Selection</strong> modules.
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-4">
                    <div className="bg-blue-500/20 rounded p-3">
                      <h4 className="font-bold text-white mb-1">Stage 1</h4>
                      <p className="text-sm">Data Analysis: News, Technical, and Fundamental agents</p>
                    </div>
                    <div className="bg-purple-500/20 rounded p-3">
                      <h4 className="font-bold text-white mb-1">Stage 2</h4>
                      <p className="text-sm">Stock Scoring: 6-dimensional evaluation</p>
                    </div>
                    <div className="bg-green-500/20 rounded p-3">
                      <h4 className="font-bold text-white mb-1">Stage 3</h4>
                      <p className="text-sm">Stock Selection: Portfolio construction</p>
                    </div>
                    <div className="bg-yellow-500/20 rounded p-3">
                      <h4 className="font-bold text-white mb-1">Stage 4</h4>
                      <p className="text-sm">Strategy Iteration: Adaptive refinement</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>

        <RelatedTools current="/portfolio-optimizer" />

        {/* Footer */}
        <footer className="bg-slate-900/80 backdrop-blur-xl border-t border-cyan-500/20 mt-0">
          <div className="max-w-7xl mx-auto px-6 py-10">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
              
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
                    <Link href="/aiscreener" className="text-cyan-300 hover:text-white transition-colors text-sm flex items-center gap-2">
                      <span className="text-lg">🔍</span>
                      <span>AI Stock Screener</span>
                    </Link>
                    <p className="text-slate-400 text-xs ml-7">Find stocks using natural language</p>
                  </li>
                  <li>
                    <Link href="/portfolio-optimizer" className="text-cyan-300 hover:text-white transition-colors text-sm flex items-center gap-2">
                      <span className="text-lg">📊</span>
                      <span>AI Portfolio Optimizer</span>
                    </Link>
                    <p className="text-slate-400 text-xs ml-7">Multi-agent portfolio optimization</p>
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
                    <span>Multi-Agent Architecture</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-cyan-400 mt-1">✓</span>
                    <span>Natural Language Processing</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-cyan-400 mt-1">✓</span>
                    <span>Adaptive Strategy Refinement</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-cyan-400 mt-1">✓</span>
                    <span>Real-time Market Data</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-cyan-400 mt-1">✓</span>
                    <span>Multi-Dimensional Scoring</span>
                  </li>
                </ul>
              </div>

              {/* About */}
              <div>
                <h3 className="text-white font-bold text-lg mb-3">About</h3>
                <p className="text-cyan-200 text-sm mb-4">
                  MokshaGPT provides AI-powered stock market analysis and portfolio optimization tools for retail investors.
                </p>
                <div className="flex gap-4 text-sm text-cyan-300">
                  <Link href="/privacy" className="hover:text-white transition-colors">Privacy</Link>
                  <Link href="/terms" className="hover:text-white transition-colors">Terms</Link>
                  <Link href="/contact" className="hover:text-white transition-colors">Contact</Link>
                </div>
              </div>
            </div>

            {/* Bottom Bar */}
            <div className="pt-6 border-t border-cyan-500/20 flex flex-col md:flex-row justify-between items-center gap-4">
              <p className="text-cyan-300 text-sm">
                © 2026 MokshaGPT. All rights reserved.
              </p>
              <p className="text-slate-400 text-xs">
                Not financial advice. For informational purposes only.
              </p>
            </div>
          </div>
        </footer>
      </div>
    </>
  );
}
