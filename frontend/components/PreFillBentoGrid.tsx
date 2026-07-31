"use client";

import { useState, useCallback } from "react";
import { 
  Cpu, 
  BarChart2,
  Database,
  ShieldCheck,
  CheckCircle2,
  ArrowRight,
  MessageSquare
} from "lucide-react";
import { motion } from "framer-motion";

const TRACKED_ITEMS = [
  { code: "MILK", name: "Fresh Milk 1L", depletion: "24h left", pct: 20, color: "bg-rose-500" },
  { code: "ATTA", name: "Chakki Atta 5kg", depletion: "5 days left", pct: 65, color: "bg-emerald-500" },
  { code: "OIL", name: "Sunflower Oil 1L", depletion: "2 days left", pct: 35, color: "bg-amber-500" },
  { code: "EGGS", name: "Eggs 6-Pack", depletion: "12h left", pct: 15, color: "bg-rose-500" }
];

export default function PreFillBentoGrid() {
  const [anomalyMode, setAnomalyMode] = useState<"party" | "filtered">("filtered");

  const handleSelectFiltered = useCallback(() => setAnomalyMode("filtered"), []);
  const handleSelectParty = useCallback(() => setAnomalyMode("party"), []);

  return (
    <div className="w-full max-w-6xl py-14 sm:py-20 flex flex-col items-center">
      
      {/* Header */}
      <motion.div 
        initial={{ opacity: 0, y: 15 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5 }}
        className="text-center max-w-xl mx-auto flex flex-col items-center gap-2 mb-8 sm:mb-10"
      >
        <span className="badge-droxy-pill">
          Core Engine Architecture
        </span>
        <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight-display text-[#252525] mt-1 font-sans">
          How PreFill Powers Proactive Restocking
        </h2>
      </motion.div>

      {/* Asymmetric 6-Card Bento Grid */}
      <div className="w-full grid grid-cols-1 md:grid-cols-12 gap-6">
        
        {/* Card 1: Prophet Consumption Velocity (4 cols) */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="md:col-span-4 card-neutral-droxy flex flex-col justify-between gap-5 bg-white relative overflow-hidden hover:border-stone-400 transition-all"
        >
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <span className="p-2 rounded-xl bg-blue-50 text-blue-700 border border-blue-200/80">
                <BarChart2 className="h-4 w-4" />
              </span>
              <h3 className="text-lg font-extrabold font-sans text-[#252525]">Prophet Depletion Modeling</h3>
            </div>
            <p className="text-xs text-stone-600 font-medium leading-relaxed">
              Calculates daily consumption velocity per item and predicts stockouts 24h before hitting threshold.
            </p>
          </div>

          {/* Telemetry Stock Bars */}
          <div className="flex flex-col gap-2.5 pt-1">
            {TRACKED_ITEMS.map((item) => (
              <div key={item.code} className="flex flex-col gap-1">
                <div className="flex items-center justify-between text-[11px] font-bold text-stone-800 font-mono">
                  <span>{item.name}</span>
                  <span className="text-stone-500 text-[10px]">{item.depletion}</span>
                </div>
                <div className="h-2 w-full rounded-full bg-stone-100 overflow-hidden">
                  <div 
                    className={`h-full rounded-full ${item.color} transition-all duration-500`} 
                    style={{ width: `${item.pct}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Card 2: LangGraph State Persistence (4 cols) */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="md:col-span-4 card-neutral-droxy flex flex-col justify-between gap-5 bg-white relative overflow-hidden hover:border-stone-400 transition-all"
        >
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <span className="p-2 rounded-xl bg-emerald-50 text-emerald-700 border border-emerald-200/80">
                <Cpu className="h-4 w-4" />
              </span>
              <h3 className="text-lg font-extrabold font-sans text-[#252525]">LangGraph Checkpointer</h3>
            </div>
            <p className="text-xs text-stone-600 font-medium leading-relaxed">
              PostgreSQL-backed state persistence remembers household cart preferences and price signals across restarts.
            </p>
          </div>

          {/* Sparkline Telemetry Box */}
          <div className="p-3.5 rounded-2xl bg-stone-50 border border-stone-200/80 shadow-2xs flex flex-col gap-2.5">
            <div className="flex items-center justify-between text-[10px] text-stone-500 font-mono">
              <span>Node Latency SLA</span>
              <span className="text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200/60">140ms</span>
            </div>
            
            <svg className="w-full h-8 stroke-stone-800 fill-none" viewBox="0 0 200 40">
              <path d="M 0 30 Q 30 10, 60 25 T 120 15 T 180 5 T 200 10" strokeWidth="2.5" />
            </svg>

            <div className="flex items-center justify-between text-[11px] font-sans pt-1 border-t border-stone-200/80">
              <span className="text-stone-600 font-medium">Postgres Checkpoints</span>
              <span className="text-stone-900 font-bold font-mono">1,291 Active</span>
            </div>
          </div>
        </motion.div>

        {/* Card 3: Universal API Webhooks (4 cols) */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="md:col-span-4 card-neutral-droxy flex flex-col justify-between gap-5 bg-white relative overflow-hidden hover:border-stone-400 transition-all"
        >
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <span className="p-2 rounded-xl bg-amber-50 text-amber-700 border border-amber-200/80">
                <Database className="h-4 w-4" />
              </span>
              <h3 className="text-lg font-extrabold font-sans text-[#252525]">Universal API Webhooks</h3>
            </div>
            <p className="text-xs text-stone-600 font-medium leading-relaxed">
              Ingests raw order receipts and delivery webhooks from quick commerce APIs, normalizing item units.
            </p>
          </div>

          {/* Central Node Diagram */}
          <div className="p-3 rounded-2xl bg-stone-50 border border-stone-200/80 flex items-center justify-between gap-2">
            <div className="flex flex-col gap-1 text-[10px] font-mono font-semibold text-stone-600">
              <span className="bg-white px-2 py-1 rounded border border-stone-200">Delivery Webhook</span>
              <span className="bg-white px-2 py-1 rounded border border-stone-200">Shopify API</span>
            </div>
            <ArrowRight className="h-4 w-4 text-stone-400 shrink-0" />
            <div className="h-9 w-9 rounded-xl bg-[#252525] text-white flex items-center justify-center font-extrabold text-xs shrink-0 shadow-xs">
              P
            </div>
            <ArrowRight className="h-4 w-4 text-stone-400 shrink-0" />
            <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 px-2.5 py-1.5 rounded-xl text-[10px] font-mono font-bold">
              WhatsApp
            </div>
          </div>
        </motion.div>

        {/* Card 4: 1-Tap WhatsApp Trigger (7 cols) */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="md:col-span-7 card-neutral-droxy flex flex-col justify-between gap-5 bg-white relative overflow-hidden hover:border-stone-400 transition-all"
        >
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="p-2 rounded-xl bg-emerald-50 text-emerald-700 border border-emerald-200/80">
                  <MessageSquare className="h-4 w-4" />
                </span>
                <h3 className="text-xl font-extrabold font-sans text-[#252525]">1-Tap WhatsApp Restock Agent</h3>
              </div>
              <span className="text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200/80 font-mono">
                Active Channel
              </span>
            </div>
            <p className="text-xs text-stone-600 font-medium leading-relaxed">
              Delivers instant pre-filled restocking carts directly to WhatsApp. Households reply with 1-tap confirmation with zero app browsing.
            </p>
          </div>

          {/* Simulated WhatsApp Chat Box */}
          <div className="p-4 rounded-2xl bg-stone-50 border border-stone-200/80 flex flex-col gap-2.5">
            <div className="flex items-center gap-2 pb-2 border-b border-stone-200/80">
              <div className="h-5 w-5 rounded-full bg-emerald-600 text-white flex items-center justify-center text-[10px] font-bold">
                P
              </div>
              <span className="text-xs font-bold text-stone-800">PreFill Assistant</span>
              <span className="text-[10px] text-emerald-700 font-mono ml-auto">● Online</span>
            </div>
            <div className="p-3 rounded-xl bg-white border border-stone-200/90 text-xs text-stone-800 shadow-2xs leading-relaxed">
              👋 Hi Rahul! Your <span className="font-bold text-[#252525]">Fresh Milk 1L</span> is at 20% threshold. Tap below to confirm restock for morning delivery (₹64).
            </div>
            <div className="inline-flex items-center gap-2 self-start bg-emerald-700 text-white text-xs font-bold px-4 py-2 rounded-full shadow-xs cursor-pointer hover:bg-emerald-800 transition-all active:scale-95">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>Confirm Restock Order</span>
            </div>
          </div>
        </motion.div>

        {/* Card 5: Anomaly Spike Exclusion (5 cols) */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="md:col-span-5 card-neutral-droxy flex flex-col justify-between gap-5 bg-white relative overflow-hidden hover:border-stone-400 transition-all"
        >
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <span className="p-2 rounded-xl bg-rose-50 text-rose-700 border border-rose-200/80">
                <ShieldCheck className="h-4 w-4" />
              </span>
              <h3 className="text-lg font-extrabold font-sans text-[#252525]">Anomaly Spike Exclusion</h3>
            </div>
            <p className="text-xs text-stone-600 font-medium leading-relaxed">
              Filters out abnormal purchase spikes (e.g. party hosting) so baseline consumption velocity rates stay 100% accurate.
            </p>
          </div>

          {/* Interactive Anomaly Toggle */}
            <div className="p-3.5 rounded-2xl bg-stone-50 border border-stone-200/80 flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-stone-700 font-sans">Filter Mode:</span>
                <div className="flex items-center gap-1 bg-stone-200/70 p-1 rounded-full text-[9.5px] font-bold font-mono">
                  <button
                    onClick={handleSelectParty}
                    className={`px-2.5 py-0.5 rounded-full transition-all cursor-pointer active:scale-95 ${
                      anomalyMode === "party" ? "bg-white text-stone-900 shadow-2xs border border-stone-200" : "text-stone-500 hover:text-stone-800"
                    }`}
                  >
                    Raw Spike
                  </button>
                  <button
                    onClick={handleSelectFiltered}
                    className={`px-2.5 py-0.5 rounded-full transition-all cursor-pointer active:scale-95 ${
                      anomalyMode === "filtered" ? "bg-emerald-700 text-white shadow-2xs" : "text-stone-500 hover:text-stone-800"
                    }`}
                  >
                    Filtered Baseline
                  </button>
                </div>
              </div>

              <div className="p-2.5 rounded-xl bg-white border border-stone-200 text-xs font-semibold text-stone-800 flex items-center justify-between shadow-2xs">
                <span className="font-sans text-[11px] font-medium">{anomalyMode === "party" ? "5x Soda Drinks (Party Anomaly)" : "1x Soda Drink (Normalized Baseline)"}</span>
                <span className={`text-[9px] px-2 py-0.5 rounded-full font-mono font-bold border ${
                  anomalyMode === "party" ? "bg-amber-50 text-amber-800 border-amber-200" : "bg-emerald-50 text-emerald-800 border-emerald-200"
                }`}>
                  {anomalyMode === "party" ? "Raw Signal" : "Anomaly Excluded"}
                </span>
              </div>
            </div>
        </motion.div>

      </div>

    </div>
  );
}
