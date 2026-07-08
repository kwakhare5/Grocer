import type { Metadata } from 'next';
import { Inter, Outfit, Geist_Mono } from 'next/font/google';
import ChatDrawer from '../components/ChatDrawer';
import Header from '../components/Header';
import './globals.css';

const inter = Inter({
  variable: '--font-sans',
  subsets: ['latin'],
});

const outfit = Outfit({
  variable: '--font-display',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  title: 'PreFill Pantry Assistant',
  description: 'Your household helper that knows what you need before you run out.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${outfit.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col selection:bg-accent selection:text-white relative overflow-x-hidden">
        
        {/* Backdrop Glow Blobs */}
        <div className="glow-blob top-[-100px] left-[-100px] w-[350px] h-[350px] bg-accent" />
        <div className="glow-blob top-[400px] right-[-100px] w-[300px] h-[300px] bg-amber-500/80" />

        {/* ── Top Nav ──────────────────────────────────────── */}
        <Header />

        {/* ── Page Content ─────────────────────────────────── */}
        <main className="flex-1 w-full max-w-6xl mx-auto px-6 py-10 md:py-12 relative z-10">
          {children}
        </main>

        {/* ── System Footer ────────────────────────────────── */}
        <footer className="border-t border-border mt-auto relative z-10 bg-surface/40 backdrop-blur-sm">
          <div className="max-w-6xl mx-auto px-6 py-5 flex items-center justify-between text-xs text-muted font-medium">
            <span>PreFill Pantry Assistant</span>
            <span>Automatically keeping your pantry stocked</span>
          </div>
        </footer>

        {/* ── Chat Sandbox Drawer ─────────────────────────── */}
        <ChatDrawer />

      </body>
    </html>
  );
}
