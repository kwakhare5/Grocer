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
  Utensils,
  HeartPulse,
  PackageCheck,
  CreditCard,
  Check,
} from "lucide-react";

const whatsappNumber = process.env.NEXT_PUBLIC_WHATSAPP_NUMBER;
const whatsappUrl = whatsappNumber
  ? `https://wa.me/${whatsappNumber}?text=${encodeURIComponent("Hi Grocer!")}`
  : null;

type ConversationTab = "staples" | "recipe" | "care" | "checkout";

interface TabData {
  id: ConversationTab;
  title: string;
  subtitle: string;
  badge: string;
  userPrompt: string;
  userTime: string;
  assistantLead: string;
  items: { name: string; price: string }[];
  subtotal: string;
  fees: string;
  total: string;
  budgetNote: string;
  deliveryAddress: string;
  eta: string;
  assistantTime: string;
  buttons?: string[];
  finalButtonText?: string;
  finalButtonLink?: string;
  isOrderConfirmed?: boolean;
}

const CONVERSATION_TABS: Record<ConversationTab, TabData> = {
  staples: {
    id: "staples",
    title: "Daily Staples",
    subtitle: "Milk, bread, and eggs replenishment",
    badge: "Household Restocking",
    userPrompt: "Restock my daily essentials: 2 litres milk, brown bread, and 6 eggs under ₹500",
    userTime: "7:45 AM",
    assistantLead: "I've selected in-stock daily staples from your local dark store:",
    items: [
      { name: "Amul Taaza Toned Milk (1L x 2)", price: "₹108" },
      { name: "Britannia 100% Whole Wheat Bread (400g)", price: "₹55" },
      { name: "Fresh Farm White Eggs (6 pcs)", price: "₹48" },
    ],
    subtotal: "₹211",
    fees: "₹35 (Delivery & packaging)",
    total: "₹246",
    budgetNote: "Well under your ₹500 budget cap",
    deliveryAddress: "Flat 402, Green Glen Layout",
    eta: "10-15 mins",
    assistantTime: "7:45 AM",
    buttons: ["Confirm Order", "Change Items"],
  },
  recipe: {
    id: "recipe",
    title: "Recipe Kits",
    subtitle: "Automatic ingredient deduction",
    badge: "Meal Kits",
    userPrompt: "I want to make pasta tonight, budget under ₹1,500. Get the ingredients!",
    userTime: "8:11 PM",
    assistantLead: "I've deduced the complete pasta kit (7 items) from your local dark store:",
    items: [
      { name: "Barilla Penne Rigate Pasta (500g)", price: "₹275" },
      { name: "Barilla Basilico Pasta Sauce (400g)", price: "₹295" },
      { name: "D'lecta Diced Mozzarella (200g)", price: "₹195" },
      { name: "Amul Butter (100g)", price: "₹58" },
      { name: "Peeled Garlic (100g)", price: "₹35" },
      { name: "Fresh Red Onion (500g)", price: "₹24" },
      { name: "Green Capsicum (250g)", price: "₹22" },
    ],
    subtotal: "₹904",
    fees: "₹35 (Delivery & handling)",
    total: "₹939",
    budgetNote: "Saved ₹561 vs your ₹1,500 budget",
    deliveryAddress: "Flat 402, Green Glen Layout",
    eta: "10-15 mins",
    assistantTime: "8:11 PM",
    buttons: ["Confirm Order", "Change Items"],
  },
  care: {
    id: "care",
    title: "Symptom Care",
    subtitle: "Cold & headache relief kit",
    badge: "Situational Care",
    userPrompt: "I have a terrible cold and sore throat, my head is pounding. Get me what I need.",
    userTime: "10:15 PM",
    assistantLead: "I've put together a cold and headache relief kit from your local dark store:",
    items: [
      { name: "Crocin Advance 650mg (15 Tablets)", price: "₹32" },
      { name: "Strepsils Honey & Lemon Lozenges (8 pcs)", price: "₹45" },
      { name: "Vicks VapoRub Balm (25ml)", price: "₹65" },
      { name: "Tetley Ginger Mint Green Tea (25 Bags)", price: "₹120" },
    ],
    subtotal: "₹262",
    fees: "₹35 (Delivery & handling)",
    total: "₹297",
    budgetNote: "Dispatched from your nearest dark store",
    deliveryAddress: "Flat 402, Green Glen Layout",
    eta: "10-15 mins",
    assistantTime: "10:15 PM",
    buttons: ["Confirm Order", "Change Items"],
  },
  checkout: {
    id: "checkout",
    title: "Gated Checkout",
    subtitle: "Explicit confirmation & UPI payment",
    badge: "Financial Safety",
    userPrompt: "Confirm Order",
    userTime: "8:12 PM",
    assistantLead: "Order confirmed! Here are your verified order details:",
    items: [
      { name: "Order Reference", price: "#IM-89211" },
      { name: "Total Payable", price: "₹939" },
    ],
    subtotal: "₹904",
    fees: "₹35",
    total: "₹939",
    budgetNote: "Server-side gated: No order placed without explicit approval",
    deliveryAddress: "Flat 402, Green Glen Layout",
    eta: "10-15 mins",
    assistantTime: "8:12 PM",
    finalButtonText: "Complete Payment via UPI (₹939)",
    finalButtonLink: "https://mcp.swiggy.com/pay/bridge?order=89211",
    isOrderConfirmed: true,
  },
};

