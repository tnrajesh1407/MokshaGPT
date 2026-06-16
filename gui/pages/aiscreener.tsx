import { useState } from "react";
import Head from "next/head";
import Link from "next/link";
import Header from "../components/Header";
import RelatedTools from "../components/RelatedTools";

// ── Types ─────────────────────────────────────────────────────────────────────

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
  // Technical indicators (optional)
  sma20?: number;
  rsi?: number;
  pct_from_52w_high?: number;
}

interface ScreenerResult {
  query: string;
  criteria: string[];
  stocks: Stock[];
  total_matches: number;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const fmt = (n: number, d = 2) =>
  n?.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });

const pct = (n: number) => `${n >= 0 ? "+" : ""}${fmt(n)}%`;

const EXAMPLE_QUERIES = [
  "S&P 500 stocks below 20 moving average",
  "US tech stocks with RSI below 30",
  "NASDAQ 100 stocks near 52-week low with P/E under 25",
  "FTSE 100 stocks above 50-day moving average with good dividend",
  "NIFTY 50 stocks below 20 moving average",
  "DAX 40 stocks with RSI above 70 (overbought)",
];

// ── Popular Screener Queries ──────────────────────────────────────────────────

const POPULAR_SCREENS: { category: string; color: string; items: { label: string; prompt: string }[] }[] = [
  {
    category: "🇺🇸 US Market Screens",
    color: "blue",
    items: [
      { label: "S&P 500 below 20 MA", prompt: "S&P 500 stocks below 20 moving average" },
      { label: "NASDAQ 100 near 52W low", prompt: "NASDAQ 100 stocks near 52-week low" },
      { label: "Dow Jones above 200 MA", prompt: "Dow Jones stocks above 200-day moving average" },
      { label: "US tech low P/E", prompt: "US tech stocks with P/E under 25 and large market cap" },
      { label: "US stocks RSI < 30", prompt: "S&P 500 stocks with RSI below 30 (oversold)" },
      { label: "US high dividend", prompt: "US stocks with dividend yield above 3% and low debt" },
    ],
  },
  {
    category: "🇮🇳 India (NSE/BSE) Screens",
    color: "orange",
    items: [
      { label: "NIFTY 50 below 20 MA", prompt: "NIFTY 50 stocks below 20 moving average" },
      { label: "NIFTY 100 near 52W low", prompt: "NIFTY 100 stocks near 52-week low" },
      { label: "Indian IT above 50 MA", prompt: "Indian IT stocks above 50-day moving average" },
      { label: "Banking oversold", prompt: "Indian banking stocks with RSI below 35" },
      { label: "NIFTY 100 low P/E", prompt: "NIFTY 100 stocks with P/E under 20" },
      { label: "Indian pharma above 200 MA", prompt: "Indian pharma stocks above 200-day moving average" },
    ],
  },
  {
    category: "🌍 International Markets",
    color: "emerald",
    items: [
      { label: "FTSE 100 oversold", prompt: "FTSE 100 stocks with RSI below 30" },
      { label: "DAX 40 near 52W low", prompt: "DAX 40 stocks near 52-week low" },
      { label: "Nikkei 225 above 200 MA", prompt: "Nikkei 225 stocks above 200-day moving average" },
      { label: "Hang Seng low P/E", prompt: "Hang Seng stocks with P/E under 15" },
      { label: "ASX 200 high dividend", prompt: "ASX 200 stocks with dividend yield above 4%" },
      { label: "TSX energy stocks", prompt: "TSX energy stocks above 50-day moving average" },
    ],
  },
  {
    category: "📊 Technical Screens",
    color: "purple",
    items: [
      { label: "Oversold RSI < 30", prompt: "S&P 500 stocks with RSI below 30 (oversold)" },
      { label: "Overbought RSI > 70", prompt: "NASDAQ 100 stocks with RSI above 70 (overbought)" },
      { label: "Below 200 MA (bearish)", prompt: "Large cap US stocks below 200-day moving average" },
      { label: "Above all MAs (bullish)", prompt: "S&P 500 stocks trading above 20, 50 and 200-day moving average" },
      { label: "Near 52-week low", prompt: "S&P 500 stocks near 52-week low with large market cap" },
    ],
  },
  {
    category: "💰 Fundamental Screens",
    color: "cyan",
    items: [
      { label: "Low P/E value stocks", prompt: "S&P 500 stocks with P/E under 15 and large market cap" },
      { label: "High dividend yield", prompt: "US stocks with dividend yield above 3% and low debt" },
      { label: "Growth stocks", prompt: "US tech stocks with revenue growth above 20%" },
      { label: "Low debt blue chips", prompt: "Large cap US stocks with low debt to equity ratio" },
      { label: "Undervalued financials", prompt: "US financial stocks with P/E under 12 and large market cap" },
    ],
  },
];

