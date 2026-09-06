import type { Metadata } from 'next';
import { Geist, Geist_Mono, Lora } from 'next/font/google';
import { Toaster } from 'sonner';
import './globals.css';
import { Analytics } from '@vercel/analytics/react';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
  display: 'swap',
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
  display: 'swap',
});

const lora = Lora({
  variable: '--font-lora',
  subsets: ['latin'],
  display: 'swap',
});

export const metadata: Metadata = {
  title: "Grocer — Intent-Preserving Grocery Replenishment",
  description:
    "WhatsApp consumer grocery replenishment assistant with deterministic intent verification, bounded recovery, and Swiggy Instamart integration.",
  icons: {
    icon: { url: '/logo.svg', type: 'image/svg+xml' },
    shortcut: '/logo.svg',
    apple: '/logo.svg',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${lora.variable} h-full antialiased`}
    >
      <head>
        <link rel="icon" href="/logo.svg" type="image/svg+xml" />
        <link rel="alternate icon" href="/logo.svg" />
        <link rel="apple-touch-icon" href="/logo.svg" />
      </head>
      <body className="min-h-full flex flex-col selection:bg-emerald-600 selection:text-white relative overflow-x-hidden bg-[#FAFAFA] text-zinc-900 font-sans">
        
        {/* Page Content */}
        {children}

        {/* System Notifications & Analytics */}
        <Toaster position="top-right" theme="light" richColors />
        <Analytics />
      </body>
    </html>
  );
}
