import type { Metadata } from 'next';
import { Geist, Geist_Mono, Lora } from 'next/font/google';
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
  title: "Grocer — Intent-Preserving WhatsApp Grocery Assistant",
  description:
    "WhatsApp grocery assistant for Swiggy Instamart. Preserves intent across messages; checkout needs explicit confirmation.",
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
      <body className="min-h-full flex flex-col selection:bg-emerald-600 selection:text-white relative overflow-x-hidden bg-matte-grain text-zinc-900 font-sans">
        
        {/* Page Content */}
        {children}

        <Analytics />
      </body>
    </html>
  );
}
