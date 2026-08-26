"use client";

import React from "react";
import { ArrowUpRight, ShieldCheck, Cpu } from "lucide-react";
import PhoneMockup from "../PhoneMockup";
import { PillButton } from "../ui/PillButton";
import { WhatsAppIcon } from "../ui/WhatsAppIcon";

export function GrocerHero() {
  return (
    <section id="demo" className="relative pt-8 sm:pt-14 pb-16 md:pb-24 overflow-hidden bg-[#FCFCFD]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        {/* Main 2-Column Hero Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
          
          {/* Left Column: Headline, Subtitle, CTAs & Value Props */}
          <div className="lg:col-span-7 space-y-6 text-left">
            {/* Prominent, Balanced Under-Construction Card */}
            <div className="inline-flex items-start sm:items-center gap-3 bg-amber-500/10 border-2 border-amber-500/25 px-4.5 py-3 sm:px-5 sm:py-3.5 rounded-2xl text-amber-950 shadow-xs max-w-2xl">
              <span className="text-xl sm:text-2xl shrink-0 mt-0.5 sm:mt-0 select-none">🚧</span>
              <p className="text-[13.5px] sm:text-[14.5px] font-medium leading-snug sm:leading-relaxed">
                <strong className="font-bold text-amber-900">Under construction:</strong> This prototype was submitted for review and is still being actively built, so some things may not work. Sorry about that, and thank you for checking it out!
              </p>
            </div>

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

          {/* Right Column: Clean Standalone iPhone 16 Pro Mockup */}
          <div className="lg:col-span-5 flex flex-col justify-center items-center">
            <div className="w-[275px] h-[562px] aspect-[1800/3680] shrink-0 relative z-10 mx-auto">
              <PhoneMockup />
            </div>
          </div>

        </div>
      </div>
    </section>
  );
}
