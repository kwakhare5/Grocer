import type { Metadata } from 'next';
import { Outfit, Newsreader } from 'next/font/google';
import Header from '../components/Header';
import { Toaster } from 'sonner';
import './globals.css';
import { Analytics } from '@vercel/analytics/react';

const outfit = Outfit({
  variable: '--font-outfit',
  subsets: ['latin'],
  weight: ['400', '500', '600', '700', '800'],
});

const newsreader = Newsreader({
  variable: '--font-newsreader',
  subsets: ['latin'],
  style: ['normal'],
  weight: ['400', '600', '700'],
});

export const metadata: Metadata = {
  title: 'PreFill — Autonomous Household Restocking Engine',
  description: 'Predictive quick commerce inventory engine. Retain household LTV with zero-friction automated restocking.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${outfit.variable} ${newsreader.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col selection:bg-slate-900 selection:text-white relative overflow-x-hidden bg-[#FAFAFA] text-slate-900 font-sans">
        
        {/* ── Top Navigation Header ────────────────────────── */}
        <Header />

        {/* ── Page Content ─────────────────────────────────── */}
        <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 md:px-8 py-6 md:py-8 relative z-10">
          {children}
        </main>

        {/* ── System Footer ────────────────────────────────── */}
        <footer className="border-t border-slate-200 mt-auto relative z-10 bg-white">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 md:px-8 py-4 flex items-center justify-between text-xs text-slate-500 font-medium font-display">
            <span>PreFill Quick Commerce Engine</span>
            <span>Subtle SaaS CRM System · LangGraph State Machine</span>
          </div>
        </footer>

        {/* ── Toast Notifications & Analytics ──────────────── */}
        <Toaster position="top-right" richColors />
        <Analytics />
      </body>
    </html>
  );
}
