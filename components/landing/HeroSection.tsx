"use client";

import React from "react";
import { ShoppingBag, ArrowDown, ExternalLink } from "lucide-react";

export interface HeroSectionProps {
  onOpenConnect: () => void;
  isConnected: boolean;
}

export function HeroSection({ onOpenConnect, isConnected }: HeroSectionProps) {
  return (
    <section className="pt-14 sm:pt-20 pb-14 px-4 sm:px-6 lg:px-8 max-w-4xl mx-auto text-center">
      {/* Official Submission Badge */}
      <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold mb-6">
        <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
        <span>Swiggy Builders Club Submission • Instamart MCP &amp; Gemini 3.5</span>
      </div>

      {/* Main Headline */}
      <h1 className="text-4xl sm:text-5xl lg:text-6xl font-editorial font-bold text-zinc-950 tracking-tight leading-[1.12]">
        Household groceries on WhatsApp. In plain English.
      </h1>

      {/* Clear, simple value prop */}
      <p className="mt-5 text-base sm:text-lg text-zinc-600 leading-relaxed max-w-2xl mx-auto font-normal">
        Send a recipe, restock essentials, or describe a symptom. Grocer checks live dark store stock in seconds, stays inside your budget, and asks for your confirmation before placing an order.
      </p>

      {/* Clean Action Buttons */}
      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <button
          type="button"
          onClick={onOpenConnect}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#fc8019] hover:bg-[#e07014] px-5 py-3 text-sm font-semibold text-white shadow-xs transition-all active:scale-[0.98] cursor-pointer"
        >
          <ShoppingBag className="w-4 h-4" />
          <span>{isConnected ? "Instamart Linked" : "Connect Instamart Account"}</span>
        </button>

        <a
          href="#conversation"
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-zinc-900 hover:bg-zinc-800 px-5 py-3 text-sm font-semibold text-white shadow-xs transition-all active:scale-[0.98]"
        >
          <span>View WhatsApp Flow</span>
          <ArrowDown className="w-4 h-4" />
        </a>

        <a
          href="https://github.com/kwakhare5/Grocer"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-white hover:bg-zinc-50 border border-zinc-200 px-4 py-3 text-sm font-medium text-zinc-800 shadow-2xs transition-colors active:scale-[0.98]"
        >
          <span>GitHub</span>
          <ExternalLink className="w-3.5 h-3.5 text-zinc-400" />
        </a>
      </div>
    </section>
  );
}
