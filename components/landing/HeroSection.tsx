"use client";

import React from "react";
import { ShoppingBag, ArrowDown } from "lucide-react";
import { WhatsAppIcon } from "../ui/WhatsAppIcon";

export interface HeroSectionProps {
  onOpenConnect: () => void;
  isConnected: boolean;
}

export function HeroSection({ onOpenConnect, isConnected }: HeroSectionProps) {
  return (
    <section className="pt-16 sm:pt-24 pb-16 sm:pb-20 bg-transparent text-center">
      <div className="max-w-5xl mx-auto px-4 sm:px-6">
        {/* Universal Quick-Commerce Live Badge */}
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-50/90 border border-emerald-200/80 text-emerald-800 text-xs font-semibold mb-6 shadow-2xs">
          <WhatsAppIcon className="w-3.5 h-3.5 shrink-0" />
          <span>WhatsApp Replenishment • Quick Commerce Agent</span>
        </div>

        {/* Main Headline */}
        <h1 className="text-3xl sm:text-5xl lg:text-[54px] font-editorial font-bold text-zinc-950 tracking-[-0.02em] leading-[1.12] max-w-3xl mx-auto">
          Turn WhatsApp messages into grocery carts.
        </h1>

      {/* Clear, simple value prop */}
      <p className="mt-5 text-base sm:text-lg text-zinc-600 leading-relaxed max-w-2xl mx-auto font-normal">
        No app clutter, no lost carts. Grocer checks live dark-store inventory, respects your budget caps, and requires your explicit confirmation before checkout.
      </p>

      {/* Clean Action Buttons */}
      <div className="mt-8 flex flex-wrap items-center justify-center gap-3 relative z-10">
        <button
          type="button"
          onClick={onOpenConnect}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-700 hover:bg-emerald-800 px-5 py-3 text-sm font-semibold text-white shadow-xs transition-all duration-150 active:scale-[0.98] cursor-pointer"
        >
          <ShoppingBag className="w-4 h-4" />
          <span>{isConnected ? "Account Linked" : "Connect Account"}</span>
        </button>

        <a
          href="#conversation"
          className="inline-flex items-center justify-center gap-2.5 rounded-xl bg-white hover:bg-zinc-50 border border-zinc-200/90 px-5 py-3 text-sm font-semibold text-zinc-800 shadow-2xs hover:border-zinc-300 transition-all duration-150 active:scale-[0.98]"
        >
          <WhatsAppIcon className="w-4 h-4 shrink-0" />
          <span>See Live Chat Flow</span>
          <ArrowDown className="w-4 h-4 text-zinc-400" />
        </a>
      </div>
      </div>
    </section>
  );
}
