"use client";

import React from "react";
import { ArrowUpRight, CheckCircle2, Zap } from "lucide-react";
import { GrocerLogo } from "../ui/GrocerLogo";

interface GrocerFooterProps {
  onLaunchCockpit?: () => void;
  onLaunchCustomer?: () => void;
}

export function GrocerFooter({ onLaunchCockpit, onLaunchCustomer }: GrocerFooterProps) {
  return (
    <footer className="bg-[#FAFAFA] text-zinc-900 pt-14 pb-10 border-t border-zinc-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
        {/* Giant CTA Container (Standard 12px Radius) */}
        <div className="bg-white rounded-xl p-6 sm:p-10 border border-zinc-200 shadow-2xs flex flex-col md:flex-row items-start md:items-center justify-between gap-6 text-zinc-950">
          {/* Left Column: Headline & Subtext */}
          <div className="space-y-3 max-w-2xl">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded bg-blue-50 border border-blue-200 text-blue-900 text-[11px] font-mono font-bold">
              <Zap className="w-3 h-3 text-blue-600" />
              <span>Explore Grocer</span>
            </div>

            <h3 className="font-sans font-bold text-2xl sm:text-3xl lg:text-4xl text-zinc-950 tracking-tight leading-[1.15]">
              Ready to see Grocer in action?
            </h3>

            <p className="text-xs sm:text-sm text-zinc-600 font-normal leading-relaxed">
              Explore automated kitchen replenishment, store network transfers, and 1-tap WhatsApp restock alerts.
            </p>

            {/* Feature Checkmarks */}
            <div className="flex flex-wrap items-center gap-4 text-xs text-zinc-700 font-medium pt-1">
              <div className="flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                <span>Household Depletion Forecasts</span>
              </div>
              <div className="flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                <span>1-Tap WhatsApp Restock</span>
              </div>
              <div className="flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                <span>Local Store Transfers</span>
              </div>
            </div>
          </div>

          {/* Right Column: Action Buttons */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 shrink-0">
            <button
              type="button"
              onClick={onLaunchCockpit}
              className="flex items-center justify-center gap-2 px-4.5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-2xs transition-all cursor-pointer active:scale-97"
            >
              <Zap className="w-3.5 h-3.5 text-blue-200" />
              <span>Launch Store Operations</span>
              <ArrowUpRight className="w-3.5 h-3.5 text-blue-100" />
            </button>
            <button
              type="button"
              onClick={onLaunchCustomer}
              className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-zinc-100 hover:bg-zinc-200 text-zinc-900 border border-zinc-200 font-semibold text-xs transition-all cursor-pointer active:scale-97"
            >
              <span>Test WhatsApp Demo</span>
            </button>
          </div>
        </div>

        {/* 4-Column Footer Links Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-xs pt-2">
          <div className="space-y-2.5">
            <p className="font-bold text-zinc-950 uppercase tracking-wider text-[11px] font-mono">Product</p>
            <ul className="space-y-1.5 text-zinc-500 font-medium">
              <li><a href="#problem" className="hover:text-zinc-950 transition-colors">The Problem</a></li>
              <li><a href="#features" className="hover:text-zinc-950 transition-colors">Replenishment Engine</a></li>
              <li><a href="#simulator" className="hover:text-zinc-950 transition-colors">Velocity Simulator</a></li>
              <li><a href="#faq" className="hover:text-zinc-950 transition-colors">FAQ</a></li>
            </ul>
          </div>

          <div className="space-y-2.5">
            <p className="font-bold text-zinc-950 uppercase tracking-wider text-[11px] font-mono">Core Capabilities</p>
            <ul className="space-y-1.5 text-zinc-500 font-medium">
              <li><span className="text-zinc-600">Consumption Forecasting</span></li>
              <li><span className="text-zinc-600">Anomaly Gate Filter</span></li>
              <li><span className="text-zinc-600">Transfer Execution Pipeline</span></li>
              <li><span className="text-zinc-600">Perishable Spoilage Rescue</span></li>
            </ul>
          </div>

          <div className="space-y-2.5">
            <p className="font-bold text-zinc-950 uppercase tracking-wider text-[11px] font-mono">Operations Deck</p>
            <ul className="space-y-1.5 text-zinc-500 font-medium">
              <li><span className="text-zinc-600">Dark Store SKU Matrix</span></li>
              <li><span className="text-zinc-600">Spatial Mumbai Map</span></li>
              <li><span className="text-zinc-600">Tradeoff Benefit Engine</span></li>
              <li><span className="text-zinc-600">1-Click PO Restocking</span></li>
            </ul>
          </div>

          <div className="space-y-2.5">
            <p className="font-bold text-zinc-950 uppercase tracking-wider text-[11px] font-mono">Prototype Stack</p>
            <ul className="space-y-1.5 text-zinc-500 font-medium">
              <li><span className="text-zinc-600">Next.js 16 (Turbopack)</span></li>
              <li><span className="text-zinc-600">TypeScript Simulation Engine</span></li>
              <li><span className="text-zinc-600">FastAPI Async Telemetry</span></li>
              <li><span className="text-zinc-600">Tailwind CSS v4</span></li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="pt-6 border-t border-zinc-200 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-zinc-500 font-medium">
          <p>© {new Date().getFullYear()} Grocer — Quick-Commerce Inventory Balancing Prototype.</p>
          <div className="flex items-center gap-2">
            <GrocerLogo size="sm" />
          </div>
        </div>
      </div>
    </footer>
  );
}

