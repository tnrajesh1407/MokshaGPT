import Head from "next/head";
import Link from "next/link";
import Header from "../components/Header";

export default function PrivacyPolicy() {
  return (
    <>
      <Head>
        <title>Privacy Policy | MokshaGPT</title>
        <meta name="description" content="Privacy Policy for MokshaGPT - Stock Market Insights by AI" />
      </Head>

      <div className="min-h-screen bg-gradient-to-br from-indigo-950 via-slate-900 to-gray-900">
        <Header />

        <main className="max-w-3xl mx-auto px-6 py-14">
          <h2 className="text-4xl font-extrabold text-white mb-2">Privacy Policy</h2>
          <p className="text-cyan-400 text-sm mb-10">Last updated: April 2026</p>

          <div className="space-y-8 text-slate-300 leading-relaxed">
            <section>
              <h3 className="text-white font-semibold text-lg mb-2">1. Information We Collect</h3>
              <p>MokshaGPT does not collect personally identifiable information. When you use our platform, we may collect anonymous usage data such as query types and feature interactions solely to improve the service.</p>
            </section>

            <section>
              <h3 className="text-white font-semibold text-lg mb-2">2. How We Use Information</h3>
              <p>Any data collected is used exclusively to improve platform performance and user experience. We do not sell, trade, or share your data with third parties.</p>
            </section>

            <section>
              <h3 className="text-white font-semibold text-lg mb-2">3. Third-Party Services</h3>
              <p>MokshaGPT uses third-party APIs (such as Yahoo Finance) to fetch market data. These services have their own privacy policies, and we encourage you to review them.</p>
            </section>

            <section>
              <h3 className="text-white font-semibold text-lg mb-2">4. Cookies</h3>
              <p>We may use minimal cookies to maintain session state. No tracking or advertising cookies are used.</p>
            </section>

            <section>
              <h3 className="text-white font-semibold text-lg mb-2">5. Data Security</h3>
              <p>We take reasonable measures to protect any data processed through our platform. However, no internet transmission is 100% secure, and we cannot guarantee absolute security.</p>
            </section>

            <section>
              <h3 className="text-white font-semibold text-lg mb-2">6. Changes to This Policy</h3>
              <p>We may update this Privacy Policy from time to time. Changes will be reflected on this page with an updated date.</p>
            </section>

            <section>
              <h3 className="text-white font-semibold text-lg mb-2">7. Contact</h3>
              <p>If you have any questions about this Privacy Policy, please <Link href="/contact" className="text-cyan-400 hover:text-white transition-colors">contact us</Link>.</p>
            </section>
          </div>
        </main>

        <footer className="mt-20 bg-slate-900/80 border-t border-cyan-500/20">
          <div className="max-w-7xl mx-auto px-6 py-6 flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-cyan-300 text-sm">© 2026 MokshaGPT. All rights reserved.</p>
            <div className="flex gap-6 text-sm text-cyan-300">
              <Link href="/privacy" className="text-white font-semibold border-b border-cyan-400">Privacy Policy</Link>
              <Link href="/terms" className="hover:text-white transition-colors">Terms of Service</Link>
              <Link href="/contact" className="hover:text-white transition-colors">Contact</Link>
            </div>
          </div>
        </footer>
      </div>
    </>
  );
}
