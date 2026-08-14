"use client";

import React from "react";
import { ArrowUpRight, Zap, MessageSquare } from "lucide-react";
import PhoneMockup from "../PhoneMockup";
import { PillBadge } from "../ui/PillBadge";
import { PillButton } from "../ui/PillButton";

export function GrocerHero() {
  return (
    <section id="demo" className="relative pt-12 sm:pt-16 pb-20 md:pb-28 overflow-hidden bg-[#FCFCFD]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
        {/* Top Centered Hero Content Block */}
        <div className="text-center max-w-3xl mx-auto space-y-6">
          {/* Top Pill Badge */}
          <div className="inline-flex justify-center">
            <PillBadge variant="kicker" color="sky">
              <span className="font-semibold">Engineering Prototype • Pre-Emptive Household Replenishment</span>
            </PillBadge>
          </div>

          {/* Headline */}
          <h1 className="font-serif font-normal text-4xl sm:text-5xl lg:text-[56px] tracking-tight text-gray-950 leading-[1.12]">
            Predicting staple depletion before households run empty.
          </h1>

          {/* Subtitle Body Copy */}
          <p className="text-base sm:text-lg text-gray-500 font-normal leading-relaxed max-w-2xl mx-auto">
            An end-to-end prototype exploring time-series Prophet ML forecasting and a 5-node LangGraph execution state machine for low-friction 1-tap WhatsApp restocking.
          </p>

          {/* Action CTAs */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <PillButton href="#demo" variant="primary">
              <span>Test Interactive iPhone Demo</span>
              <ArrowUpRight className="w-4 h-4 ml-1.5" />
            </PillButton>
            <PillButton href="#features" variant="secondary">
              View ML & Agent Pipeline
            </PillButton>
          </div>
        </div>

        {/* Hero Interactive Canvas Container */}
        <div className="relative max-w-5xl mx-auto rounded-3xl border border-gray-200/80 bg-white p-6 sm:p-10 shadow-[0_10px_40px_rgba(0,0,0,0.03)] overflow-hidden flex justify-center">
          <div className="w-[280px] sm:w-[320px] aspect-[1800/3680] shrink-0 relative z-10">
            <PhoneMockup activeScenario="whatsapp" />
          </div>
        </div>
      </div>
    </section>
  );
}
