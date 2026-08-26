"use client";

import React, { useState } from "react";
import { ChevronDown, HelpCircle } from "lucide-react";

export function GrocerFAQ() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  const faqs = [
    {
      question: "How does Grocer forecast household inventory stockouts?",
      answer:
        "Grocer uses a Prophet-based Machine Learning model to calculate daily consumption velocity per item (e.g. 0.48L/day for milk) from purchase history, predicting depletion dates 24 hours in advance.",
    },
    {
      question: "How does the Anomaly Detector handle trips or guest visits?",
      answer:
        "The Anomaly Detector filters out bulk guest purchases (>2.5x baseline) and travel gaps (>5 days) from the training model so temporary spikes don't distort normal replenishment dates.",
    },
    {
      question: "How are the dark store endpoints handled in this prototype?",
      answer:
        "All dark store checkout endpoints are safely mocked in python (`backend/mcp/mock_server.py`). The prototype runs an end-to-end simulated ordering loop without touching live payment or platform webhooks.",
    },
    {
      question: "How can quick commerce platforms test this without live user risk?",
      answer:
        "Through the Historical Backtest protocol: platforms run the Prophet model against 5 months of past anonymized purchase logs and verify whether it correctly predicts month-6 depletion dates before any live pilot.",
    },
    {
      question: "How does the 5-node LangGraph execution state machine operate?",
      answer:
        "The LangGraph agent runs a deterministic state graph (`check_pantry → generate_alert → parse_user_reply → build_cart → execute_order`) backed by PostgreSQL checkpointers.",
    },
  ];

  return (
    <section id="faq" className="py-20 md:py-28 bg-[#FCFCFD] border-t border-gray-200/40">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
        {/* Section Header */}
        <div className="text-center space-y-3">
          <div className="inline-flex items-center gap-1.5 px-3.5 py-1 rounded-full bg-sky-50 border border-sky-200/80 text-sky-800 text-xs font-semibold">
            <HelpCircle className="w-3.5 h-3.5 text-sky-600" />
            <span>Got Questions?</span>
          </div>
          <h2 className="font-serif font-normal text-3xl sm:text-4xl lg:text-[44px] tracking-tight text-gray-950 leading-[1.15]">
            Frequently Asked Questions
          </h2>
          <p className="text-sm text-gray-500 max-w-lg mx-auto font-normal">
            Technical and operational details behind Grocer&apos;s predictive household engine.
          </p>
        </div>

        {/* Accordion List */}
        <div className="space-y-4">
          {faqs.map((faq, idx) => {
            const isOpen = openIndex === idx;
            return (
              <div
                key={faq.question}
                className="bg-white rounded-2xl border border-gray-200/60 shadow-[0_2px_12px_rgba(0,0,0,0.02)] overflow-hidden transition-all"
              >
                <button
                  onClick={() => setOpenIndex(isOpen ? null : idx)}
                  aria-expanded={isOpen}
                  className="w-full p-6 text-left flex items-center justify-between gap-4 cursor-pointer hover:bg-gray-50/50 transition-colors"
                >
                  <h3 className="text-base font-bold text-gray-950 leading-snug">
                    {faq.question}
                  </h3>
                  <ChevronDown
                    className={`w-5 h-5 text-gray-400 shrink-0 transition-transform duration-300 ${
                      isOpen ? "rotate-180 text-sky-600" : ""
                    }`}
                  />
                </button>

                {isOpen && (
                  <div className="px-6 pb-6 pt-1 text-xs sm:text-sm text-gray-500 font-normal leading-relaxed border-t border-gray-100/80 animate-fadeIn">
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
