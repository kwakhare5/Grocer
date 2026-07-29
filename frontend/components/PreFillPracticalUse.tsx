"use client";

import { useState } from "react";
import { CheckCircle2, PhoneCall, User, Wrench } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

// ponytail: static tabs array moved outside component body to avoid re-allocation on render
const PRACTICAL_TABS = [
  {
    name: "Fresh Dairy & Milk",
    title: "Daily Dairy & Milk Depletion",
    bullets: [
      "Never run out of morning milk — Prophet models daily household tea & cereal usage.",
      "Predicts 20% remaining threshold 24 hours before stockout.",
      "Delivers 1-tap WhatsApp prompt for instant 10-minute quick commerce restocking."
    ],
    user: "Family Household",
    detail: "Fresh Milk 1L & Curd 500g",
    status: "Prophet Predicted",
    time: "Depletion in 18h"
  },
  {
    name: "Pantry Staples & Atta",
    title: "Grain & Pantry Staples",
    bullets: [
      "Tracks consumption cycles for Atta 5kg, Rice 10kg, and Dal staples.",
      "Automatically adjusts for family size (Solo, Couple, Small/Large Family).",
      "Filters out party spikes so large weekend meals don't break baseline predictions."
    ],
    user: "Large Family (4 Persons)",
    detail: "Chakki Fresh Atta 5kg & Rice 10kg",
    status: "Threshold Alert",
    time: "Reorder Triggered"
  },
  {
    name: "Household Cleaners",
    title: "Home & Laundry Supplies",
    bullets: [
      "Monitors high-friction household replenishment items like detergent and dish soap.",
      "Eliminates emergency night store trips when laundry detergent runs dry.",
      "Sends automated WhatsApp reminder when stock drops to 2 days remaining."
    ],
    user: "Couple Household",
    detail: "Liquid Detergent 1L & Dishwash Gel",
    status: "Smart Alert",
    time: "Scheduled Reorder"
  },
  {
    name: "Specialty Organics",
    title: "Organic Oils & Superfoods",
    bullets: [
      "Monitors daily commodity price signals for cold-pressed oils, ghee, and organic tea.",
      "Triggers restock alerts when preferred specialty items hit historic price drops.",
      "Builds recipe-aware carts so you only buy missing specialty ingredients."
    ],
    user: "Solo Household",
    detail: "Cold-Pressed Sunflower Oil 1L",
    status: "Price Signal",
    time: "23% Price Drop Alert"
  }
];

export default function PreFillPracticalUse() {
  const [activeTab, setActiveTab] = useState(0);
  const currentTab = PRACTICAL_TABS[activeTab] || PRACTICAL_TABS[0];

  return (
    <div className="w-full max-w-6xl py-14 sm:py-20 flex flex-col items-center">
      
      {/* Badge & H2 */}
      <motion.div 
        initial={{ opacity: 0, y: 15 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5 }}
        className="text-center max-w-xl mx-auto flex flex-col items-center gap-2 mb-8 sm:mb-10"
      >
        <span className="badge-droxy-pill">
          <Wrench className="h-3.5 w-3.5 text-stone-700" />
          <span>Practical use cases</span>
        </span>
        <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight-display text-[#252525] mt-1 font-sans">
          How PreFill Manages Household Inventory
        </h2>
      </motion.div>

      {/* Horizontal Pill Bar */}
      <motion.div 
        initial={{ opacity: 0, y: 15 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5, delay: 0.1 }}
        className="w-full flex items-center justify-center overflow-x-auto no-scrollbar py-1 mb-6 sm:mb-8"
      >
        <div className="bg-stone-200/70 p-1.5 rounded-full flex items-center gap-1.5 shrink-0 border border-stone-300/60">
          {PRACTICAL_TABS.map((t, idx) => (
            <button
              key={t.name}
              onClick={() => setActiveTab(idx)}
              className={`px-4 py-2 rounded-full text-xs font-bold transition-all cursor-pointer select-none font-sans ${
                activeTab === idx
                  ? "bg-white text-[#252525] shadow-xs border border-stone-200"
                  : "text-stone-600 hover:text-[#252525] hover:bg-stone-200/50"
              }`}
            >
              {t.name}
            </button>
          ))}
        </div>
      </motion.div>

      {/* Card Content (Neutral White Styled) */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5, delay: 0.2 }}
        className="w-full card-neutral-droxy p-6 sm:p-8 flex flex-col lg:flex-row items-center justify-between gap-6 sm:gap-8 bg-ascii-dotted-grid relative overflow-hidden hover:border-stone-400 transition-all"
      >
        
        {/* Left Bullet Points */}
        <div className="flex-1 flex flex-col items-start gap-6">
          <AnimatePresence mode="wait">
            <motion.div 
              key={activeTab}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.25 }}
              className="flex flex-col gap-4 items-start"
            >
              <h3 className="text-2xl sm:text-3xl font-extrabold font-sans tracking-tight title-accent text-[#252525]">
                {currentTab.title}
              </h3>

              <div className="flex flex-col gap-4">
                {currentTab.bullets.map((b, i) => (
                  <div key={i} className="flex items-start gap-3 text-xs sm:text-sm text-stone-700 font-medium leading-relaxed">
                    <CheckCircle2 className="h-4 w-4 text-[#252525] shrink-0 mt-0.5" />
                    <span>{b}</span>
                  </div>
                ))}
              </div>
            </motion.div>
          </AnimatePresence>

          <a href="#demo-stage" className="btn-droxy-pill-primary text-xs mt-2">
            Try Interactive Prototype
          </a>
        </div>

        {/* Right Side Detail Card Mockup */}
        <div className="w-full max-w-[320px] bg-stone-50 rounded-2xl border border-stone-200 p-5 shadow-2xs flex flex-col gap-4">
          
          <div className="flex items-center justify-between border-b border-stone-200/80 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="h-9 w-9 rounded-full bg-[#252525] text-white flex items-center justify-center font-bold text-xs">
                <User className="h-4 w-4" />
              </div>
              <div className="flex flex-col">
                <span className="font-bold text-xs text-[#252525] font-sans">{currentTab.user}</span>
                <span className="text-[10px] text-stone-500 font-medium flex items-center gap-1">
                  <PhoneCall className="h-3 w-3 text-stone-600" />
                  {currentTab.status} • {currentTab.time}
                </span>
              </div>
            </div>
            <span className="text-[9px] font-semibold text-stone-500 bg-white px-2 py-0.5 rounded border border-stone-200 font-mono">
              Telemetry
            </span>
          </div>

          <div className="flex flex-col gap-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-stone-500 font-medium text-[11px]">Tracked Item:</span>
              <span className="font-bold text-[#252525] text-[11px] font-sans">{currentTab.detail}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-stone-500 font-medium text-[11px]">Channel:</span>
              <span className="font-bold text-stone-900 text-[11px]">WhatsApp 1-Tap</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-stone-500 font-medium text-[11px]">Delivery ETA:</span>
              <span className="font-bold text-stone-900 text-[11px]">10 Minutes</span>
            </div>
          </div>

          <div className="p-2.5 rounded-xl status-pill-green text-[10px] font-semibold text-center font-sans">
            Prophet Depletion Confidence: 94.2%
          </div>

        </div>

      </motion.div>

    </div>
  );
}
