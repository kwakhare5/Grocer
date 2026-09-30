"use client";

import React, { useState } from "react";
import {
  Terminal,
  Check,
  CheckCircle2,
  MapPin,
  ExternalLink,
  ChevronRight,
  ShieldCheck,
} from "lucide-react";
import { GrocerLogo } from "../ui/GrocerLogo";
import { VerifiedJourneyTurn } from "./types";
import { VERIFIED_JOURNEY_TURNS } from "./data";

export function WhatsAppSimulator() {
  const [activeTurnNumber, setActiveTurnNumber] = useState<number>(2);

  const currentTurn: VerifiedJourneyTurn =
    VERIFIED_JOURNEY_TURNS.find((t) => t.turn === activeTurnNumber) ||
    VERIFIED_JOURNEY_TURNS[1];

  // Progressive conversation: shows turns up to current selected turn
  const visibleTurns = VERIFIED_JOURNEY_TURNS.filter(
    (t) => t.turn <= currentTurn.turn,
  );

  return (
    <section id="sandbox" className="py-16 sm:py-20 bg-zinc-100/70 border-y border-zinc-200 scroll-mt-16">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-2xl mx-auto mb-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold mb-3">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            <span>Empirical E2E Execution Transcript</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-editorial font-bold text-zinc-950">
            Real WhatsApp conversation trajectory
          </h2>
          <p className="mt-3 text-base sm:text-lg text-zinc-600 leading-relaxed font-normal">
            Step through the verified 6-turn customer journey recorded from our live Gemini 3.5 &amp; Swiggy MCP backend pipeline.
          </p>
        </div>

        {/* 6-Turn Stepper / Tab Switcher */}
        <div className="flex flex-wrap items-center justify-center gap-2 mb-8">
          {VERIFIED_JOURNEY_TURNS.map((t) => {
            const isActive = t.turn === currentTurn.turn;
            return (
              <button
                key={t.turn}
                type="button"
                onClick={() => setActiveTurnNumber(t.turn)}
                className={`px-3.5 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all cursor-pointer border ${
                  isActive
                    ? "bg-white text-zinc-950 border-emerald-600 shadow-sm ring-2 ring-emerald-500/20"
                    : "bg-white/80 hover:bg-white text-zinc-700 border-zinc-200 shadow-2xs"
                }`}
              >
                <span>{t.label}</span>
              </button>
            );
          })}
        </div>

        {/* Unified Two-Column Interface Card */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Full Progressive WhatsApp Conversation (7 cols) */}
          <div className="lg:col-span-7 bg-white rounded-3xl border border-zinc-200 shadow-xs overflow-hidden flex flex-col h-[580px]">
            {/* WhatsApp Header Bar */}
            <div className="bg-zinc-50/90 px-5 py-3.5 border-b border-zinc-200 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-3">
                <GrocerLogo size="sm" iconOnly />
                <div>
                  <div className="font-bold text-sm text-zinc-950 flex items-center gap-1.5">
                    <span>Grocer Replenishment</span>
                    <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                  </div>
                  <div className="text-xs text-zinc-500 font-medium">
                    Verified Trajectory • Gemini 3.5 Flash-Lite Live API
                  </div>
                </div>
              </div>
              <span className="text-xs font-mono px-2.5 py-1 rounded-lg bg-zinc-100 text-zinc-700 border border-zinc-200 font-medium">
                State: {currentTurn.state}
              </span>
            </div>

            {/* Conversation Messages Scroll Stream */}
            <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4 bg-zinc-50/40 text-zinc-900 text-sm font-sans">
              {/* Delivery Address Pill */}
              <div className="mx-auto w-fit px-3 py-1 rounded-full bg-white border border-zinc-200 text-xs text-zinc-600 flex items-center gap-1.5 shadow-2xs">
                <MapPin className="w-3.5 h-3.5 text-emerald-600" />
                <span>Active Store: Charholi Budruk, Pune Hub #2041</span>
              </div>

              {visibleTurns.map((turnData) => (
                <div key={turnData.turn} className="space-y-3">
                  {/* User Turn */}
                  <div className="flex flex-col items-end">
                    <div className="max-w-[85%] rounded-2xl p-3.5 bg-emerald-600 text-white rounded-tr-none shadow-2xs">
                      <p className="text-sm font-normal">{turnData.userInput}</p>
                      <div className="mt-1 flex items-center justify-end gap-1 text-[11px] text-emerald-200 font-mono">
                        <span>Turn {turnData.turn}</span>
                        <span className="font-bold">Read</span>
                      </div>
                    </div>
                  </div>

                  {/* Assistant Turn */}
                  <div className="flex flex-col items-start">
                    <div className="max-w-[90%] rounded-2xl p-4 bg-white text-zinc-900 rounded-tl-none border border-zinc-200 shadow-2xs space-y-2">
                      <p className="leading-relaxed whitespace-pre-wrap text-sm font-normal">
                        {turnData.assistantMessage}
                      </p>

                      {/* Itemized Dark Store Receipt */}
                      {turnData.items && turnData.items.length > 0 && (
                        <div className="mt-2.5 pt-2.5 border-t border-zinc-200 space-y-1.5 text-xs sm:text-sm">
                          {turnData.items.map((item, idx) => (
                            <div key={idx} className="flex justify-between gap-3 text-zinc-700">
                              <span className="truncate">• {item.name}</span>
                              <span className="font-mono shrink-0 font-semibold text-zinc-900">{item.price}</span>
                            </div>
                          ))}

                          <div className="mt-2.5 pt-2.5 border-t border-zinc-200 space-y-1 text-xs">
                            {turnData.subtotal && (
                              <div className="flex justify-between text-zinc-500">
                                <span>Subtotal:</span>
                                <span className="font-mono">{turnData.subtotal}</span>
                              </div>
                            )}
                            {turnData.fees && (
                              <div className="flex justify-between text-zinc-500">
                                <span>Delivery &amp; Packaging:</span>
                                <span className="font-mono">{turnData.fees}</span>
                              </div>
                            )}
                            {turnData.total && (
                              <div className="flex justify-between font-bold text-zinc-950 pt-1.5 border-t border-zinc-200 text-sm">
                                <span>Grand Total:</span>
                                <span className="font-mono text-emerald-700">{turnData.total}</span>
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Official Dynamic UPI Payment Link */}
                      {turnData.paymentLink && (
                        <div className="mt-3 pt-2.5 border-t border-zinc-200">
                          <a
                            href={turnData.paymentLink}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-3 rounded-xl bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 flex items-center justify-between text-xs text-emerald-950 font-medium transition cursor-pointer"
                          >
                            <span>Official Swiggy UPI Payment Link</span>
                            <ExternalLink className="w-3.5 h-3.5 text-emerald-700" />
                          </a>
                        </div>
                      )}

                      <div className="mt-1 flex items-center justify-end text-[11px] text-zinc-400 font-mono">
                        <span>Latency: {turnData.latencyMs} ms</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Stepper Navigation Footer */}
            <div className="bg-zinc-50/80 px-4 py-2.5 border-t border-zinc-200 flex items-center justify-between shrink-0 text-xs">
              <span className="font-mono text-zinc-600">
                Step {currentTurn.turn} of 6
              </span>
              <div className="flex items-center gap-2">
                {currentTurn.turn < 6 ? (
                  <button
                    type="button"
                    onClick={() => setActiveTurnNumber(currentTurn.turn + 1)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs shadow-2xs transition cursor-pointer"
                  >
                    <span>Next Turn</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => setActiveTurnNumber(1)}
                    className="px-3 py-1.5 rounded-lg bg-zinc-200 hover:bg-zinc-300 text-zinc-800 font-medium text-xs transition cursor-pointer"
                  >
                    Restart Journey
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Right Column: Live Swiggy MCP Tool Execution Inspector (5 cols) */}
          <div className="lg:col-span-5 space-y-4">
            <div className="bg-white rounded-3xl p-5 sm:p-6 border border-zinc-200 shadow-xs">
              <div className="flex items-center justify-between pb-3.5 border-b border-zinc-100 mb-4">
                <div className="flex items-center gap-2">
                  <Terminal className="w-4 h-4 text-emerald-700" />
                  <h3 className="font-mono text-sm font-bold text-zinc-950">
                    Swiggy MCP Tool Execution
                  </h3>
                </div>
                <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-zinc-100 text-zinc-700 border border-zinc-200 font-medium">
                  HTTP/2 Pooled
                </span>
              </div>

              <div className="space-y-4 font-mono text-xs">
                <div>
                  <div className="text-zinc-500 text-[11px] mb-1 uppercase tracking-wider font-semibold">
                    Executed Tool / Guard
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-800 border border-emerald-200 font-bold">
                      {currentTurn.toolTrace.tool}
                    </span>
                    <span className="text-zinc-600 text-xs">
                      Latency: {currentTurn.toolTrace.latencyMs} ms
                    </span>
                  </div>
                </div>

                <div>
                  <div className="text-zinc-500 text-[11px] mb-1 uppercase tracking-wider font-semibold">
                    Verified Invariant
                  </div>
                  <div className="px-2.5 py-1 rounded-lg bg-zinc-50 text-zinc-800 border border-zinc-200 text-xs font-sans">
                    {currentTurn.toolTrace.invariantTested}
                  </div>
                </div>

                <div>
                  <div className="text-zinc-500 text-[11px] mb-1 uppercase tracking-wider font-semibold">
                    Tool Arguments / State
                  </div>
                  <pre className="p-3 rounded-xl bg-zinc-50 text-zinc-800 text-xs overflow-x-auto border border-zinc-200">
                    {JSON.stringify(currentTurn.toolTrace.params, null, 2)}
                  </pre>
                </div>

                <div>
                  <div className="text-zinc-500 text-[11px] mb-1 uppercase tracking-wider font-semibold">
                    Runtime Result Summary
                  </div>
                  <p className="text-zinc-700 text-xs font-sans bg-zinc-50 p-3 rounded-xl border border-zinc-200 leading-relaxed">
                    {currentTurn.toolTrace.resultSummary}
                  </p>
                </div>

                <div className="pt-3 border-t border-zinc-100 flex items-center justify-between text-xs text-zinc-600">
                  <span className="flex items-center gap-1.5 font-sans">
                    <Check className="w-3.5 h-3.5 text-emerald-600" />
                    Verified by test_e2e_pipeline.py
                  </span>
                  <span className="font-mono">JSON-RPC 2.0</span>
                </div>
              </div>
            </div>

            {/* Zero-Math Assurance Note */}
            <div className="bg-white rounded-2xl p-4 sm:p-5 border border-zinc-200 text-xs text-zinc-600 space-y-1.5 shadow-2xs">
              <div className="font-bold text-zinc-950 flex items-center gap-1.5 text-xs sm:text-sm">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Deterministic Safety Gate</span>
              </div>
              <p className="leading-relaxed font-normal">
                Notice Turn 5: the AI model cannot place an order until the customer explicitly replies &ldquo;Confirm&rdquo;. Once confirmed, pure Python executes checkout and verifies payment state.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
