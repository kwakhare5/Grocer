import type { Metadata, Viewport } from "next";
import { Fraunces, Golos_Text } from "next/font/google";
import "./globals.css";
import { Motion } from "./components/motion";

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  display: "swap",
});

const golosText = Golos_Text({
  subsets: ["latin"],
  variable: "--font-golos",
  display: "swap",
});

const title = "Grocer: Swiggy Instamart on WhatsApp";
const description =
  "Type what you need on WhatsApp. Grocer builds a live Swiggy Instamart basket with real prices and stock. No new app. Payments open next.";

export const metadata: Metadata = {
  metadataBase: new URL("https://grocerr.vercel.app"),
  title,
  description,
  applicationName: "Grocer",
  authors: [{ name: "Karan Wakhare" }],
  creator: "Karan Wakhare",
  icons: { icon: "/logo-mark.svg" },
  openGraph: {
    title,
    description,
    url: "/",
    siteName: "Grocer",
    locale: "en_IN",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
  },
  robots: { index: true, follow: true },
  alternates: { canonical: "/" },
};

export const viewport: Viewport = {
  themeColor: "#ffffff",
  colorScheme: "light",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${fraunces.variable} ${golosText.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: "document.documentElement.classList.add('js-motion')",
          }}
        />
      </head>
      <body>
        {children}
        <Motion />
      </body>
    </html>
  );
}
