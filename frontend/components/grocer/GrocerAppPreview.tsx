"use client";

import React, { useState } from "react";
import PhoneMockup from "../PhoneMockup";
import { MessageSquare, Calendar, ShoppingCart } from "lucide-react";
import { PillBadge } from "../ui/PillBadge";

export function GrocerAppPreview() {
  const [activeTab, setActiveTab] = useState<"whatsapp" | "pantry" | "cart">("whatsapp");

  return (
    <section className="py-20 md:py-28 bg-[#FCFCFD] border-t border-gray-200/40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-14">
        {/* Header */}
        <div className="text-center space-y-3 max-w-2xl mx-auto">
          <PillBadge variant="kicker" color="sky">
            Grocer Interactive Demo
          </PillBadge>
          <h2 className="font-serif font-normal text-3xl sm:text-4xl lg:text-[44px] tracking-tight text-gray-950 leading-[1.15]">
            Experience Grocer's Household Restock Engine
          </h2>
          <p className="text-sm text-gray-500 font-normal">
            Select a scenario below to test the live iPhone interface in real time.
          </p>
        </div>

        {/* Tab Selector */}
        <div className="flex justify-center gap-3">
          <button
            onClick={() => setActiveTab("whatsapp")}
            className={`px-4 py-2 rounded-full text-xs font-semibold flex items-center gap-2 transition-all cursor-pointer ${
              activeTab === "whatsapp"
                ? "bg-gray-950 text-white shadow-sm"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200/60"
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            <span>1-Tap WhatsApp Alert</span>
          </button>
          <button
            onClick={() => setActiveTab("pantry")}
            className={`px-4 py-2 rounded-full text-xs font-semibold flex items-center gap-2 transition-all cursor-pointer ${
              activeTab === "pantry"
                ? "bg-gray-950 text-white shadow-sm"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200/60"
            }`}
          >
            <Calendar className="w-3.5 h-3.5" />
            <span>Pantry Velocity Tracker</span>
          </button>
          <button
            onClick={() => setActiveTab("cart")}
            className={`px-4 py-2 rounded-full text-xs font-semibold flex items-center gap-2 transition-all cursor-pointer ${
              activeTab === "cart"
                ? "bg-gray-950 text-white shadow-sm"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200/60"
            }`}
          >
            <ShoppingCart className="w-3.5 h-3.5" />
            <span>Auto-Generated Cart</span>
          </button>
        </div>

        {/* Mockup Canvas */}
        <div className="relative max-w-4xl mx-auto rounded-3xl border border-gray-200/80 bg-white p-6 sm:p-10 shadow-[0_10px_40px_rgba(0,0,0,0.03)] flex justify-center">
          <div className="w-[280px] sm:w-[320px] aspect-[1800/3680] shrink-0">
            <PhoneMockup activeScenario={activeTab} />
          </div>
        </div>
      </div>
    </section>
  );
}

