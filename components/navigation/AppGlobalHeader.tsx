import React, { useState } from "react";
import Link from "next/link";
import { ExternalLink, MessageSquare, ShieldCheck, Terminal } from "lucide-react";
import { GrocerLogo } from "../ui/GrocerLogo";
import { LiveDebugInspector } from "../debug/LiveDebugInspector";

interface AppGlobalHeaderProps {
  isBackendConnected?: boolean;
}

export function AppGlobalHeader({
  isBackendConnected = false,
}: AppGlobalHeaderProps) {
  const [isDebugDrawerOpen, setIsDebugDrawerOpen] = useState(false);

  return (
    <>
      <header className="sticky top-0 z-40 w-full bg-white/95 backdrop-blur-md border-b border-zinc-200 shadow-2xs">
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

          {/* Right: Developer Live-Debug & Safety Guard */}
          <div className="flex items-center gap-2 sm:gap-3">
            {/* Developer Live-Debug Trigger Button */}
            <button
              type="button"
              onClick={() => setIsDebugDrawerOpen(true)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-zinc-900 text-zinc-100 hover:bg-zinc-800 border border-zinc-700 text-xs font-mono font-medium shadow-xs transition-colors cursor-pointer"
              title="Open Developer Live-Debug Drawer"
            >
              <Terminal className="w-3.5 h-3.5 text-emerald-400" />
              <span>LIVE DEBUG</span>
            </button>

            {/* Direct /debug link */}
            <Link
              href="/debug"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden sm:flex items-center gap-1 px-2 py-1.5 rounded-lg text-zinc-500 hover:text-zinc-800 text-xs font-mono transition-colors"
              title="Open Live Debug in dedicated tab for phone testing"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span className="text-[11px]">/debug</span>
            </Link>

            {/* Safety Guard Indicator */}
            <div className="hidden lg:flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-emerald-50/70 border border-emerald-200/80 text-emerald-900 text-xs font-mono">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              <span className="text-[11px] font-semibold">CONSEQUENTIAL GUARD ACTIVE</span>
            </div>
          </div>
        </div>
      </header>

      {/* Slide-Over Live-Debug Drawer */}
      {isDebugDrawerOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-black/50 backdrop-blur-xs flex justify-end">
          <div
            className="fixed inset-0"
            onClick={() => setIsDebugDrawerOpen(false)}
            aria-hidden="true"
          />
          <div className="relative w-full max-w-2xl h-full shadow-2xl z-10 animate-in slide-in-from-right duration-200">
            <LiveDebugInspector onClose={() => setIsDebugDrawerOpen(false)} />
          </div>
        </div>
      )}
    </>
  );
}
