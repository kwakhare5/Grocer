import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
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

export const metadata: Metadata = {
  title: "Grocer — Quick-Commerce Inventory Balancing & Proactive Restocking",
  description:
    "An end-to-end prototype exploring time-series consumption forecasting, inter-store spatial transfers, and 1-tap WhatsApp pantry restocking.",
  icons: {
    icon: '/logo.svg',
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
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
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
