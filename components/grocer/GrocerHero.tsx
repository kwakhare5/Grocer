"use client";

import React from "react";
import { ArrowUpRight, ShieldCheck, Cpu, Zap } from "lucide-react";
import PhoneMockup from "../PhoneMockup";
import { WhatsAppIcon } from "../ui/WhatsAppIcon";

interface GrocerHeroProps {
  onLaunchCockpit?: () => void;
  onLaunchCustomer?: () => void;
}

export function GrocerHero({ onLaunchCockpit, onLaunchCustomer }: GrocerHeroProps) {
  return (
    <section id="problem" className="relative pt-8 sm:pt-14 pb-14 md:pb-20 overflow-hidden bg-[#FAFAFA]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        {/* Main 2-Column Hero Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
          
          {/* Left Column: Headline, Subtitle, CTAs & Value Props */}
          <div className="lg:col-span-7 space-y-5 text-left">
            {/* Status Pill */}
            <div className="inline-flex items-center gap-2 bg-blue-50 border border-blue-200 px-3 py-1 rounded-full text-blue-900 text-xs font-semibold">
              <span className="w-2 h-2 rounded-full bg-blue-600 animate-pulse" />
              <span>Grocery Inventory Balancing & Restock</span>
            </div>

            <h1 className="font-display font-bold text-3xl sm:text-5xl lg:text-[50px] tracking-tight text-zinc-950 leading-[1.12]">
              Stop grocery stockouts before they happen.
            </h1>

            <p className="text-sm sm:text-base text-zinc-600 font-normal leading-relaxed max-w-2xl">
              Predict household grocery depletion and balance inventory across dark store networks with automatic WhatsApp reorders.
            </p>

            {/* Core Pillars (12px Card Radius) */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
              <div className="bg-white p-3.5 rounded-xl border border-zinc-200 shadow-2xs space-y-1">
                <div className="flex items-center gap-1.5 text-blue-800 font-bold text-xs">
                  <WhatsAppIcon className="w-3.5 h-3.5 shrink-0" />
                  <span>WhatsApp Orders</span>
                </div>
                <p className="text-[11.5px] text-zinc-500 leading-snug">
                  Customers reorder in 1 tap before items run out.
                </p>
              </div>

              <div className="bg-white p-3.5 rounded-xl border border-zinc-200 shadow-2xs space-y-1">
                <div className="flex items-center gap-1.5 text-sky-800 font-bold text-xs">
                  <Cpu className="w-3.5 h-3.5 text-sky-600 shrink-0" />
                  <span>Store Transfers</span>
                </div>
                <p className="text-[11.5px] text-zinc-500 leading-snug">
                  Move excess stock between nearby stores before shelves empty.
                </p>
              </div>

              <div className="bg-white p-3.5 rounded-xl border border-zinc-200 shadow-2xs space-y-1">
                <div className="flex items-center gap-1.5 text-purple-800 font-bold text-xs">
                  <ShieldCheck className="w-3.5 h-3.5 text-purple-600 shrink-0" />
                  <span>Freshness Protection</span>
                </div>
                <p className="text-[11.5px] text-zinc-500 leading-snug">
                  Discount and move near-expiry perishables to cut waste.
                </p>
              </div>
            </div>

            {/* Action CTAs (8px Button Radius) */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 pt-2">
              <button
                type="button"
                onClick={onLaunchCockpit}
                className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-2xs transition-all cursor-pointer active:scale-97"
              >
                <Zap className="w-3.5 h-3.5 text-blue-200" />
                <span>Launch Store Operations</span>
                <ArrowUpRight className="w-3.5 h-3.5 text-blue-100" />
              </button>

              <button
                type="button"
                onClick={onLaunchCustomer}
                className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-white hover:bg-zinc-50 border border-zinc-200 hover:border-zinc-300 text-zinc-900 font-semibold text-xs transition-all cursor-pointer active:scale-97"
              >
                <WhatsAppIcon className="w-3.5 h-3.5" />
                <span>Test WhatsApp Demo</span>
              </button>
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


