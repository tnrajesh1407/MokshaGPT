import Link from "next/link";
import { useRouter } from "next/router";

const NAV_LINKS = [
  { href: "/",                    label: "Home" },
  { href: "/ai-backtesting",      label: "AI Backtesting" },
  { href: "/aibacktester",        label: "AI Backtester" },
  { href: "/backtest-optimizer",  label: "Backtest Optimizer" },
  { href: "/ensemble-builder",    label: "Ensemble Builder" },
  { href: "/aiscreener",          label: "AI Screener" },
  { href: "/aireporter",          label: "AI Reporter" },
  { href: "/tradeanalyzer",       label: "Trade Analyzer" },
];

export default function Header() {
  const { pathname } = useRouter();

  return (
    <header className="bg-slate-900/80 backdrop-blur-xl border-b border-cyan-500/20 shadow-lg">
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <img
            src="/mokshagpt-logo.png"
            alt="MokshaGPT Logo"
            className="w-12 h-12 rounded-full object-cover shadow-lg shadow-cyan-500/30"
          />
          <div>
            <p className="text-xl font-bold text-white">MokshaGPT</p>
            <p className="text-xs text-cyan-300">Stock Market Insights by AI</p>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex gap-4 text-sm flex-wrap">
          {NAV_LINKS.map(({ href, label }) => {
            const isActive = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={
                  isActive
                    ? "text-white font-semibold border-b-2 border-cyan-400 pb-0.5"
                    : "text-cyan-300 hover:text-white transition-colors"
                }
              >
                {label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
