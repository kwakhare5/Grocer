"use client";

import React from "react";
import { Smartphone, LayoutDashboard, Sparkles, BookOpen } from "lucide-react";
import { GrocerLogo } from "../ui/GrocerLogo";

interface AppGlobalHeaderProps {
  mode: "landing" | "operations" | "customer";
  setMode: (mode: "landing" | "operations" | "customer") => void;
  criticalRiskCount?: number;
  isLiveApiConnected?: boolean;
  onDemoMode?: () => void;
}

export function AppGlobalHeader({
  mode,
  setMode,
  criticalRiskCount = 0,
  isLiveApiConnected = false,
  onDemoMode,
}: AppGlobalHeaderProps) {
  return (
    <header className="sticky top-0 z-50 w-full bg-white/95 backdrop-blur-md border-b border-zinc-200 shadow-2xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        {/* Left: Brand Identity & Telemetry */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setMode("landing")}
            className="flex items-center gap-2 hover:opacity-90 transition-opacity cursor-pointer text-left"
          >
            <GrocerLogo size="sm" iconOnly />
            <span className="font-bold text-zinc-950 tracking-tight text-base font-sans">Grocer</span>
          </button>

          {/* Live Telemetry Pill */}
          <div className="hidden sm:flex items-center gap-2 pl-3 border-l border-zinc-200">
            <span
              className={`w-2 h-2 rounded-full ${
                criticalRiskCount > 0 ? "bg-rose-500 animate-pulse" : "bg-emerald-500"
              }`}
            />
            <span className="text-[11px] font-mono text-zinc-600 font-medium">
              {criticalRiskCount > 0 ? `${criticalRiskCount} Stockout Risks` : "All Stores Stocked"}
            </span>
            {isLiveApiConnected && (
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-blue-50 text-blue-700 border border-blue-200 font-semibold">
                LIVE API
              </span>
            )}
          </div>
        </div>

        {/* Right: Persistent 3-Mode Clean Switcher + Demo */}
        <div className="flex items-center gap-2.5">
          {onDemoMode && (
            <button
              type="button"
              onClick={onDemoMode}
              className="hidden md:flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-lg bg-blue-50 hover:bg-blue-100 border border-blue-300 text-blue-900 transition-all cursor-pointer active:scale-97 shadow-2xs"
            >
              <Sparkles className="w-3.5 h-3.5 text-blue-600" />
              <span>Quick Demo</span>
            </button>
          )}

          <div className="flex items-center bg-zinc-100 p-1 rounded-lg border border-zinc-200">
            <button
              type="button"
              onClick={() => setMode("landing")}
              className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-md transition-all cursor-pointer ${
                mode === "landing"
                  ? "bg-white text-blue-950 shadow-xs border border-zinc-200/80 font-bold"
                  : "text-zinc-600 hover:text-zinc-900"
              }`}
            >
              <BookOpen className={`w-3.5 h-3.5 ${mode === "landing" ? "text-blue-600" : "text-zinc-500"}`} />
              <span>Home</span>
            </button>

            <button
              type="button"
              onClick={() => setMode("operations")}
              className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-md transition-all cursor-pointer ${
                mode === "operations"
                  ? "bg-white text-blue-950 shadow-xs border border-zinc-200/80 font-bold"
                  : "text-zinc-600 hover:text-zinc-900"
              }`}
            >
              <LayoutDashboard className={`w-3.5 h-3.5 ${mode === "operations" ? "text-blue-600" : "text-zinc-500"}`} />
              <span>Store Operations</span>
            </button>

            <button
              type="button"
              onClick={() => setMode("customer")}
              className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-md transition-all cursor-pointer ${
                mode === "customer"
                  ? "bg-white text-blue-950 shadow-xs border border-zinc-200/80 font-bold"
                  : "text-zinc-600 hover:text-zinc-900"
              }`}
            >
              <Smartphone className={`w-3.5 h-3.5 ${mode === "customer" ? "text-blue-600" : "text-zinc-500"}`} />
              <span>WhatsApp Demo</span>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
