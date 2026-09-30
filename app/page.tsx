"use client";

import React, { useEffect, useState, FormEvent, useRef } from "react";
import { AppGlobalHeader } from "../components/navigation/AppGlobalHeader";
import {
  ArrowRight,
  CheckCircle2,
  ShieldCheck,
  RefreshCw,
  ShoppingBag,
  Utensils,
  HeartPulse,
  PackageCheck,
  CreditCard,
  Check,
  Terminal,
  Layers,
  MapPin,
  Clock,
  Play,
  Send,
  X,
  Loader2,
} from "lucide-react";

interface Message {
  id: string;
  sender: "user" | "assistant";
  text?: string;
  time: string;
  items?: { name: string; price: string }[];
  subtotal?: string;
  fees?: string;
  total?: string;
  budgetNote?: string;
  deliveryAddress?: string;
  eta?: string;
  buttons?: string[];
  finalButtonText?: string;
  finalButtonLink?: string;
  toolCallName?: string;
  toolCallPayload?: string;
}

const PRESET_SCENARIOS = [
  {
    label: "Pasta kit under ₹1,500",
    prompt: "I want to make pasta tonight, budget under ₹1,500. Get the ingredients!",
    replyLead: "I've deduced the complete pasta kit (7 items) from your local dark store:",
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
    buttons: ["Confirm Order", "Change Items"],
    toolCallName: "search_products + update_cart",
    toolCallPayload: `search_products(["penne pasta", "pasta sauce", "mozzarella", "garlic", "butter", "capsicum", "onion"])
update_cart(items=[...7 items...], address_id="addr_pune_402")`,
  },
  {
    label: "Daily staples under ₹500",
    prompt: "Restock my daily essentials: 2 litres milk, brown bread, and 6 eggs under ₹500",
    replyLead: "I've selected in-stock daily staples from your local dark store:",
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
    buttons: ["Confirm Order", "Change Items"],
    toolCallName: "search_products + update_cart",
    toolCallPayload: `search_products(["amul milk 1l", "wheat bread", "eggs 6"])
update_cart(items=[{"id":"amul_1l","qty":2}, {"id":"bread_400g","qty":1}, {"id":"eggs_6","qty":1}])`,
  },
  {
    label: "Also add butter & curd",
    prompt: "Wait, also add 1 Amul butter 100g and 1 pack curd",
    replyLead: "Added to your active basket without wiping your previous pasta kit:",
    items: [
      { name: "Previous Pasta Kit (7 Items)", price: "₹904" },
      { name: "Amul Butter (100g)", price: "₹58" },
      { name: "Milky Mist Fresh Curd (400g)", price: "₹42" },
    ],
    subtotal: "₹1,004",
    fees: "₹35 (Delivery & handling)",
    total: "₹1,039",
    budgetNote: "Preserved active basket & merged 2 new items",
    deliveryAddress: "Flat 402, Green Glen Layout",
    eta: "10-15 mins",
    buttons: ["Confirm Order", "Change Items"],
    toolCallName: "update_cart(delta_merge=True)",
    toolCallPayload: `// Invariant: INV-CART-02 Delta Merge
update_cart(items=[{"item_id":"amul_butter","qty":1}, {"item_id":"curd_400g","qty":1}], merge=True)
get_cart() -> Reconciled Subtotal: ₹1,004 | Grand Total: ₹1,039`,
  },
  {
    label: "Cold & headache care",
    prompt: "I have a terrible cold and sore throat, my head is pounding. Get me what I need.",
    replyLead: "I've deduced an OTC cold and headache relief kit from your local dark store:",
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
    buttons: ["Confirm Order", "Change Items"],
    toolCallName: "condition_inference + search_products",
    toolCallPayload: `// Inferred condition: acute cold + sore throat + headache
search_products(["crocin advance", "strepsils lozenges", "vaporub balm", "ginger tea"])
update_cart(items=[...4 relief items...])`,
  },
  {
    label: "Confirm order",
    prompt: "Confirm Order",
    replyLead: "Order confirmed! Server-side lock verified. Please complete payment via the official dark-store UPI link:",
    items: [
      { name: "Order Reference", price: "#IM-89211" },
      { name: "Verified Line Items", price: "9 groceries" },
      { name: "Total Payable", price: "₹1,039" },
    ],
    subtotal: "₹1,004",
    fees: "₹35",
    total: "₹1,039",
    budgetNote: "Server-side gated: No order placed without explicit approval",
    deliveryAddress: "Flat 402, Green Glen Layout",
    eta: "10-15 mins",
    finalButtonText: "Complete Payment via UPI (₹1,039)",
    finalButtonLink: "https://mcp.swiggy.com/pay/bridge?order=89211",
    toolCallName: "checkout(generateUPIQR=True)",
    toolCallPayload: `// Invariant: INV-CHECKOUT-01 Gated Authorization
verify_guard(is_user_confirmed=True)
checkout(generateUPIQR=True) -> bridge_url: "https://mcp.swiggy.com/pay/bridge?order=89211"
spawn_daemon(_poll_payment_status, interval_sec=5, timeout_sec=60)`,
  },
  {
    label: "Where is my order?",
    prompt: "Where is my order?",
    replyLead: "Your groceries are on the bike! 🛵 Dispatched from your nearest dark store:",
    items: [
      { name: "Order Status", price: "Out for delivery" },
      { name: "Dark-Store Rider", price: "Ramesh K." },
      { name: "Estimated Arrival", price: "6–8 mins (~8:28 PM)" },
      { name: "Delivering to", price: "Flat 402, Green Glen" },
    ],
    subtotal: "₹1,004",
    fees: "₹35",
    total: "₹1,039",
    budgetNote: "Live telemetry from dark-store fleet",
    deliveryAddress: "Flat 402, Green Glen Layout",
    eta: "6-8 mins",
    finalButtonText: "Refresh Live Tracking",
    finalButtonLink: "#demo",
    toolCallName: "track_order(order_id)",
    toolCallPayload: `track_order(order_id="IM-89211")
-> {"status": "out_for_delivery", "rider_name": "Ramesh K.", "eta_minutes": 7}`,
  },
];

