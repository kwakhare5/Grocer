"use client";

import React from "react";
import { MessageCircle } from "lucide-react";
import { GrocerLogo } from "../ui/GrocerLogo";

export function AppGlobalHeader() {
  return (
    <header className="sticky top-0 z-40 w-full bg-white/95 backdrop-blur-md border-b border-zinc-200">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        {/* Brand identity */}
        <div className="flex items-center gap-3">
          <GrocerLogo size="sm" iconOnly />
          <div className="flex flex-col">
            <span className="font-bold text-zinc-950 tracking-tight text-base font-sans leading-tight">
              Grocer
            </span>
            <span className="text-xs text-zinc-500 font-sans">
              Grocery replenishment on WhatsApp
            </span>
          </div>
        </div>

        {/* Action */}
        <div className="flex items-center gap-3">
          <a
            href="https://wa.me/15556631707?text=Hi%20Grocer!"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#25D366] hover:bg-[#1ebd59] text-white text-xs font-sans font-semibold transition-colors shadow-xs"
          >
            <MessageCircle className="w-4 h-4" />
            <span>Open WhatsApp</span>
          </a>
        </div>
      </div>
    </header>
  );
}