// ── Stock Card ────────────────────────────────────────────────────────────────

function StockCard({ stock }: { stock: Stock }) {
  const isPositive = stock.change_pct >= 0;
  return (
    <div className="bg-slate-800/60 border border-cyan-500/20 rounded-xl p-5 hover:border-cyan-500/40 transition-all hover:shadow-lg hover:shadow-cyan-500/10">
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
          <p className="text-cyan-300 font-medium">{stock.market_cap}</p>
        </div>
        <div>
          <p className="text-slate-500 text-xs">P/E Ratio</p>
          <p className="text-cyan-300 font-medium">{stock.pe_ratio > 0 ? fmt(stock.pe_ratio) : "N/A"}</p>
        </div>
        <div>
          <p className="text-slate-500 text-xs">Volume</p>
          <p className="text-cyan-300 font-medium">{stock.volume}</p>
        </div>
        <div>
          <p className="text-slate-500 text-xs">Sector</p>
          <p className="text-cyan-300 font-medium">{stock.sector}</p>
        </div>
        {/* Technical indicators if available */}
        {stock.sma20 && (
          <div>
            <p className="text-slate-500 text-xs">20-day MA</p>
            <p className="text-cyan-300 font-medium">{stock.currency ?? "$"}{fmt(stock.sma20)}</p>
          </div>
        )}
        {stock.rsi && (
          <div>
            <p className="text-slate-500 text-xs">RSI</p>
            <p className={`font-medium ${stock.rsi < 30 ? "text-green-400" : stock.rsi > 70 ? "text-red-400" : "text-cyan-300"}`}>
              {fmt(stock.rsi, 1)}
            </p>
          </div>
        )}
        {stock.pct_from_52w_high !== undefined && (
          <div>
            <p className="text-slate-500 text-xs">From 52W High</p>
            <p className={`font-medium ${stock.pct_from_52w_high > -10 ? "text-yellow-400" : "text-cyan-300"}`}>
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
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function AIScreenerPage() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ScreenerResult | null>(null);

  const handleScreen = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/screen`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Screening failed");
      }
      const data: ScreenerResult = await res.json();
      setResult(data);
    } catch (e: any) {
      setError(e.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleScreen();
    }
  };

  return (
    <>
      <Head>
        <title>MokshaGPT – AI Stock Screener | Stock Screener & Stock Market Screener Free</title>
        <meta name="description" content="The best free AI stock screener — find stocks using plain English. Screen S&P 500, NASDAQ, NIFTY, FTSE, DAX and global markets by P/E, RSI, moving averages, market cap, sector, and more. No code required." />
        <meta name="keywords" content="ai screener, stock screener, stock market screener, ai stock screener, free stock screener, natural language stock screener, stock finder, stock filter, technical stock screener, fundamental stock screener, nifty stock screener, nasdaq stock screener, sp500 screener, global stock screener" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="robots" content="index, follow" />
        <link rel="canonical" href="https://mokshagpt.com/aiscreener" />

        {/* Open Graph */}
        <meta property="og:type" content="website" />
        <meta property="og:url" content="https://mokshagpt.com/aiscreener" />
        <meta property="og:title" content="MokshaGPT – AI Stock Screener | Find Stocks in Plain English" />
        <meta property="og:description" content="The smartest AI stock screener on the web. Screen global markets by any criteria — RSI, P/E, moving averages, sector, market cap — just describe what you want in plain English. Free to use." />
        <meta property="og:image" content="https://mokshagpt.com/og-screener.jpg" />

        {/* Twitter */}
        <meta property="twitter:card" content="summary_large_image" />
        <meta property="twitter:url" content="https://mokshagpt.com/aiscreener" />
        <meta property="twitter:title" content="MokshaGPT – AI Stock Screener | Stock Market Screener Free" />
        <meta property="twitter:description" content="Screen stocks across US, India, UK, Germany, Japan and more using plain English. The best free AI stock screener — no sign-up required." />
        <meta property="twitter:image" content="https://mokshagpt.com/twitter-screener.jpg" />

        {/* Structured Data – SoftwareApplication */}
        <script type="application/ld+json">
          {JSON.stringify({
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": "MokshaGPT AI Stock Screener",
            "applicationCategory": "FinanceApplication",
            "description": "AI stock screener and stock market screener that accepts natural language queries to find stocks matching any criteria across global markets.",
            "url": "https://mokshagpt.com/aiscreener",
            "offers": {
              "@type": "Offer",
              "price": "0",
              "priceCurrency": "USD"
            },
            "featureList": [
              "AI stock screener",
              "Stock market screener",
              "Natural language stock screening",
              "Technical screening (RSI, SMA, EMA, Bollinger Bands)",
              "Fundamental screening (P/E, market cap, dividend yield, debt)",
              "Global market coverage (US, India, UK, Germany, Japan, HK, Australia, Canada)",
              "Real-time stock data",
              "Sector and industry filtering",
              "52-week high/low screening"
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
                "name": "What is an AI stock screener?",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "An AI stock screener lets you find stocks using plain English instead of complex filter forms. Just describe what you're looking for — 'S&P 500 stocks with RSI below 30 and P/E under 20' — and the AI stock screener returns matching stocks instantly with full details."
                }
              },
              {
                "@type": "Question",
                "name": "How is an AI screener different from a traditional stock screener?",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "A traditional stock screener requires you to manually set filters using dropdown menus and number inputs. An AI screener understands natural language — you describe your criteria conversationally and the AI interprets and applies the right filters automatically."
                }
              },
              {
                "@type": "Question",
                "name": "Which markets does the stock market screener cover?",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "MokshaGPT's stock market screener covers US markets (S&P 500, NASDAQ 100, Dow Jones), Indian markets (NIFTY 50, NIFTY 100, BSE), UK (FTSE 100), Germany (DAX 40), Japan (Nikkei 225), Hong Kong (Hang Seng), Australia (ASX 200), and Canada (TSX)."
                }
              },
              {
                "@type": "Question",
                "name": "What criteria can I use to screen stocks?",
                "acceptedAnswer": {
                  "@type": "Answer",
                  "text": "You can screen by any combination of technical indicators (RSI, SMA, EMA, Bollinger Bands, 52-week high/low) and fundamental metrics (P/E ratio, market cap, dividend yield, debt-to-equity, revenue growth, sector). Just describe your criteria in plain English."
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
              Free AI Stock Screener — No Sign-up Required
            </div>
            <h1 className="text-4xl font-extrabold text-white mb-3">
              <span className="bg-gradient-to-r from-cyan-400 via-blue-400 to-cyan-400 bg-clip-text text-transparent">
                AI Stock Screener
              </span>
            </h1>
            <p className="text-cyan-100 max-w-2xl mx-auto mb-2">
              The smartest <span className="text-white font-semibold">stock screener</span> powered by AI. Describe what stocks you're looking for in plain English — our AI stock screener finds matching stocks across global markets instantly.
            </p>
            <p className="text-cyan-200 max-w-xl mx-auto text-sm">
              No filter forms. No dropdowns. Just tell the <span className="text-white font-semibold">stock market screener</span> what you want and get results in seconds.
            </p>
            <p className="text-cyan-300 text-sm mt-2">
              🌍 Global Markets • US (S&P 500, NASDAQ) • India (NIFTY) • UK (FTSE) • Germany (DAX) • Japan (Nikkei) • HK • Australia • Canada
            </p>
          </div>

          {/* Input */}
          <div className="max-w-3xl mx-auto mb-10">
            {/* Disclaimer */}
            <div className="mb-4 bg-amber-950/30 border border-amber-500/30 rounded-xl px-5 py-4 flex gap-3 text-xs text-amber-200/80">
              <span className="text-amber-400 text-base shrink-0 mt-0.5">⚠️</span>
              <span>
                <span className="font-semibold text-amber-300">Research tool only — not financial advice. </span>
                Screener results are for informational and educational purposes only. Data may be delayed. Always do your own research before investing.
              </span>
            </div>
            <div className="bg-slate-800/60 backdrop-blur-xl rounded-2xl border border-cyan-500/30 p-6 shadow-2xl">
              <label className="block text-cyan-300 text-sm font-medium mb-2">
                What stocks are you looking for?
              </label>
              <textarea
                rows={3}
                placeholder="e.g. Find tech stocks with P/E ratio under 20 and market cap over $10B"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                className="w-full px-4 py-3 text-white bg-slate-900/70 border-2 border-cyan-500/30 rounded-xl focus:outline-none focus:border-cyan-500 transition-all placeholder:text-slate-400 resize-none"
              />

              {/* Market indicators */}
              <div className="mt-2 flex items-center gap-2 text-xs text-slate-400 flex-wrap">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                  🇺🇸 US (S&P 500, NASDAQ)
                </span>
                <span className="text-slate-600">•</span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-orange-500"></span>
                  🇮🇳 India (NIFTY 50/100)
                </span>
                <span className="text-slate-600">•</span>
                <span className="text-slate-500">🇬🇧 FTSE • 🇩🇪 DAX • 🇯🇵 Nikkei • 🇭🇰 Hang Seng • 🇦🇺 ASX • 🇨🇦 TSX</span>
              </div>

              {/* Popular screens picker */}
              <div className="mt-4">
                <p className="text-slate-400 text-xs mb-2 uppercase tracking-wider">Popular Screens</p>
                <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                  {POPULAR_SCREENS.map((group) => (
                    <div key={group.category}>
                      <p className="text-xs text-slate-500 mb-1">{group.category}</p>
                      <div className="flex flex-wrap gap-1.5">
                        {group.items.map((item) => (
                          <button
                            key={item.label}
                            onClick={() => setQuery(item.prompt)}
                            className={`text-xs px-3 py-1 rounded-full border transition-all
                              ${group.color === "orange"  ? "bg-orange-900/40 border-orange-500/30 text-orange-300 hover:bg-orange-800/50 hover:text-white" : ""}
                              ${group.color === "blue"    ? "bg-blue-900/40 border-blue-500/30 text-blue-300 hover:bg-blue-800/50 hover:text-white" : ""}
                              ${group.color === "cyan"    ? "bg-cyan-900/40 border-cyan-500/30 text-cyan-300 hover:bg-cyan-800/50 hover:text-white" : ""}
                              ${group.color === "purple"  ? "bg-purple-900/40 border-purple-500/30 text-purple-300 hover:bg-purple-800/50 hover:text-white" : ""}
                              ${group.color === "emerald" ? "bg-emerald-900/40 border-emerald-500/30 text-emerald-300 hover:bg-emerald-800/50 hover:text-white" : ""}
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
                onClick={handleScreen}
                disabled={loading || !query.trim()}
                className="mt-4 w-full py-3 bg-gradient-to-r from-cyan-600 to-blue-600 text-white font-semibold rounded-xl hover:from-cyan-700 hover:to-blue-700 disabled:from-slate-600 disabled:to-slate-700 disabled:cursor-not-allowed transition-all shadow-lg shadow-cyan-500/30"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Screening Stocks…
                  </span>
                ) : (
                  "Find Stocks"
                )}
              </button>

              {error && (
                <div className="mt-4 bg-red-900/40 border-l-4 border-red-500 text-red-200 px-4 py-3 rounded text-sm">
                  {error}
                </div>
              )}
            </div>
          </div>

          {/* Results */}
          {result && !loading && (
            <div className="space-y-6">
              {/* Summary */}
              <div className="bg-slate-800/40 border border-cyan-500/20 rounded-2xl p-5">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="text-white font-bold text-lg mb-2">Search Results</h3>
                    <p className="text-cyan-200 text-sm mb-3">{result.query}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-3xl font-bold text-cyan-400">{result.total_matches}</p>
                    <p className="text-xs text-slate-400">stocks found</p>
                  </div>
                </div>
                
                {result.criteria.length > 0 && (
                  <div>
                    <p className="text-slate-400 text-xs mb-2">Applied Criteria:</p>
                    <div className="flex flex-wrap gap-2">
                      {result.criteria.map((criterion, i) => (
                        <span key={i} className="px-3 py-1 bg-cyan-900/50 border border-cyan-500/30 rounded-full text-cyan-200 text-xs">
                          {criterion}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Stock Grid */}
              {result.stocks.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {result.stocks.map((stock) => (
                    <StockCard key={stock.ticker} stock={stock} />
                  ))}
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
                  Screener results are for informational and educational purposes only. Stock data may be delayed up to 15 minutes. Always conduct your own due diligence and consult a licensed financial advisor before making investment decisions.
                </span>
              </div>
            </div>
          )}
        </main>

        {/* ── SEO Content: Features + FAQ ── */}
        <section className="bg-slate-900/60 border-t border-cyan-500/10 py-16">
          <div className="max-w-6xl mx-auto px-6">

            {/* Intro */}
            <div className="text-center mb-12">
              <h2 className="text-3xl font-bold text-white mb-3">
                The AI Screener That Understands You
              </h2>
              <p className="text-cyan-200 max-w-2xl mx-auto">
                Traditional stock screeners make you fill out complex filter forms. MokshaGPT's AI stock screener is different — just describe what you want in plain English and the AI handles the rest. It's the fastest stock market screener for both beginners and professionals.
              </p>
            </div>

            {/* Feature cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-14">
              <div className="bg-slate-800/50 border border-cyan-500/20 rounded-2xl p-6 hover:border-cyan-500/40 transition-all">
                <div className="text-3xl mb-3">💬</div>
                <h3 className="text-white font-bold text-lg mb-2">Natural Language Screening</h3>
                <p className="text-slate-300 text-sm leading-relaxed">
                  No filter forms needed. Ask the AI screener anything — "NIFTY 50 stocks with RSI below 30" or "US tech stocks with P/E under 20 and large market cap".
                </p>
              </div>
              <div className="bg-slate-800/50 border border-blue-500/20 rounded-2xl p-6 hover:border-blue-500/40 transition-all">
                <div className="text-3xl mb-3">📊</div>
                <h3 className="text-white font-bold text-lg mb-2">Technical + Fundamental</h3>
                <p className="text-slate-300 text-sm leading-relaxed">
                  The stock screener combines technical indicators (RSI, SMA, EMA, 52-week levels) with fundamental metrics (P/E, market cap, dividend yield, debt) in a single query.
                </p>
              </div>
              <div className="bg-slate-800/50 border border-purple-500/20 rounded-2xl p-6 hover:border-purple-500/40 transition-all">
                <div className="text-3xl mb-3">🌍</div>
                <h3 className="text-white font-bold text-lg mb-2">Global Stock Market Screener</h3>
                <p className="text-slate-300 text-sm leading-relaxed">
                  Screen stocks across US (S&P 500, NASDAQ), India (NIFTY 50/100), UK (FTSE 100), Germany (DAX 40), Japan (Nikkei 225), Hong Kong, Australia, and Canada — all in one stock market screener.
                </p>
              </div>
              <div className="bg-slate-800/50 border border-emerald-500/20 rounded-2xl p-6 hover:border-emerald-500/40 transition-all">
                <div className="text-3xl mb-3">⚡</div>
                <h3 className="text-white font-bold text-lg mb-2">Instant Results</h3>
                <p className="text-slate-300 text-sm leading-relaxed">
                  Get matching stocks in seconds with price, change %, market cap, P/E ratio, volume, sector, RSI, 20-day MA, and distance from 52-week high — all in one view.
                </p>
              </div>
            </div>

            {/* What you can screen for */}
            <div className="bg-slate-800/30 border border-cyan-500/15 rounded-2xl p-8 mb-14">
              <h2 className="text-2xl font-bold text-white mb-6 text-center">What You Can Screen For</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {[
                  { icon: "📉", name: "Oversold Stocks (RSI < 30)", desc: "Find stocks that are technically oversold and potentially due for a bounce across any index." },
                  { icon: "📈", name: "Momentum Stocks", desc: "Screen for stocks trading above their 20, 50, or 200-day moving averages — classic bullish signals." },
                  { icon: "💰", name: "Value Stocks (Low P/E)", desc: "Find undervalued stocks with P/E ratios below market average, filtered by market cap and sector." },
                  { icon: "💸", name: "High Dividend Yield", desc: "Screen for stocks with dividend yields above a threshold — great for income-focused investors." },
                  { icon: "📏", name: "Near 52-Week Low", desc: "Identify stocks trading near their 52-week lows — potential contrarian opportunities." },
                  { icon: "🏭", name: "Sector & Industry Screens", desc: "Screen within specific sectors — tech, banking, pharma, energy, financials — across any market." },
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
              <h2 className="text-2xl font-bold text-white mb-6 text-center">Stock Screener FAQ</h2>
              <div className="space-y-4">
                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                  <h3 className="text-white font-semibold mb-2">What is an AI stock screener?</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    An AI stock screener uses artificial intelligence to interpret plain English queries and find stocks that match your criteria. Unlike traditional stock screeners that require manual filter setup, an AI screener understands natural language — just describe what you want and it returns matching stocks instantly.
                  </p>
                </div>
                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                  <h3 className="text-white font-semibold mb-2">How is this stock screener different from Finviz or TradingView?</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    Finviz and TradingView require you to manually set each filter using dropdowns and number inputs. MokshaGPT's AI stock screener understands natural language — you describe your criteria conversationally and the AI applies the right filters. It also covers global markets including India (NIFTY), UK (FTSE), Germany (DAX), and more.
                  </p>
                </div>
                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                  <h3 className="text-white font-semibold mb-2">Which indices does the stock market screener support?</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    The stock market screener supports S&P 500, NASDAQ 100, Dow Jones (US), NIFTY 50, NIFTY 100 (India), FTSE 100 (UK), DAX 40 (Germany), Nikkei 225 (Japan), Hang Seng (Hong Kong), ASX 200 (Australia), and TSX (Canada).
                  </p>
                </div>
                <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                  <h3 className="text-white font-semibold mb-2">Is the AI screener free to use?</h3>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    Yes. MokshaGPT's AI stock screener is completely free to use with no sign-up required. Screen stocks across global markets using plain English — for educational and informational purposes.
                  </p>
                </div>
              </div>
            </div>

          </div>
        </section>

        <RelatedTools current="/aiscreener" />

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
                  MokshaGPT is an advanced AI-powered platform for stock market analysis, strategy backtesting, and stock discovery. 
                  We leverage cutting-edge language models to help traders and investors make data-driven decisions.
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
