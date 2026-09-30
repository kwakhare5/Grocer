"use client";

import React from "react";
import {
  RefreshCw,
  Utensils,
  HeartPulse,
  ShieldCheck,
  Check,
} from "lucide-react";

export function CapabilitiesSection() {
  return (
    <section id="features" className="py-16 sm:py-20 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto scroll-mt-16">
      <div className="text-center max-w-2xl mx-auto mb-14">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold mb-3">
          <span>What We Built</span>
        </div>
        <h2 className="text-3xl sm:text-4xl font-editorial font-bold text-zinc-950">
          Four capabilities that redefine replenishment
        </h2>
        <p className="mt-3 text-base sm:text-lg text-zinc-600 leading-relaxed font-normal">
          GROCER pairs autonomous reasoning with deterministic dark-store stock checks and hard financial locks.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* 1. Daily Staples Replenishment */}
        <div className="bg-white rounded-3xl p-7 border border-zinc-200 shadow-xs flex flex-col justify-between">
          <div>
            <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-700 flex items-center justify-center mb-5 border border-emerald-100">
              <RefreshCw className="w-6 h-6" />
            </div>
            <div className="inline-block text-xs font-semibold text-emerald-800 uppercase tracking-wider mb-2">
              Household Replenishment
            </div>
            <h3 className="text-xl font-bold text-zinc-950 mb-2">
              Daily Staples Restocking
            </h3>
            <p className="text-xs sm:text-sm text-zinc-600 mb-4 font-mono bg-zinc-50 p-3 rounded-xl border border-zinc-100">
              &ldquo;Get 2L milk, whole wheat bread, and 6 eggs under ₹500&rdquo;
            </p>
            <p className="text-sm text-zinc-600 leading-relaxed">
              Picks standard in-stock dark store variants (Amul, Britannia, fresh farm eggs) without asking tedious pack-size questions.
            </p>
          </div>
          <div className="pt-6 border-t border-zinc-100 mt-6 flex items-center gap-2 text-xs sm:text-sm font-semibold text-emerald-700">
            <Check className="w-4 h-4 shrink-0" />
            <span>Zero redundant clarification questions</span>
          </div>
        </div>

        {/* 2. Recipe & Meal Kits */}
        <div className="bg-white rounded-3xl p-7 border border-zinc-200 shadow-xs flex flex-col justify-between">
          <div>
            <div className="w-12 h-12 rounded-2xl bg-orange-50 text-[#fc8019] flex items-center justify-center mb-5 border border-orange-100">
              <Utensils className="w-6 h-6" />
            </div>
            <div className="inline-block text-xs font-semibold text-[#fc8019] uppercase tracking-wider mb-2">
              Recipe Intent
            </div>
            <h3 className="text-xl font-bold text-zinc-950 mb-2">
              Recipe &amp; Meal Kit Deduction
            </h3>
            <p className="text-xs sm:text-sm text-zinc-600 mb-4 font-mono bg-zinc-50 p-3 rounded-xl border border-zinc-100">
              &ldquo;I want to make pasta tonight under ₹1,500. Get ingredients!&rdquo;
            </p>
            <p className="text-sm text-zinc-600 leading-relaxed">
              Deduces the full grocery basket (pasta, sauce, cheese, garlic) and fires parallel dark-store searches to build the kit in under 3.5 seconds.
            </p>
          </div>
          <div className="pt-6 border-t border-zinc-100 mt-6 flex items-center gap-2 text-xs sm:text-sm font-semibold text-[#fc8019]">
            <Check className="w-4 h-4 shrink-0" />
            <span>Builds complete meal kits in seconds</span>
          </div>
        </div>

        {/* 3. Symptom Care */}
        <div className="bg-white rounded-3xl p-7 border border-zinc-200 shadow-xs flex flex-col justify-between">
          <div>
            <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-700 flex items-center justify-center mb-5 border border-blue-100">
              <HeartPulse className="w-6 h-6" />
            </div>
            <div className="inline-block text-xs font-semibold text-blue-800 uppercase tracking-wider mb-2">
              Medical &amp; Wellness
            </div>
            <h3 className="text-xl font-bold text-zinc-950 mb-2">
              Symptom Care &amp; Urgent Relief
            </h3>
            <p className="text-xs sm:text-sm text-zinc-600 mb-4 font-mono bg-zinc-50 p-3 rounded-xl border border-zinc-100">
              &ldquo;Terrible cold and sore throat, my head is pounding&rdquo;
            </p>
            <p className="text-sm text-zinc-600 leading-relaxed">
              Translates fuzzy medical symptoms into essential OTC comfort relief (Crocin, Strepsils, Vicks, herbal tea) delivered to your door in 10-15 minutes.
            </p>
          </div>
          <div className="pt-6 border-t border-zinc-100 mt-6 flex items-center gap-2 text-xs sm:text-sm font-semibold text-blue-700">
            <Check className="w-4 h-4 shrink-0" />
            <span>Relief essentials in 10–15 minutes</span>
          </div>
        </div>

        {/* 4. Intent Preservation & Hard Budget Caps */}
        <div className="bg-white rounded-3xl p-7 border border-zinc-200 shadow-xs flex flex-col justify-between">
          <div>
            <div className="w-12 h-12 rounded-2xl bg-purple-50 text-purple-700 flex items-center justify-center mb-5 border border-purple-100">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div className="inline-block text-xs font-semibold text-purple-800 uppercase tracking-wider mb-2">
              Budget &amp; Dietary Safety
            </div>
            <h3 className="text-xl font-bold text-zinc-950 mb-2">
              Intent Preservation &amp; Budget Caps
            </h3>
            <p className="text-xs sm:text-sm text-zinc-600 mb-4 font-mono bg-zinc-50 p-3 rounded-xl border border-zinc-100">
              &ldquo;Vegetarian only, keep total strictly under ₹1,000&rdquo;
            </p>
            <p className="text-sm text-zinc-600 leading-relaxed">
              Enforces non-negotiable dietary boundaries and hard financial caps. Automatically recovers in-policy substitutions rather than failing silently.
            </p>
          </div>
          <div className="pt-6 border-t border-zinc-100 mt-6 flex items-center gap-2 text-xs sm:text-sm font-semibold text-purple-700">
            <Check className="w-4 h-4 shrink-0" />
            <span>Exact dark-store billing verification</span>
          </div>
        </div>
      </div>
    </section>
  );
}
