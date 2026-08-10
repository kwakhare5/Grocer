"use client";

import React from "react";
import Link from "next/link";
import { ArrowUpRight, CheckCircle2, Zap, ShieldCheck } from "lucide-react";
import { PreFillLogo } from "../ui/PreFillLogo";
import { PillButton } from "../ui/PillButton";

export function PreFillFooter() {
  return (
    <footer className="bg-gray-950 text-white pt-20 pb-12 border-t border-gray-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">
        {/* Beside Section 7 1:1 Giant CTA Container (Clean Text CTA, Zero Phone Mockup) */}
        <div className="bg-gradient-to-r from-gray-950 via-slate-900 to-gray-950 rounded-[2.5rem] p-8 sm:p-14 border border-gray-800/80 shadow-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-8">
          {/* Left Column: Headline & Subtext */}
          <div className="space-y-4 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sky-500/10 border border-sky-500/20 text-sky-400 text-xs font-semibold">
              <Zap className="w-3.5 h-3.5" />
              <span>Predictive Grocery Restock Engine</span>
            </div>

            <h3 className="font-serif font-normal text-3xl sm:text-4xl lg:text-5xl text-white tracking-tight leading-[1.12]">
              Try PreFill for free
            </h3>

            <p className="text-sm sm:text-base text-gray-300 font-medium leading-relaxed">
              A predictive grocery engine that knows before you run empty on milk, eggs, or snacks. 10-minute delivery.
            </p>

            {/* Feature Checkmarks Pills */}
            <div className="flex flex-wrap items-center gap-4 text-xs text-gray-300 font-medium pt-2">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-sky-400 shrink-0" />
                <span>Zero app browsing</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-sky-400 shrink-0" />
                <span>1-Tap WhatsApp restock</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-sky-400 shrink-0" />
                <span>10-Minute quick commerce</span>
              </div>
            </div>
          </div>

          {/* Right Column: Action Buttons */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 shrink-0">
            <PillButton href="#demo" variant="secondary" className="!bg-white !text-gray-950 hover:!bg-gray-100 shadow-md text-xs sm:text-sm">
              <span>Try PreFill</span>
              <ArrowUpRight className="w-4 h-4" />
            </PillButton>
            <PillButton href="#features" variant="secondary" className="!bg-white/10 !text-white hover:!bg-white/20 !border-white/20 text-xs sm:text-sm">
              Calculate Savings
            </PillButton>
          </div>
        </div>

        {/* Beside 1:1 Bottom CTA Text Ribbon */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-b border-gray-900 pb-12">
          <h4 className="font-serif font-normal text-2xl sm:text-3xl text-white">
            Try PreFill now.
          </h4>
          <div className="flex items-center gap-3">
            <PillButton href="#demo" variant="secondary" className="!bg-white !text-gray-950 text-xs shadow-md">
              Try PreFill
            </PillButton>
            <PillButton href="#features" variant="secondary" className="!bg-gray-900 !text-gray-300 text-xs border-gray-800">
              Compare Spec
            </PillButton>
          </div>
        </div>

        {/* Beside 1:1 5-Column Footer Links Grid */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-8 text-xs">
          <div className="space-y-3">
            <p className="font-bold text-white uppercase tracking-wider text-[11px]">Product</p>
            <ul className="space-y-2 text-gray-400 font-medium">
              <li><Link href="#demo" className="hover:text-white transition-colors">Overview</Link></li>
              <li><Link href="#features" className="hover:text-white transition-colors">How It Works</Link></li>
              <li><Link href="#roi" className="hover:text-white transition-colors">Pantry Calculator</Link></li>
              <li><Link href="#faq" className="hover:text-white transition-colors">FAQ</Link></li>
            </ul>
          </div>

          <div className="space-y-3">
            <p className="font-bold text-white uppercase tracking-wider text-[11px]">Features</p>
            <ul className="space-y-2 text-gray-400 font-medium">
              <li><span className="text-gray-400">1-Tap WhatsApp</span></li>
              <li><span className="text-gray-400">24-Hour Alert</span></li>
              <li><span className="text-gray-400">10-Min Delivery</span></li>
              <li><span className="text-gray-400">Shared Household</span></li>
            </ul>
          </div>

          <div className="space-y-3">
            <p className="font-bold text-white uppercase tracking-wider text-[11px]">Integrations</p>
            <ul className="space-y-2 text-gray-400 font-medium">
              <li><span className="text-gray-400">Zepto</span></li>
              <li><span className="text-gray-400">Blinkit</span></li>
              <li><span className="text-gray-400">Instamart</span></li>
              <li><span className="text-gray-400">WhatsApp</span></li>
            </ul>
          </div>

          <div className="space-y-3">
            <p className="font-bold text-white uppercase tracking-wider text-[11px]">Social</p>
            <ul className="space-y-2 text-gray-400 font-medium">
              <li><span className="text-gray-400">X (Twitter)</span></li>
              <li><span className="text-gray-400">LinkedIn</span></li>
              <li><span className="text-gray-400">GitHub</span></li>
            </ul>
          </div>

          <div className="space-y-3">
            <p className="font-bold text-white uppercase tracking-wider text-[11px]">Legal</p>
            <ul className="space-y-2 text-gray-400 font-medium">
              <li><span className="text-gray-400">Privacy Policy</span></li>
              <li><span className="text-gray-400">Terms of Service</span></li>
              <li><span className="text-gray-400">Security</span></li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="pt-8 border-t border-gray-900 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-gray-500 font-medium">
          <p>© {new Date().getFullYear()} PreFill Inc. All rights reserved.</p>
          <div className="flex items-center gap-2">
            <PreFillLogo size="sm" className="[&_span]:!text-white" />
          </div>
        </div>
      </div>
    </footer>
  );
}
