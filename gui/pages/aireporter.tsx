
import { useState, useRef, useCallback } from "react";
import Head from "next/head";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import Header from "../components/Header";
import RelatedTools from "../components/RelatedTools";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ReportSection {
  heading: string;
  content: string;
}

interface ReportResult {
  report_type: string;
  title: string;
  generated_at: string;
  firm_name: string;
  client_name: string;
  report_period: string;
  currency: string;
  as_of_date: string | null;
  executive_summary: string;
  sections: ReportSection[];
  qc_warnings: string[];
  qc_errors: string[];
  qc_passed: boolean;
  metadata: {
    sheets_processed: string[];
    summary_stats: Record<string, any>;
    tone: string;
  };
}

interface ReportTemplate {
  id: string;
  label: string;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const TONE_OPTIONS = [
  { id: "professional", label: "Professional" },
  { id: "formal", label: "Formal" },
  { id: "conversational", label: "Conversational" },
];

const REPORT_TYPE_ICONS: Record<string, string> = {
  portfolio_summary: "📊",
  performance_review: "📈",
  market_commentary: "🌍",
  client_letter: "✉️",
  risk_report: "🛡️",
  custom: "📝",
};

// ── Helper Components ─────────────────────────────────────────────────────────

function SectionCard({ section, index }: { section: ReportSection; index: number }) {
  const [expanded, setExpanded] = useState(true);
  return (
    <div className="bg-slate-800/50 border border-cyan-500/20 rounded-xl overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-6 py-4 text-left hover:bg-slate-700/30 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="w-7 h-7 rounded-full bg-cyan-900/60 border border-cyan-500/30 flex items-center justify-center text-xs text-cyan-300 font-bold">
            {index + 1}
          </span>
          <h3 className="text-white font-semibold">{section.heading}</h3>
        </div>
        <span className="text-slate-400 text-sm">{expanded ? "▲" : "▼"}</span>
      </button>
      {expanded && (
        <div className="px-6 pb-6 border-t border-slate-700/50">
          <div className="mt-4 prose prose-invert prose-sm max-w-none">
            <ReactMarkdown
              components={{
                h1: ({ children }) => <h1 className="text-xl font-bold text-white mt-4 mb-2">{children}</h1>,
                h2: ({ children }) => <h2 className="text-lg font-bold text-cyan-200 mt-4 mb-2">{children}</h2>,
                h3: ({ children }) => <h3 className="text-base font-semibold text-cyan-300 mt-3 mb-1">{children}</h3>,
                p: ({ children }) => <p className="text-slate-300 leading-relaxed mb-3">{children}</p>,
                ul: ({ children }) => <ul className="list-disc list-inside text-slate-300 space-y-1 mb-3">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal list-inside text-slate-300 space-y-1 mb-3">{children}</ol>,
                li: ({ children }) => <li className="text-slate-300">{children}</li>,
                strong: ({ children }) => <strong className="text-white font-semibold">{children}</strong>,
                em: ({ children }) => <em className="text-cyan-300">{children}</em>,
                table: ({ children }) => (
                  <div className="overflow-x-auto mb-3">
                    <table className="w-full text-sm border-collapse">{children}</table>
                  </div>
                ),
                th: ({ children }) => (
                  <th className="px-3 py-2 bg-slate-700/60 text-cyan-300 text-left border border-slate-600/40 font-semibold">{children}</th>
                ),
                td: ({ children }) => (
                  <td className="px-3 py-2 text-slate-300 border border-slate-700/40">{children}</td>
                ),
              }}
            >
              {section.content}
            </ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}

function QCBadge({ warnings, errors, passed }: { warnings: string[]; errors: string[]; passed: boolean }) {
  const [open, setOpen] = useState(false);
  const total = warnings.length + errors.length;
  if (total === 0) {
    return (
      <span className="flex items-center gap-1.5 px-3 py-1 bg-emerald-900/40 border border-emerald-500/30 rounded-full text-emerald-300 text-xs">
        ✓ Data QC Passed
      </span>
    );
  }
  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs border transition-colors ${
          errors.length > 0
            ? "bg-red-900/40 border-red-500/30 text-red-300 hover:bg-red-900/60"
            : "bg-yellow-900/40 border-yellow-500/30 text-yellow-300 hover:bg-yellow-900/60"
        }`}
      >
        {errors.length > 0 ? "⚠ QC Errors" : "⚠ QC Warnings"} ({total})
      </button>
      {open && (
        <div className="absolute top-8 left-0 z-10 w-80 bg-slate-900 border border-slate-600/50 rounded-xl shadow-2xl p-4">
          {errors.length > 0 && (
            <div className="mb-3">
              <p className="text-red-400 text-xs font-semibold uppercase mb-1">Errors</p>
              {errors.map((e, i) => (
                <p key={i} className="text-red-300 text-xs mb-1">• {e}</p>
              ))}
            </div>
          )}
          {warnings.length > 0 && (
            <div>
              <p className="text-yellow-400 text-xs font-semibold uppercase mb-1">Warnings</p>
              {warnings.map((w, i) => (
                <p key={i} className="text-yellow-300 text-xs mb-1">• {w}</p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Download helpers ──────────────────────────────────────────────────────────

function downloadReportAsText(report: ReportResult) {
  const lines: string[] = [];
  lines.push("=".repeat(70));
  lines.push(report.title.toUpperCase());
  lines.push(`Generated: ${report.generated_at}`);
  lines.push(`Firm: ${report.firm_name}  |  Client: ${report.client_name}`);
  if (report.report_period) lines.push(`Period: ${report.report_period}`);
  if (report.as_of_date) lines.push(`As of: ${report.as_of_date}`);
  lines.push("=".repeat(70));
  lines.push("");
  lines.push("EXECUTIVE SUMMARY");
  lines.push("-".repeat(40));
  lines.push(report.executive_summary);
  lines.push("");
  report.sections.forEach((s, i) => {
    lines.push(`${i + 1}. ${s.heading.toUpperCase()}`);
    lines.push("-".repeat(40));
    lines.push(s.content);
    lines.push("");
  });
  if (report.qc_warnings.length > 0) {
    lines.push("DATA QUALITY NOTES");
    lines.push("-".repeat(40));
    report.qc_warnings.forEach((w) => lines.push(`• ${w}`));
    lines.push("");
  }
  lines.push("─".repeat(70));
  lines.push("This report was generated by AI and is for informational purposes only.");
  lines.push("It does not constitute financial advice.");

  const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8;" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${report.title.replace(/[^a-z0-9]/gi, "_")}_${new Date().toISOString().split("T")[0]}.txt`;
  link.click();
}

function downloadReportAsMarkdown(report: ReportResult) {
  const lines: string[] = [];
  lines.push(`# ${report.title}`);
  lines.push("");
  lines.push(`**Generated:** ${report.generated_at}  `);
  lines.push(`**Firm:** ${report.firm_name}  `);
  lines.push(`**Client:** ${report.client_name}  `);
  if (report.report_period) lines.push(`**Period:** ${report.report_period}  `);
  if (report.as_of_date) lines.push(`**As of:** ${report.as_of_date}  `);
  lines.push("");
  lines.push("---");
  lines.push("");
  lines.push("## Executive Summary");
  lines.push("");
  lines.push(report.executive_summary);
  lines.push("");
  report.sections.forEach((s) => {
    lines.push(`## ${s.heading}`);
    lines.push("");
    lines.push(s.content);
    lines.push("");
  });
  if (report.qc_warnings.length > 0) {
    lines.push("## Data Quality Notes");
    lines.push("");
    report.qc_warnings.forEach((w) => lines.push(`- ${w}`));
    lines.push("");
  }
  lines.push("---");
  lines.push("*This report was generated by AI and is for informational purposes only. It does not constitute financial advice.*");

  const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8;" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${report.title.replace(/[^a-z0-9]/gi, "_")}_${new Date().toISOString().split("T")[0]}.md`;
  link.click();
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function AIReporterPage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Form state
  const [file, setFile] = useState<File | null>(null);
  const [reportType, setReportType] = useState("portfolio_summary");
  const [firmName, setFirmName] = useState("");
  const [clientName, setClientName] = useState("");
  const [reportPeriod, setReportPeriod] = useState("");
  const [customInstructions, setCustomInstructions] = useState("");
  const [tone, setTone] = useState("professional");

  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ReportResult | null>(null);
  const [templates, setTemplates] = useState<ReportTemplate[]>([
    { id: "portfolio_summary", label: "Portfolio Summary Report" },
    { id: "performance_review", label: "Performance Review Report" },
    { id: "market_commentary", label: "Market Commentary" },
    { id: "client_letter", label: "Client Investment Letter" },
    { id: "risk_report", label: "Risk & Compliance Report" },
    { id: "custom", label: "Custom Financial Report" },
  ]);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Drag-and-drop handlers
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);
  const handleDragLeave = useCallback(() => setDragOver(false), []);
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) setFile(dropped);
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) setFile(f);
  };

