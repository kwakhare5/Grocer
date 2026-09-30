"use client";

import React from "react";
import {
  ShoppingBag,
  PackageCheck,
  ShieldCheck,
  CreditCard,
} from "lucide-react";
import { FAQ_ITEMS } from "./data";

export function FaqSection() {
  return (
    <section id="faq" className="py-16 sm:py-20 bg-zinc-50/70 border-t border-zinc-200 scroll-mt-16">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-2xl mx-auto mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold mb-3">
            <span>Guarantees &amp; Safety</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-editorial font-bold text-zinc-950">
            Commerce safety &amp; questions
          </h2>
          <p className="mt-3 text-base sm:text-lg text-zinc-600 leading-relaxed font-normal">
            Deterministic code boundaries guaranteeing financial, inventory, and delivery safety.
          </p>
        </div>

        {/* 4 Guardrail Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-14">
          <div className="p-6 rounded-2xl border border-zinc-200 bg-white shadow-2xs">
            <div className="w-10 h-10 rounded-xl bg-orange-50 text-[#fc8019] flex items-center justify-center mb-4 border border-orange-200/60">
              <ShoppingBag className="w-5 h-5" />
            </div>
            <h3 className="text-sm sm:text-base font-bold text-zinc-950 mb-1.5">
              Live Store Stock
            </h3>
            <p className="text-xs sm:text-sm text-zinc-600 leading-relaxed font-normal">
              Queries real-time dark store inventory serving your pin code. No stale catalog caching.
            </p>
          </div>

          <div className="p-6 rounded-2xl border border-zinc-200 bg-white shadow-2xs">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center mb-4 border border-emerald-200/60">
              <PackageCheck className="w-5 h-5" />
            </div>
            <h3 className="text-sm sm:text-base font-bold text-zinc-950 mb-1.5">
              Provider Pricing
            </h3>
            <p className="text-xs sm:text-sm text-zinc-600 leading-relaxed font-normal">
              Prices, packaging, and delivery fees come directly from dark-store billing. No model arithmetic.
            </p>
          </div>

          <div className="p-6 rounded-2xl border border-zinc-200 bg-white shadow-2xs">
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-700 flex items-center justify-center mb-4 border border-blue-200/60">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <h3 className="text-sm sm:text-base font-bold text-zinc-950 mb-1.5">
              Gated Checkout
            </h3>
            <p className="text-xs sm:text-sm text-zinc-600 leading-relaxed font-normal">
              Checkout requires your explicit confirmation before calling provider order APIs.
            </p>
          </div>

          <div className="p-6 rounded-2xl border border-zinc-200 bg-white shadow-2xs">
            <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-700 flex items-center justify-center mb-4 border border-purple-200/60">
              <CreditCard className="w-5 h-5" />
            </div>
            <h3 className="text-sm sm:text-base font-bold text-zinc-950 mb-1.5">
              Secure UPI QR
            </h3>
            <p className="text-xs sm:text-sm text-zinc-600 leading-relaxed font-normal">
              Generates official UPI links and polls payment status before retry to avoid double billing.
            </p>
          </div>
        </div>

        {/* Detailed FAQ List */}
        <div className="max-w-4xl mx-auto space-y-4">
          {FAQ_ITEMS.map((item, idx) => (
            <div key={idx} className="p-6 rounded-2xl bg-white border border-zinc-200 shadow-2xs">
              <h3 className="text-sm sm:text-base font-bold text-zinc-950 mb-2">
                {item.question}
              </h3>
              <p className="text-xs sm:text-sm text-zinc-600 leading-relaxed font-normal">
                {item.answer}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
