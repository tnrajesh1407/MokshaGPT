import Head from "next/head";
import Link from "next/link";
import Header from "../components/Header";

export default function TermsOfService() {
  return (
    <>
      <Head>
        <title>Terms of Service | MokshaGPT</title>
        <meta name="description" content="Terms of Service for MokshaGPT - Stock Market Insights by AI" />
      </Head>

      <div className="min-h-screen bg-gradient-to-br from-indigo-950 via-slate-900 to-gray-900">
        <Header />

        <main className="max-w-3xl mx-auto px-6 py-14">
          <h2 className="text-4xl font-extrabold text-white mb-2">Terms of Service</h2>
          <p className="text-cyan-400 text-sm mb-10">Last updated: April 2026</p>

          <div className="space-y-8 text-slate-300 leading-relaxed">
            <section>
              <h3 className="text-white font-semibold text-lg mb-2">1. Acceptance of Terms</h3>
              <p>By accessing or using MokshaGPT, you agree to be bound by these Terms of Service. If you do not agree, please do not use the platform.</p>
            </section>

            <section>
              <h3 className="text-white font-semibold text-lg mb-2">2. Not Financial Advice</h3>
              <p>All content provided by MokshaGPT — including stock analysis, backtesting results, and screener outputs — is for <span className="text-white font-medium">informational and educational purposes only</span>. Nothing on this platform constitutes financial, investment, or trading advice. Always consult a qualified financial advisor before making investment decisions.</p>
            </section>

            <section>
              <h3 className="text-white font-semibold text-lg mb-2">3. Use of the Platform</h3>
              <p>You agree to use MokshaGPT only for lawful purposes. You must not misuse the platform, attempt to disrupt its services, or use it in any way that violates applicable laws or regulations.</p>
            </section>

            <section>
              <h3 className="text-white font-semibold text-lg mb-2">4. Accuracy of Information</h3>
              <p>While we strive to provide accurate and up-to-date market data, MokshaGPT makes no warranties regarding the completeness, accuracy, or reliability of any information provided. Market data is sourced from third-party providers and may be delayed or incorrect.</p>
            </section>

            <section>
              <h3 className="text-white font-semibold text-lg mb-2">5. Limitation of Liability</h3>
              <p>MokshaGPT and its creators shall not be liable for any losses or damages arising from your use of the platform, including but not limited to financial losses resulting from trading decisions made based on information provided here.</p>
            </section>

            <section>
              <h3 className="text-white font-semibold text-lg mb-2">6. Intellectual Property</h3>
              <p>All content, design, and code on MokshaGPT is the property of its creators. You may not reproduce or distribute any part of the platform without prior written permission.</p>
            </section>

            <section>
              <h3 className="text-white font-semibold text-lg mb-2">7. Changes to Terms</h3>
              <p>We reserve the right to modify these Terms at any time. Continued use of the platform after changes constitutes acceptance of the updated Terms.</p>
            </section>

            <section>
              <h3 className="text-white font-semibold text-lg mb-2">8. Contact</h3>
              <p>For questions about these Terms, please <Link href="/contact" className="text-cyan-400 hover:text-white transition-colors">contact us</Link>.</p>
            </section>
          </div>
        </main>

        <footer className="mt-20 bg-slate-900/80 border-t border-cyan-500/20">
          <div className="max-w-7xl mx-auto px-6 py-6 flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-cyan-300 text-sm">© 2026 MokshaGPT. All rights reserved.</p>
            <div className="flex gap-6 text-sm text-cyan-300">
              <Link href="/privacy" className="hover:text-white transition-colors">Privacy Policy</Link>
              <Link href="/terms" className="text-white font-semibold border-b border-cyan-400">Terms of Service</Link>
              <Link href="/contact" className="hover:text-white transition-colors">Contact</Link>
            </div>
          </div>
        </footer>
      </div>
    </>
  );
}
