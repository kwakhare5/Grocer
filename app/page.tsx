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
      setTimeout(() => setBusy(true), 0);
      fetch("/api/auth/swiggy/callback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, state }),
      })
        .then((res) => {
          if (!res.ok) throw new Error("Failed to link Swiggy account");
          return res.json();
        })
        .then((data) => {
          if (data.success) {
            if (mounted) setIsConnected(true);
            window.history.replaceState({}, document.title, window.location.pathname);
          } else {
            throw new Error(data.error || "Failed to link Swiggy account");
          }
        })
        .catch((err) => {
          if (mounted) setError(err instanceof Error ? err.message : "Connection failed");
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
        throw new Error(errorData.error || errorData.detail || "Unable to initiate Swiggy connection");
      }

      const data = await res.json();
      if (data.authorize_url) {
        window.location.href = data.authorize_url;
      } else {
        throw new Error("Missing authorization redirect link");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connection error");
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
                Text what you need in plain words. Grocer finds your items on Swiggy Instamart, swaps out-of-stock items within your budget, and asks for your approval before checkout.
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
                  Smart out-of-stock swaps
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
                  <div className="mb-5 rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-800">
                    {error}
                  </div>
                )}

                {isConnected ? (
                  <div className="space-y-4">
                    <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 flex items-center gap-3 text-emerald-800 text-sm font-semibold">
                      <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0" />
                      <span>Swiggy account connected</span>
                    </div>

                    <a
                      href="https://wa.me/15556631707?text=Hi%20Grocer!"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="w-full flex items-center justify-center gap-2 rounded-xl bg-[#25D366] px-4 py-3.5 text-sm font-semibold text-white hover:bg-[#1ebd59] transition shadow-xs"
                    >
                      <MessageCircle className="h-4 w-4" />
                      <span>Start on WhatsApp</span>
                    </a>
                  </div>
                ) : (
                  <form onSubmit={handleConnect} className="space-y-4">
                    <div>
                      <label className="block text-xs font-semibold text-zinc-700 mb-2">
                        WhatsApp Phone Number
                      </label>
                      <div className="flex rounded-xl border border-zinc-200 bg-zinc-50 focus-within:border-emerald-500 focus-within:bg-white focus-within:ring-2 focus-within:ring-emerald-500/10 transition">
                        <span className="inline-flex items-center px-3.5 bg-zinc-100 border-r border-zinc-200 rounded-l-xl text-zinc-700 font-mono text-sm font-semibold select-none">
                          +91
                        </span>
                        <input
                          type="tel"
                          inputMode="numeric"
                          maxLength={10}
                          placeholder="8237803170"
                          value={phone}
                          onChange={handlePhoneChange}
                          disabled={busy}
                          className="w-full bg-transparent px-3.5 py-3 text-sm font-mono text-zinc-900 placeholder:text-zinc-400 outline-none"
                        />
                      </div>
                      <p className="mt-1.5 text-[11px] text-zinc-400">
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
                  Connect your Swiggy Instamart account once with your phone number to access your saved addresses and cart.
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
                  Grocer builds your cart, handles out-of-stock replacements, and waits for your confirmation before placing the order.
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

          <div className="max-w-md mx-auto bg-[#EFEAE2] rounded-3xl overflow-hidden border border-zinc-300 shadow-xl">
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
                  <p>Get my weekly groceries under ₹2,000, vegetarian, use my usual brands.</p>
                  <span className="block text-[10px] text-zinc-400 text-right mt-1">10:14 AM</span>
                </div>
              </div>

              {/* Grocer response */}
              <div className="flex justify-start">
                <div className="bg-white text-zinc-900 rounded-2xl rounded-tl-xs px-3.5 py-2.5 max-w-[90%] shadow-xs space-y-2">
                  <p>Found 6 of your items on Instamart. Amul Gold Milk 1L is currently out of stock.</p>
                  <p className="font-semibold text-zinc-800">Choose a replacement:</p>
                  <div className="space-y-1 bg-zinc-50 p-2 rounded-xl border border-zinc-100">
                    <p>1. Nandini Special Milk 1L — <span className="font-mono font-semibold">₹54</span></p>
                    <p>2. Mother Dairy Full Cream 1L — <span className="font-mono font-semibold">₹66</span></p>
                  </div>
                  <p className="text-[11px] text-zinc-500">Reply 1 or 2 to select.</p>
                  <span className="block text-[10px] text-zinc-400 text-right">10:14 AM</span>
                </div>
              </div>

              {/* User reply */}
              <div className="flex justify-end">
                <div className="bg-[#D9FDD3] text-zinc-900 rounded-2xl rounded-tr-xs px-3.5 py-2 max-w-[40%] shadow-xs text-center">
                  <p className="font-mono font-semibold">1</p>
                  <span className="block text-[10px] text-zinc-400 text-right mt-0.5">10:15 AM</span>
                </div>
              </div>

              {/* Grocer cart confirmation */}
              <div className="flex justify-start">
                <div className="bg-white text-zinc-900 rounded-2xl rounded-tl-xs px-3.5 py-2.5 max-w-[92%] shadow-xs space-y-2.5">
                  <p className="text-emerald-700 font-semibold">Added Nandini Special Milk.</p>
                  <div>
                    <p className="font-semibold text-zinc-800 mb-1">Cart summary:</p>
                    <div className="space-y-0.5 text-[11px] text-zinc-600">
                      <div className="flex justify-between">
                        <span>• Nandini Special Milk 1L</span>
                        <span className="font-mono">₹54</span>
                      </div>
                      <div className="flex justify-between">
                        <span>• Aashirvaad Atta 5kg</span>
                        <span className="font-mono">₹245</span>
                      </div>
                      <div className="flex justify-between">
                        <span>• Fortune Sunflower Oil 1L</span>
                        <span className="font-mono">₹165</span>
                      </div>
                      <div className="flex justify-between">
                        <span>• Organic Brown Eggs 6pk</span>
                        <span className="font-mono">₹89</span>
                      </div>
                      <div className="flex justify-between">
                        <span>• Fresh Spinach 250g</span>
                        <span className="font-mono">₹32</span>
                      </div>
                      <div className="flex justify-between">
                        <span>• Tomato 1kg</span>
                        <span className="font-mono">₹38</span>
                      </div>
                    </div>
                  </div>

                  <div className="pt-2 border-t border-zinc-100 flex justify-between items-center font-semibold text-zinc-900">
                    <span>Total (within ₹2,000 budget):</span>
                    <span className="font-mono text-emerald-700">₹623</span>
                  </div>

                  <p className="text-[11px] text-zinc-500">
                    Delivery to: Home, Green Glen Layout
                  </p>

                  <div className="pt-1 flex gap-2">
                    <div className="flex-1 bg-emerald-600 text-white text-center py-2 rounded-xl font-semibold shadow-xs">
                      Confirm Order
                    </div>
                    <div className="px-3 bg-zinc-100 text-zinc-700 text-center py-2 rounded-xl font-medium border border-zinc-200">
                      Edit
                    </div>
                  </div>

                  <span className="block text-[10px] text-zinc-400 text-right">10:15 AM</span>
                </div>
              </div>
            </div>
          </div>
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
                  Set a price limit or dietary rule. Grocer enforces them strictly and never exceeds your budget.
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
