"use client";

import React, { useState } from "react";
import {
  ShieldCheck,
  Check,
  ChevronRight,
  ChevronDown,
  Code2,
  Phone,
  Video,
  MoreVertical,
  ArrowLeft,
  Smile,
  Mic,
  ExternalLink,
} from "lucide-react";
import { GrocerLogo } from "../ui/GrocerLogo";
import { WhatsAppIcon } from "../ui/WhatsAppIcon";
import { VerifiedJourneyTurn } from "./types";
import { VERIFIED_JOURNEY_TURNS } from "./data";

export function WhatsAppSimulator() {
  const [activeTurnNumber, setActiveTurnNumber] = useState<number>(1);
  const [showTechnicalDetails, setShowTechnicalDetails] = useState<boolean>(false);

  const currentTurn: VerifiedJourneyTurn =
    VERIFIED_JOURNEY_TURNS.find((t) => t.turn === activeTurnNumber) ||
    VERIFIED_JOURNEY_TURNS[0];

  return (
    <section id="conversation" className="py-16 sm:py-20 bg-[#FAFAFA] border-b border-zinc-200/80 scroll-mt-16">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-2xl mx-auto mb-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold mb-3">
            <WhatsAppIcon className="w-3.5 h-3.5" />
            <span>Verified WhatsApp Conversation Flow</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-editorial font-bold text-zinc-950 tracking-tight">
            Real WhatsApp conversation flow
          </h2>
          <p className="mt-2.5 text-sm sm:text-base text-zinc-600 leading-relaxed font-normal">
            Recorded live from our Gemini 3.5 Flash-Lite &amp; Quick-Commerce engine. Select any turn to inspect the exact message and backend safety rules.
          </p>
        </div>

        {/* 6-Turn Clean Tab Switcher */}
        <div className="flex flex-wrap items-center justify-center gap-2 mb-10">
          {VERIFIED_JOURNEY_TURNS.map((t) => {
            const isActive = t.turn === currentTurn.turn;
            return (
              <button
                key={t.turn}
                type="button"
                onClick={() => setActiveTurnNumber(t.turn)}
                className={`px-3.5 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all duration-150 active:scale-[0.98] cursor-pointer border ${
                  isActive
                    ? "bg-white text-zinc-950 border-emerald-600 shadow-xs ring-2 ring-emerald-500/20"
                    : "bg-white/80 hover:bg-white text-zinc-700 border-zinc-200 shadow-2xs hover:border-zinc-300"
                }`}
              >
                <span>{t.label}</span>
              </button>
            );
          })}
        </div>

        {/* Two-Column Showcase: Left = Borderless Floating WhatsApp Chassis, Right = Invariant Spec */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* ─── LEFT: Borderless Floating HTML WhatsApp Chassis (7 cols) ─── */}
          <div className="lg:col-span-7">
            <div className="rounded-3xl bg-[#EFEAE2] shadow-xl shadow-zinc-950/10 ring-1 ring-zinc-950/5 overflow-hidden max-w-md mx-auto w-full">
              {/* WhatsApp Mobile Header Bar */}
              <div className="bg-[#008069] text-white px-3.5 py-3 flex items-center justify-between shadow-xs">
                <div className="flex items-center gap-2.5">
                  <ArrowLeft className="w-4 h-4 cursor-pointer text-white/90" />
                  <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center text-emerald-800 shrink-0 shadow-2xs">
                    <GrocerLogo size="sm" iconOnly />
                  </div>
                  <div>
                    <div className="font-semibold text-sm leading-tight flex items-center gap-1.5">
                      <span>Grocer</span>
                      <WhatsAppIcon className="w-3.5 h-3.5" />
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-300"></span>
                    </div>
                    <div className="text-xs text-white/80 leading-tight">
                      online • Swiggy Instamart Gateway
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3 text-white/90">
                  <Video className="w-4 h-4 cursor-pointer" />
                  <Phone className="w-3.5 h-3.5 cursor-pointer" />
                  <MoreVertical className="w-4 h-4 cursor-pointer" />
                </div>
              </div>

              {/* Chat Viewport (Zero Scroll Trapping, Clean Natural Fit) */}
              <div className="p-4 sm:p-5 space-y-3.5 bg-[#EFEAE2] min-h-[440px] flex flex-col justify-between">
                <div className="space-y-3">
                  {/* Delivery Location Pill */}
                  <div className="mx-auto w-fit px-3 py-1 rounded-full bg-white/90 border border-zinc-200/80 text-xs text-zinc-600 font-medium shadow-2xs">
                    Baner, Pune Hub • Turn {currentTurn.turn} of 6
                  </div>

                  {/* 1. Customer Speech Bubble */}
                  <div className="flex flex-col items-end">
                    <div className="max-w-[85%] rounded-2xl rounded-tr-none p-3 bg-[#D9FDD3] text-zinc-900 shadow-2xs">
                      <p className="text-xs sm:text-sm font-normal leading-relaxed">{currentTurn.userInput}</p>
                      <div className="mt-1 flex items-center justify-end gap-1 text-xs text-zinc-500 font-mono">
                        <span>12:4{currentTurn.turn} PM</span>
                        <span className="text-[#53BDEB] font-bold">✓✓</span>
                      </div>
                    </div>
                  </div>

                  {/* 2. Grocer Agent Speech Bubble */}
                  <div className="flex flex-col items-start">
                    <div className="max-w-[92%] rounded-2xl rounded-tl-none p-3.5 bg-white text-zinc-900 shadow-2xs border border-zinc-200/60 space-y-2.5">
                      <p className="leading-relaxed whitespace-pre-wrap text-xs sm:text-sm font-normal">
                        {currentTurn.assistantMessage}
                      </p>

                      {/* Itemized Receipt Table (when present) */}
                      {currentTurn.items && currentTurn.items.length > 0 && (
                        <div className="pt-2 border-t border-zinc-100 space-y-1.5 text-xs sm:text-sm">
                          {currentTurn.items.map((item, idx) => (
                            <div key={idx} className="flex justify-between gap-3 text-zinc-700">
                              <span className="truncate">• {item.name}</span>
                              <span className="font-mono font-semibold text-zinc-900 shrink-0">
                                {item.price}
                              </span>
                            </div>
                          ))}

                          <div className="pt-2 border-t border-zinc-100 space-y-1 text-xs">
                            {currentTurn.subtotal && (
                              <div className="flex justify-between text-zinc-500">
                                <span>Subtotal:</span>
                                <span className="font-mono">{currentTurn.subtotal}</span>
                              </div>
                            )}
                            {currentTurn.fees && (
                              <div className="flex justify-between text-zinc-500">
                                <span>Delivery &amp; Handling:</span>
                                <span className="font-mono">{currentTurn.fees}</span>
                              </div>
                            )}
                            {currentTurn.total && (
                              <div className="flex justify-between font-bold text-zinc-950 pt-1.5 border-t border-zinc-200 text-sm">
                                <span>Grand Total:</span>
                                <span className="font-mono text-emerald-700">{currentTurn.total}</span>
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Official Payment Link Card */}
                      {currentTurn.paymentLink && (
                        <div className="pt-2 border-t border-zinc-100">
                          <a
                            href={currentTurn.paymentLink}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-2.5 rounded-xl bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 flex items-center justify-between text-xs text-emerald-950 font-semibold transition active:scale-[0.98]"
                          >
                            <span>Official Swiggy UPI Payment Link</span>
                            <ExternalLink className="w-3.5 h-3.5 text-emerald-700" />
                          </a>
                        </div>
                      )}

                      <div className="mt-1 flex items-center justify-end text-xs text-zinc-400 font-mono">
                        <span>12:4{currentTurn.turn} PM</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* WhatsApp Chat Bottom Input Bar */}
                <div className="mt-4 pt-2 border-t border-zinc-300/40 flex items-center gap-2 text-zinc-500">
                  <div className="flex-1 bg-white rounded-full px-3.5 py-1.5 text-xs text-zinc-400 flex items-center justify-between border border-zinc-200">
                    <span className="flex items-center gap-2">
                      <Smile className="w-4 h-4 text-zinc-400" />
                      <span>Message</span>
                    </span>
                  </div>
                  <div className="w-8 h-8 rounded-full bg-[#008069] flex items-center justify-center text-white shadow-2xs">
                    <Mic className="w-4 h-4" />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ─── RIGHT: Invariant Decision Card (5 cols) ────────────────── */}
          <div className="lg:col-span-5 space-y-4">
            <div className="bg-white rounded-3xl p-5 sm:p-6 border border-zinc-200 shadow-xs space-y-4">
              <div className="flex items-center justify-between pb-3.5 border-b border-zinc-100">
                <span className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
                  Behind The Scenes
                </span>
                <span className="px-2.5 py-0.5 rounded-lg text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                  {currentTurn.tag}
                </span>
              </div>

              {/* 1. Customer Intent */}
              <div className="p-3.5 rounded-2xl bg-zinc-50 border border-zinc-200/80 space-y-1">
                <div className="text-xs uppercase tracking-wider font-bold text-zinc-500">
                  Customer Asked
                </div>
                <p className="text-zinc-800 text-xs sm:text-sm font-medium leading-relaxed">
                  {currentTurn.humanExplanation.customerIntent}
                </p>
              </div>

              {/* 2. Safety Rule Enforced */}
              <div className="p-3.5 rounded-2xl bg-emerald-50/60 border border-emerald-200/80 space-y-1">
                <div className="text-xs uppercase tracking-wider font-bold text-emerald-800 flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Safety Rule Enforced</span>
                </div>
                <p className="text-emerald-950 text-xs sm:text-sm font-medium leading-relaxed">
                  {currentTurn.humanExplanation.safetyRule}
                </p>
              </div>

              {/* 3. Store Outcome */}
              <div className="p-3.5 rounded-2xl bg-zinc-50 border border-zinc-200/80 space-y-1">
                <div className="text-xs uppercase tracking-wider font-bold text-zinc-500">
                  Store Outcome
                </div>
                <p className="text-zinc-800 text-xs sm:text-sm font-medium leading-relaxed">
                  {currentTurn.humanExplanation.storeOutcome}
                </p>
              </div>

              {/* Collapsible Technical Inspector */}
              <div className="pt-1">
                <button
                  type="button"
                  onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
                  className="w-full flex items-center justify-between p-2.5 rounded-xl border border-zinc-200 hover:bg-zinc-50 text-zinc-700 text-xs font-medium transition active:scale-[0.98] cursor-pointer"
                >
                  <span className="flex items-center gap-1.5">
                    <Code2 className="w-3.5 h-3.5 text-zinc-500" />
                    <span>{showTechnicalDetails ? "Hide technical payload" : "Inspect technical payload"}</span>
                  </span>
                  {showTechnicalDetails ? (
                    <ChevronDown className="w-3.5 h-3.5 text-zinc-500" />
                  ) : (
                    <ChevronRight className="w-3.5 h-3.5 text-zinc-500" />
                  )}
                </button>

                {showTechnicalDetails && (
                  <div className="mt-3 p-3.5 rounded-2xl bg-zinc-50 text-zinc-800 font-mono text-xs space-y-2 border border-zinc-200">
                    <div className="flex items-center justify-between text-zinc-500 pb-1.5 border-b border-zinc-200">
                      <span>Tool: <strong className="text-emerald-700">{currentTurn.toolTrace.tool}</strong></span>
                      <span>{currentTurn.toolTrace.latencyMs} ms</span>
                    </div>
                    <div>
                      <div className="text-zinc-500 text-xs uppercase tracking-wider mb-1 font-semibold">
                        Arguments
                      </div>
                      <pre className="p-2.5 rounded-xl bg-white text-zinc-800 border border-zinc-200 overflow-x-auto text-xs">
                        {JSON.stringify(currentTurn.toolTrace.params, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}
              </div>

              {/* Bottom Invariant Proof */}
              <div className="pt-2 border-t border-zinc-100 flex items-center justify-between text-xs text-zinc-600">
                <span className="flex items-center gap-1.5 font-sans">
                  <Check className="w-3.5 h-3.5 text-emerald-600" />
                  {currentTurn.toolTrace.invariantTested}
                </span>
                <span className="font-mono text-emerald-700 font-semibold">Verified</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
