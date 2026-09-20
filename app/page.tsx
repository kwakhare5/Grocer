"use client";

import React, { useEffect, useState, FormEvent } from "react";
import { AppGlobalHeader } from "../components/navigation/AppGlobalHeader";
import {
  ArrowRight,
  CheckCircle2,
  MessageCircle,
  Loader2,
  ShieldCheck,
  Sparkles,
  RefreshCw,
  ShoppingBag,
} from "lucide-react";

const whatsappNumber = process.env.NEXT_PUBLIC_WHATSAPP_NUMBER;
const whatsappUrl = whatsappNumber
  ? `https://wa.me/${whatsappNumber}?text=${encodeURIComponent("Hi Grocer!")}`
  : null;

export default function Home() {
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    let mounted = true;
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");

    if (code && state) {
      window.setTimeout(() => {
        if (mounted) {
          setBusy(true);
          setError(null);
        }
      }, 0);
      fetch("/api/auth/swiggy/callback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, state }),
      })
        .then((res) => {
          if (!res.ok) throw new Error("Unable to link your Swiggy account. Please try again.");
          return res.json();
        })
        .then((data) => {
          if (data.success) {
            if (mounted) setIsConnected(true);
            window.history.replaceState({}, document.title, window.location.pathname);
          } else {
            throw new Error("Unable to link your Swiggy account. Please try again.");
          }
        })
        .catch((err) => {
          if (mounted) {
            setError(
              err instanceof Error
                ? err.message
                : "Unable to link your Swiggy account. Please try again.",
            );
          }
        })
        .finally(() => {
          if (mounted) setBusy(false);
        });
    }
    return () => {
      mounted = false;
    };
  }, []);

  const handlePhoneChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let digits = e.target.value.replace(/\D/g, "");
    if (digits.startsWith("91") && digits.length > 10) {
      digits = digits.slice(2);
    }
    if (digits.startsWith("0") && digits.length > 10) {
      digits = digits.slice(1);
    }
    if (digits.length > 10) {
      digits = digits.slice(0, 10);
    }
    setPhone(digits);
    if (error) setError(null);
  };

  const handleConnect = async (e: FormEvent) => {
    e.preventDefault();
    if (!phone || phone.length !== 10) {
      setError("Please enter your 10-digit phone number");
      return;
    }

    setBusy(true);
    setError(null);

    try {
      const formattedPhone = `91${phone}`;
      const res = await fetch("/api/auth/swiggy/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone_number: formattedPhone }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(
          errorData.error || "Unable to start the Swiggy connection. Please try again.",
        );
      }

      const data = await res.json();
      if (data.authorize_url) {
        window.location.href = data.authorize_url;
      } else {
        throw new Error("Unable to start the Swiggy connection. Please try again.");
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to start the Swiggy connection. Please try again.",
      );
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FAFAFA] text-zinc-900 flex flex-col font-sans">
      <AppGlobalHeader />

      <main className="flex-1">
        {/* Hero Section */}
        <section className="pt-16 pb-20 px-4 sm:px-6 lg:px-8 max-w-6xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
            {/* Left: Value Proposition */}
            <div className="lg:col-span-7 space-y-6">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-medium">
                <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
                <span>Smart replenishment on Swiggy Instamart</span>
              </div>

              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-editorial font-bold text-zinc-950 tracking-tight leading-[1.15]">
                Weekly groceries on WhatsApp.
              </h1>

              <p className="text-base sm:text-lg text-zinc-600 leading-relaxed max-w-xl">
                Text what you need in plain English. Grocer checks live Swiggy Instamart options, explains anything that changes, and asks before every user-facing decision.
              </p>

              <div className="pt-2 flex flex-wrap items-center gap-6 text-xs text-zinc-500">
                <span className="flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  No checkout without approval
                </span>
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  Hard budget limits
                </span>
                <span className="flex items-center gap-1.5">
                  <RefreshCw className="w-4 h-4 text-emerald-600" />
                  Clear out-of-stock choices
                </span>
              </div>
            </div>

            {/* Right: Swiggy Connect Card */}
            <div className="lg:col-span-5">
              <div className="bg-white rounded-3xl p-6 sm:p-8 border border-zinc-200 shadow-lg shadow-zinc-100/80">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-10 h-10 rounded-2xl bg-orange-50 flex items-center justify-center text-[#fc8019]">
                    <ShoppingBag className="w-5 h-5" />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-zinc-950 leading-tight">
                      Connect your account
                    </h2>
                    <p className="text-xs text-zinc-500">
                      Link Swiggy Instamart to your WhatsApp
                    </p>
                  </div>
                </div>

                {error && (
                  <div
                    className="mb-5 rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-800"
                    role="alert"
                    aria-live="assertive"
                  >
                    {error}
                  </div>
                )}

                {isConnected ? (
                  <div className="space-y-4">
                    <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 flex items-center gap-3 text-emerald-800 text-sm font-semibold">
                      <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0" />
                      <span>Swiggy account connected</span>
                    </div>

                    {whatsappUrl ? (
                      <a
                        href={whatsappUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="w-full flex items-center justify-center gap-2 rounded-xl bg-[#25D366] px-4 py-3.5 text-sm font-semibold text-white hover:bg-[#1ebd59] transition shadow-xs"
                      >
                        <MessageCircle className="h-4 w-4" />
                        <span>Start on WhatsApp</span>
                      </a>
                    ) : (
                      <p className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 text-center text-sm text-zinc-600">
                        WhatsApp access will be available when GROCER is configured for this environment.
                      </p>
                    )}
                  </div>
                ) : (
                  <form onSubmit={handleConnect} className="space-y-4">
                    <div>
                      <label htmlFor="whatsapp-phone" className="block text-xs font-semibold text-zinc-700 mb-2">
                        WhatsApp Phone Number
                      </label>
                      <div className="flex rounded-xl border border-zinc-200 bg-zinc-50 focus-within:border-emerald-500 focus-within:bg-white focus-within:ring-2 focus-within:ring-emerald-500/10 transition">
                        <span className="inline-flex items-center px-3.5 bg-zinc-100 border-r border-zinc-200 rounded-l-xl text-zinc-700 font-mono text-sm font-semibold select-none">
                          +91
                        </span>
                        <input
                          id="whatsapp-phone"
                          name="whatsapp-phone"
                          type="tel"
                          inputMode="numeric"
                          maxLength={10}
                          placeholder="8237803170"
                          value={phone}
                          onChange={handlePhoneChange}
                          disabled={busy}
                          required
                          aria-invalid={Boolean(error)}
                          aria-describedby="whatsapp-phone-help"
                          className="w-full bg-transparent px-3.5 py-3 text-sm font-mono text-zinc-900 placeholder:text-zinc-400 outline-none"
                        />
                      </div>
                      <p id="whatsapp-phone-help" className="mt-1.5 text-[11px] text-zinc-500">
                        Enter your 10-digit mobile number
                      </p>
                    </div>

                    <button
                      type="submit"
                      disabled={busy || phone.length !== 10}
                      className="w-full flex items-center justify-center gap-2 rounded-xl bg-[#fc8019] hover:bg-[#e47112] px-4 py-3.5 text-sm font-semibold text-white transition shadow-xs disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                    >
                      {busy ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          <span>Connecting...</span>
                        </>
                      ) : (
                        <>
                          <span>Connect Swiggy Instamart</span>
                          <ArrowRight className="h-4 w-4" />
                        </>
                      )}
                    </button>

                    <p className="text-[11px] text-zinc-500 text-center leading-relaxed">
                      Safe checkout. Grocer never places an order without your explicit confirmation.
                    </p>
                  </form>
                )}
              </div>
            </div>
          </div>
        </section>

        {/* How It Works */}
        <section className="py-16 bg-white border-y border-zinc-200">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-2xl mx-auto mb-12">
              <h2 className="text-2xl sm:text-3xl font-editorial font-bold text-zinc-950">
                How it works
              </h2>
              <p className="mt-2 text-sm text-zinc-600">
                Replenish your household groceries in three simple steps.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="bg-[#FAFAFA] rounded-2xl p-6 border border-zinc-200">
                <div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-800 flex items-center justify-center text-sm font-bold mb-4">
                  1
                </div>
                <h3 className="text-base font-semibold text-zinc-900 mb-2">
                  Link your account
                </h3>
                <p className="text-sm text-zinc-600 leading-relaxed">
                  Connect your Swiggy Instamart account once to use your saved addresses and shop through WhatsApp.
                </p>
              </div>

              <div className="bg-[#FAFAFA] rounded-2xl p-6 border border-zinc-200">
                <div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-800 flex items-center justify-center text-sm font-bold mb-4">
                  2
                </div>
                <h3 className="text-base font-semibold text-zinc-900 mb-2">
                  Text what you need
                </h3>
                <p className="text-sm text-zinc-600 leading-relaxed">
                  Send a WhatsApp message like &ldquo;weekly groceries under ₹2,000, vegetarian, use my usual brands.&rdquo;
                </p>
              </div>

              <div className="bg-[#FAFAFA] rounded-2xl p-6 border border-zinc-200">
                <div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-800 flex items-center justify-center text-sm font-bold mb-4">
                  3
                </div>
                <h3 className="text-base font-semibold text-zinc-900 mb-2">
                  Review and confirm
                </h3>
                <p className="text-sm text-zinc-600 leading-relaxed">
                  Grocer shows any unavailable-item choices, verifies the live cart, and waits for your confirmation before checkout.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* WhatsApp Experience Preview */}
        <section className="py-20 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <h2 className="text-2xl sm:text-3xl font-editorial font-bold text-zinc-950">
              Natural conversation on WhatsApp
            </h2>
            <p className="mt-2 text-sm text-zinc-600">
              No endless search menus. Just text your shopping list and review the cart.
            </p>
          </div>

          <figure className="max-w-md mx-auto" aria-label="Example GROCER conversation. The buttons shown are not interactive.">
            <figcaption className="mb-3 text-center text-xs text-zinc-500">
              Example conversation — shown for illustration only.
            </figcaption>
            <div className="bg-[#EFEAE2] rounded-3xl overflow-hidden border border-zinc-300 shadow-xl">
            {/* WhatsApp Header */}
            <div className="bg-[#075E54] px-4 py-3 flex items-center justify-between text-white">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-emerald-700 flex items-center justify-center text-white font-bold text-sm">
                  G
                </div>
                <div>
                  <div className="font-semibold text-sm leading-tight">Grocer</div>
                  <div className="text-[11px] text-emerald-200">Online</div>
                </div>
              </div>
              <div className="text-xs text-emerald-200">WhatsApp</div>
            </div>

            {/* Chat Body */}
            <div className="p-4 space-y-3 text-xs leading-relaxed">
              {/* User message */}
              <div className="flex justify-end">
                <div className="bg-[#D9FDD3] text-zinc-900 rounded-2xl rounded-tr-xs px-3.5 py-2.5 max-w-[85%] shadow-xs">
                  <p>I want to make pasta tonight, budget under ₹1,500. Get the ingredients!</p>
                  <span className="block text-[10px] text-zinc-400 text-right mt-1">8:11 PM</span>
                </div>
              </div>

              {/* Grocer response */}
              <div className="flex justify-start">
                <div className="bg-white text-zinc-900 rounded-2xl rounded-tl-xs px-3.5 py-2.5 max-w-[92%] shadow-xs space-y-2">
                  <p>I&apos;ve picked 7 fresh ingredients from your local Swiggy Instamart store:</p>
                  <div className="space-y-1 bg-zinc-50 p-2.5 rounded-xl border border-zinc-100 text-[11px]">
                    <div className="flex justify-between"><span>• Barilla Penne Rigate (500g)</span><span className="font-mono">₹275</span></div>
                    <div className="flex justify-between"><span>• Barilla Basilico Sauce (400g)</span><span className="font-mono">₹295</span></div>
                    <div className="flex justify-between"><span>• Borges Extra Virgin Olive Oil (250ml)</span><span className="font-mono">₹380</span></div>
                    <div className="flex justify-between"><span>• D&apos;lecta Mozzarella (200g)</span><span className="font-mono">₹195</span></div>
                    <div className="flex justify-between"><span>• Fresh Garlic (100g)</span><span className="font-mono">₹25</span></div>
                    <div className="flex justify-between"><span>• Fresh Basil (50g)</span><span className="font-mono">₹30</span></div>
                    <div className="flex justify-between"><span>• Cherry Tomatoes (250g)</span><span className="font-mono">₹45</span></div>
                  </div>
                  <div className="border-t border-zinc-100 pt-1.5 flex justify-between font-semibold text-zinc-800">
                    <span>Total (within ₹1,500 budget)</span>
                    <span className="font-mono text-emerald-700">₹1,245</span>
                  </div>
                  <p className="text-[10px] text-zinc-500">Delivering to: Home (10-15 mins)</p>
                  <p className="text-[11px] font-medium text-zinc-800">Would you like me to place this order?</p>
                  <span className="block text-[10px] text-zinc-400 text-right">8:12 PM</span>
                </div>
              </div>

              {/* User reply */}
              <div className="flex justify-end">
                <div className="bg-[#D9FDD3] text-zinc-900 rounded-2xl rounded-tr-xs px-3.5 py-2 max-w-[60%] shadow-xs text-center font-medium">
                  <p>Yes, order it!</p>
                  <span className="block text-[10px] text-zinc-400 text-right mt-0.5">8:12 PM</span>
                </div>
              </div>

              {/* Grocer payment link */}
              <div className="flex justify-start">
                <div className="bg-white text-zinc-900 rounded-2xl rounded-tl-xs px-3.5 py-2.5 max-w-[92%] shadow-xs space-y-2">
                  <p className="text-emerald-700 font-semibold">Order created!</p>
                  <p className="text-[11px] text-zinc-600">Tap below to complete payment via UPI:</p>
                  <a
                    href="upi://pay?pa=swiggy@icici&pn=SwiggyInstamart&am=1245&cu=INR"
                    className="block bg-emerald-50 border border-emerald-300 hover:bg-emerald-100 rounded-xl p-2.5 text-center transition-colors"
                  >
                    <span className="font-mono text-xs font-semibold text-emerald-800">👉 Pay ₹1,245 via UPI</span>
                  </a>
                  <span className="block text-[10px] text-zinc-400 text-right">8:13 PM</span>
                </div>
              </div>
            </div>
            </div>
          </figure>
        </section>

        {/* Three Core Commitments */}
        <section className="py-16 bg-white border-t border-zinc-200">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="p-6 rounded-2xl border border-zinc-200 bg-[#FAFAFA]">
                <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center mb-4">
                  <CheckCircle2 className="w-5 h-5" />
                </div>
                <h3 className="text-base font-semibold text-zinc-900 mb-2">
                  Budget and diet limits
                </h3>
                <p className="text-sm text-zinc-600 leading-relaxed">
                  Set a price limit or dietary rule. Grocer checks the live cart and asks if a change would affect it.
                </p>
              </div>

              <div className="p-6 rounded-2xl border border-zinc-200 bg-[#FAFAFA]">
                <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center mb-4">
                  <RefreshCw className="w-5 h-5" />
                </div>
                <h3 className="text-base font-semibold text-zinc-900 mb-2">
                  Smart replacements
                </h3>
                <p className="text-sm text-zinc-600 leading-relaxed">
                  When an item is sold out, Grocer finds matching alternatives from Instamart and asks for your choice.
                </p>
              </div>

              <div className="p-6 rounded-2xl border border-zinc-200 bg-[#FAFAFA]">
                <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center mb-4">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <h3 className="text-base font-semibold text-zinc-900 mb-2">
                  Confirmation before checkout
                </h3>
                <p className="text-sm text-zinc-600 leading-relaxed">
                  You review the final cart and total price on WhatsApp. Nothing is ordered until you approve it.
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Clean Footer */}
      <footer className="bg-[#FAFAFA] border-t border-zinc-200 py-8 px-4 sm:px-6 lg:px-8 text-center text-xs text-zinc-500">
        <p className="max-w-md mx-auto leading-relaxed">
          Grocer connects to Swiggy Instamart through the Builders Club MCP.
        </p>
        <p className="mt-2 text-zinc-400">
          © {new Date().getFullYear()} Grocer. All rights reserved.
        </p>
      </footer>
    </div>
  );
}
