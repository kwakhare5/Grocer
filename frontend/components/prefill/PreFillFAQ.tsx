"use client";

import React, { useState } from "react";
import { ChevronDown, HelpCircle } from "lucide-react";
import { CardSurface } from "../ui/CardSurface";

export function PreFillFAQ() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  const faqs = [
    {
      question: "How does PreFill know when my groceries are running low?",
      answer:
        "PreFill tracks your household consumption velocity using simple data models. It calculates daily usage rates for staples like milk, eggs, and bread, then triggers a WhatsApp notice 24 hours before you run empty.",
    },
    {
      question: "Do I need to install a special app to confirm restocks?",
      answer:
        "No! PreFill communicates directly through WhatsApp. When your pantry runs low, you receive a single WhatsApp message with your cart total. Reply 'YES' to confirm instant delivery.",
    },
    {
      question: "Which grocery delivery services are supported?",
      answer:
        "PreFill integrates seamlessly with Zepto, Blinkit, Swiggy Instamart, and BigBasket. Orders are automatically routed to your preferred local 10-minute dark store.",
    },
    {
      question: "Can multiple family members share one PreFill account?",
      answer:
        "Yes! You can add household members to your PreFill account so anyone in the family can view pantry stock levels and confirm WhatsApp restock alerts.",
    },
    {
      question: "Is there any subscription fee for testing PreFill?",
      answer:
        "PreFill is currently 100% free to test and use during our public showcase preview. You only pay for the actual groceries delivered by your quick-commerce store.",
    },
  ];

  return (
    <section id="faq" className="py-20 md:py-28 bg-[#FAFAFA] border-t border-gray-200/60">
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
            Everything you need to know about testing PreFill's predictive household grocery restock app.
          </p>
        </div>

        {/* Accordion Cards Grid */}
        <div className="space-y-4">
          {faqs.map((faq, idx) => {
            const isOpen = openIndex === idx;
            return (
              <CardSurface
                key={faq.question}
                variant="default"
                onClick={() => setOpenIndex(isOpen ? null : idx)}
                className="!p-6 cursor-pointer"
              >
                <div className="flex items-center justify-between gap-4">
                  <h3 className="text-base font-bold text-gray-950 leading-snug">
                    {faq.question}
                  </h3>
                  <ChevronDown
                    className={`w-5 h-5 text-gray-400 shrink-0 transition-transform duration-300 ${
                      isOpen ? "rotate-180 text-sky-600" : ""
                    }`}
                  />
                </div>

                {isOpen && (
                  <p className="text-xs sm:text-sm text-gray-500 font-normal leading-relaxed pt-3 border-t border-gray-100 mt-3 animate-fadeIn">
                    {faq.answer}
                  </p>
                )}
              </CardSurface>
            );
          })}
        </div>
      </div>
    </section>
  );
}