export default function Home() {
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [activeTab, setActiveTab] = useState<ConversationTab>("staples");

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

  const currentTabData = CONVERSATION_TABS[activeTab];

  return (
    <div className="min-h-screen bg-[#FAFAFA] text-zinc-900 flex flex-col font-sans">
      <AppGlobalHeader />

      <main className="flex-1">
        {/* ─── Hero Section ─────────────────────────────────────────── */}
        <section className="pt-14 pb-20 px-4 sm:px-6 lg:px-8 max-w-6xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
            {/* Left: What Grocer Does */}
            <div className="lg:col-span-7 space-y-6">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-medium">
                <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
                <span>Autonomous grocery replenishment</span>
              </div>

              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-editorial font-bold text-zinc-950 tracking-tight leading-[1.15]">
                Weekly groceries on WhatsApp.
              </h1>

              <p className="text-base sm:text-lg text-zinc-600 leading-relaxed max-w-xl">
                Text what you need in plain English—from daily staples to complete recipe kits. Grocer checks live dark-store inventory, keeps everything strictly within your budget, and gets your explicit confirmation before placing any order.
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
                  Automatic replenishment
                </span>
              </div>
            </div>

            {/* Right: Connect Account Card (Functional Core) */}
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
                      Link your dark-store account to WhatsApp
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
                      <span>Account connected</span>
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
                          placeholder="9820184729"
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
                          <span>Connect Instamart Account</span>
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

        {/* ─── How It Works (3 Clear Steps) ─────────────────────────── */}
        <section id="how-it-works" className="py-16 bg-white border-y border-zinc-200 scroll-mt-16">
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
                  Connect your phone once to securely load your saved delivery addresses and preferences.
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
                  Send a natural WhatsApp message like &ldquo;restock milk and bread&rdquo;, &ldquo;pasta for dinner under ₹1,500&rdquo;, or &ldquo;cold care kit&rdquo;.
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
                  Grocer verifies live stock, applies real prices and fees, and requires your explicit confirmation before placing the order.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ─── Features (Replenishment, Intent, Medical, Policy) ──────── */}
        <section id="features" className="py-20 px-4 sm:px-6 lg:px-8 max-w-6xl mx-auto scroll-mt-16">
          <div className="text-center max-w-2xl mx-auto mb-14">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold mb-3">
              <span>Features</span>
            </div>
            <h2 className="text-3xl sm:text-4xl font-editorial font-bold text-zinc-950">
              From natural intent to doorstep delivery.
            </h2>
            <p className="mt-3 text-sm sm:text-base text-zinc-600 leading-relaxed">
              GROCER combines high-level intent understanding with automated replenishment, condition-based care, and strict deterministic budget enforcement.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* 1. Daily Staples Replenishment */}
            <div className="bg-white rounded-3xl p-7 border border-zinc-200 shadow-xs flex flex-col justify-between">
              <div>
                <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-700 flex items-center justify-center mb-5">
                  <RefreshCw className="w-6 h-6" />
                </div>
                <div className="inline-block text-[11px] font-semibold text-emerald-800 uppercase tracking-wider mb-2">
                  Household Replenishment
                </div>
                <h3 className="text-xl font-bold text-zinc-950 mb-2">
                  Daily Staples Restocking
                </h3>
                <p className="text-xs text-zinc-500 mb-4 font-mono bg-zinc-50 p-2.5 rounded-xl border border-zinc-100">
                  &ldquo;Get 2L milk, whole wheat bread, and 6 eggs under ₹500&rdquo;
                </p>
                <p className="text-sm text-zinc-600 leading-relaxed">
                  Picks standard in-stock dark store variants (Amul, Britannia, fresh eggs) without asking tedious brand or pack-size questions.
                </p>
              </div>
              <div className="pt-6 border-t border-zinc-100 mt-6 flex items-center gap-2 text-xs font-semibold text-emerald-700">
                <Check className="w-4 h-4" />
                <span>Zero redundant clarification questions</span>
              </div>
            </div>

            {/* 2. Recipe & Meal Kits */}
            <div className="bg-white rounded-3xl p-7 border border-zinc-200 shadow-xs flex flex-col justify-between">
              <div>
                <div className="w-12 h-12 rounded-2xl bg-orange-50 text-[#fc8019] flex items-center justify-center mb-5">
                  <Utensils className="w-6 h-6" />
                </div>
                <div className="inline-block text-[11px] font-semibold text-[#fc8019] uppercase tracking-wider mb-2">
                  Recipe Intent
                </div>
                <h3 className="text-xl font-bold text-zinc-950 mb-2">
                  Recipe & Meal Kit Deduction
                </h3>
                <p className="text-xs text-zinc-500 mb-4 font-mono bg-zinc-50 p-2.5 rounded-xl border border-zinc-100">
                  &ldquo;I want to make pasta tonight under ₹1,500. Get ingredients!&rdquo;
                </p>
                <p className="text-sm text-zinc-600 leading-relaxed">
                  Deduces the entire multi-item grocery basket (pasta, sauce, cheese, aromatics) and fires parallel searches to build the kit in under 3.5 seconds.
                </p>
              </div>
              <div className="pt-6 border-t border-zinc-100 mt-6 flex items-center gap-2 text-xs font-semibold text-[#fc8019]">
                <Check className="w-4 h-4" />
                <span>Parallel catalogue deduction</span>
              </div>
            </div>

            {/* 3. Symptom Care */}
            <div className="bg-white rounded-3xl p-7 border border-zinc-200 shadow-xs flex flex-col justify-between">
              <div>
                <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-700 flex items-center justify-center mb-5">
                  <HeartPulse className="w-6 h-6" />
                </div>
                <div className="inline-block text-[11px] font-semibold text-blue-800 uppercase tracking-wider mb-2">
                  Medical & Wellness
                </div>
                <h3 className="text-xl font-bold text-zinc-950 mb-2">
                  Symptom Care & Urgent Relief
                </h3>
                <p className="text-xs text-zinc-500 mb-4 font-mono bg-zinc-50 p-2.5 rounded-xl border border-zinc-100">
                  &ldquo;Terrible cold and sore throat, my head is pounding&rdquo;
                </p>
                <p className="text-sm text-zinc-600 leading-relaxed">
                  Translates fuzzy household medical symptoms into OTC comfort relief (Crocin, Strepsils, Vicks, Herbal Tea) delivered immediately in 10-15 minutes.
                </p>
              </div>
              <div className="pt-6 border-t border-zinc-100 mt-6 flex items-center gap-2 text-xs font-semibold text-blue-700">
                <Check className="w-4 h-4" />
                <span>Condition-based medical inference</span>
              </div>
            </div>

            {/* 4. Intent Preservation & Hard Budget Caps */}
            <div className="bg-white rounded-3xl p-7 border border-zinc-200 shadow-xs flex flex-col justify-between">
              <div>
                <div className="w-12 h-12 rounded-2xl bg-purple-50 text-purple-700 flex items-center justify-center mb-5">
                  <ShieldCheck className="w-6 h-6" />
                </div>
                <div className="inline-block text-[11px] font-semibold text-purple-800 uppercase tracking-wider mb-2">
                  Deterministic Policy
                </div>
                <h3 className="text-xl font-bold text-zinc-950 mb-2">
                  Intent Preservation & Budget Caps
                </h3>
                <p className="text-xs text-zinc-500 mb-4 font-mono bg-zinc-50 p-2.5 rounded-xl border border-zinc-100">
                  &ldquo;Vegetarian only, keep total strictly under ₹1,000&rdquo;
                </p>
                <p className="text-sm text-zinc-600 leading-relaxed">
                  Enforces non-negotiable dietary constraints and hard financial boundaries. Automatically recovers substitutions within policy rather than failing.
                </p>
              </div>
              <div className="pt-6 border-t border-zinc-100 mt-6 flex items-center gap-2 text-xs font-semibold text-purple-700">
                <Check className="w-4 h-4" />
                <span>Zero model arithmetic hallucination</span>
              </div>
            </div>
          </div>
        </section>

        {/* ─── Interactive WhatsApp Flow Viewer ──────────────────────── */}
        <section id="demo" className="py-20 bg-white border-y border-zinc-200 scroll-mt-16">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-2xl mx-auto mb-10">
              <h2 className="text-2xl sm:text-3xl font-editorial font-bold text-zinc-950">
                The WhatsApp experience
              </h2>
              <p className="mt-2 text-sm text-zinc-600">
                Click a scenario below to preview how Grocer responds on WhatsApp.
              </p>
            </div>

            {/* Tab Selectors */}
            <div className="flex flex-wrap items-center justify-center gap-2 mb-8">
              {(Object.keys(CONVERSATION_TABS) as ConversationTab[]).map((tabKey) => {
                const tab = CONVERSATION_TABS[tabKey];
                const isActive = activeTab === tabKey;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tabKey)}
                    className={`px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition cursor-pointer ${
                      isActive
                        ? "bg-zinc-900 text-white shadow-xs"
                        : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200"
                    }`}
                  >
                    {tab.title}
                  </button>
                );
              })}
            </div>

            {/* Simulated Phone Mockup */}
            <figure className="max-w-md mx-auto" aria-label="Simulated WhatsApp preview">
              <div className="bg-[#EFEAE2] rounded-3xl overflow-hidden border border-zinc-300 shadow-xl">
                {/* WhatsApp Header */}
                <div className="bg-[#075E54] px-4 py-3 flex items-center justify-between text-white">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-emerald-700 flex items-center justify-center text-white font-bold text-sm">
                      G
                    </div>
                    <div>
                      <div className="font-semibold text-sm leading-tight">Grocer</div>
                      <div className="text-[11px] text-emerald-200">Online • Dark-Store Assistant</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-emerald-200">
                    <span className="inline-block w-2 h-2 rounded-full bg-emerald-400"></span>
                    <span>Live</span>
                  </div>
                </div>

                {/* Chat Body */}
                <div className="p-4 space-y-3.5 text-xs leading-relaxed min-h-[380px] flex flex-col justify-start">
                  {/* User message */}
                  <div className="flex justify-end">
                    <div className="bg-[#D9FDD3] text-zinc-900 rounded-2xl rounded-tr-xs px-3.5 py-2 max-w-[85%] shadow-xs">
                      <p className="text-[13px] leading-relaxed">{currentTabData.userPrompt}</p>
                      <div className="flex items-center justify-end gap-1 mt-1 text-[10px] text-zinc-500">
                        <span>{currentTabData.userTime}</span>
                        <span className="text-[#53bdeb] font-bold">✓✓</span>
                      </div>
                    </div>
                  </div>

                  {/* Grocer response: Native WhatsApp speech bubble with attached quick reply buttons */}
                  <div className="flex justify-start">
                    <div className="bg-white text-zinc-900 rounded-2xl rounded-tl-xs max-w-[92%] shadow-xs border border-zinc-200/50 overflow-hidden">
                      <div className="p-3.5 space-y-2">
                        <p className="text-[13px] text-zinc-900 leading-snug">{currentTabData.assistantLead}</p>

                        <div className="space-y-1.5 py-1 text-[12px] text-zinc-800">
                          {currentTabData.items.map((item, idx) => (
                            <div key={idx} className="flex justify-between items-baseline gap-2">
                              <span className="leading-snug">• {item.name}</span>
                              <span className="font-semibold text-zinc-950 font-mono shrink-0">{item.price}</span>
                            </div>
                          ))}
                        </div>

                        <div className="pt-2 border-t border-dashed border-zinc-200 space-y-1 text-[12px]">
                          <div className="flex justify-between text-zinc-600">
                            <span>Subtotal</span>
                            <span className="font-mono">{currentTabData.subtotal}</span>
                          </div>
                          <div className="flex justify-between text-zinc-600">
                            <span>Fees</span>
                            <span className="font-mono">{currentTabData.fees}</span>
                          </div>
                          <div className="flex justify-between font-bold text-zinc-950 text-xs pt-1 border-t border-zinc-200">
                            <span>Total</span>
                            <span className="font-mono text-emerald-700">{currentTabData.total}</span>
                          </div>
                          {currentTabData.budgetNote && (
                            <p className="text-[11px] text-zinc-500 italic pt-0.5">
                              ({currentTabData.budgetNote})
                            </p>
                          )}
                        </div>

                        <div className="pt-1 text-[11px] text-zinc-500 flex items-center justify-between">
                          <span>📍 {currentTabData.deliveryAddress}</span>
                          <span className="text-emerald-700 font-medium">~{currentTabData.eta}</span>
                        </div>

                        <div className="flex items-center justify-end text-[10px] text-zinc-400 pt-0.5">
                          <span>{currentTabData.assistantTime}</span>
                        </div>
                      </div>

                      {/* Native attached quick reply button rows */}
                      {currentTabData.finalButtonLink ? (
                        <div className="border-t border-zinc-200/80 bg-white">
                          <a
                            href={currentTabData.finalButtonLink}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="w-full flex items-center justify-center gap-2 py-2.5 px-3 text-center text-[#00A884] font-medium text-[13px] hover:bg-zinc-50 active:bg-zinc-100 transition-colors"
                          >
                            <span>{currentTabData.finalButtonText}</span>
                          </a>
                        </div>
                      ) : (
                        <div className="border-t border-zinc-200/80 bg-white divide-y divide-zinc-200/80">
                          {(currentTabData.buttons || ["Confirm Order", "Change Items"]).map((btnText, idx) => (
                            <button
                              key={idx}
                              type="button"
                              onClick={() => {
                                if (btnText === "Confirm Order") setActiveTab("checkout");
                              }}
                              className="w-full py-2.5 px-3 text-center text-[#00A884] font-medium text-[13px] hover:bg-zinc-50 active:bg-zinc-100 transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
                            >
                              <span>{btnText}</span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
              <figcaption className="mt-3 text-center text-xs text-zinc-500">
                Interactive preview of authentic WhatsApp replenishment flow.
              </figcaption>
            </figure>
          </div>
        </section>

        {/* ─── Commerce Architecture & Safety ────────────────────────── */}
        <section id="safety" className="py-20 px-4 sm:px-6 lg:px-8 max-w-6xl mx-auto scroll-mt-16">
          <div className="text-center max-w-2xl mx-auto mb-14">
            <h2 className="text-2xl sm:text-3xl font-editorial font-bold text-zinc-950">
              Commerce architecture & safety
            </h2>
            <p className="mt-2 text-sm text-zinc-600">
              Designed with strict deterministic controls to guarantee financial and inventory safety.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="p-6 rounded-2xl border border-zinc-200 bg-white shadow-xs">
              <div className="w-10 h-10 rounded-xl bg-orange-50 text-[#fc8019] flex items-center justify-center mb-4">
                <ShoppingBag className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-zinc-950 mb-2">
                Live Dark Store Stock
              </h3>
              <p className="text-xs text-zinc-600 leading-relaxed">
                Queries the live catalogue of the exact dark store serving your saved address. No stale inventory.
              </p>
            </div>

            <div className="p-6 rounded-2xl border border-zinc-200 bg-white shadow-xs">
              <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center mb-4">
                <PackageCheck className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-zinc-950 mb-2">
                Verified Pricing in ₹
              </h3>
              <p className="text-xs text-zinc-600 leading-relaxed">
                All prices, discounts, and delivery fees come directly from the provider billing engine. Zero model arithmetic hallucination.
              </p>
            </div>

            <div className="p-6 rounded-2xl border border-zinc-200 bg-white shadow-xs">
              <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-700 flex items-center justify-center mb-4">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-zinc-950 mb-2">
                Server-Side Gated Checkout
              </h3>
              <p className="text-xs text-zinc-600 leading-relaxed">
                The agent is physically blocked from placing orders autonomously. Checkout requires explicit customer confirmation.
              </p>
            </div>

            <div className="p-6 rounded-2xl border border-zinc-200 bg-white shadow-xs">
              <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-700 flex items-center justify-center mb-4">
                <CreditCard className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-zinc-950 mb-2">
                Dynamic UPI Payments
              </h3>
              <p className="text-xs text-zinc-600 leading-relaxed">
                Returns official secure payment links and checks order status before retrying, preventing duplicate charges.
              </p>
            </div>
          </div>
        </section>
      </main>

      {/* ─── Clean Footer ─────────────────────────────────────────── */}
      <footer className="bg-white border-t border-zinc-200 py-10 px-4 sm:px-6 lg:px-8 text-center text-xs text-zinc-500">
        <div className="max-w-4xl mx-auto space-y-3">
          <p className="font-semibold text-zinc-700">
            GROCER — WhatsApp Grocery Replenishment
          </p>
          <p className="text-zinc-500 leading-relaxed max-w-xl mx-auto">
            Built for the official Swiggy Builders Club using Model Context Protocol (MCP) and Meta WhatsApp Business Platform.
          </p>
          <div className="pt-3 flex flex-wrap items-center justify-center gap-4 text-zinc-400 text-xs">
            <span>
              Built by{" "}
              <a
                href="https://karan30.vercel.app"
                target="_blank"
                rel="noopener noreferrer"
                className="text-zinc-800 hover:text-zinc-950 font-medium underline transition"
              >
                Karan Wakhare
              </a>
            </span>
            <span>•</span>
            <a
              href="https://github.com/kwakhare5/Grocer"
              target="_blank"
              rel="noopener noreferrer"
              className="text-zinc-600 hover:text-zinc-900 underline transition"
            >
              GitHub Repository
            </a>
          </div>
          <p className="text-zinc-400 pt-2">
            © {new Date().getFullYear()} Grocer. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