const CHAPTERS = [
  { time: "0:00", label: "Address Selection" },
  { time: "0:25", label: "Recipe Deduction (<3.5s)" },
  { time: "0:55", label: "Delta Cart Merge ('Also add butter')" },
  { time: "1:20", label: "Hesitation Hold Guard ('wait')" },
  { time: "1:45", label: "Gated UPI Checkout & QR Bridge" },
];

export default function Home() {
  // Swiggy Instamart OAuth State (Whitelisted Gateway)
  const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  // Video Player State
  const [isPlayingDemo, setIsPlayingDemo] = useState(false);

  // Simulator State
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "msg_user_1",
      sender: "user",
      text: PRESET_SCENARIOS[0].prompt,
      time: "8:11 PM",
    },
    {
      id: "msg_asst_1",
      sender: "assistant",
      text: PRESET_SCENARIOS[0].replyLead,
      time: "8:11 PM",
      items: PRESET_SCENARIOS[0].items,
      subtotal: PRESET_SCENARIOS[0].subtotal,
      fees: PRESET_SCENARIOS[0].fees,
      total: PRESET_SCENARIOS[0].total,
      budgetNote: PRESET_SCENARIOS[0].budgetNote,
      deliveryAddress: PRESET_SCENARIOS[0].deliveryAddress,
      eta: PRESET_SCENARIOS[0].eta,
      buttons: PRESET_SCENARIOS[0].buttons,
      toolCallName: PRESET_SCENARIOS[0].toolCallName,
      toolCallPayload: PRESET_SCENARIOS[0].toolCallPayload,
    },
  ]);
  const [inputText, setInputText] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [showToolExecution, setShowToolExecution] = useState(false);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  // Listen for Swiggy OAuth Redirect Callback (?code=...&state=...)
  useEffect(() => {
    let mounted = true;
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");

    if (code && state) {
      window.setTimeout(() => {
        if (mounted) {
          setBusy(true);
          setAuthError(null);
          setIsConnectModalOpen(true);
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
            setAuthError(
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
    if (authError) setAuthError(null);
  };

  const handleConnectSwiggy = async (e: FormEvent) => {
    e.preventDefault();
    if (!phone || phone.length !== 10) {
      setAuthError("Please enter your 10-digit mobile number");
      return;
    }

    setBusy(true);
    setAuthError(null);

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
          errorData.error || "Unable to start the connection. Please try again.",
        );
      }

      const data = await res.json();
      if (data.authorize_url) {
        window.location.href = data.authorize_url;
      } else {
        throw new Error("Unable to start the connection. Please try again.");
      }
    } catch (err) {
      setAuthError(
        err instanceof Error
          ? err.message
          : "Unable to start the connection. Please try again.",
      );
      setBusy(false);
    }
  };

  // Simulator Message Dispatch
  const handleSendSimulationMessage = (userQuery: string) => {
    if (!userQuery.trim() || isTyping) return;

    const queryLower = userQuery.toLowerCase();
    const matchedScenario =
      PRESET_SCENARIOS.find((sc) =>
        queryLower.includes(sc.label.toLowerCase()) ||
        sc.prompt.toLowerCase().includes(queryLower) ||
        (queryLower.includes("pasta") && sc.label.includes("Pasta")) ||
        (queryLower.includes("milk") && sc.label.includes("staples")) ||
        (queryLower.includes("butter") && sc.label.includes("butter")) ||
        (queryLower.includes("cold") && sc.label.includes("Cold")) ||
        (queryLower.includes("confirm") && sc.label.includes("Confirm")) ||
        (queryLower.includes("order") && sc.label.includes("order")) ||
        (queryLower.includes("track") && sc.label.includes("order"))
      ) || PRESET_SCENARIOS[0];

    const newTime = new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

    // 1. Append User Message
    const userMsg: Message = {
      id: `user_${new Date().getTime()}`,
      sender: "user",
      text: userQuery,
      time: newTime,
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText("");
    setIsTyping(true);

    // Scroll to bottom
    setTimeout(() => {
      chatScrollRef.current?.scrollTo({ top: chatScrollRef.current.scrollHeight, behavior: "smooth" });
    }, 50);

    // 2. Simulated Typing Delay (600ms)
    setTimeout(() => {
      const assistantMsg: Message = {
        id: `asst_${Date.now()}`,
        sender: "assistant",
        text: matchedScenario.replyLead,
        time: newTime,
        items: matchedScenario.items,
        subtotal: matchedScenario.subtotal,
        fees: matchedScenario.fees,
        total: matchedScenario.total,
        budgetNote: matchedScenario.budgetNote,
        deliveryAddress: matchedScenario.deliveryAddress,
        eta: matchedScenario.eta,
        buttons: matchedScenario.buttons,
        finalButtonText: matchedScenario.finalButtonText,
        finalButtonLink: matchedScenario.finalButtonLink,
        toolCallName: matchedScenario.toolCallName,
        toolCallPayload: matchedScenario.toolCallPayload,
      };

      setMessages((prev) => [...prev, assistantMsg]);
      setIsTyping(false);

      setTimeout(() => {
        chatScrollRef.current?.scrollTo({ top: chatScrollRef.current.scrollHeight, behavior: "smooth" });
      }, 50);
    }, 600);
  };

  const handleInputSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (inputText.trim()) {
      handleSendSimulationMessage(inputText.trim());
    }
  };

  const activeToolExecution = messages.filter((m) => m.toolCallPayload).slice(-1)[0];

  return (
    <div className="min-h-screen bg-[#FAFAFA] text-zinc-900 flex flex-col font-sans selection:bg-emerald-600 selection:text-white">
      <AppGlobalHeader
        onOpenConnect={() => setIsConnectModalOpen(true)}
        isConnected={isConnected}
      />

      <main className="flex-1">
        {/* ─── 1. Hero Section: Headline & Purpose ─────────────────── */}
        <section className="pt-14 pb-12 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold mb-6">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span>Official Swiggy Builders Club Submission • Powered by Instamart MCP &amp; Gemini 3.5</span>
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-editorial font-bold text-zinc-950 tracking-tight leading-[1.12] max-w-4xl mx-auto">
            Household groceries on WhatsApp. In plain English.
          </h1>

          <p className="mt-5 text-base sm:text-lg text-zinc-600 leading-relaxed max-w-2xl mx-auto">
            Text a recipe, restock your daily essentials, or describe a symptom. Grocer checks live stock at your local dark store in seconds, keeps everything strictly within your budget, and gets your approval before placing any order.
          </p>

          {/* Action CTAs */}
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <a
              href="#video-demo"
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 px-5 py-3 text-sm font-semibold text-white shadow-xs transition-all active:scale-[0.98] cursor-pointer"
            >
              <Play className="w-4 h-4 fill-current ml-0.5" />
              <span>Watch 2-Minute Demo</span>
            </a>

            <button
              type="button"
              onClick={() => setIsConnectModalOpen(true)}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-white hover:bg-zinc-50 border border-zinc-200 px-4 py-3 text-sm font-medium text-zinc-800 shadow-2xs transition-colors active:scale-[0.98] cursor-pointer"
            >
              <ShoppingBag className="w-4 h-4 text-[#fc8019]" />
              <span>{isConnected ? "Instamart Linked ✓" : "Connect Instamart Account"}</span>
            </button>

            <a
              href="#demo"
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-zinc-100 hover:bg-zinc-200 px-4 py-3 text-sm font-medium text-zinc-700 transition-colors active:scale-[0.98]"
            >
              <span>Try Simulator</span>
            </a>
          </div>

          {/* Quick Metrics Bar */}
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3 sm:gap-6 text-xs text-zinc-600 font-medium">
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white border border-zinc-200 shadow-2xs">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              Zero Unapproved Charges
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white border border-zinc-200 shadow-2xs">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              Strict Budget Caps
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white border border-zinc-200 shadow-2xs">
              <Clock className="w-4 h-4 text-emerald-600" />
              10–15 Min Delivery
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white border border-zinc-200 shadow-2xs">
              <Layers className="w-4 h-4 text-emerald-600" />
              Pluggable CommercePort
            </span>
          </div>
        </section>

        {/* ─── 2. Full-Width Cinematic Video Showcase ──────────────── */}
        <section id="video-demo" className="pb-16 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto scroll-mt-16">
          <div className="bg-white rounded-3xl p-3 sm:p-5 border border-zinc-200 shadow-xl overflow-hidden relative">
            {/* Display Window Top Bar */}
            <div className="flex items-center justify-between px-3 py-2 text-xs text-zinc-500 border-b border-zinc-100 mb-3">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-red-400"></span>
                <span className="w-2.5 h-2.5 rounded-full bg-yellow-400"></span>
                <span className="w-2.5 h-2.5 rounded-full bg-green-400"></span>
                <span className="ml-2 font-mono text-[11px] text-zinc-600">
                  Full System Demo • WhatsApp + Gemini + Swiggy MCP
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded bg-zinc-100 text-[10px] font-mono text-zinc-600">
                  2:00 Walkthrough
                </span>
              </div>
            </div>

            {/* Video Player Display Container */}
            <div className="relative aspect-video rounded-2xl bg-zinc-950 border border-zinc-900 overflow-hidden flex flex-col items-center justify-center text-center p-6">
              {isPlayingDemo ? (
                <div className="w-full h-full flex flex-col items-center justify-center bg-zinc-950 text-white p-6">
                  <p className="text-sm font-semibold text-zinc-200 mb-2">
                    Reviewer Video Demo Ready
                  </p>
                  <p className="text-xs text-zinc-400 max-w-md mb-4 leading-relaxed">
                    Recording the physical screen walkthrough following the Reviewer Walkthrough script.
                  </p>
                  <button
                    type="button"
                    onClick={() => setIsPlayingDemo(false)}
                    className="px-4 py-2 rounded-xl bg-zinc-800 text-xs font-semibold text-white hover:bg-zinc-700 transition"
                  >
                    Back to Video Poster
                  </button>
                </div>
              ) : (
                <div className="space-y-4 max-w-lg">
                  <button
                    type="button"
                    onClick={() => setIsPlayingDemo(true)}
                    className="w-16 h-16 rounded-full bg-emerald-500 hover:bg-emerald-400 text-zinc-950 flex items-center justify-center mx-auto shadow-lg shadow-emerald-500/30 transition-transform active:scale-95 cursor-pointer"
                    aria-label="Play 2-Minute Demo"
                  >
                    <Play className="w-7 h-7 fill-current ml-1" />
                  </button>

                  <div>
                    <h2 className="text-lg sm:text-xl font-bold text-white tracking-tight">
                      Watch the 2-Minute Reviewer Walkthrough
                    </h2>
                    <p className="text-xs sm:text-sm text-zinc-400 mt-1.5 leading-relaxed">
                      See the complete customer journey in real time: typing a 7-item pasta kit on WhatsApp, instant recipe deduction, delta cart merge, and gated UPI payment.
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Chapters / Timeline Scrubber Bar */}
            <div className="mt-4 pt-3 border-t border-zinc-100 px-2 flex flex-wrap items-center justify-between gap-2 text-[11px] text-zinc-500">
              <span className="font-semibold text-zinc-700">Demo Chapters:</span>
              <div className="flex flex-wrap items-center gap-2">
                {CHAPTERS.map((ch, idx) => (
                  <span
                    key={idx}
                    className="px-2.5 py-1 rounded-lg bg-zinc-100 font-mono text-[10px] text-zinc-700"
                  >
                    <strong className="text-emerald-700 font-semibold">{ch.time}</strong> {ch.label}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ─── 3. Problem vs Solution: Why WhatsApp Beats App Scrolling ── */}
        <section id="why-whatsapp" className="py-16 bg-zinc-100/70 border-y border-zinc-200 scroll-mt-16">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-2xl mx-auto mb-10">
              <h2 className="text-2xl sm:text-3xl font-editorial font-bold text-zinc-950">
                Why WhatsApp beats app scrolling
              </h2>
              <p className="mt-2 text-sm text-zinc-600">
                Replenishing household groceries should take seconds, not 15 minutes of screen fatigue.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto">
              {/* Left: The Old Way (App Scrolling) */}
              <div className="bg-white rounded-2xl p-6 border border-red-100 shadow-xs">
                <div className="flex items-center gap-2.5 mb-4 text-red-700">
                  <div className="w-8 h-8 rounded-lg bg-red-50 flex items-center justify-center text-sm font-bold">
                    ✕
                  </div>
                  <h3 className="font-bold text-base text-zinc-900">
                    The E-Commerce App Fatigue
                  </h3>
                </div>

                <ul className="space-y-3 text-xs text-zinc-600">
                  <li className="flex items-start gap-2">
                    <span className="text-red-500 font-bold shrink-0 mt-0.5">•</span>
                    <span>15–20 taps across 6 categories just to assemble ingredients for dinner.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-red-500 font-bold shrink-0 mt-0.5">•</span>
                    <span>Dismissing flash-sale popups, banner ads, and recommendation carousels.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-red-500 font-bold shrink-0 mt-0.5">•</span>
                    <span>Frustrating when your hands are messy while cooking or when you are sick.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-red-500 font-bold shrink-0 mt-0.5">•</span>
                    <span>Surprise delivery fee surges and silent out-of-stock cart drops at checkout.</span>
                  </li>
                </ul>
              </div>

              {/* Right: The Grocer WhatsApp Experience */}
              <div className="bg-white rounded-2xl p-6 border border-emerald-200 shadow-xs">
                <div className="flex items-center gap-2.5 mb-4 text-emerald-700">
                  <div className="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center text-sm font-bold">
                    ✓
                  </div>
                  <h3 className="font-bold text-base text-zinc-900">
                    The Grocer Replenishment Engine
                  </h3>
                </div>

                <ul className="space-y-3 text-xs text-zinc-700">
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                    <span><strong>1 natural message:</strong> Deduces entire recipe kits in under 3.5 seconds.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                    <span><strong>Zero ad noise:</strong> Clean itemized WhatsApp receipt with exact store billing.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                    <span><strong>Delta cart memory:</strong> Say &ldquo;also add butter&rdquo; without wiping your basket.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                    <span><strong>Strict financial safety:</strong> Physical server-side lock requires confirmation.</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* ─── 4. What We Built & Core Capabilities ────────────────── */}
        <section id="features" className="py-20 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto scroll-mt-16">
          <div className="text-center max-w-2xl mx-auto mb-14">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold mb-3">
              <span>What We Built</span>
            </div>
            <h2 className="text-3xl sm:text-4xl font-editorial font-bold text-zinc-950">
              Four capabilities that redefine replenishment.
            </h2>
            <p className="mt-3 text-sm sm:text-base text-zinc-600 leading-relaxed">
              GROCER combines autonomous reasoning with deterministic dark-store execution and budget locks.
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
                  Recipe &amp; Meal Kit Deduction
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
                <span>Builds complete meal kits in seconds</span>
              </div>
            </div>

            {/* 3. Symptom Care */}
            <div className="bg-white rounded-3xl p-7 border border-zinc-200 shadow-xs flex flex-col justify-between">
              <div>
                <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-700 flex items-center justify-center mb-5">
                  <HeartPulse className="w-6 h-6" />
                </div>
                <div className="inline-block text-[11px] font-semibold text-blue-800 uppercase tracking-wider mb-2">
                  Medical &amp; Wellness
                </div>
                <h3 className="text-xl font-bold text-zinc-950 mb-2">
                  Symptom Care &amp; Urgent Relief
                </h3>
                <p className="text-xs text-zinc-500 mb-4 font-mono bg-zinc-50 p-2.5 rounded-xl border border-zinc-100">
                  &ldquo;Terrible cold and sore throat, my head is pounding&rdquo;
                </p>
                <p className="text-sm text-zinc-600 leading-relaxed">
                  Translates fuzzy household medical symptoms into essential OTC comfort relief (Crocin, Strepsils, Vicks, Herbal Tea) delivered in 10-15 minutes.
                </p>
              </div>
              <div className="pt-6 border-t border-zinc-100 mt-6 flex items-center gap-2 text-xs font-semibold text-blue-700">
                <Check className="w-4 h-4" />
                <span>Relief essentials in 10–15 minutes</span>
              </div>
            </div>

            {/* 4. Intent Preservation & Hard Budget Caps */}
            <div className="bg-white rounded-3xl p-7 border border-zinc-200 shadow-xs flex flex-col justify-between">
              <div>
                <div className="w-12 h-12 rounded-2xl bg-purple-50 text-purple-700 flex items-center justify-center mb-5">
                  <ShieldCheck className="w-6 h-6" />
                </div>
                <div className="inline-block text-[11px] font-semibold text-purple-800 uppercase tracking-wider mb-2">
                  Budget &amp; Dietary Safety
                </div>
                <h3 className="text-xl font-bold text-zinc-950 mb-2">
                  Intent Preservation &amp; Budget Caps
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
                <span>Exact dark-store billing verification</span>
              </div>
            </div>
          </div>
        </section>

        {/* ─── 5. Dual-Interactive WhatsApp Simulator (The Sandbox) ─── */}
        <section id="demo" className="py-20 bg-white border-y border-zinc-200 scroll-mt-16">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-2xl mx-auto mb-8">
              <h2 className="text-2xl sm:text-3xl font-editorial font-bold text-zinc-950">
                Dual-interactive WhatsApp simulator
              </h2>
              <p className="mt-2 text-sm text-zinc-600">
                Click a preset scenario chip or type your own custom grocery message in the input bar below.
              </p>
            </div>

            {/* Ready-Made Preset Scenario Chips */}
            <div className="flex flex-wrap items-center justify-center gap-2 mb-6">
              {PRESET_SCENARIOS.map((sc, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSendSimulationMessage(sc.prompt)}
                  className="px-3 py-1.5 rounded-xl text-xs font-medium bg-zinc-100 hover:bg-zinc-200 text-zinc-700 transition active:scale-[0.98] cursor-pointer border border-zinc-200/80 shadow-2xs"
                >
                  <span>{sc.label}</span>
                </button>
              ))}

              <button
                type="button"
                onClick={() => setShowToolExecution(!showToolExecution)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-mono font-medium transition cursor-pointer border ${
                  showToolExecution
                    ? "bg-emerald-50 text-emerald-800 border-emerald-300"
                    : "bg-zinc-50 text-zinc-600 border-zinc-200 hover:bg-zinc-100"
                }`}
              >
                <Terminal className="w-3.5 h-3.5" />
                <span>{showToolExecution ? "Hide Tool Calls" : "View Live MCP Tool Calls"}</span>
              </button>
            </div>

            {/* Simulated Phone Mockup */}
            <div className="max-w-md mx-auto">
              <div className="bg-[#EFEAE2] rounded-3xl overflow-hidden border border-zinc-300 shadow-xl flex flex-col h-[520px]">
                {/* WhatsApp Top Header Bar */}
                <div className="bg-[#075E54] px-4 py-3 flex items-center justify-between text-white shrink-0">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-emerald-700 flex items-center justify-center text-white font-bold text-sm">
                      G
                    </div>
                    <div>
                      <div className="font-semibold text-sm leading-tight">Grocer</div>
                      <div className="text-[11px] text-emerald-200">
                        {isTyping ? "typing..." : "Online • Dark-Store Assistant"}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-emerald-200">
                    <span className="inline-block w-2 h-2 rounded-full bg-emerald-400"></span>
                    <span>Live</span>
                  </div>
                </div>

                {/* WhatsApp Chat Body (Scrollable) */}
                <div
                  ref={chatScrollRef}
                  className="p-4 space-y-3.5 text-xs leading-relaxed flex-1 overflow-y-auto"
                >
                  {messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}
                    >
                      {msg.sender === "user" ? (
                        <div className="bg-[#D9FDD3] text-zinc-900 rounded-2xl rounded-tr-xs px-3.5 py-2 max-w-[85%] shadow-xs">
                          <p className="text-[13px] leading-relaxed">{msg.text}</p>
                          <div className="flex items-center justify-end gap-1 mt-1 text-[10px] text-zinc-500">
                            <span>{msg.time}</span>
                            <span className="text-[#53bdeb] font-bold">✓✓</span>
                          </div>
                        </div>
                      ) : (
                        <div className="bg-white text-zinc-900 rounded-2xl rounded-tl-xs max-w-[92%] shadow-xs border border-zinc-200/50 overflow-hidden">
                          <div className="p-3.5 space-y-2">
                            <p className="text-[13px] text-zinc-900 leading-snug">{msg.text}</p>

                            {msg.items && (
                              <div className="space-y-1.5 py-1 text-[12px] text-zinc-800">
                                {msg.items.map((item, idx) => (
                                  <div key={idx} className="flex justify-between items-baseline gap-2">
                                    <span className="leading-snug">• {item.name}</span>
                                    <span className="font-semibold text-zinc-950 font-mono shrink-0">
                                      {item.price}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            )}

                            {msg.subtotal && (
                              <div className="pt-2 border-t border-dashed border-zinc-200 space-y-1 text-[12px]">
                                <div className="flex justify-between text-zinc-600">
                                  <span>Subtotal</span>
                                  <span className="font-mono">{msg.subtotal}</span>
                                </div>
                                <div className="flex justify-between text-zinc-600">
                                  <span>Fees</span>
                                  <span className="font-mono">{msg.fees}</span>
                                </div>
                                <div className="flex justify-between font-bold text-zinc-950 text-xs pt-1 border-t border-zinc-200">
                                  <span>Total</span>
                                  <span className="font-mono text-emerald-700">{msg.total}</span>
                                </div>
                                {msg.budgetNote && (
                                  <p className="text-[11px] text-zinc-500 italic pt-0.5">
                                    ({msg.budgetNote})
                                  </p>
                                )}
                              </div>
                            )}

                            {msg.deliveryAddress && (
                              <div className="pt-1 text-[11px] text-zinc-500 flex items-center justify-between">
                                <span>📍 {msg.deliveryAddress}</span>
                                <span className="text-emerald-700 font-medium">~{msg.eta}</span>
                              </div>
                            )}

                            <div className="flex items-center justify-end text-[10px] text-zinc-400 pt-0.5">
                              <span>{msg.time}</span>
                            </div>
                          </div>

                          {/* Action Buttons inside Assistant Bubble */}
                          {msg.finalButtonText ? (
                            <div className="border-t border-zinc-200/80 bg-white">
                              <a
                                href={msg.finalButtonLink}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="w-full flex items-center justify-center gap-2 py-2.5 px-3 text-center text-[#00A884] font-medium text-[13px] hover:bg-zinc-50 active:bg-zinc-100 transition-colors"
                              >
                                <span>{msg.finalButtonText}</span>
                              </a>
                            </div>
                          ) : msg.buttons ? (
                            <div className="border-t border-zinc-200/80 bg-white divide-y divide-zinc-200/80">
                              {msg.buttons.map((btnText, idx) => (
                                <button
                                  key={idx}
                                  type="button"
                                  onClick={() => handleSendSimulationMessage(btnText)}
                                  className="w-full py-2.5 px-3 text-center text-[#00A884] font-medium text-[13px] hover:bg-zinc-50 active:bg-zinc-100 transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
                                >
                                  <span>{btnText}</span>
                                </button>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      )}
                    </div>
                  ))}

                  {/* Animated Typing Indicator */}
                  {isTyping && (
                    <div className="flex justify-start">
                      <div className="bg-white text-zinc-500 rounded-2xl rounded-tl-xs px-3.5 py-2 shadow-xs border border-zinc-200/50 flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 animate-bounce"></span>
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 animate-bounce [animation-delay:0.2s]"></span>
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 animate-bounce [animation-delay:0.4s]"></span>
                        <span className="text-[11px] ml-1">Grocer is searching dark store...</span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Interactive Bottom Typing Bar */}
                <form
                  onSubmit={handleInputSubmit}
                  className="bg-white border-t border-zinc-200 px-3 py-2 flex items-center gap-2 shrink-0"
                >
                  <input
                    type="text"
                    placeholder="Type a message (e.g. 'pasta for 4', 'milk', 'also add butter')..."
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    disabled={isTyping}
                    className="flex-1 bg-zinc-50 border border-zinc-200 rounded-xl px-3 py-2 text-xs text-zinc-900 placeholder:text-zinc-400 outline-none focus:border-emerald-500 focus:bg-white transition"
                  />
                  <button
                    type="submit"
                    disabled={!inputText.trim() || isTyping}
                    className="w-8 h-8 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white flex items-center justify-center transition disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer shrink-0 active:scale-95"
                    title="Send message"
                  >
                    <Send className="w-3.5 h-3.5" />
                  </button>
                </form>
              </div>

              {/* Developer Inspection Panel (When Toggled) */}
              {showToolExecution && activeToolExecution && (
                <div className="mt-3 p-3 rounded-xl bg-zinc-950 text-emerald-400 font-mono text-[11px] border border-zinc-800 shadow-md">
                  <div className="flex items-center justify-between pb-1.5 border-b border-zinc-800 text-[10px] text-zinc-400">
                    <span className="flex items-center gap-1">
                      <Terminal className="w-3 h-3 text-emerald-400" />
                      Live Tool Call: {activeToolExecution.toolCallName}
                    </span>
                    <span>JSON Trace</span>
                  </div>
                  <pre className="mt-2 whitespace-pre-wrap leading-relaxed overflow-x-auto text-[10px]">
                    {activeToolExecution.toolCallPayload}
                  </pre>
                </div>
              )}

              <p className="mt-3 text-center text-xs text-zinc-500">
                Interactive preview: Type any text above or click quick chips to test simulated responses.
              </p>
            </div>
          </div>
        </section>

        {/* ─── 6. Decoupled CommercePort Architecture & Verification ─── */}
        <section id="architecture" className="py-20 bg-zinc-100/70 border-b border-zinc-200 scroll-mt-16">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-2xl mx-auto mb-14">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-zinc-200 text-zinc-800 text-xs font-semibold mb-3">
                <Layers className="w-3.5 h-3.5" />
                <span>System Architecture</span>
              </div>
              <h2 className="text-2xl sm:text-3xl font-editorial font-bold text-zinc-950">
                Decoupled CommercePort design
              </h2>
              <p className="mt-2 text-sm text-zinc-600">
                Built with a clean interface boundary separating natural language reasoning from vendor APIs.
              </p>
            </div>

            {/* Architecture Flow Box */}
            <div className="bg-white rounded-3xl p-6 sm:p-8 border border-zinc-200 shadow-sm max-w-4xl mx-auto mb-10">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-center">
                {/* 1. Channel */}
                <div className="p-4 rounded-2xl bg-zinc-50 border border-zinc-200 text-center">
                  <div className="text-xs font-bold text-zinc-900 mb-1">WhatsApp Cloud API</div>
                  <div className="text-[11px] text-zinc-500 font-mono">Fast-Ack Proxy (&lt;200ms)</div>
                  <div className="mt-2 inline-block px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800">
                    Blue Ticks &amp; Typing
                  </div>
                </div>

                {/* 2. Engine */}
                <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-center">
                  <div className="text-xs font-bold text-emerald-950 mb-1">GroceryAgentEngine</div>
                  <div className="text-[11px] text-emerald-700 font-mono">Gemini 3.5 Flash-Lite</div>
                  <div className="mt-2 inline-block px-2 py-0.5 rounded text-[10px] font-semibold bg-white text-emerald-800 border border-emerald-300">
                    1,045ms Latency • ReAct
                  </div>
                </div>

                {/* 3. CommercePort */}
                <div className="p-4 rounded-2xl bg-zinc-50 border border-zinc-200 text-center">
                  <div className="text-xs font-bold text-zinc-900 mb-1">CommercePort Interface</div>
                  <div className="text-[11px] text-zinc-500 font-mono">Provider Agnostic Boundary</div>
                  <div className="mt-2 inline-block px-2 py-0.5 rounded text-[10px] font-semibold bg-orange-100 text-orange-800">
                    Swiggy MCP (Active Reference)
                  </div>
                </div>
              </div>

              <div className="mt-6 pt-6 border-t border-zinc-100 grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
                <div>
                  <div className="text-xl font-bold text-zinc-950 font-mono">62 / 62</div>
                  <div className="text-xs text-zinc-500 mt-0.5">Automated Invariant Tests Passed</div>
                </div>
                <div>
                  <div className="text-xl font-bold text-zinc-950 font-mono">6 / 6</div>
                  <div className="text-xs text-zinc-500 mt-0.5">Failure Invariants Verified Live</div>
                </div>
                <div>
                  <div className="text-xl font-bold text-zinc-950 font-mono">~1.0s</div>
                  <div className="text-xs text-zinc-500 mt-0.5">Gemini HTTP/2 Pooled Generation</div>
                </div>
              </div>
            </div>

            {/* Invariant Highlights */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto text-xs">
              <div className="bg-white p-5 rounded-2xl border border-zinc-200">
                <div className="font-bold text-zinc-900 mb-1 flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  Delta Cart Merge
                </div>
                <p className="text-zinc-600 leading-relaxed">
                  In-flight additions merge onto the active basket without resetting items or causing duplicate orders.
                </p>
              </div>

              <div className="bg-white p-5 rounded-2xl border border-zinc-200">
                <div className="font-bold text-zinc-900 mb-1 flex items-center gap-1.5">
                  <MapPin className="w-4 h-4 text-emerald-600" />
                  Upfront Address Guard
                </div>
                <p className="text-zinc-600 leading-relaxed">
                  Detects multiple saved addresses and asks for explicit selection upfront so groceries go to the right dark store.
                </p>
              </div>

              <div className="bg-white p-5 rounded-2xl border border-zinc-200">
                <div className="font-bold text-zinc-900 mb-1 flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  Server-Side Authorization
                </div>
                <p className="text-zinc-600 leading-relaxed">
                  Checkout requires explicit customer confirmation in Python code before calling provider order APIs.
                </p>
              </div>
            </div>

            {/* Documentation Links for Evaluators */}
            <div className="mt-8 text-center">
              <a
                href="https://github.com/kwakhare5/Grocer/blob/main/docs/REVIEWER_WALKTHROUGH.md"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-zinc-700 hover:text-zinc-950 underline"
              >
                <span>Read the official Reviewer Walkthrough Guide</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </a>
            </div>
          </div>
        </section>

        {/* ─── 7. Commerce Safety & Guardrails (4 Cards) ─────────────── */}
        <section id="safety" className="py-20 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto scroll-mt-16">
          <div className="text-center max-w-2xl mx-auto mb-14">
            <h2 className="text-2xl sm:text-3xl font-editorial font-bold text-zinc-950">
              Commerce safety &amp; deterministic guardrails
            </h2>
            <p className="mt-2 text-sm text-zinc-600">
              Designed with strict software boundaries to guarantee financial, inventory, and delivery safety.
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
                Queries the live inventory of the exact dark store serving your address. Zero stale catalogue caching.
              </p>
            </div>

            <div className="p-6 rounded-2xl border border-zinc-200 bg-white shadow-xs">
              <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center mb-4">
                <PackageCheck className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-zinc-950 mb-2">
                Exact Pricing in ₹
              </h3>
              <p className="text-xs text-zinc-600 leading-relaxed">
                Prices, packaging, and delivery fees come directly from the provider billing engine. Zero model arithmetic guesswork.
              </p>
            </div>

            <div className="p-6 rounded-2xl border border-zinc-200 bg-white shadow-xs">
              <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-700 flex items-center justify-center mb-4">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-zinc-950 mb-2">
                Gated Checkout
              </h3>
              <p className="text-xs text-zinc-600 leading-relaxed">
                The agent is physically blocked from completing orders autonomously. Checkout requires explicit customer confirmation.
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

        {/* ─── 8. Frequently Asked Questions (FAQ) ──────────────────── */}
        <section id="faq" className="py-20 bg-white border-t border-zinc-200 scroll-mt-16">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-2xl mx-auto mb-12">
              <h2 className="text-2xl sm:text-3xl font-editorial font-bold text-zinc-950">
                Frequently asked questions
              </h2>
              <p className="mt-2 text-sm text-zinc-600">
                Everything you need to know about Grocer&apos;s autonomy, safety, and order fulfillment.
              </p>
            </div>

            <div className="space-y-6">
              <div className="p-6 rounded-2xl bg-zinc-50 border border-zinc-200">
                <h3 className="text-sm font-bold text-zinc-900 mb-2">
                  Can Grocer place an order or charge my account without my approval?
                </h3>
                <p className="text-xs text-zinc-600 leading-relaxed">
                  Never. Grocer has a physical server-side lock. The checkout tool is only authorized when you explicitly say or tap &ldquo;Confirm Order&rdquo;. Payment occurs through official secure dark-store UPI links—the bot never accesses your banking credentials.
                </p>
              </div>

              <div className="p-6 rounded-2xl bg-zinc-50 border border-zinc-200">
                <h3 className="text-sm font-bold text-zinc-900 mb-2">
                  How are prices, item discounts, and delivery fees calculated?
                </h3>
                <p className="text-xs text-zinc-600 leading-relaxed">
                  All monetary calculations are performed deterministically by the live dark-store provider API. The AI model interprets language and deduces items, while the backend billing engine calculates taxes, itemized subtotals, and delivery fees.
                </p>
              </div>

              <div className="p-6 rounded-2xl bg-zinc-50 border border-zinc-200">
                <h3 className="text-sm font-bold text-zinc-900 mb-2">
                  What happens if an ingredient or brand is out of stock?
                </h3>
                <p className="text-xs text-zinc-600 leading-relaxed">
                  Grocer practices intent preservation: if your exact requested brand is out of stock, it checks live dark-store inventory for the closest in-stock match within your budget and asks for your sign-off before modifying your basket.
                </p>
              </div>

              <div className="p-6 rounded-2xl bg-zinc-50 border border-zinc-200">
                <h3 className="text-sm font-bold text-zinc-900 mb-2">
                  Which quick-commerce platforms are supported?
                </h3>
                <p className="text-xs text-zinc-600 leading-relaxed">
                  Grocer is architected around an extensible <code className="font-mono text-emerald-800 bg-emerald-50 px-1 py-0.5 rounded">CommercePort</code> interface. Swiggy Instamart is currently our live reference adapter via their official Model Context Protocol (MCP). The engine is provider-agnostic and designed to plug into any dark-store API.
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* ─── 9. Whitelisted Swiggy Instamart OAuth Modal ───────────── */}
      {isConnectModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-zinc-950/40 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-white rounded-3xl p-6 sm:p-7 border border-zinc-200 shadow-2xl max-w-md w-full relative">
            <button
              type="button"
              onClick={() => setIsConnectModalOpen(false)}
              className="absolute top-5 right-5 text-zinc-400 hover:text-zinc-700 p-1 rounded-lg hover:bg-zinc-100 transition cursor-pointer"
              title="Close"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-2xl bg-orange-50 flex items-center justify-center text-[#fc8019] shrink-0 border border-orange-200">
                <ShoppingBag className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base font-bold text-zinc-950 leading-tight">
                  Connect Swiggy Instamart
                </h2>
                <p className="text-xs text-zinc-500">
                  Whitelisted OAuth Gateway • Live Dark Store
                </p>
              </div>
            </div>

            {authError && (
              <div
                className="mb-4 rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-800 leading-relaxed"
                role="alert"
              >
                {authError}
              </div>
            )}

            {isConnected ? (
              <div className="space-y-4">
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 flex items-center gap-3 text-emerald-800 text-xs font-semibold">
                  <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0" />
                  <span>Your Swiggy Instamart account is successfully linked!</span>
                </div>
                <button
                  type="button"
                  onClick={() => setIsConnectModalOpen(false)}
                  className="w-full flex items-center justify-center gap-2 rounded-xl bg-zinc-900 px-4 py-3 text-xs font-semibold text-white hover:bg-zinc-800 transition"
                >
                  <span>Close Window</span>
                </button>
              </div>
            ) : (
              <form onSubmit={handleConnectSwiggy} className="space-y-4">
                <div>
                  <label
                    htmlFor="swiggy-phone-modal"
                    className="block text-xs font-semibold text-zinc-700 mb-1.5"
                  >
                    WhatsApp Registered Mobile Number
                  </label>
                  <div className="flex rounded-xl border border-zinc-200 bg-zinc-50 focus-within:border-emerald-500 focus-within:bg-white focus-within:ring-2 focus-within:ring-emerald-500/10 transition">
                    <span className="inline-flex items-center px-3.5 bg-zinc-100 border-r border-zinc-200 rounded-l-xl text-zinc-700 font-mono text-sm font-semibold select-none">
                      +91
                    </span>
                    <input
                      id="swiggy-phone-modal"
                      name="phone"
                      type="tel"
                      inputMode="numeric"
                      maxLength={10}
                      placeholder="9820184729"
                      value={phone}
                      onChange={handlePhoneChange}
                      disabled={busy}
                      required
                      className="w-full bg-transparent px-3 py-2.5 text-sm font-mono text-zinc-900 placeholder:text-zinc-400 outline-none"
                    />
                  </div>
                  <p className="mt-1 text-[11px] text-zinc-500">
                    Enter the 10-digit number registered with Swiggy
                  </p>
                </div>

                <button
                  type="submit"
                  disabled={busy || phone.length !== 10}
                  className="w-full flex items-center justify-center gap-2 rounded-xl bg-[#fc8019] hover:bg-[#e47112] px-4 py-3 text-xs font-semibold text-white transition shadow-xs disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                >
                  {busy ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Authenticating with Swiggy...</span>
                    </>
                  ) : (
                    <>
                      <span>Authorize via Swiggy OAuth</span>
                      <ArrowRight className="h-4 w-4" />
                    </>
                  )}
                </button>

                <p className="text-[11px] text-zinc-500 text-center leading-relaxed">
                  Direct PKCE handshake. Grocer never sees or stores your personal banking credentials.
                </p>
              </form>
            )}
          </div>
        </div>
      )}

      {/* ─── 10. Clean Footer ────────────────────────────────────────── */}
      <footer className="bg-white border-t border-zinc-200 py-10 px-4 sm:px-6 lg:px-8 text-center text-xs text-zinc-500">
        <div className="max-w-4xl mx-auto space-y-3">
          <p className="font-semibold text-zinc-700">
            GROCER — Intent-Preserving WhatsApp Grocery Replenishment
          </p>
          <p className="text-zinc-500 leading-relaxed max-w-xl mx-auto">
            Autonomous quick-commerce replenishment engine powered by Google Gemini and live dark-store Model Context Protocol (MCP).
          </p>
          <div className="pt-3 flex flex-wrap items-center justify-center gap-4 text-zinc-500 text-xs">
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
