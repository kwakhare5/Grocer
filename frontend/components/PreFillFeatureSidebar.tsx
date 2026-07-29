"use client";

import { useState, useEffect } from "react";
import { 
  TrendingDown, 
  MessageSquare, 
  Utensils, 
  Tag, 
  ShieldAlert,
  Sparkles,
  Check,
  CheckCircle2
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const SIDEBAR_ITEMS = [
  { id: "depletion", label: "Prophet Depletion Forecasting", icon: TrendingDown },
  { id: "restock", label: "LangGraph Restock Agent", icon: MessageSquare },
  { id: "recipe", label: "Recipe Gap Analyzer", icon: Utensils },
  { id: "price", label: "Commodity Price Signals", icon: Tag },
  { id: "anomaly", label: "Anomaly Spike Exclusion", icon: ShieldAlert },
];

const CONTENT_MAP: Record<string, { title: string; desc: string }> = {
  depletion: {
    title: "Prophet ML Depletion Modeling",
    desc: "Analyzes historical order timestamps and normalized item quantities to calculate per-household daily consumption velocity."
  },
  restock: {
    title: "Autonomous Restock Workflow",
    desc: "Triggers proactive 1-tap WhatsApp notifications 24 hours before stockouts, allowing instant household reordering."
  },
  recipe: {
    title: "Pantry-Aware Recipe Gap Parsing",
    desc: "Extracts ingredients from user recipes, checks live pantry inventory levels, and adds only missing items to the cart."
  },
  price: {
    title: "Real-time Commodity Price Tracking",
    desc: "Monitors daily price drops across staples and essentials, alerting households when preferred items hit historic lows."
  },
  anomaly: {
    title: "Anomaly Spike Exclusion Engine",
    desc: "Filters out one-off purchase spikes (like party orders or holiday hosting) to prevent skewing baseline consumption rates."
  }
};

export default function PreFillFeatureSidebar() {
  const [activeTab, setActiveTab] = useState("depletion");

  const activeContent = CONTENT_MAP[activeTab] || CONTENT_MAP.depletion;

  // Continuous background auto-cycle (every 3.5s)
  useEffect(() => {
    const timer = setInterval(() => {
      setActiveTab((prev) => {
        const currentIndex = SIDEBAR_ITEMS.findIndex((item) => item.id === prev);
        const nextIndex = (currentIndex + 1) % SIDEBAR_ITEMS.length;
        return SIDEBAR_ITEMS[nextIndex].id;
      });
    }, 3500);

    return () => clearInterval(timer);
  }, []);

  return (
    <div className="w-full bg-white border border-stone-200/90 rounded-3xl p-6 sm:p-10 shadow-sm relative overflow-hidden">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center z-10 relative">
        
        {/* Left Sidebar Menu (4 cols) */}
        <div className="lg:col-span-4 flex flex-col gap-2.5">
          <div className="flex items-center justify-between px-1 mb-1">
            <span className="text-[11px] font-bold text-stone-500 font-mono uppercase tracking-wider">
              Interactive Features
            </span>
          </div>

          {SIDEBAR_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full px-4 py-3 rounded-2xl text-xs font-semibold flex items-center gap-3 transition-all cursor-pointer select-none relative overflow-hidden ${
                  isActive
                    ? "bg-white text-[#252525] shadow-xs border border-stone-800"
                    : "text-stone-500 hover:text-[#252525] hover:bg-stone-50"
                }`}
              >
                <Icon className={`h-4 w-4 ${isActive ? "text-[#252525]" : "text-stone-400"}`} />
                <span className="text-left font-sans flex-1 font-extrabold">{item.label}</span>
              </button>
            );
          })}
        </div>

        {/* Right Main Showcase Panel (8 cols) */}
        <div className="lg:col-span-8 p-4 sm:p-6 flex flex-col lg:flex-row items-center justify-between gap-8 relative min-h-[260px]">
          
          {/* Left Text & CTA */}
          <div className="flex-1 flex flex-col items-start gap-4">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.25 }}
                className="flex flex-col gap-3 items-start"
              >
                <h3 className="text-2xl sm:text-3xl font-extrabold font-sans tracking-tight text-[#252525]">
                  {activeContent.title}
                </h3>
                <p className="text-xs sm:text-sm text-stone-600 font-medium leading-relaxed max-w-sm">
                  {activeContent.desc}
                </p>
                <a
                  href="#demo-stage"
                  className="mt-1 inline-flex items-center gap-2 bg-[#252525] text-white font-bold text-xs px-5 py-2.5 rounded-full shadow-xs hover:bg-stone-900 transition-all cursor-pointer active:scale-95"
                >
                  <span>Test Prototype</span>
                  <Sparkles className="h-3.5 w-3.5 text-white" />
                </a>
              </motion.div>
            </AnimatePresence>
          </div>

          {/* Right Motion Graphic Animated Container (Clean & Borderless) */}
          <div className="w-full max-w-[320px] flex flex-col gap-3 relative min-h-[200px]">
            
            <AnimatePresence mode="wait">
              
              {/* Graphic 1: Depletion Stock Bar Shrinking (100% -> 20%) */}
              {activeTab === "depletion" && (
                <motion.div
                  key="depletion-graphic"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ duration: 0.3 }}
                  className="flex flex-col gap-3 w-full"
                >
                  <div className="flex items-center justify-between text-xs font-bold text-stone-800">
                    <span>Fresh Milk 1L</span>
                    <span className="text-rose-600 font-mono text-[11px] font-extrabold">20% Stockout Threshold</span>
                  </div>
                  <div className="h-3 w-full bg-stone-200 rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: "90%" }}
                      animate={{ width: "20%" }}
                      transition={{ duration: 3.5, repeat: Infinity, repeatType: "reverse", ease: "easeInOut" }}
                      className="h-full bg-rose-500 rounded-full"
                    />
                  </div>
                  <div className="p-3 rounded-xl bg-white border border-rose-200 text-xs text-rose-800 font-medium shadow-2xs flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-rose-500 animate-pulse" />
                    <span>Prophet ML Alert: Triggering 24h restock notification.</span>
                  </div>
                </motion.div>
              )}

              {/* Graphic 2: WhatsApp Chat Slide-In */}
              {activeTab === "restock" && (
                <motion.div
                  key="restock-graphic"
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -15 }}
                  transition={{ duration: 0.3 }}
                  className="flex flex-col gap-2.5 w-full"
                >
                  <div className="p-3 rounded-xl bg-white border border-stone-200 text-xs text-stone-800 shadow-2xs leading-relaxed">
                    👋 Hi Rahul! Restock <span className="font-bold text-[#252525]">Fresh Milk 1L</span> & Eggs 6-pack for morning delivery?
                  </div>
                  <motion.div
                    initial={{ scale: 0.9, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: 0.4 }}
                    className="inline-flex items-center gap-2 self-start bg-emerald-700 text-white text-xs font-bold px-3.5 py-1.5 rounded-full shadow-xs"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    <span>Customer Confirmed &apos;YES&apos;</span>
                  </motion.div>
                </motion.div>
              )}

              {/* Graphic 3: Recipe Ingredient Checklist Animation */}
              {activeTab === "recipe" && (
                <motion.div
                  key="recipe-graphic"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ duration: 0.3 }}
                  className="flex flex-col gap-2 w-full text-xs font-medium"
                >
                  <span className="font-bold text-stone-800">Recipe: Paneer Butter Masala</span>
                  <div className="flex flex-col gap-1.5 pt-1">
                    <div className="flex items-center gap-2 text-emerald-700 bg-emerald-50 p-1.5 rounded border border-emerald-200">
                      <Check className="h-3.5 w-3.5" />
                      <span>Paneer 200g — In Stock</span>
                    </div>
                    <div className="flex items-center gap-2 text-emerald-700 bg-emerald-50 p-1.5 rounded border border-emerald-200">
                      <Check className="h-3.5 w-3.5" />
                      <span>Spices & Tomatos — In Stock</span>
                    </div>
                    <motion.div
                      initial={{ scale: 0.95 }}
                      animate={{ scale: 1 }}
                      className="flex items-center justify-between text-rose-700 bg-rose-50 p-1.5 rounded border border-rose-200 font-bold"
                    >
                      <span>Butter 200g — Missing</span>
                      <span className="bg-rose-600 text-white px-2 py-0.5 rounded text-[10px] uppercase font-mono">Added to Cart</span>
                    </motion.div>
                  </div>
                </motion.div>
              )}

              {/* Graphic 4: Commodity Price Signals Dip */}
              {activeTab === "price" && (
                <motion.div
                  key="price-graphic"
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -15 }}
                  transition={{ duration: 0.3 }}
                  className="flex flex-col gap-2.5 w-full"
                >
                  <div className="flex items-center justify-between text-xs font-bold text-stone-800">
                    <span>Sunflower Oil 1L Price Signal</span>
                    <span className="bg-emerald-600 text-white text-[10px] font-mono font-bold px-2 py-0.5 rounded">-23% Dip</span>
                  </div>
                  <svg className="w-full h-10 stroke-emerald-600 fill-none" viewBox="0 0 200 40">
                    <path d="M 0 10 L 60 12 L 120 15 L 160 35 L 200 32" strokeWidth="3" />
                  </svg>
                  <div className="p-2 rounded-xl bg-white border border-stone-200 text-xs text-stone-800 font-semibold shadow-2xs">
                    Historic Dip Alert: Save ₹180 on 2L reorder.
                  </div>
                </motion.div>
              )}

              {/* Graphic 5: Anomaly Spike Exclusion */}
              {activeTab === "anomaly" && (
                <motion.div
                  key="anomaly-graphic"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ duration: 0.3 }}
                  className="flex flex-col gap-2.5 w-full"
                >
                  <div className="flex items-center justify-between text-xs font-bold text-stone-800">
                    <span>Party Spike Anomaly</span>
                    <span className="bg-amber-50 text-amber-800 border border-amber-200/80 text-[9px] font-mono px-2 py-0.5 rounded-full font-bold">Flagged & Filtered</span>
                  </div>
                  <div className="p-3 rounded-xl bg-white border border-stone-200 text-xs text-stone-800 leading-relaxed shadow-2xs">
                    5x Soft Drinks ordered on Saturday (Party Spike). Baseline trajectory unaffected.
                  </div>
                </motion.div>
              )}

            </AnimatePresence>

          </div>

        </div>

      </div>
    </div>
  );
}
