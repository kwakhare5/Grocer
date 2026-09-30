"use client";

import React, { useState } from "react";
import {
  Play,
  ShoppingBag,
  ShieldCheck,
  CheckCircle2,
  Clock,
  Layers,
} from "lucide-react";
import { VIDEO_CHAPTERS } from "./data";

export interface HeroSectionProps {
  onOpenConnect: () => void;
  isConnected: boolean;
}

export function HeroSection({ onOpenConnect, isConnected }: HeroSectionProps) {
  const [isPlayingDemo, setIsPlayingDemo] = useState(false);

  return (
    <section id="demo" className="pt-12 sm:pt-16 pb-12 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto text-center scroll-mt-20">
      {/* Official Submission Banner */}
      <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold mb-6">
        <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
        <span>Swiggy Builders Club Submission • Instamart MCP &amp; Gemini 3.5</span>
      </div>

      {/* Main Impact Headline */}
      <h1 className="text-4xl sm:text-5xl lg:text-6xl font-editorial font-bold text-zinc-950 tracking-tight leading-[1.12] max-w-4xl mx-auto">
        Household groceries on WhatsApp. In plain English.
      </h1>

      {/* Subheading: direct, human, no slop */}
      <p className="mt-5 text-base sm:text-lg text-zinc-600 leading-relaxed max-w-2xl mx-auto font-normal">
        Send a recipe, restock essentials, or describe a symptom. Grocer checks live dark store stock in seconds, stays inside your budget, and asks for your confirmation before placing an order.
      </p>

      {/* Action CTAs */}
      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <a
          href="#video-walkthrough"
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 px-5 py-3 text-sm font-semibold text-white shadow-xs transition-all active:scale-[0.98] cursor-pointer"
        >
          <Play className="w-4 h-4 fill-current ml-0.5" />
          <span>Watch 2-Minute Demo</span>
        </a>

        <button
          type="button"
          onClick={onOpenConnect}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-white hover:bg-zinc-50 border border-zinc-200 px-4 py-3 text-sm font-medium text-zinc-800 shadow-2xs transition-colors active:scale-[0.98] cursor-pointer"
        >
          <ShoppingBag className="w-4 h-4 text-[#fc8019]" />
          <span>{isConnected ? "Instamart Linked" : "Connect Instamart Account"}</span>
        </button>

        <a
          href="#sandbox"
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-zinc-100 hover:bg-zinc-200 px-4 py-3 text-sm font-medium text-zinc-700 transition-colors active:scale-[0.98]"
        >
          <span>Try Sandbox</span>
        </a>
      </div>

      {/* Quick Metrics Bar */}
      <div className="mt-8 flex flex-wrap items-center justify-center gap-3 sm:gap-6 text-xs text-zinc-700 font-semibold">
        <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white border border-zinc-200 shadow-2xs">
          <ShieldCheck className="w-4 h-4 text-emerald-600" />
          Zero unapproved charges
        </span>
        <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white border border-zinc-200 shadow-2xs">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          Strict budget limits
        </span>
        <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white border border-zinc-200 shadow-2xs">
          <Clock className="w-4 h-4 text-emerald-600" />
          10–15 min delivery
        </span>
        <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white border border-zinc-200 shadow-2xs">
          <Layers className="w-4 h-4 text-emerald-600" />
          Pluggable CommercePort
        </span>
      </div>

      {/* Video Showcase Card (Unified Editorial Light Design) */}
      <div id="video-walkthrough" className="mt-12 text-left scroll-mt-20">
        <div className="bg-white rounded-3xl p-4 sm:p-6 border border-zinc-200 shadow-sm overflow-hidden relative">
          {/* Display Window Top Bar */}
          <div className="flex items-center justify-between pb-3 border-b border-zinc-100 mb-4 text-xs text-zinc-500">
            <div className="flex items-center gap-2 font-mono text-zinc-700 text-xs">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
              <span>System Demo: WhatsApp + Gemini 3.5 + Swiggy MCP</span>
            </div>
            <span className="px-2.5 py-1 rounded bg-zinc-100 text-xs font-mono text-zinc-700 font-medium">
              2:00 Walkthrough
            </span>
          </div>

          {/* Unified Light Video Display Viewport */}
          <div className="relative aspect-video rounded-2xl bg-zinc-50 border border-zinc-200 overflow-hidden flex flex-col items-center justify-center text-center p-6">
            {isPlayingDemo ? (
              <div className="w-full h-full flex flex-col items-center justify-center p-6">
                <p className="text-base font-semibold text-zinc-900 mb-2">
                  Reviewer Video Demo
                </p>
                <p className="text-sm text-zinc-600 max-w-md mb-4 leading-relaxed font-normal">
                  Screen walkthrough following the official Reviewer Walkthrough script.
                </p>
                <button
                  type="button"
                  onClick={() => setIsPlayingDemo(false)}
                  className="px-4 py-2 rounded-xl bg-zinc-200 text-xs font-semibold text-zinc-800 hover:bg-zinc-300 transition cursor-pointer"
                >
                  Back to Poster
                </button>
              </div>
            ) : (
              <div className="space-y-4 max-w-lg">
                <button
                  type="button"
                  onClick={() => setIsPlayingDemo(true)}
                  className="w-16 h-16 rounded-full bg-emerald-600 hover:bg-emerald-500 text-white flex items-center justify-center mx-auto shadow-md transition-transform active:scale-95 cursor-pointer"
                  aria-label="Play 2-Minute Demo"
                >
                  <Play className="w-7 h-7 fill-current ml-1" />
                </button>

                <div>
                  <h2 className="text-lg sm:text-xl font-bold text-zinc-950 tracking-tight">
                    2-Minute Reviewer Walkthrough
                  </h2>
                  <p className="text-xs sm:text-sm text-zinc-600 mt-1.5 leading-relaxed font-normal">
                    Shows address disambiguation, recipe deduction, delta cart merge, and gated UPI payment.
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Chapters / Timeline Scrubber Bar */}
          <div className="mt-4 pt-3 border-t border-zinc-100 flex flex-wrap items-center justify-between gap-2 text-xs text-zinc-600">
            <span className="font-semibold text-zinc-800">Timeline Chapters:</span>
            <div className="flex flex-wrap items-center gap-2">
              {VIDEO_CHAPTERS.map((ch, idx) => (
                <span
                  key={idx}
                  className="px-2.5 py-1 rounded-lg bg-zinc-50 border border-zinc-200 font-mono text-xs text-zinc-700"
                >
                  <strong className="text-emerald-700 font-semibold">{ch.time}</strong> {ch.label}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
