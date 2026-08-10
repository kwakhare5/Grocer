import type { Metadata } from 'next';
import { Outfit, Cambo } from 'next/font/google';
import { Toaster } from 'sonner';
import './globals.css';
import { Analytics } from '@vercel/analytics/react';

const outfit = Outfit({
  variable: '--font-outfit',
  subsets: ['latin'],
  weight: ['400', '500', '600', '700', '800'],
});

const cambo = Cambo({
  variable: '--font-cambo',
  subsets: ['latin'],
  weight: ['400'],
});

export const metadata: Metadata = {
  title: 'PreFill — Predictive Household Inventory Engine for Quick Commerce',
  description: 'PreFill models daily household grocery depletion velocity to trigger automated 1-tap WhatsApp restocking before items run out.',
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
      className={`${outfit.variable} ${cambo.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col selection:bg-gray-950 selection:text-white relative overflow-x-hidden bg-[#FAFAFA] text-gray-900 font-sans">
        
        {/* Page Content */}
        {children}

        {/* System Notifications & Analytics */}
        <Toaster position="top-right" theme="light" richColors />
        <Analytics />
      </body>
    </html>
  );
}
