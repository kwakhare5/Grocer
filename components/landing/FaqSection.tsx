"use client";

import React from "react";
import { HelpCircle } from "lucide-react";
import { FAQ_ITEMS } from "./data";

export function FaqSection() {
  return (
    <section id="faq" className="py-16 sm:py-20 bg-zinc-50/70 border-t border-zinc-200 scroll-mt-16">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-2xl mx-auto mb-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold mb-3">
            <HelpCircle className="w-3.5 h-3.5 text-emerald-600" />
            <span>Frequently Asked Questions</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-editorial font-bold text-zinc-950">
            Common questions about Grocer
          </h2>
          <p className="mt-3 text-base sm:text-lg text-zinc-600 leading-relaxed font-normal">
            How ordering, store inventory, billing, and Swiggy connection work.
          </p>
        </div>

        {/* Detailed FAQ List */}
        <div className="space-y-4">
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
