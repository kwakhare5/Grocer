import type { Metadata } from 'next';
import { Inter, Manrope, Newsreader } from 'next/font/google';
import ChatDrawer from '../components/ChatDrawer';
import Header from '../components/Header';
import './globals.css';
import { Analytics } from '@vercel/analytics/react';

const inter = Inter({
  variable: '--font-sans',
  subsets: ['latin'],
});

const manrope = Manrope({
  variable: '--font-manrope',
  subsets: ['latin'],
  weight: ['400', '700', '800'],
});

const newsreader = Newsreader({
  variable: '--font-newsreader',
  subsets: ['latin'],
  weight: ['400', '700'],
});

export const metadata: Metadata = {
  title: 'PreFill Pantry Assistant',
  description: 'Your helper that knows what you need before you run out.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${manrope.variable} ${newsreader.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col selection:bg-accent selection:text-white relative overflow-x-hidden">
        
        {/* ── Top Nav ──────────────────────────────────────── */}
        <Header />

        {/* ── Page Content ─────────────────────────────────── */}
        <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 md:px-8 py-10 md:py-12 relative z-10">
          {children}
        </main>

        {/* ── System Footer ────────────────────────────────── */}
        <footer className="border-t border-border mt-auto relative z-10 bg-surface/40 backdrop-blur-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 md:px-8 py-5 flex items-center justify-between text-xs text-muted font-medium">
            <span>PreFill Pantry Assistant</span>
            <span>Automatically keeping your pantry stocked</span>
          </div>
        </footer>

        {/* ── Chat Sandbox Drawer ─────────────────────────── */}
        <ChatDrawer />
        <Analytics />
      </body>
    </html>
  );
}