  const handleGenerate = async () => {
    if (!file) { setError("Please upload an Excel or CSV file."); return; }
    setLoading(true);
    setError("");
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("report_type", reportType);
    formData.append("firm_name", firmName || "Our Firm");
    formData.append("client_name", clientName || "Valued Client");
    formData.append("report_period", reportPeriod);
    formData.append("custom_instructions", customInstructions);
    formData.append("tone", tone);

    try {
      const res = await fetch(`${apiUrl}/report/generate`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `Server error ${res.status}` }));
        throw new Error(err.detail || "Report generation failed");
      }
      const data: ReportResult = await res.json();
      setResult(data);
    } catch (e: any) {
      setError(e.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const fileExt = file?.name.split(".").pop()?.toLowerCase() ?? "";
  const fileValid = ["xlsx", "xls", "xlsm", "csv"].includes(fileExt);

  return (
    <>
      <Head>
        <title>AI Financial Report Generator | MokshaGPT</title>
        <meta
          name="description"
          content="Transform Excel and CSV financial data into professional, client-ready investment reports and commentary using AI. Supports portfolio summaries, performance reviews, client letters, and risk reports."
        />
        <meta
          name="keywords"
          content="AI financial report generator, wealth management reports, investment commentary, portfolio report, client letter, Excel to report, AI report automation"
        />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="robots" content="index, follow" />
        <link rel="canonical" href="https://mokshagpt.com/aireporter" />
        <meta property="og:type" content="website" />
        <meta property="og:url" content="https://mokshagpt.com/aireporter" />
        <meta property="og:title" content="AI Financial Report Generator | MokshaGPT" />
        <meta
          property="og:description"
          content="Upload your Excel data and generate professional financial reports with AI — portfolio summaries, performance reviews, client letters, and more."
        />
      </Head>

      <div className="min-h-screen bg-gradient-to-br from-indigo-950 via-slate-900 to-gray-900">
        <Header />

        <main className="max-w-6xl mx-auto px-6 py-12">
          {/* Hero */}
          <div className="text-center mb-10">
            <h2 className="text-4xl font-extrabold text-white mb-4 leading-tight">
              <span className="bg-gradient-to-r from-cyan-400 via-blue-400 to-cyan-400 bg-clip-text text-transparent">
                AI Financial Report Generator
              </span>
            </h2>
            <p className="text-cyan-100 max-w-2xl mx-auto">
              Upload your Excel or CSV data and generate professional, client-ready financial reports
              with consistent tone, structure, and analytical depth — powered by LLM.
            </p>
            <div className="mt-3 flex flex-wrap justify-center gap-2 text-xs text-slate-400">
              {["Portfolio Summary", "Performance Review", "Market Commentary", "Client Letter", "Risk Report"].map((t) => (
                <span key={t} className="px-2 py-1 bg-slate-800/60 border border-slate-600/30 rounded-full">{t}</span>
              ))}
            </div>

            {/* Audience notice */}
            <div className="mt-6 inline-flex items-start gap-3 max-w-2xl mx-auto bg-amber-950/50 border border-amber-500/30 rounded-xl px-5 py-4 text-left">
              <span className="text-amber-400 text-xl shrink-0 mt-0.5">🏦</span>
              <div>
                <p className="text-amber-300 font-semibold text-sm">Designed for institutional & wealth management use</p>
                <p className="text-amber-200/80 text-xs mt-1 leading-relaxed">
                  This tool is built for financial advisors, portfolio managers, RIAs, and wealth management firms
                  who need to generate client-ready reports from structured portfolio data.
                  If you are a retail trader looking to analyse your own trades, the{" "}
                  <a href="/" className="text-cyan-400 hover:text-cyan-300 underline underline-offset-2 transition-colors">AI Stock Analyzer</a>{" "}
                  or{" "}
                  <a href="/aibacktester" className="text-cyan-400 hover:text-cyan-300 underline underline-offset-2 transition-colors">AI Backtester</a>{" "}
                  may be more suitable for your needs.
                </p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
            {/* ── Left: Configuration Panel ── */}
            <div className="lg:col-span-2 space-y-5">

              {/* File Upload */}
              <div className="bg-slate-800/60 backdrop-blur-xl rounded-2xl border border-cyan-500/30 p-5">
                <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                  <span className="text-cyan-400">📂</span> Upload Data File
                </h3>
                <div
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${
                    dragOver
                      ? "border-cyan-400 bg-cyan-900/20"
                      : file && fileValid
                      ? "border-emerald-500/50 bg-emerald-900/10"
                      : file && !fileValid
                      ? "border-red-500/50 bg-red-900/10"
                      : "border-slate-600/50 hover:border-cyan-500/50 hover:bg-slate-700/20"
                  }`}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".xlsx,.xls,.xlsm,.csv"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                  {file ? (
                    <div>
                      <p className={`font-medium text-sm ${fileValid ? "text-emerald-300" : "text-red-300"}`}>
                        {fileValid ? "✓" : "✗"} {file.name}
                      </p>
                      <p className="text-slate-400 text-xs mt-1">
                        {(file.size / 1024).toFixed(1)} KB
                        {!fileValid && " — unsupported format"}
                      </p>
                      <button
                        onClick={(e) => { e.stopPropagation(); setFile(null); }}
                        className="mt-2 text-xs text-slate-400 hover:text-red-400 transition-colors"
                      >
                        Remove
                      </button>
                    </div>
                  ) : (
                    <div>
                      <p className="text-slate-300 text-sm">Drop your file here or click to browse</p>
                      <p className="text-slate-500 text-xs mt-1">Supports .xlsx, .xls, .xlsm, .csv — max 20 MB</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Report Configuration */}
              <div className="bg-slate-800/60 backdrop-blur-xl rounded-2xl border border-cyan-500/30 p-5 space-y-4">
                <h3 className="text-white font-semibold flex items-center gap-2">
                  <span className="text-cyan-400">⚙️</span> Report Configuration
                </h3>

                {/* Report Type */}
                <div>
                  <label className="block text-cyan-300 text-xs font-medium mb-1.5 uppercase tracking-wider">
                    Report Type
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {templates.map((t) => (
                      <button
                        key={t.id}
                        onClick={() => setReportType(t.id)}
                        className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs text-left transition-all ${
                          reportType === t.id
                            ? "bg-cyan-900/50 border-cyan-500/60 text-cyan-200"
                            : "bg-slate-700/30 border-slate-600/30 text-slate-400 hover:border-slate-500/50 hover:text-slate-300"
                        }`}
                      >
                        <span>{REPORT_TYPE_ICONS[t.id] || "📄"}</span>
                        <span>{t.label}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Tone */}
                <div>
                  <label className="block text-cyan-300 text-xs font-medium mb-1.5 uppercase tracking-wider">
                    Writing Tone
                  </label>
                  <div className="flex gap-2">
                    {TONE_OPTIONS.map((t) => (
                      <button
                        key={t.id}
                        onClick={() => setTone(t.id)}
                        className={`flex-1 py-1.5 rounded-lg border text-xs transition-all ${
                          tone === t.id
                            ? "bg-blue-900/50 border-blue-500/60 text-blue-200"
                            : "bg-slate-700/30 border-slate-600/30 text-slate-400 hover:border-slate-500/50"
                        }`}
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Firm Name */}
                <div>
                  <label className="block text-cyan-300 text-xs font-medium mb-1.5 uppercase tracking-wider">
                    Firm Name
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Apex Wealth Management"
                    value={firmName}
                    onChange={(e) => setFirmName(e.target.value)}
                    className="w-full px-3 py-2 text-white bg-slate-900/70 border border-slate-600/40 rounded-lg focus:outline-none focus:border-cyan-500 text-sm placeholder:text-slate-500 transition-colors"
                  />
                </div>

                {/* Client Name */}
                <div>
                  <label className="block text-cyan-300 text-xs font-medium mb-1.5 uppercase tracking-wider">
                    Client Name
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Mr. John Smith"
                    value={clientName}
                    onChange={(e) => setClientName(e.target.value)}
                    className="w-full px-3 py-2 text-white bg-slate-900/70 border border-slate-600/40 rounded-lg focus:outline-none focus:border-cyan-500 text-sm placeholder:text-slate-500 transition-colors"
                  />
                </div>

                {/* Report Period */}
                <div>
                  <label className="block text-cyan-300 text-xs font-medium mb-1.5 uppercase tracking-wider">
                    Report Period
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Q1 2026, January 2026"
                    value={reportPeriod}
                    onChange={(e) => setReportPeriod(e.target.value)}
                    className="w-full px-3 py-2 text-white bg-slate-900/70 border border-slate-600/40 rounded-lg focus:outline-none focus:border-cyan-500 text-sm placeholder:text-slate-500 transition-colors"
                  />
                </div>

                {/* Custom Instructions */}
                <div>
                  <label className="block text-cyan-300 text-xs font-medium mb-1.5 uppercase tracking-wider">
                    Custom Instructions <span className="text-slate-500 normal-case">(optional)</span>
                  </label>
                  <textarea
                    rows={3}
                    placeholder="e.g. Focus on ESG metrics. Highlight technology sector exposure. Compare to S&P 500 benchmark."
                    value={customInstructions}
                    onChange={(e) => setCustomInstructions(e.target.value)}
                    className="w-full px-3 py-2 text-white bg-slate-900/70 border border-slate-600/40 rounded-lg focus:outline-none focus:border-cyan-500 text-sm placeholder:text-slate-500 resize-none transition-colors"
                  />
                </div>

                {/* Generate Button */}
                <button
                  onClick={handleGenerate}
                  disabled={loading || !file || !fileValid}
                  className="w-full py-3 bg-gradient-to-r from-cyan-600 to-blue-600 text-white font-semibold rounded-xl hover:from-cyan-700 hover:to-blue-700 disabled:from-slate-600 disabled:to-slate-700 disabled:cursor-not-allowed transition-all shadow-lg shadow-cyan-500/20"
                >
                  {loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Generating Report…
                    </span>
                  ) : (
                    "Generate Report"
                  )}
                </button>

                {error && (
                  <div className="bg-red-900/40 border-l-4 border-red-500 text-red-200 px-4 py-3 rounded text-sm">
                    {error}
                  </div>
                )}
              </div>

              {/* How it works */}
              <div className="bg-slate-800/40 border border-slate-600/20 rounded-2xl p-5">
                <h3 className="text-slate-300 font-semibold mb-3 text-sm">How it works</h3>
                <ol className="space-y-2 text-xs text-slate-400">
                  {[
                    "Upload your Excel or CSV file with financial data",
                    "Select the report type and configure firm/client details",
                    "AI parses your data, runs QC checks, and extracts metrics",
                    "LLM generates each section with consistent tone and structure",
                    "Download the finished report as Markdown or plain text",
                  ].map((step, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="w-5 h-5 rounded-full bg-cyan-900/50 border border-cyan-500/30 flex items-center justify-center text-cyan-400 font-bold shrink-0 mt-0.5">
                        {i + 1}
                      </span>
                      {step}
                    </li>
                  ))}
                </ol>
              </div>
            </div>

            {/* ── Right: Report Output ── */}
            <div className="lg:col-span-3">
              {!result && !loading && (
                <div className="h-full flex items-center justify-center">
                  <div className="text-center text-slate-500 py-20">
                    <div className="text-6xl mb-4">📋</div>
                    <p className="text-lg font-medium text-slate-400">Your report will appear here</p>
                    <p className="text-sm mt-2">Upload a file and click Generate Report to get started</p>
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
                    <p className="text-cyan-300 font-medium">Generating your report…</p>
                    <p className="text-slate-400 text-sm mt-2">Parsing data, running QC, writing sections</p>
                  </div>
                </div>
              )}

              {result && !loading && (
                <div className="space-y-5">
                  {/* Report Header */}
                  <div className="bg-gradient-to-r from-slate-800/80 to-slate-700/60 border border-cyan-500/30 rounded-2xl p-6">
                    <div className="flex items-start justify-between gap-4 flex-wrap">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-2xl">{REPORT_TYPE_ICONS[result.report_type] || "📄"}</span>
                          <h2 className="text-xl font-bold text-white">{result.title}</h2>
                        </div>
                        <div className="flex flex-wrap gap-3 text-xs text-slate-400 mt-2">
                          <span>🏢 {result.firm_name}</span>
                          <span>👤 {result.client_name}</span>
                          {result.report_period && <span>📅 {result.report_period}</span>}
                          {result.as_of_date && <span>📌 As of {result.as_of_date}</span>}
                          <span>💱 {result.currency}</span>
                          <span className="text-slate-500">Generated {result.generated_at}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <QCBadge
                          warnings={result.qc_warnings}
                          errors={result.qc_errors}
                          passed={result.qc_passed}
                        />
                        <button
                          onClick={() => downloadReportAsMarkdown(result)}
                          className="px-3 py-1.5 bg-slate-700/60 border border-slate-500/40 text-slate-300 rounded-lg text-xs hover:bg-slate-600/60 hover:text-white transition-colors"
                        >
                          ↓ Markdown
                        </button>
                        <button
                          onClick={() => downloadReportAsText(result)}
                          className="px-3 py-1.5 bg-slate-700/60 border border-slate-500/40 text-slate-300 rounded-lg text-xs hover:bg-slate-600/60 hover:text-white transition-colors"
                        >
                          ↓ Text
                        </button>
                      </div>
                    </div>

                    {/* Sheets processed */}
                    {result.metadata.sheets_processed.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        <span className="text-xs text-slate-500">Sheets:</span>
                        {result.metadata.sheets_processed.map((s) => (
                          <span key={s} className="px-2 py-0.5 bg-slate-700/50 border border-slate-600/30 rounded text-xs text-slate-400">
                            {s}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Mismatch / QC error banner — shown prominently when data doesn't fit the report type */}
                  {!result.qc_passed && result.qc_errors.length > 0 && (
                    <div className="bg-red-950/60 border border-red-500/40 rounded-2xl p-5">
                      <div className="flex items-start gap-3">
                        <span className="text-2xl shrink-0">⚠️</span>
                        <div>
                          <p className="text-red-300 font-semibold mb-2">Data / Report Type Mismatch</p>
                          {result.qc_errors.map((e, i) => (
                            <p key={i} className="text-red-200 text-sm leading-relaxed mb-1">{e}</p>
                          ))}
                          <p className="text-red-400 text-xs mt-3">
                            The report has still been generated using whatever data was found, but sections may contain estimated or placeholder content.
                            Please upload a file that matches the selected report type, or switch to <strong className="text-red-300">Custom Financial Report</strong> to generate a report from any data.
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Partial match warning — softer yellow banner */}
                  {result.qc_passed && result.qc_warnings.some(w => w.startsWith("Partial data match")) && (
                    <div className="bg-yellow-950/50 border border-yellow-500/30 rounded-2xl p-4">
                      <div className="flex items-start gap-3">
                        <span className="text-xl shrink-0">⚡</span>
                        <div>
                          <p className="text-yellow-300 font-semibold text-sm mb-1">Partial Data Match</p>
                          {result.qc_warnings
                            .filter(w => w.startsWith("Partial data match"))
                            .map((w, i) => (
                              <p key={i} className="text-yellow-200 text-xs leading-relaxed">{w}</p>
                            ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Executive Summary */}
                  <div className="bg-slate-800/60 border border-blue-500/30 rounded-2xl p-6">
                    <h3 className="text-blue-300 font-bold text-sm uppercase tracking-wider mb-3 flex items-center gap-2">
                      <span>⭐</span> Executive Summary
                    </h3>
                    <div className="prose prose-invert prose-sm max-w-none">
                      <ReactMarkdown
                        components={{
                          p: ({ children }) => <p className="text-slate-200 leading-relaxed mb-3">{children}</p>,
                          strong: ({ children }) => <strong className="text-white font-semibold">{children}</strong>,
                        }}
                      >
                        {result.executive_summary}
                      </ReactMarkdown>
                    </div>
                  </div>

                  {/* Sections */}
                  <div className="space-y-3">
                    {result.sections.map((section, i) => (
                      <SectionCard key={i} section={section} index={i} />
                    ))}
                  </div>

                  {/* Disclaimer */}
                  <div className="bg-slate-800/30 border border-slate-600/20 rounded-xl px-5 py-4 text-xs text-slate-500">
                    <span className="text-slate-400 font-semibold">Disclaimer: </span>
                    This report was generated by AI based on the data provided. It is for informational purposes only
                    and does not constitute financial advice, investment recommendations, or a solicitation to buy or sell
                    any securities. Always consult a qualified financial advisor before making investment decisions.
                  </div>
                </div>
              )}
            </div>
          </div>
        </main>

        <RelatedTools current="/aireporter" />

        {/* Footer */}
        <footer className="mt-0 bg-slate-900/80 border-t border-cyan-500/20">
          <div className="max-w-7xl mx-auto px-6 py-12">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
              {/* About */}
              <div>
                <h3 className="text-white font-bold text-lg mb-3 flex items-center gap-2">
                  <span className="text-2xl">📊</span>
                  About MokshaGPT
                </h3>
                <p className="text-cyan-200 text-sm leading-relaxed">
                  MokshaGPT is an advanced AI-powered platform for stock market analysis, strategy backtesting,
                  stock discovery, and financial report generation. We leverage cutting-edge language models
                  to help traders and investors make data-driven decisions.
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
                    <Link href="/aireporter" className="text-white font-semibold text-sm flex items-center gap-2">
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
                    <p className="text-slate-400 text-xs ml-7">Analyse your brokerage trade history</p>
                  </li>
                </ul>
              </div>

              {/* Technology */}
              <div>
                <h3 className="text-white font-bold text-lg mb-3">Technology</h3>
                <ul className="space-y-2 text-sm text-cyan-200">
                  {[
                    "Natural Language Processing",
                    "Excel & CSV Ingestion",
                    "Automated QC Checks",
                    "Multi-section Report Generation",
                    "Real-time Market Data",
                  ].map((t) => (
                    <li key={t} className="flex items-start gap-2">
                      <span className="text-cyan-400 mt-1">✓</span>
                      <span>{t}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Bottom bar */}
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
