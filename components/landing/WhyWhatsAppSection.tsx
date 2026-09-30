"use client";

import React from "react";
import { CheckCircle2 } from "lucide-react";

export function WhyWhatsAppSection() {
  return (
    <section id="why-whatsapp" className="py-16 sm:py-20 bg-zinc-100/70 border-y border-zinc-200 scroll-mt-16">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-2xl mx-auto mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold mb-3">
            <span>The Contrast</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-editorial font-bold text-zinc-950">
            Why WhatsApp beats app scrolling
          </h2>
          <p className="mt-3 text-base sm:text-lg text-zinc-600 leading-relaxed font-normal">
            Replenishing household groceries should take 5 seconds, not 15 minutes of screen fatigue.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto">
          {/* Left: The Old Way (App Scrolling) */}
          <div className="bg-white rounded-3xl p-6 sm:p-8 border border-red-200/80 shadow-xs flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-3 mb-5 text-red-700">
                <div className="w-9 h-9 rounded-xl bg-red-50 flex items-center justify-center text-base font-bold border border-red-100">
                  ✕
                </div>
                <h3 className="font-bold text-lg text-zinc-950">
                  The E-Commerce App Fatigue
                </h3>
              </div>

              <ul className="space-y-4 text-sm text-zinc-600">
                <li className="flex items-start gap-2.5">
                  <span className="text-red-500 font-bold shrink-0 mt-0.5">•</span>
                  <span><strong>15–20 taps:</strong> Browsing 6 separate categories just to assemble ingredients for dinner.</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="text-red-500 font-bold shrink-0 mt-0.5">•</span>
                  <span><strong>Banner spam:</strong> Dismissing flash-sale popups, banner ads, and irrelevant upsell widgets.</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="text-red-500 font-bold shrink-0 mt-0.5">•</span>
                  <span><strong>High friction:</strong> Frustrating when your hands are wet while cooking or when you are sick.</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="text-red-500 font-bold shrink-0 mt-0.5">•</span>
                  <span><strong>Silent drops:</strong> Surprise delivery fee surges and items dropped at checkout without notice.</span>
                </li>
              </ul>
            </div>

            <div className="mt-6 pt-5 border-t border-zinc-100 text-xs font-semibold text-red-600">
              Average session time: 8–15 minutes
            </div>
          </div>

          {/* Right: The Grocer WhatsApp Experience */}
          <div className="bg-white rounded-3xl p-6 sm:p-8 border border-emerald-300 shadow-xs flex flex-col justify-between relative overflow-hidden">
            <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 rounded-bl-full pointer-events-none" />
            <div>
              <div className="flex items-center gap-3 mb-5 text-emerald-700">
                <div className="w-9 h-9 rounded-xl bg-emerald-50 flex items-center justify-center text-base font-bold border border-emerald-200">
                  ✓
                </div>
                <h3 className="font-bold text-lg text-zinc-950">
                  The Grocer Replenishment Engine
                </h3>
              </div>

              <ul className="space-y-4 text-sm text-zinc-700">
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                  <span><strong>1 natural message:</strong> Deduces complete recipe kits from your dark store in under 3.5 seconds.</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                  <span><strong>Zero ad noise:</strong> Clean itemized WhatsApp receipt showing exact dark-store billing.</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                  <span><strong>Delta cart memory:</strong> Text &ldquo;also add butter&rdquo; without wiping your existing basket.</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                  <span><strong>Strict financial safety:</strong> Physical server lock requires your explicit confirmation to pay.</span>
                </li>
              </ul>
            </div>

            <div className="mt-6 pt-5 border-t border-zinc-100 text-xs font-semibold text-emerald-700">
              Average session time: 10–15 seconds
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
