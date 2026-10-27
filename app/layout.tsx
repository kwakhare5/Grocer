import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Grocer — Instamart on WhatsApp",
  description: "AI-powered grocery concierge for Swiggy Instamart on WhatsApp. Instant dark-store search, automated coupon optimization, and 1-tap checkout.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#0A0A0B] text-[#F4F4F5] antialiased selection:bg-[#FC8019]/20 selection:text-[#FC8019]">
        {children}
      </body>
    </html>
  );
}
