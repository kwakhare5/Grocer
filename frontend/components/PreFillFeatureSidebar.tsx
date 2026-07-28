"use client";

import { useState } from "react";
import { 
  TrendingDown, 
  MessageSquare, 
  Utensils, 
  Tag, 
  ShieldAlert,
  Sparkles
} from "lucide-react";

// ponytail: static constants moved outside component body to avoid re-allocation on render
const SIDEBAR_ITEMS = [
  { id: "depletion", label: "Prophet Depletion Forecasting", icon: TrendingDown },
  { id: "restock", label: "LangGraph Restock Agent", icon: MessageSquare },
  { id: "recipe", label: "Recipe Gap Analyzer", icon: Utensils },
  { id: "price", label: "Commodity Price Signals", icon: Tag },
  { id: "anomaly", label: "Anomaly Spike Exclusion", icon: ShieldAlert },
];

const CONTENT_MAP: Record<string, { title: string; desc: string; msg1: string; msg2: string; msg3: string }> = {
  depletion: {
    title: "Prophet ML Depletion Modeling",
    desc: "Analyzes historical order timestamps and normalized item quantities to calculate per-household daily consumption velocity.",
    msg1: "Fresh Milk 1L — 20% remaining threshold reached (ETA 24h)",
    msg2: "Pantry Atta 5kg — Consumption rate 0.45kg/day (Depletion Aug 2)",
    msg3: "Sunflower Oil 1L — Stable trajectory, restock prompt scheduled"
  },
  restock: {
    title: "Autonomous Restock Workflow",
    desc: "Triggers proactive 1-tap WhatsApp notifications 24 hours before stockouts, allowing instant household reordering.",
    msg1: "WhatsApp Alert Sent: Fresh Milk 1L & Eggs 6-pack restock?",
    msg2: "Customer Reply: 'YES' → 1-tap cart generated",
    msg3: "Order Dispatched to Quick Commerce API (10-min delivery)"
  },
  recipe: {
    title: "Pantry-Aware Recipe Gap Parsing",
    desc: "Extracts ingredients from user recipes, checks live pantry inventory levels, and adds only missing items to the cart.",
    msg1: "Recipe Parsed: Paneer Butter Masala",
    msg2: "Pantry Audit: Paneer & Spices in stock; Butter 200g missing",
    msg3: "Cart Built: 1x Butter 200g added to restock list"
  },
  price: {
    title: "Real-time Commodity Price Tracking",
    desc: "Monitors daily price drops across staples and essentials, alerting households when preferred items hit historic lows.",
    msg1: "Price Signal: Cold-Pressed Oil price dropped -23%",
    msg2: "Smart Alert: Recommend 2L bulk purchase to save ₹180",
    msg3: "Household Action: Added to upcoming weekly restock"
  },
  anomaly: {
    title: "Anomaly Spike Exclusion Engine",
    desc: "Filters out one-off purchase spikes (like party orders or holiday hosting) to prevent skewing baseline consumption rates.",
    msg1: "Spike Detected: 5x Soft Drinks ordered on Saturday",
    msg2: "Anomaly Flagged: Excluded from Prophet baseline model",
    msg3: "Model Accuracy Preserved: Normal 1x/week rate maintained"
  }
};

