"use client";

import React from "react";
import { MessageSquare, ShieldCheck } from "lucide-react";
import { GrocerLogo } from "../ui/GrocerLogo";

interface AppGlobalHeaderProps {
  isBackendConnected?: boolean;
}

export function AppGlobalHeader({
  isBackendConnected = false,
}: AppGlobalHeaderProps) {
  return (
    <header className="sticky top-0 z-50 w-full bg-white/95 backdrop-blur-md border-b border-zinc-200 shadow-2xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        {/* Left: Brand Identity & Subsystem Telemetry */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-left">
            <GrocerLogo size="sm" iconOnly />
            <div className="flex flex-col">
              <span className="font-bold text-zinc-950 tracking-tight text-base font-sans leading-tight">
                Grocer
              </span>
              <span className="text-[10px] font-mono text-emerald-700 font-semibold uppercase tracking-wider flex items-center gap-1">
                <MessageSquare className="w-2.5 h-2.5 text-emerald-600" /> WhatsApp Proactive Agent
              </span>
            </div>
          </div>

          {/* CommercePort Telemetry Pill */}
          <div className="hidden sm:flex items-center gap-2 pl-3 border-l border-zinc-200">
            <span
              className={`w-2 h-2 rounded-full ${isBackendConnected ? "bg-emerald-500" : "bg-zinc-400"}`}
            />
            <span className="text-[11px] font-mono text-zinc-600 font-medium">
              {isBackendConnected ? "Backend connected" : "Backend unavailable"}
            </span>
            {isBackendConnected ? (
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold">
                FASTAPI LIVE
              </span>
            ) : (
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-100 text-zinc-600 border border-zinc-200 font-medium">
                EDGE SIM
              </span>
            )}
          </div>
        </div>

        {/* Right: Safety Guard */}
        <div className="flex items-center gap-3">
          {/* Safety Guard Indicator */}
          <div className="hidden lg:flex items-center gap-1 px-2.5 py-1 rounded-md bg-emerald-50/70 border border-emerald-200/80 text-emerald-900 text-xs font-mono">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            <span className="text-[11px] font-semibold">CONSEQUENTIAL GUARD ACTIVE</span>
          </div>
        </div>
      </div>
    </header>
  );
}
