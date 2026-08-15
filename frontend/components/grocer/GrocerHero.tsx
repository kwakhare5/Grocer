"use client";

import React, { useState } from "react";
import { ArrowUpRight, BarChart3, ShieldCheck, Cpu } from "lucide-react";
import PhoneMockup from "../PhoneMockup";
import { PillButton } from "../ui/PillButton";
import { WhatsAppIcon } from "../ui/WhatsAppIcon";

export function GrocerHero() {
  const [viewMode, setViewMode] = useState<"lockscreen" | "whatsapp" | "pantry">("lockscreen");

  return (
    <section id="demo" className="relative pt-8 sm:pt-14 pb-16 md:pb-24 overflow-hidden bg-[#FCFCFD]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        


        {/* Main 2-Column Hero Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
          
          {/* Left Column: Headline, Subtitle, CTAs & Value Props */}
          <div className="lg:col-span-7 space-y-6 text-left">
            <h1 className="font-serif font-normal text-3xl sm:text-4xl lg:text-[48px] tracking-tight text-gray-950 leading-[1.12]">
              Predicting staple depletion before households run empty.
            </h1>

            <p className="text-sm sm:text-base text-gray-500 font-normal leading-relaxed max-w-2xl">
              Zero manual app searching. Prophet ML calculates per-household consumption velocity and sends a 1-tap WhatsApp restocking prompt 24 hours before stockout.
            </p>

            {/* Core Architectural Pillars */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
              <div className="bg-white p-3.5 rounded-xl border border-gray-200/80 shadow-2xs space-y-1">
                <div className="flex items-center gap-1.5 text-emerald-700 font-bold text-xs font-display">
                  <WhatsAppIcon className="w-4 h-4 shrink-0" />
                  <span>Proactive Nudge</span>
                </div>
                <p className="text-[11px] text-gray-500 leading-snug">
                  1-tap WhatsApp prompt delivered 24h before stock runs dry.
                </p>
              </div>

              <div className="bg-white p-3.5 rounded-xl border border-gray-200/80 shadow-2xs space-y-1">
                <div className="flex items-center gap-1.5 text-sky-700 font-bold text-xs font-display">
                  <Cpu className="w-4 h-4 text-sky-600 shrink-0" />
                  <span>Prophet ML</span>
                </div>
                <p className="text-[11px] text-gray-500 leading-snug">
                  Tracks velocity & excludes vacation gaps and bulk spikes.
                </p>
              </div>

              <div className="bg-white p-3.5 rounded-xl border border-gray-200/80 shadow-2xs space-y-1">
                <div className="flex items-center gap-1.5 text-purple-700 font-bold text-xs font-display">
                  <ShieldCheck className="w-4 h-4 text-purple-600 shrink-0" />
                  <span>LangGraph Agent</span>
                </div>
                <p className="text-[11px] text-gray-500 leading-snug">
                  5-node execution state machine dispatches to dark store.
                </p>
              </div>
            </div>

            {/* Action CTAs */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 pt-2">
              <PillButton href="#demo" variant="primary">
                <span>Test Interactive Demo</span>
                <ArrowUpRight className="w-4 h-4 ml-1.5" />
              </PillButton>
              <PillButton href="#features" variant="secondary">
                View Architecture Spec
              </PillButton>
            </div>
          </div>

          {/* Right Column: Clean iPhone 16 Pro Mockup with Exterior View Switcher */}
          <div className="lg:col-span-5 flex flex-col justify-center items-center gap-4">
            
            {/* Clean Exterior View Mode Switcher */}
            <div className="bg-white/90 backdrop-blur-md p-1.5 rounded-full border border-gray-200/90 shadow-2xs flex items-center gap-1 z-20">
              <button
                onClick={() => setViewMode("lockscreen")}
                className={`px-3 py-1.5 rounded-full text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
                  viewMode === "lockscreen" || viewMode === "whatsapp"
                    ? "bg-[#25D366] text-gray-950 shadow-2xs font-extrabold"
                    : "text-gray-600 hover:text-gray-950 hover:bg-gray-100"
                }`}
              >
                <WhatsAppIcon className="w-3.5 h-3.5 shrink-0" />
                <span>WhatsApp Flow</span>
              </button>

              <button
                onClick={() => setViewMode("pantry")}
                className={`px-3 py-1.5 rounded-full text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
                  viewMode === "pantry"
                    ? "bg-gray-950 text-white shadow-2xs font-extrabold"
                    : "text-gray-600 hover:text-gray-950 hover:bg-gray-100"
                }`}
              >
                <BarChart3 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                <span>Pantry Health</span>
              </button>
            </div>

            {/* Live Interactive Phone Mockup */}
            <div className="w-[275px] h-[562px] aspect-[1800/3680] shrink-0 relative z-10 mx-auto">
              <PhoneMockup initialViewMode={viewMode} />
            </div>
          </div>

        </div>
      </div>
    </section>
  );
}
