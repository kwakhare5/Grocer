import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import Link from 'next/link';
import ChatDrawer from '../components/ChatDrawer';
import './globals.css';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  title: 'Instamart Intelligence',
  description: 'Household grocery consumption forecasting — AI that knows your kitchen.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col selection:bg-accent selection:text-white">

        {/* ── Top Nav ──────────────────────────────────────── */}
        <header className="border-b border-border bg-surface/90 backdrop-blur-sm sticky top-0 z-50">
          <div className="max-w-6xl mx-auto px-6 h-12 flex items-center justify-between">
            <div className="flex items-center gap-6">
              <Link href="/" className="font-data text-xs font-bold text-accent tracking-widest uppercase">
                Instamart_INTEL
              </Link>
              <span className="font-data text-[10px] text-muted hidden sm:inline tracking-widest uppercase">
                <span className="text-ok">●</span> Online · 34 items modeled
              </span>
            </div>
            <nav className="flex items-center gap-5 font-data text-[11px] uppercase tracking-widest">
              <Link href="/"             className="text-muted hover:text-accent transition-colors">Index</Link>
              <Link href="/household"    className="text-muted hover:text-accent transition-colors">Household</Link>
              <Link href="/predictions"  className="text-muted hover:text-accent transition-colors">Predictions</Link>
              <Link href="/recipes"      className="text-muted hover:text-accent transition-colors hidden sm:inline">Recipes</Link>
              <Link href="/price-alerts" className="text-muted hover:text-accent transition-colors hidden sm:inline">Prices</Link>
            </nav>
          </div>
        </header>

        {/* ── Page Content ─────────────────────────────────── */}
        <main className="flex-1 w-full max-w-6xl mx-auto px-6 py-12">
          {children}
        </main>

        {/* ── System Footer ────────────────────────────────── */}
        <footer className="border-t border-border mt-auto">
          <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between font-data text-[10px] text-muted uppercase tracking-widest">
            <span>Instamart Intelligence · Swiggy Builders Club Demo</span>
            <span>4mo data · Prophet + LangGraph + Claude</span>
          </div>
        </footer>

        {/* ── Chat Sandbox Drawer ─────────────────────────── */}
        <ChatDrawer />

      </body>
    </html>

  );
}
