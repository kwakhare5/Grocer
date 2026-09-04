"use client";

import React, { useState } from "react";
import { ChevronDown } from "lucide-react";

export function GrocerFAQ() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  const faqs = [
    {
      question: "How does Grocer forecast household inventory stockouts?",
      answer:
        "Grocer uses a time-series consumption velocity model to calculate daily burn rate per item (e.g. 0.48L/day for milk) from purchase history, projecting depletion dates 24 hours in advance.",
    },
    {
      question: "How does the Decision Engine decide between Transfer, Reorder, Discount, and Hold?",
      answer:
        "The deterministic Decision Engine evaluates 4 actions: TRANSFER (when nearby store has safe excess and supplier ETA is too slow), REORDER (when multiple nodes need bulk stock and supplier is on time), DISCOUNT (when batch expiry is imminent and stock exceeds sell-through), and HOLD (when inventory is healthy).",
    },
    {
      question: "How is 'Safe Excess' calculated before approving an inter-store transfer?",
      answer:
        "Safe excess is calculated as: current_inventory - expected_demand_during_safety_window - safety_buffer. A source store is never allowed to transfer stock if doing so would risk creating a downstream shortage at the source node.",
    },
    {
      question: "Why does the transfer execution require operator approval?",
      answer:
        "In quick-commerce operations, consequential inventory re-allocations carry financial and delivery risk. The system ranks the best options with a structured WHY reasoning panel; human operators click Approve, and the execution pipeline applies the mutation with automated pre-checks.",
    },
    {
      question: "How does the customer WhatsApp simulation interact with dark store inventory?",
      answer:
        "Both sides share the same underlying simulation state. When a customer confirms a WhatsApp 1-tap reorder, the order is fulfilled from their designated home dark store, instantly updating real-time stock levels, demand velocity, and rebalancing triggers.",
    },
  ];

  return (
    <section id="faq" className="py-16 md:py-24 bg-[#FAFAFA] border-t border-zinc-200">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10">
        {/* Section Header */}
        <div className="text-center space-y-2">
          <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-blue-800 bg-blue-50 px-2.5 py-0.5 rounded border border-blue-200 inline-block">
            Frequently Asked Questions
          </span>
          <h2 className="font-sans font-bold text-2xl sm:text-3xl lg:text-4xl tracking-tight text-zinc-950">
            Technical & Architecture Explanations
          </h2>
          <p className="text-xs sm:text-sm text-zinc-600 max-w-lg mx-auto font-normal">
            Operational details behind Grocer&apos;s predictive household engine, dark store fleet rebalancing, and transfer execution pipelines.
          </p>
        </div>

        {/* Accordion List */}
        <div className="space-y-3">
          {faqs.map((faq, idx) => {
            const isOpen = openIndex === idx;
            return (
              <div
                key={faq.question}
                className="bg-white rounded-xl border border-zinc-200 shadow-2xs overflow-hidden transition-all"
              >
                <button
                  type="button"
                  onClick={() => setOpenIndex(isOpen ? null : idx)}
                  aria-expanded={isOpen}
                  className="w-full p-4.5 text-left flex items-center justify-between gap-4 cursor-pointer hover:bg-zinc-50 transition-colors"
                >
                  <h3 className="text-sm font-bold text-zinc-950 leading-snug">
                    {faq.question}
                  </h3>
                  <ChevronDown
                    className={`w-4 h-4 text-zinc-400 shrink-0 transition-transform duration-200 ${
                      isOpen ? "rotate-180 text-emerald-700" : ""
                    }`}
                  />
                </button>

                {isOpen && (
                  <div className="px-4.5 pb-4.5 pt-0 text-xs text-zinc-600 font-normal leading-relaxed border-t border-zinc-100">
                    {faq.answer}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
