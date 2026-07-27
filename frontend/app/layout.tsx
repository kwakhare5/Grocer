import type { Metadata } from 'next';
import { Outfit, Cambo, Instrument_Serif } from 'next/font/google';
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

const instrumentSerif = Instrument_Serif({
  variable: '--font-instrument-serif',
  subsets: ['latin'],
  weight: ['400'],
  style: ['italic'],
});

export const metadata: Metadata = {
  title: 'PreFill — Build and deploy reliable AI restock agents',
  description: 'The all-in-one platform for customer-facing AI restocking agents across any channel. Launch and monitor your first agent in minutes.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${outfit.variable} ${cambo.variable} ${instrumentSerif.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col selection:bg-[#252525] selection:text-white relative overflow-x-hidden bg-[#F6F7F8] text-[#252525] font-sans">
        
        {/* Page Content */}
        {children}

        {/* System Notifications & Analytics */}
        <Toaster position="top-right" theme="light" richColors />
        <Analytics />
      </body>
    </html>
  );
}
