"use client";

import { 
  RefreshCw, 
  Cpu, 
  Zap,
  BarChart2,
  Database,
  ShieldCheck
} from "lucide-react";

export default function PreFillBentoGrid() {
  const trackedItems = [
    { code: "MILK", name: "Fresh Milk 1L", depletion: "24h left" },
    { code: "ATTA", name: "Chakki Atta 5kg", depletion: "5 days left" },
    { code: "OIL", name: "Sunflower Oil 1L", depletion: "2 days left" },
    { code: "EGGS", name: "Eggs 6-Pack", depletion: "12h left" },
    { code: "RICE", name: "Basmati Rice 5kg", depletion: "12 days left" },
    { code: "TEA", name: "Assam Tea 250g", depletion: "4 days left" },
  ];

  return (
    <div className="w-full max-w-5xl py-12 flex flex-col items-center">
      
      {/* H2 Header */}
      <div className="text-center max-w-xl mx-auto flex flex-col items-center gap-2 mb-12">
        <span className="badge-droxy-pill">
          Core Engine Architecture
        </span>
        <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight-display text-[#252525] mt-1 font-sans">
          How PreFill Powers Proactive Restocking
        </h2>
      </div>

      {/* 6 Bento Grid Cards (PreFill Technical Architecture) */}
      <div className="w-full grid grid-cols-1 md:grid-cols-12 gap-6">
        
        {/* Card 1: Prophet Consumption Velocity (Pastel Sky Blue Family) */}
        <div className="md:col-span-4 card-pastel-blue flex flex-col justify-between gap-5 bg-ascii-dotted-grid relative overflow-hidden">
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <BarChart2 className="h-5 w-5 text-blue-700" />
              <h3 className="text-xl font-extrabold font-sans title-accent">Prophet Depletion Modeling</h3>
            </div>
            <p className="text-xs text-stone-600 font-medium leading-relaxed">
              Calculates daily consumption velocity per item and predicts depletion dates 24 hours before reaching the 20% remaining threshold.
            </p>
          </div>

          {/* Tracked Items Telemetry List */}
          <div className="flex flex-col gap-1.5 pt-2">
            {trackedItems.map((item) => (
              <div 
                key={item.code}
                className="px-3 py-1.5 rounded-xl bg-white border border-blue-200/80 text-[11px] font-bold text-blue-950 shadow-2xs flex items-center justify-between"
              >
                <div className="flex items-center gap-2">
                  <span className="text-[9px] text-blue-500 font-mono">{item.code}</span>
                  <span>{item.name}</span>
                </div>
                <span className="text-[10px] text-emerald-700 font-semibold">{item.depletion}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Card 2: LangGraph State Persistence (Pastel Sky Blue Family) */}
        <div className="md:col-span-4 card-pastel-blue flex flex-col justify-between gap-5 bg-ascii-dotted-grid relative overflow-hidden">
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <Cpu className="h-5 w-5 text-blue-700" />
              <h3 className="text-xl font-extrabold font-sans title-accent">LangGraph Checkpointer</h3>
            </div>
            <p className="text-xs text-stone-600 font-medium leading-relaxed">
              PostgreSQL-backed LangGraph state persistence remembers household preferences, active cart items, and price signals across restarts.
            </p>
          </div>

          {/* Sparkline Telemetry Box */}
          <div className="p-4 rounded-2xl bg-white border border-blue-200/80 shadow-2xs flex flex-col gap-3">
            <div className="flex items-center justify-between text-[10px] text-blue-400 font-mono">
              <span>LangGraph Nodes</span>
              <span>Postgres Checkpoints</span>
            </div>
            
            <svg className="w-full h-8 stroke-blue-600 fill-none" viewBox="0 0 200 40">
              <path d="M 0 30 Q 30 10, 60 25 T 120 15 T 180 5 T 200 10" strokeWidth="2.5" />
            </svg>

            <div className="flex flex-col gap-1.5 pt-1 border-t border-blue-100 text-xs font-sans">
              <div className="flex items-center justify-between font-semibold">
                <span className="text-stone-600">Restock Graph Latency</span>
                <span className="text-blue-950 font-bold">140ms <span className="text-emerald-600 text-[10px]">99.8% SLA</span></span>
              </div>
              <div className="flex items-center justify-between font-semibold">
                <span className="text-stone-600">Active Checkpoints</span>
                <span className="text-blue-950 font-bold">1,291 <span className="text-emerald-600 text-[10px]">Postgres SQL</span></span>
              </div>
            </div>
          </div>
        </div>

        {/* Card 3: Quick Commerce Webhooks (Pastel Mint Green Family) */}
        <div className="md:col-span-4 card-pastel-green flex flex-col justify-between gap-5 bg-ascii-dotted-grid relative overflow-hidden">
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <Database className="h-5 w-5 text-emerald-700" />
              <h3 className="text-xl font-extrabold font-sans title-accent">Universal API Webhooks</h3>
            </div>
            <p className="text-xs text-stone-600 font-medium leading-relaxed">
              Ingests raw order receipts and delivery webhooks from quick commerce APIs, normalizing item quantities into standardized units.
            </p>
          </div>

          {/* Central Node Graph */}
          <div className="h-32 w-full flex items-center justify-center relative">
            <div className="h-12 w-12 rounded-full bg-emerald-700 text-white flex items-center justify-center font-extrabold text-base shadow-md z-10 font-sans">
              P
            </div>
            
            <div className="absolute top-2 left-4 p-2 rounded-xl bg-white border border-emerald-200 text-[11px] shadow-2xs font-semibold text-emerald-900 font-mono">Order Webhook</div>
            <div className="absolute top-2 right-4 p-2 rounded-xl bg-white border border-emerald-200 text-[11px] shadow-2xs font-semibold text-emerald-900 font-mono">WhatsApp API</div>
            <div className="absolute bottom-2 left-4 p-2 rounded-xl bg-white border border-emerald-200 text-[11px] shadow-2xs font-semibold text-emerald-900 font-mono">Receipt Parser</div>
            <div className="absolute bottom-2 right-4 p-2 rounded-xl bg-white border border-emerald-200 text-[11px] shadow-2xs font-semibold text-emerald-900 font-mono">Shopify SDK</div>
          </div>
        </div>

        {/* Card 4: Anomaly Spike Exclusion (Pastel Warm Amber Family) */}
        <div className="md:col-span-4 card-pastel-amber flex flex-col justify-between gap-4 bg-ascii-dotted-grid relative">
          <div className="flex flex-col gap-2">
            <ShieldCheck className="h-5 w-5 text-amber-700" />
            <h3 className="text-xl font-extrabold font-sans title-accent">Anomaly Exclusion</h3>
            <p className="text-xs text-stone-600 font-medium leading-relaxed">
              Detects and excludes irregular purchase spikes (e.g. party orders) so Prophet consumption velocity stays 100% accurate.
            </p>
          </div>
        </div>

        {/* Card 5: 1-Tap WhatsApp Reorder (Pastel Rose Red Family) */}
        <div className="md:col-span-4 card-pastel-red flex flex-col justify-between gap-4 bg-ascii-dotted-grid relative">
          <div className="flex flex-col gap-2">
            <Zap className="h-5 w-5 text-rose-700" />
            <h3 className="text-xl font-extrabold font-sans title-accent">1-Tap WhatsApp Checkout</h3>
            <p className="text-xs text-stone-600 font-medium leading-relaxed">
              Customers reply &apos;YES&apos; on WhatsApp to automatically dispatch 10-minute grocery restocks without opening an app.
            </p>
          </div>
        </div>

        {/* Card 6: Recapturing Kirana Leakage (Pastel Warm Amber Family) */}
        <div className="md:col-span-4 card-pastel-amber flex flex-col justify-between gap-4 bg-ascii-dotted-grid relative">
          <div className="flex flex-col gap-2">
            <RefreshCw className="h-5 w-5 text-amber-700" />
            <h3 className="text-xl font-extrabold font-sans title-accent">Recapturing Kirana Spend</h3>
            <p className="text-xs text-stone-600 font-medium leading-relaxed">
              Recaptures +₹1,450 monthly grocery spend per household lost to offline Kirana stores due to emergency stockouts.
            </p>
          </div>

          <div className="flex items-center gap-3 pt-2">
            <div className="h-9 w-9 rounded-full bg-[#252525] text-white flex items-center justify-center font-bold text-xs font-sans">P</div>
            <span className="text-amber-700 font-bold">+</span>
            <div className="px-3 py-1.5 rounded-full bg-emerald-100 text-emerald-900 border border-emerald-300 font-bold text-xs font-mono">
              +₹1,450/hh Recaptured
            </div>
          </div>
        </div>

      </div>

    </div>
  );
}