export default function PreFillFeatureSidebar() {
  const [activeTab, setActiveTab] = useState("depletion");
  const activeContent = CONTENT_MAP[activeTab] || CONTENT_MAP.depletion;

  return (
    <div className="w-full bg-[#FFFFFF] border border-stone-200/90 rounded-3xl p-6 sm:p-10 shadow-[0_4px_24px_rgba(0,0,0,0.03)] bg-ascii-dotted-grid relative overflow-hidden">
      
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center z-10 relative">
        
        {/* Left Sidebar Menu (4 cols) */}
        <div className="lg:col-span-4 flex flex-col gap-2.5">
          {SIDEBAR_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full px-4 py-3 rounded-full text-xs font-semibold flex items-center gap-3 transition-all cursor-pointer select-none ${
                  isActive
                    ? "bg-white text-[#252525] shadow-[0_2px_10px_rgba(0,0,0,0.08)] border border-stone-200"
                    : "text-stone-500 hover:text-[#252525] hover:bg-stone-100/60"
                }`}
              >
                <Icon className={`h-4 w-4 ${isActive ? "text-[#252525]" : "text-stone-400"}`} />
                <span className="text-left font-sans">{item.label}</span>
              </button>
            );
          })}
        </div>

        {/* Right Main Showcase Panel (8 cols - Pastel Amber Styled) */}
        <div className="lg:col-span-8 card-pastel-amber p-6 sm:p-8 flex flex-col lg:flex-row items-center justify-between gap-8 shadow-xs relative">
          
          {/* Left Text & CTA */}
          <div className="flex-1 flex flex-col items-start gap-4">
            <h3 className="text-2xl sm:text-3xl font-extrabold font-sans tracking-tight title-accent">
              {activeContent.title}
            </h3>
            <p className="text-xs sm:text-sm text-stone-700 font-medium leading-relaxed max-w-sm">
              {activeContent.desc}
            </p>
            <a
              href="#demo-stage"
              className="mt-2 inline-flex items-center gap-2 bg-white text-[#252525] font-bold text-xs px-5 py-2.5 rounded-full border border-stone-300 shadow-xs hover:bg-stone-50 transition-all cursor-pointer"
            >
              <span>Test Interactive Demo</span>
              <Sparkles className="h-3.5 w-3.5 text-stone-700" />
            </a>
          </div>

          {/* Right Live Stream UI Mockup */}
          <div className="w-full max-w-[320px] bg-white rounded-2xl border border-amber-200 p-4 shadow-sm flex flex-col gap-3 relative">
            
            {/* Header user */}
            <div className="flex items-center justify-between border-b border-stone-100 pb-3">
              <div className="flex items-center gap-2">
                <div className="h-6 w-6 rounded-full bg-[#252525] text-white flex items-center justify-center text-[10px] font-extrabold font-sans">
                  P
                </div>
                <div className="text-[11px] font-bold text-[#252525] font-sans">PreFill Engine Telemetry</div>
              </div>
              <span className="text-[10px] text-emerald-700 font-semibold font-mono">Live Sync</span>
            </div>

            {/* Telemetry Stream List */}
            <div className="flex flex-col gap-2.5">
              
              {/* Event 1 */}
              <div className="p-2.5 rounded-xl bg-emerald-50/70 border border-emerald-100 flex items-center gap-2.5">
                <div className="h-2 w-2 rounded-full bg-emerald-600 shrink-0" />
                <span className="text-[11px] text-stone-700 font-medium leading-tight">
                  {activeContent.msg1}
                </span>
              </div>

              {/* Event 2 */}
              <div className="p-2.5 rounded-xl bg-blue-50/70 border border-blue-100 flex items-center gap-2.5">
                <div className="h-2 w-2 rounded-full bg-blue-600 shrink-0" />
                <span className="text-[11px] text-stone-700 font-medium leading-tight">
                  {activeContent.msg2}
                </span>
              </div>

              {/* Event 3 */}
              <div className="p-2.5 rounded-xl bg-amber-50/70 border border-amber-100 flex items-center gap-2.5">
                <div className="h-2 w-2 rounded-full bg-amber-600 shrink-0" />
                <span className="text-[11px] text-stone-700 font-medium leading-tight">
                  {activeContent.msg3}
                </span>
              </div>

            </div>

            {/* Clean Badges */}
            <div className="flex items-center justify-center gap-2 mt-1">
              <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 text-[10px] font-bold font-mono">FastAPI</span>
              <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-800 border border-blue-200 text-[10px] font-bold font-mono">LangGraph</span>
              <span className="px-2 py-0.5 rounded bg-stone-100 text-stone-700 border border-stone-200 text-[10px] font-bold font-mono">Prophet ML</span>
            </div>

          </div>

        </div>

      </div>

    </div>
  );
}
