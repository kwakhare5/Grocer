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
    <section className="pt-16 sm:pt-20 pb-16 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto text-center">
      {/* Universal Quick-Commerce Badge */}
      <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold mb-6">
        <WhatsAppIcon className="w-3.5 h-3.5 shrink-0" />
        <span>WhatsApp Replenishment • Quick Commerce Agent</span>
      </div>

      {/* Main Headline */}
      <h1 className="text-3xl sm:text-4xl lg:text-5xl font-editorial font-bold text-zinc-950 tracking-tight leading-[1.15] max-w-3xl mx-auto">
        Quick commerce on WhatsApp.
      </h1>

      {/* Clear, simple value prop */}
      <p className="mt-5 text-base sm:text-lg text-zinc-600 leading-relaxed max-w-2xl mx-auto font-normal">
        Turn natural messages and recipe ideas into verified carts. Eliminates cart amnesia, respects budget caps, and requires explicit confirmation before checkout.
      </p>

      {/* Clean Action Buttons */}
      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <button
          type="button"
          onClick={onOpenConnect}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-700 hover:bg-emerald-800 px-5 py-3 text-sm font-semibold text-white shadow-xs transition-all active:scale-[0.98] cursor-pointer"
        >
          <ShoppingBag className="w-4 h-4" />
          <span>{isConnected ? "Account Linked" : "Connect Account"}</span>
        </button>

        <a
          href="#conversation"
          className="inline-flex items-center justify-center gap-2.5 rounded-xl bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 px-5 py-3 text-sm font-semibold text-emerald-950 shadow-2xs transition-all active:scale-[0.98]"
        >
          <WhatsAppIcon className="w-5 h-5 shrink-0" />
          <span>See WhatsApp Demo</span>
          <ArrowDown className="w-4 h-4 text-emerald-700" />
        </a>
      </div>
    </section>
  );
}
