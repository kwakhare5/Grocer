"use client";

import React, { useState, useEffect } from "react";
import { MessageSquare, ArrowRight, ShieldCheck, Zap, Sparkles, CheckCircle2, Lock, ShoppingBag, ExternalLink } from "lucide-react";

export default function Home() {
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Check query params on mount (for Swiggy OAuth redirect & ticket handling)
  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const code = params.get("code");
      const state = params.get("state");
      const ticket = params.get("ticket") || params.get("connect_ticket");

      if (code && state) {
        setIsLoading(true);
        window.history.replaceState({}, "", window.location.pathname);
        fetch("/api/auth/swiggy/callback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code, state }),
        })
          .then(async (res) => {
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || "Failed to exchange authorization code");
            setIsConnected(true);
            setStatusMessage("Swiggy account linked successfully! You can now order directly on WhatsApp.");
          })
          .catch((err) => {
            setErrorMessage(err.message || "Failed to link Swiggy account. Please try again.");
          })
          .finally(() => setIsLoading(false));
      } else if (ticket) {
        setStatusMessage("WhatsApp session detected. Click below to authorize Swiggy.");
      }

      const link = params.get("t");
      if (link) {
        setLinkToken(link);
        setStatusMessage("Open from WhatsApp confirmed. Tap below to authorize Swiggy.");
      }
    }
  }, []);

  const handleConnect = async () => {
    setErrorMessage(null);

    if (!linkToken) {
      setErrorMessage(
        "Open the connect link sent by the Grocer bot on WhatsApp to link your account.",
      );
      return;
    }

    setIsLoading(true);
    try {
      const res = await fetch("/api/auth/swiggy/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: linkToken }),
      });
      const data = await res.json();
      if (!res.ok || !data.authorizeUrl) {
        throw new Error(data.error || "Could not initiate Swiggy authorization.");
      }
      // Redirect to official Swiggy OAuth 2.1 screen
      window.location.href = data.authorizeUrl;
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Connection failed. Please verify network and try again.";
      setErrorMessage(message);
      setIsLoading(false);
    }
  };

  const whatsappNumber = process.env.NEXT_PUBLIC_WHATSAPP_NUMBER || "919876543210";
  const whatsappUrl = `https://wa.me/${whatsappNumber}`;

  return (
    <div className="relative min-h-screen bg-[#0A0A0B] text-[#F4F4F5] bg-grid-pattern flex flex-col font-sans selection:bg-[#FC8019]/25 selection:text-[#FC8019]">
      {/* Sticky Navigation Bar */}
      <nav className="sticky top-0 z-50 glass-nav px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <img
            src="/logo.svg"
            alt="Grocer Logo"
            className="w-8 h-8 rounded-lg object-contain shadow-[0_0_15px_rgba(252,128,25,0.3)]"
          />
          <span className="font-semibold tracking-tight text-lg text-white">Grocer</span>
          <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-mono bg-white/5 border border-white/10 text-zinc-400">
            <span className="w-1.5 h-1.5 rounded-full bg-[#FC8019] animate-pulse"></span>
            ⚡ Powered by Swiggy Builders Club MCP
          </span>
        </div>

        <div className="flex items-center gap-4">
          <a
            href={whatsappUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-xs font-medium text-zinc-300 hover:text-white px-3.5 py-1.5 rounded-md border border-white/10 hover:border-white/20 transition-all bg-white/[0.03]"
          >
            <MessageSquare className="w-3.5 h-3.5 text-emerald-400" />
            <span>Connect WhatsApp</span>
          </a>
        </div>
      </nav>

      {/* Hero Section */}
      <main className="flex-1 max-w-5xl mx-auto px-6 pt-20 pb-28 flex flex-col items-center text-center">
        {/* Top Badge */}
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono font-medium bg-[#FC8019]/10 border border-[#FC8019]/20 text-[#FC8019] mb-8">
          <Sparkles className="w-3.5 h-3.5" />
          <span>WhatsApp Concierge for Swiggy Instamart</span>
        </div>

        {/* Main Headline */}
        <h1 className="text-4xl sm:text-6xl font-bold tracking-tight text-white max-w-3xl leading-[1.1] mb-6">
          Groceries at the speed of thought.
        </h1>

        {/* Subtitle */}
        <p className="text-lg sm:text-xl text-zinc-400 max-w-2xl leading-relaxed mb-12">
          Chat in natural English or Hinglish on WhatsApp. Real-time dark-store search, automated coupon optimization, and deterministic 3-lock checkout.
        </p>

        {/* Interactive Connection Widget */}
        <div className="w-full max-w-md p-6 rounded-2xl glass-card text-left shadow-2xl relative mb-20 border border-white/10">
          {isConnected ? (
            <div className="py-4 text-center space-y-4">
              <div className="w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 mx-auto flex items-center justify-center">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <h3 className="font-semibold text-lg text-white">Account Linked!</h3>
              <p className="text-sm text-zinc-400 leading-relaxed">
                {statusMessage || "Your Swiggy account is active. Open WhatsApp and send your grocery list to start ordering."}
              </p>
              <a
                href={whatsappUrl}
                className="inline-flex items-center justify-center gap-2 w-full py-3 px-4 rounded-xl font-medium text-black bg-white hover:bg-zinc-200 transition-all text-sm font-semibold mt-2"
              >
                <span>Chat on WhatsApp</span>
                <ArrowRight className="w-4 h-4" />
              </a>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-xs text-zinc-400 leading-relaxed text-center">
                Linking starts in WhatsApp. Open the connect link the bot sends you,
                then authorize Swiggy here.
              </p>

              {errorMessage && (
                <div className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-lg p-2.5 leading-relaxed">
                  {errorMessage}
                </div>
              )}

              <button
                type="button"
                onClick={handleConnect}
                disabled={isLoading || !linkToken}
                className="w-full py-3 px-4 rounded-xl font-semibold text-black bg-[#FC8019] hover:bg-[#ff8f33] active:scale-[0.99] transition-all text-sm flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(252,128,25,0.3)] disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              >
                {isLoading ? (
                  <span className="flex items-center gap-2">
                    <span className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin"></span>
                    <span>Connecting to Swiggy...</span>
                  </span>
                ) : (
                  <>
                    <span>Connect with Swiggy</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>

              <div className="flex items-center justify-between text-[11px] text-zinc-500 pt-1 font-mono">
                <span className="flex items-center gap-1">
                  <Lock className="w-3 h-3 text-zinc-400" />
                  AES-256 Vault
                </span>
                <span>Official OAuth 2.1 via Swiggy Builders Club</span>
              </div>
            </div>
          )}
        </div>

        {/* Bento Grid: 3 Pillars */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full text-left mb-20">
          {/* Card 1: Conversational Kirana */}
          <div className="p-6 rounded-2xl glass-card space-y-3">
            <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-white">
              <ShoppingBag className="w-5 h-5 text-[#FC8019]" />
            </div>
            <h3 className="font-semibold text-white text-base">Conversational Brain</h3>
            <p className="text-sm text-zinc-400 leading-relaxed">
              Understands everyday grocery phrasing, recipes, and Hinglish. Evaluates real dark store variants without forcing rigid commands.
            </p>
          </div>

          {/* Card 2: Wallet Champion */}
          <div className="p-6 rounded-2xl glass-card space-y-3">
            <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-white">
              <Zap className="w-5 h-5 text-amber-400" />
            </div>
            <h3 className="font-semibold text-white text-base">Wallet Champion</h3>
            <p className="text-sm text-zinc-400 leading-relaxed">
              Auto-applies the best valid Swiggy coupon. Radically stops checkout if store prices shift by even ₹1 before payment.
            </p>
          </div>

          {/* Card 3: 3-Lock Safety */}
          <div className="p-6 rounded-2xl glass-card space-y-3">
            <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-white">
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
            </div>
            <h3 className="font-semibold text-white text-base">3-Lock Payment Gate</h3>
            <p className="text-sm text-zinc-400 leading-relaxed">
              Money is never spent on text alone. Checkout requires physical WhatsApp button confirmation, delivered via Swiggy HTTPS Bridge.
            </p>
          </div>
        </div>

        {/* How It Works (3 Steps) */}
        <div className="w-full max-w-3xl text-left glass-card rounded-2xl p-8 border border-white/10 space-y-6">
          <h2 className="text-xl font-bold tracking-tight text-white">How It Works</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 pt-2">
            <div className="space-y-2">
              <span className="text-xs font-mono font-bold text-[#FC8019]">STEP 01</span>
              <h4 className="font-semibold text-white text-sm">Link Your Number</h4>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Open the connect link from the WhatsApp bot and authorize Swiggy.
              </p>
            </div>
            <div className="space-y-2">
              <span className="text-xs font-mono font-bold text-[#FC8019]">STEP 02</span>
              <h4 className="font-semibold text-white text-sm">Message on WhatsApp</h4>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Text your list, ask for recipes, or order past staples directly in chat.
              </p>
            </div>
            <div className="space-y-2">
              <span className="text-xs font-mono font-bold text-[#FC8019]">STEP 03</span>
              <h4 className="font-semibold text-white text-sm">1-Tap Pay & Track</h4>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Review your receipt card and tap the Swiggy Bridge payment link to complete.
              </p>
            </div>
          </div>
        </div>
      </main>

      {/* Minimal Footer */}
      <footer className="border-t border-white/10 py-8 px-6 text-center text-xs text-zinc-500 font-mono space-y-2">
        <div className="flex items-center justify-center gap-4">
          <span>● Systems Operational</span>
          <span>•</span>
          <span>DPDP 24h Data Minimization</span>
          <span>•</span>
          <span>Whitelisted at grocerr.vercel.app</span>
        </div>
        <p className="text-[11px] text-zinc-600">
          Independent grocery concierge powered by Swiggy Builders Club MCP.
        </p>
      </footer>
    </div>
  );
}
