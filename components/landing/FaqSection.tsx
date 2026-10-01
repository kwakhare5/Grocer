"use client";

import React from "react";
import { HelpCircle } from "lucide-react";
import { FAQ_ITEMS } from "./data";

export function FaqSection() {
  return (
    <section id="faq" className="py-16 sm:py-20 bg-transparent border-b border-zinc-200/80 scroll-mt-16">
      <div className="max-w-6xl mx-auto px-3.5 sm:px-5">
        {/* Section Header */}
        <div className="text-center max-w-2xl mx-auto mb-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold mb-3">
            <HelpCircle className="w-3.5 h-3.5 text-emerald-600" />
            <span>Frequently Asked Questions</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-editorial font-bold text-zinc-950 tracking-tight">
            Common questions about Grocer
          </h2>
          <p className="mt-2.5 text-sm sm:text-base text-zinc-600 leading-relaxed font-normal">
            How ordering, store inventory, billing, and store connections work.
          </p>
        </div>

        {/* Detailed FAQ List (max-w-3xl for optimal typography reading line length) */}
        <div className="max-w-3xl mx-auto space-y-4">
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
