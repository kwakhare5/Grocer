"use client";

import React from "react";
import Link from "next/link";
import { ArrowUpRight, CheckCircle2, Zap } from "lucide-react";
import { GrocerLogo } from "../ui/GrocerLogo";
import { PillButton } from "../ui/PillButton";

export function GrocerFooter() {
  return (
    <footer className="bg-[#FCFCFD] text-gray-900 pt-16 pb-12 border-t border-gray-200/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-14">
        {/* Giant CTA Container (Clean Light Slate Accent Card) */}
        <div className="bg-slate-50/90 rounded-3xl p-8 sm:p-12 border border-slate-200/80 shadow-[0_2px_12px_rgba(0,0,0,0.03)] flex flex-col md:flex-row items-start md:items-center justify-between gap-8 text-gray-950">
          {/* Left Column: Headline & Subtext */}
          <div className="space-y-4 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sky-50 border border-sky-200/80 text-sky-900 text-xs font-semibold">
              <Zap className="w-3.5 h-3.5 text-sky-600" />
              <span>Engineering Prototype & Problem Exploration</span>
            </div>

            <h3 className="font-serif font-normal text-3xl sm:text-4xl lg:text-5xl text-gray-950 tracking-tight leading-[1.12]">
              Explore pre-emptive staple replenishment.
            </h3>

            <p className="text-sm sm:text-base text-gray-600 font-normal leading-relaxed">
              Experience Grocer&apos;s Prophet ML depletion model and 5-node LangGraph execution state machine live in action.
            </p>

            {/* Feature Checkmarks Pills */}
            <div className="flex flex-wrap items-center gap-4 text-xs text-gray-700 font-medium pt-1">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-sky-600 shrink-0" />
                <span>Prophet ML Depletion</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-sky-600 shrink-0" />
                <span>1-Tap WhatsApp restock</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-sky-600 shrink-0" />
                <span>Recipe & Price Agents</span>
              </div>
            </div>
          </div>

          {/* Right Column: Action Buttons */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 shrink-0">
            <PillButton href="#demo" variant="primary">
              <span>Test Interactive Demo</span>
              <ArrowUpRight className="w-4 h-4 ml-1" />
            </PillButton>
          </div>
        </div>

        {/* 5-Column Footer Links Grid */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-8 text-xs pt-4">
          <div className="space-y-3">
            <p className="font-bold text-gray-950 uppercase tracking-wider text-[11px]">Product</p>
            <ul className="space-y-2 text-gray-500 font-medium">
              <li><Link href="#demo" className="hover:text-gray-950 transition-colors">Interactive Demo</Link></li>
              <li><Link href="#features" className="hover:text-gray-950 transition-colors">Pantry Simulator</Link></li>
              <li><Link href="#roi" className="hover:text-gray-950 transition-colors">Metrics Calculator</Link></li>
              <li><Link href="#faq" className="hover:text-gray-950 transition-colors">FAQ</Link></li>
            </ul>
          </div>

          <div className="space-y-3">
            <p className="font-bold text-gray-950 uppercase tracking-wider text-[11px]">Core Features</p>
            <ul className="space-y-2 text-gray-500 font-medium">
              <li><span className="text-gray-600">Prophet ML Forecasting</span></li>
              <li><span className="text-gray-600">Anomaly Exclusion</span></li>
              <li><span className="text-gray-600">LangGraph Restock Agent</span></li>
              <li><span className="text-gray-600">Recipe Pantry Checker</span></li>
            </ul>
          </div>

          <div className="space-y-3">
            <p className="font-bold text-gray-950 uppercase tracking-wider text-[11px]">Agents</p>
            <ul className="space-y-2 text-gray-500 font-medium">
              <li><span className="text-gray-600">Restock Agent</span></li>
              <li><span className="text-gray-600">Recipe Agent</span></li>
              <li><span className="text-gray-600">Price Intelligence Agent</span></li>
              <li><span className="text-gray-600">WhatsApp Alert Loop</span></li>
            </ul>
          </div>

          <div className="space-y-3">
            <p className="font-bold text-gray-950 uppercase tracking-wider text-[11px]">Architecture</p>
            <ul className="space-y-2 text-gray-500 font-medium">
              <li><span className="text-gray-600">FastAPI Async Backend</span></li>
              <li><span className="text-gray-600">SQLAlchemy Models</span></li>
              <li><span className="text-gray-600">TimescaleDB Prices</span></li>
              <li><span className="text-gray-600">Next.js 15 Prototype</span></li>
            </ul>
          </div>

          <div className="space-y-3">
            <p className="font-bold text-gray-950 uppercase tracking-wider text-[11px]">Project</p>
            <ul className="space-y-2 text-gray-500 font-medium">
              <li><span className="text-gray-600">Quick Commerce Concept</span></li>
              <li><span className="text-gray-600">Developer Demo</span></li>
              <li><span className="text-gray-600">Open Integration</span></li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="pt-8 border-t border-gray-200/60 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-gray-500 font-medium">
          <p>© {new Date().getFullYear()} Grocer — Predictive Household Inventory Concept.</p>
          <div className="flex items-center gap-2">
            <GrocerLogo size="sm" />
          </div>
        </div>
      </div>
    </footer>
  );
}
