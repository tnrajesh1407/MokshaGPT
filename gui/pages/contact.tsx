import Head from "next/head";
import Link from "next/link";
import { useState } from "react";
import Header from "../components/Header";

export default function Contact() {
  const [submitted, setSubmitted] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", message: "" });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Placeholder — wire up to a backend or email service as needed
    setSubmitted(true);
  };

  return (
    <>
      <Head>
        <title>Contact | MokshaGPT</title>
        <meta name="description" content="Get in touch with the MokshaGPT team." />
      </Head>

      <div className="min-h-screen bg-gradient-to-br from-indigo-950 via-slate-900 to-gray-900">
        <Header />

        <main className="max-w-xl mx-auto px-6 py-14">
          <h2 className="text-4xl font-extrabold text-white mb-2">Contact Us</h2>
          <p className="text-cyan-400 text-sm mb-10">Have a question or feedback? We&apos;d love to hear from you.</p>

          {submitted ? (
            <div className="bg-emerald-900/40 border border-emerald-500/40 rounded-2xl p-8 text-center">
              <p className="text-emerald-300 text-xl font-semibold mb-2">Message sent!</p>
              <p className="text-slate-400 text-sm">Thanks for reaching out. We'll get back to you soon.</p>
              <Link href="/" className="inline-block mt-6 text-cyan-400 hover:text-white transition-colors text-sm">← Back to Home</Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="bg-slate-800/60 backdrop-blur-xl rounded-2xl border border-cyan-500/30 p-8 space-y-5 shadow-2xl">
              <div>
                <label className="block text-cyan-300 text-sm font-medium mb-1">Name</label>
                <input
                  type="text"
                  required
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Your name"
                  className="w-full px-4 py-3 text-white bg-slate-900/70 border-2 border-cyan-500/30 rounded-xl focus:outline-none focus:border-cyan-500 transition-all placeholder:text-slate-500"
                />
              </div>

              <div>
                <label className="block text-cyan-300 text-sm font-medium mb-1">Email</label>
                <input
                  type="email"
                  required
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  placeholder="you@example.com"
                  className="w-full px-4 py-3 text-white bg-slate-900/70 border-2 border-cyan-500/30 rounded-xl focus:outline-none focus:border-cyan-500 transition-all placeholder:text-slate-500"
                />
              </div>

              <div>
                <label className="block text-cyan-300 text-sm font-medium mb-1">Message</label>
                <textarea
                  rows={5}
                  required
                  value={form.message}
                  onChange={(e) => setForm({ ...form, message: e.target.value })}
                  placeholder="How can we help?"
                  className="w-full px-4 py-3 text-white bg-slate-900/70 border-2 border-cyan-500/30 rounded-xl focus:outline-none focus:border-cyan-500 transition-all placeholder:text-slate-500 resize-none"
                />
              </div>

              <button
                type="submit"
                className="w-full py-3 bg-gradient-to-r from-cyan-600 to-blue-600 text-white font-semibold rounded-xl hover:from-cyan-700 hover:to-blue-700 transition-all shadow-lg shadow-cyan-500/30"
              >
                Send Message
              </button>
            </form>
          )}
        </main>

        <footer className="mt-20 bg-slate-900/80 border-t border-cyan-500/20">
          <div className="max-w-7xl mx-auto px-6 py-6 flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-cyan-300 text-sm">© 2026 MokshaGPT. All rights reserved.</p>
            <div className="flex gap-6 text-sm text-cyan-300">
              <Link href="/privacy" className="hover:text-white transition-colors">Privacy Policy</Link>
              <Link href="/terms" className="hover:text-white transition-colors">Terms of Service</Link>
              <Link href="/contact" className="text-white font-semibold border-b border-cyan-400">Contact</Link>
            </div>
          </div>
        </footer>
      </div>
    </>
  );
}
