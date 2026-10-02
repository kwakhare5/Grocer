"use client";

import React, { useState } from "react";
import {
  Workflow,
  Check,
  ShieldCheck,
  ArrowRight,
  ArrowLeft,
  MapPin,
  Search,
  Lock,
  ShoppingBag,
} from "lucide-react";
import { WhatsAppIcon } from "../ui/WhatsAppIcon";
import { PIPELINE_NODES } from "./data";

export function ArchitectureSection() {
  const [activeStepIndex, setActiveStepIndex] = useState<number>(0); // Default to WhatsApp Message (Step 01)

  const activeNode = PIPELINE_NODES[activeStepIndex] || PIPELINE_NODES[0];

  const getStepIcon = (id: string) => {
    switch (id) {
      case "whatsapp":
        return <WhatsAppIcon className="w-4 h-4 shrink-0" />;
      case "address":
        return <MapPin className="w-4 h-4" />;
      case "groq":
        return <Search className="w-4 h-4" />;
      case "guards":
        return <Lock className="w-4 h-4" />;
      case "swiggy":
        return <ShoppingBag className="w-4 h-4" />;
      default:
        return <Workflow className="w-4 h-4" />;
    }
  };

  return (
    <section id="architecture" className="py-16 sm:py-20 bg-transparent border-b border-zinc-200/80 scroll-mt-16">
      <div className="max-w-5xl mx-auto px-4 sm:px-6">
        {/* Section Header */}
        <div className="text-center max-w-2xl mx-auto mb-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold mb-3">
            <Workflow className="w-3.5 h-3.5 text-emerald-700" />
            <span>Behind The Scenes</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-editorial font-bold text-zinc-950 tracking-tight">
            How Grocer connects WhatsApp to your local store
          </h2>
          <p className="mt-2.5 text-sm sm:text-base text-zinc-600 leading-relaxed font-normal">
            From the moment you send a message to local store stock verification and safe UPI payment. Follow the 5-step journey below.
          </p>
        </div>

        {/* ─── 5-Step Unified Interactive Stepper Bar ─── */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 mb-8">
          {PIPELINE_NODES.map((node, idx) => {
            const isActive = idx === activeStepIndex;
            return (
              <button
                key={node.id}
                type="button"
                onClick={() => setActiveStepIndex(idx)}
                className={`p-3 rounded-2xl border text-left transition-all duration-150 active:scale-[0.98] cursor-pointer flex flex-col justify-between gap-2.5 ${
                  isActive
                    ? "bg-white border-emerald-600 shadow-xs ring-2 ring-emerald-500/20"
                    : "bg-zinc-50/80 hover:bg-white border-zinc-200 hover:border-zinc-300"
                }`}
              >
                <div className="flex items-center justify-between w-full">
                  <span
                    className={`font-mono text-xs font-bold px-2 py-0.5 rounded-md ${
                      isActive
                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                        : "bg-zinc-100 text-zinc-600 border border-zinc-200"
                    }`}
                  >
                    {node.stepNumber}
                  </span>
                  <div
                    className={`${
                      isActive ? "text-emerald-700" : "text-zinc-400"
                    }`}
                  >
                    {getStepIcon(node.id)}
                  </div>
                </div>

                <div>
                  <div className="font-bold text-xs sm:text-sm text-zinc-950 leading-tight">
                    {node.title}
                  </div>
                  <div className="text-xs text-zinc-500 mt-0.5 truncate">
                    {node.metric}
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        {/* ─── Active Stage Detail Showcase Card ─── */}
        <div className="rounded-3xl border border-zinc-200 bg-white p-6 sm:p-8 shadow-xs">
          {/* Card Top Banner */}
          <div className="flex flex-wrap items-center justify-between gap-3 pb-6 border-b border-zinc-100 mb-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-700 shrink-0">
                {getStepIcon(activeNode.id)}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-bold text-emerald-700">
                    Step {activeNode.stepNumber}
                  </span>
                  <span className="text-xs text-zinc-400">•</span>
                  <span className="text-xs text-zinc-500 font-medium">
                    {activeNode.subtitle}
                  </span>
                </div>
                <h3 className="text-lg sm:text-xl font-bold text-zinc-950">
                  {activeNode.title}
                </h3>
              </div>
            </div>

            <span className="px-3 py-1 rounded-xl text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
              {activeNode.metric}
            </span>
          </div>

          {/* Card Summary Text */}
          <p className="text-sm sm:text-base text-zinc-600 leading-relaxed font-normal mb-8 max-w-3xl">
            {activeNode.description}
          </p>

          {/* Two-Column Details: Responsibilities (Left) + Protection Guarantee (Right) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* Left Column: 3 Core Responsibilities (7 cols) */}
            <div className="lg:col-span-7 space-y-3">
              <div className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
                What happens in this step
              </div>
              <ul className="space-y-2.5">
                {activeNode.responsibilities.map((resp, idx) => (
                  <li
                    key={idx}
                    className="p-3.5 rounded-2xl bg-zinc-50 border border-zinc-200/80 flex items-start gap-3"
                  >
                    <Check className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                    <span className="text-xs sm:text-sm text-zinc-800 leading-relaxed">
                      {resp}
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Right Column: Customer Protection Callout (5 cols) */}
            <div className="lg:col-span-5 space-y-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
                Customer Guarantee
              </div>
              <div className="p-5 rounded-2xl bg-emerald-50/70 border border-emerald-200/80 space-y-2.5">
                <div className="text-xs font-bold text-emerald-800 uppercase tracking-wider flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  <span>Why this protects you</span>
                </div>
                <p className="text-xs sm:text-sm text-emerald-950 leading-relaxed font-medium">
                  {activeNode.whyItMatters}
                </p>
              </div>

              <div className="p-4 rounded-2xl bg-zinc-50 border border-zinc-200 text-xs text-zinc-600 space-y-1">
                <div className="font-semibold text-zinc-950">
                  Verification Status
                </div>
                <p className="text-zinc-500 leading-relaxed">
                  Verified with 62 automated invariant tests against live Swiggy Instamart schemas.
                </p>
              </div>
            </div>
          </div>

          {/* Stepper Navigation Controls */}
          <div className="mt-8 pt-6 border-t border-zinc-100 flex items-center justify-between">
            <button
              type="button"
              disabled={activeStepIndex === 0}
              onClick={() => setActiveStepIndex((prev) => Math.max(0, prev - 1))}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold border border-zinc-200 bg-white hover:bg-zinc-50 text-zinc-700 disabled:opacity-40 disabled:cursor-not-allowed transition duration-150 active:scale-[0.98] cursor-pointer shadow-2xs"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Previous Step</span>
            </button>

            <span className="text-xs text-zinc-400 font-mono">
              {activeStepIndex + 1} of {PIPELINE_NODES.length}
            </span>

            <button
              type="button"
              disabled={activeStepIndex === PIPELINE_NODES.length - 1}
              onClick={() =>
                setActiveStepIndex((prev) =>
                  Math.min(PIPELINE_NODES.length - 1, prev + 1)
                )
              }
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold border border-zinc-200 bg-white hover:bg-zinc-50 text-zinc-700 disabled:opacity-40 disabled:cursor-not-allowed transition duration-150 active:scale-[0.98] cursor-pointer shadow-2xs"
            >
              <span>Next Step</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
