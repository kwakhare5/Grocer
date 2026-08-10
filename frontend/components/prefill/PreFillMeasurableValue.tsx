"use client";

import React from "react";
import {
  TrendingUp,
  PhoneCall,
  Users,
  BarChart3,
  ToggleLeft,
} from "lucide-react";
import { PreFillRoiCalculator } from "./PreFillRoiCalculator";
import { CardSurface } from "../ui/CardSurface";
import { PillBadge } from "../ui/PillBadge";

export function PreFillMeasurableValue() {
  return (
    <section id="roi" className="py-20 md:py-28 bg-[#FAFAFA] border-t border-gray-200/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-14">
        {/* Beside 1:1 Two-Column Header */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-end">
          <div className="lg:col-span-7 space-y-3">
            <h2 className="font-serif font-normal text-3xl sm:text-4xl lg:text-[44px] tracking-tight text-gray-950 leading-[1.15]">
              AI that actually delivers measurable value for your home
            </h2>
          </div>
          <div className="lg:col-span-5">
            <p className="text-sm sm:text-base text-gray-500 font-normal leading-relaxed">
              Save hours every week, eliminate stockouts completely, and never wake up to an empty fridge.
            </p>
          </div>
        </div>

        {/* Interactive Motion Tool: Grocery Time & Savings Calculator */}
        <PreFillRoiCalculator />

        {/* Beside 1:1 5-Card Bento Grid Layout */}
        <div className="space-y-6">
          {/* Top Row: 3 Mini Micro-Widget Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Card 1: Line Chart Visualizer Widget */}
            <CardSurface variant="default">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest flex items-center gap-1.5">
                  <BarChart3 className="w-3.5 h-3.5 text-sky-600" /> Increase Accuracy
                </span>
                <span className="text-[10px] font-bold font-mono bg-sky-50 text-sky-700 px-2 py-0.5 rounded-full border border-sky-100 shadow-2xs">
                  $10k Saved
                </span>
              </div>
              <h3 className="text-[15px] font-bold text-gray-950">
                Predicts replenishment with 98% accuracy
              </h3>

              {/* Micro Line Chart Widget */}
              <div className="h-16 bg-sky-50/60 rounded-xl border border-sky-100 p-2.5 flex items-end justify-between">
                <div className="w-2 h-4 bg-sky-300 rounded-sm" />
                <div className="w-2 h-7 bg-sky-400 rounded-sm" />
                <div className="w-2 h-5 bg-sky-300 rounded-sm" />
                <div className="w-2 h-10 bg-sky-500 rounded-sm" />
                <div className="w-2 h-12 bg-sky-600 rounded-sm" />
              </div>
            </CardSurface>

            {/* Card 2: Interactive Toggle Switch Widget */}
            <CardSurface variant="default">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest flex items-center gap-1.5">
                <ToggleLeft className="w-3.5 h-3.5 text-emerald-600" /> Route Orders Fast
              </span>
              <h3 className="text-[15px] font-bold text-gray-950">
                Auto-routes orders to nearest store
              </h3>

              {/* Micro Pill Toggle Widget */}
              <div className="bg-emerald-50/80 p-2.5 rounded-xl border border-emerald-100 flex items-center justify-between text-xs font-bold text-emerald-950">
                <span>10-Min Delivery</span>
                <div className="w-8 h-4 rounded-full bg-emerald-600 p-0.5 flex items-center justify-end">
                  <div className="w-3 h-3 rounded-full bg-white shadow-xs" />
                </div>
              </div>
            </CardSurface>

            {/* Card 3: Contact Avatar List Widget */}
            <CardSurface variant="default">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest flex items-center gap-1.5">
                <Users className="w-3.5 h-3.5 text-indigo-600" /> Shared Family Pantry
              </span>
              <h3 className="text-[15px] font-bold text-gray-950">
                Shared family accounts & 100+ staples
              </h3>

              {/* Micro Avatar List Widget */}
              <div className="flex items-center gap-2">
                <div className="flex -space-x-2">
                  <div className="w-7 h-7 rounded-full bg-sky-500 text-white font-bold text-[10px] flex items-center justify-center border-2 border-white shadow-2xs">KW</div>
                  <div className="w-7 h-7 rounded-full bg-emerald-500 text-white font-bold text-[10px] flex items-center justify-center border-2 border-white shadow-2xs">AP</div>
                  <div className="w-7 h-7 rounded-full bg-purple-500 text-white font-bold text-[10px] flex items-center justify-center border-2 border-white shadow-2xs">RK</div>
                </div>
                <span className="text-[10px] font-bold text-gray-500">+3 Household Members</span>
              </div>
            </CardSurface>
          </div>

          {/* Bottom Row: 2 Asymmetric Wide Bento Cards */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Wide Card 1: Stat Callout Tile with Soft Mesh Gradient */}
            <div className="lg:col-span-6">
              <CardSurface variant="mesh" meshColor="sky">
                <div className="space-y-3 relative z-10">
                  <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest flex items-center gap-1.5">
                    <TrendingUp className="w-3.5 h-3.5 text-sky-600" /> Tested for Household Speed
                  </span>
                  <h3 className="text-xl font-bold text-gray-950">
                    Zero manual app browsing or list writing required
                  </h3>
                </div>

                {/* Beside 1:1 Big Stat Tile */}
                <div className="flex items-end gap-4 relative z-10 pt-4">
                  <span className="text-5xl sm:text-6xl font-serif font-light tracking-tighter text-sky-600">
                    32%
                  </span>
                  <p className="text-xs text-gray-600 font-medium max-w-xs leading-snug">
                    Increase in monthly grocery savings from zero emergency runs
                  </p>
                </div>
              </CardSurface>
            </div>

            {/* Wide Card 2: 21st.dev Multi-Stop Sky-to-Indigo Gradient Card */}
            <div className="lg:col-span-6">
              <CardSurface variant="gradient">
                <div className="space-y-3 relative z-10">
                  <span className="text-[11px] font-semibold text-sky-200 uppercase tracking-widest flex items-center gap-1.5">
                    <PhoneCall className="w-3.5 h-3.5 text-sky-200" /> Stay Stocked Together
                  </span>
                  <h3 className="text-xl font-bold text-white">
                    Never forget milk, eggs, or kitchen staples
                  </h3>
                </div>

                <div className="flex items-end gap-4 relative z-10 pt-4">
                  <span className="text-5xl sm:text-6xl font-serif font-light tracking-tighter text-white">
                    100%
                  </span>
                  <p className="text-xs text-sky-100 font-medium max-w-xs leading-snug">
                    Kitchen Staples Stocked Automatically on WhatsApp
                  </p>
                </div>
              </CardSurface>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
