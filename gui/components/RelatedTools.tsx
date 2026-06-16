import Link from "next/link";

interface Tool {
  href: string;
  icon: string;
  name: string;
  description: string;
  color: string; // tailwind border/text color token
}

const ALL_TOOLS: Tool[] = [
  {
    href: "/",
    icon: "📈",
    name: "AI Stock Analyzer",
    description: "Analyze any stock with AI — technicals, fundamentals, and market sentiment in plain English.",
    color: "cyan",
  },
  {
    href: "/aibacktester",
    icon: "🔬",
    name: "AI Backtester",
    description: "Describe any trading strategy and backtest it instantly. Sharpe ratio, win rate, drawdown, and more.",
    color: "blue",
  },
  {
    href: "/backtest-optimizer",
    icon: "🚀",
    name: "Backtest Optimizer",
    description: "Autonomous LangGraph loop that iteratively refines your strategy until Sharpe, drawdown, and win-rate targets are met.",
    color: "purple",
  },
  {
    href: "/ensemble-builder",
    icon: "🚀",
    name: "Ensemble Builder",
    description: "Combine multiple uncorrelated trading strategies into a single robust portfolio with diversified risk.",
    color: "yellow",
  },
  {
    href: "/aiscreener",
    icon: "🔍",
    name: "AI Stock Screener",
    description: "Find stocks using plain English — RSI, P/E, moving averages, sector, market cap across global markets.",
    color: "purple",
  },
  {
    href: "/aireporter",
    icon: "📋",
    name: "AI Reporter",
    description: "Generate professional financial reports from Excel/CSV data — for advisors and wealth managers.",
    color: "indigo",
  },
  {
    href: "/tradeanalyzer",
    icon: "📊",
    name: "Trade Analyzer",
    description: "Upload your brokerage trade history and get P&L analysis, overtrading detection, and AI coaching.",
    color: "emerald",
  },
];

const COLOR_MAP: Record<string, { border: string; text: string; hover: string }> = {
  cyan:    { border: "border-cyan-500/20",    text: "text-cyan-300",    hover: "hover:border-cyan-500/50" },
  blue:    { border: "border-blue-500/20",    text: "text-blue-300",    hover: "hover:border-blue-500/50" },
  purple:  { border: "border-purple-500/20",  text: "text-purple-300",  hover: "hover:border-purple-500/50" },
  yellow:  { border: "border-yellow-500/20",  text: "text-yellow-300",  hover: "hover:border-yellow-500/50" },
  indigo:  { border: "border-indigo-500/20",  text: "text-indigo-300",  hover: "hover:border-indigo-500/50" },
  emerald: { border: "border-emerald-500/20", text: "text-emerald-300", hover: "hover:border-emerald-500/50" },
};

interface RelatedToolsProps {
  /** href of the current page — this tool will be excluded from the list */
  current: string;
  /** Optional heading override */
  heading?: string;
}

export default function RelatedTools({ current, heading = "Explore More AI Tools" }: RelatedToolsProps) {
  const others = ALL_TOOLS.filter((t) => t.href !== current);

  return (
    <section className="bg-slate-900/60 border-t border-cyan-500/10 py-12">
      <div className="max-w-6xl mx-auto px-6">
        <h2 className="text-2xl font-bold text-white mb-2 text-center">{heading}</h2>
        <p className="text-slate-400 text-sm text-center mb-8">
          MokshaGPT is a full suite of AI-powered trading tools — all free, no sign-up required.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {others.map((tool) => {
            const c = COLOR_MAP[tool.color] ?? COLOR_MAP.cyan;
            return (
              <Link
                key={tool.href}
                href={tool.href}
                className={`flex items-start gap-4 p-5 bg-slate-800/50 border ${c.border} ${c.hover} rounded-2xl hover:bg-slate-700/50 transition-all group`}
              >
                <span className="text-3xl shrink-0">{tool.icon}</span>
                <div>
                  <p className={`font-semibold text-sm mb-1 ${c.text} group-hover:text-white transition-colors`}>
                    {tool.name}
                  </p>
                  <p className="text-slate-400 text-xs leading-relaxed">{tool.description}</p>
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </section>
  );
}
