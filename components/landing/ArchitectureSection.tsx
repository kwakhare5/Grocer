"use client";

import React, { useState } from "react";
import {
  Layers,
  CheckCircle2,
  MapPin,
  ShieldCheck,
  ArrowRight,
  Code,
  Zap,
} from "lucide-react";
import { PIPELINE_NODES } from "./data";
import { PipelineNode } from "./types";

export function ArchitectureSection() {
  const [selectedNodeId, setSelectedNodeId] = useState<string>("swiggy");

  const activeNode: PipelineNode =
    PIPELINE_NODES.find((n) => n.id === selectedNodeId) || PIPELINE_NODES[4];

  return (
    <section id="architecture" className="py-16 sm:py-20 bg-zinc-100/70 border-b border-zinc-200 scroll-mt-16">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-2xl mx-auto mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-zinc-200 text-zinc-800 text-xs font-semibold mb-3">
            <Layers className="w-3.5 h-3.5" />
            <span>Technical Architecture</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-editorial font-bold text-zinc-950">
            Decoupled CommercePort &amp; Swiggy MCP pipeline
          </h2>
          <p className="mt-3 text-base sm:text-lg text-zinc-600 leading-relaxed font-normal">
            A production-tested, provider-agnostic replenishment engine pairing autonomous LLM reasoning with deterministic safety guards.
          </p>
        </div>

        {/* ─── Interactive Visual Pipeline Flow Diagram ──────────────── */}
        <div className="bg-white rounded-3xl p-6 sm:p-8 border border-zinc-200 shadow-sm max-w-5xl mx-auto mb-10">
          <div className="flex items-center justify-between pb-4 border-b border-zinc-100 mb-6">
            <div className="flex items-center gap-2 text-xs font-semibold text-zinc-800">
              <Zap className="w-4 h-4 text-emerald-600" />
              <span>Interactive Pipeline Diagram • Click any stage to inspect technical specs</span>
            </div>
            <span className="text-xs font-mono text-zinc-500">
              HTTP/2 Persistent Pool
            </span>
          </div>

          {/* 5-Step Pipeline Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 relative">
            {PIPELINE_NODES.map((node, index) => {
              const isSelected = node.id === activeNode.id;
              return (
                <button
                  key={node.id}
                  type="button"
                  onClick={() => setSelectedNodeId(node.id)}
                  className={`relative p-4 rounded-2xl text-left transition-all cursor-pointer flex flex-col justify-between border ${
                    isSelected
                      ? "bg-zinc-900 text-white border-zinc-900 shadow-md scale-[1.02] ring-2 ring-emerald-500/50"
                      : "bg-zinc-50 hover:bg-zinc-100/80 text-zinc-800 border-zinc-200"
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between text-xs mb-2">
                      <span className={`font-mono font-bold ${isSelected ? "text-emerald-400" : "text-zinc-500"}`}>
                        {node.stepNumber}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                          isSelected
                            ? "bg-zinc-800 text-zinc-300"
                            : "bg-white text-zinc-700 border border-zinc-200"
                        }`}
                      >
                        {node.badge}
                      </span>
                    </div>

                    <h4 className="font-bold text-xs sm:text-sm leading-tight mb-1">
                      {node.title}
                    </h4>
                    <p className={`text-[11px] ${isSelected ? "text-zinc-400" : "text-zinc-500"}`}>
                      {node.subtitle}
                    </p>
                  </div>

                  <div className="mt-4 pt-2 border-t border-zinc-200/50 dark:border-zinc-800 flex items-center justify-between text-[11px]">
                    <span className={`font-mono font-semibold ${isSelected ? "text-emerald-400" : "text-emerald-700"}`}>
                      {node.metric}
                    </span>
                    {index < PIPELINE_NODES.length - 1 && (
                      <ArrowRight className={`w-3 h-3 hidden lg:block ${isSelected ? "text-zinc-500" : "text-zinc-400"}`} />
                    )}
                  </div>
                </button>
              );
            })}
          </div>

          {/* ─── Deep-Dive Technical Node Inspector ─────────────────── */}
          <div className="mt-6 p-5 sm:p-6 rounded-2xl bg-zinc-900 text-white border border-zinc-800">
            <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-zinc-800 mb-4">
              <div className="flex items-center gap-2">
                <Code className="w-4 h-4 text-emerald-400" />
                <span className="text-xs sm:text-sm font-bold font-mono text-zinc-100">
                  Stage {activeNode.stepNumber}: {activeNode.title}
                </span>
                <span className="text-xs px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 font-mono">
                  {activeNode.technicalDetails.protocol}
                </span>
              </div>
              <span className="text-xs text-zinc-400 font-mono truncate max-w-xs">
                {activeNode.technicalDetails.endpointOrFile}
              </span>
            </div>

            <p className="text-xs sm:text-sm text-zinc-300 mb-4 leading-relaxed font-sans">
              {activeNode.description}
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Enforced Invariants */}
              <div>
                <div className="text-[11px] font-mono uppercase tracking-wider text-zinc-400 mb-2">
                  Key Invariants Enforced
                </div>
                <ul className="space-y-1.5 text-xs text-zinc-300 font-sans">
                  {activeNode.technicalDetails.invariants.map((inv, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                      <span>{inv}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Sample Payload Inspection */}
              <div>
                <div className="text-[11px] font-mono uppercase tracking-wider text-zinc-400 mb-2">
                  Runtime Payload / Memory Schema
                </div>
                <pre className="p-3 rounded-xl bg-zinc-950 text-zinc-300 text-[11px] font-mono overflow-x-auto border border-zinc-800 max-h-36">
                  {JSON.stringify(activeNode.technicalDetails.samplePayload, null, 2)}
                </pre>
              </div>
            </div>
          </div>

          {/* Test & Verification Summary Stats */}
          <div className="mt-6 pt-6 border-t border-zinc-100 grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-zinc-950 font-mono">62 / 62</div>
              <div className="text-xs text-zinc-600 mt-1 font-medium">Automated Invariant Tests Passed</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-zinc-950 font-mono">6 / 6</div>
              <div className="text-xs text-zinc-600 mt-1 font-medium">Failure Invariants Verified Live</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-zinc-950 font-mono">~1.0s</div>
              <div className="text-xs text-zinc-600 mt-1 font-medium">Gemini HTTP/2 Pooled Generation</div>
            </div>
          </div>
        </div>

        {/* ─── Swiggy Instamart Live MCP Tool Contract Grid ──────────── */}
        <div className="bg-white rounded-3xl p-6 sm:p-8 border border-zinc-200 shadow-sm max-w-5xl mx-auto mb-10">
          <div className="mb-6">
            <h3 className="text-lg sm:text-xl font-bold text-zinc-950">
              Swiggy Instamart Live MCP Tool Contract
            </h3>
            <p className="text-xs sm:text-sm text-zinc-600 mt-1 leading-relaxed">
              GROCER implements the official Model Context Protocol tools exposed at <code className="font-mono text-xs bg-zinc-100 px-1.5 py-0.5 rounded text-zinc-800">https://mcp.swiggy.com/im</code>.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-xs font-sans">
            <div className="p-4 rounded-2xl bg-zinc-50 border border-zinc-200">
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono font-bold text-zinc-950 text-xs sm:text-sm">search_products</span>
                <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-mono text-[10px]">Read Tool</span>
              </div>
              <p className="text-zinc-600 leading-relaxed">
                Queries real-time dark store stock, prices, variants, and pack sizes. Supports concurrent execution via <code className="font-mono text-zinc-800">asyncio.gather</code>.
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-zinc-50 border border-zinc-200">
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono font-bold text-zinc-950 text-xs sm:text-sm">update_cart</span>
                <span className="px-2 py-0.5 rounded bg-blue-100 text-blue-800 font-mono text-[10px]">Delta Mutation</span>
              </div>
              <p className="text-zinc-600 leading-relaxed">
                Adds, increments, or decrements dark store SKUs while preserving existing basket items and respecting store minimums.
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-zinc-50 border border-zinc-200">
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono font-bold text-zinc-950 text-xs sm:text-sm">get_cart</span>
                <span className="px-2 py-0.5 rounded bg-zinc-200 text-zinc-800 font-mono text-[10px]">State Verify</span>
              </div>
              <p className="text-zinc-600 leading-relaxed">
                Reads back verified provider totals, item discounts, packaging fees, and delivery charges. Eliminates model arithmetic.
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-zinc-50 border border-zinc-200">
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono font-bold text-zinc-950 text-xs sm:text-sm">checkout</span>
                <span className="px-2 py-0.5 rounded bg-purple-100 text-purple-800 font-mono text-[10px]">Gated Mutator</span>
              </div>
              <p className="text-zinc-600 leading-relaxed">
                Server-side gated: only executes when <code className="font-mono text-zinc-800">is_user_confirmed</code> is true. Generates dynamic UPI payment bridge QR.
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-zinc-50 border border-zinc-200">
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono font-bold text-zinc-950 text-xs sm:text-sm">track_order</span>
                <span className="px-2 py-0.5 rounded bg-orange-100 text-orange-800 font-mono text-[10px]">Fulfillment</span>
              </div>
              <p className="text-zinc-600 leading-relaxed">
                Reports live delivery boy status, vehicle details, contact number, and ETA directly into WhatsApp.
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-zinc-50 border border-zinc-200 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono font-bold text-zinc-950 text-xs sm:text-sm">Payment Poller</span>
                  <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-mono text-[10px]">Daemon</span>
                </div>
                <p className="text-zinc-600 leading-relaxed">
                  Background daemon checks order status every 5s for 60s following UPI QR generation, sending instant confirmation upon payment completion.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* 3 Core Invariant Pillars */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto text-xs sm:text-sm">
          <div className="bg-white p-6 rounded-2xl border border-zinc-200 shadow-2xs">
            <div className="font-bold text-zinc-950 mb-2 flex items-center gap-2 text-sm sm:text-base">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              Delta Cart Merge
            </div>
            <p className="text-zinc-600 leading-relaxed">
              In-flight additions merge onto the active basket without resetting items or causing duplicate orders.
            </p>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-zinc-200 shadow-2xs">
            <div className="font-bold text-zinc-950 mb-2 flex items-center gap-2 text-sm sm:text-base">
              <MapPin className="w-4 h-4 text-emerald-600" />
              Upfront Address Guard
            </div>
            <p className="text-zinc-600 leading-relaxed">
              Detects multiple saved addresses and asks for explicit selection upfront so groceries go to the right dark store.
            </p>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-zinc-200 shadow-2xs">
            <div className="font-bold text-zinc-950 mb-2 flex items-center gap-2 text-sm sm:text-base">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              Server-Side Authorization
            </div>
            <p className="text-zinc-600 leading-relaxed">
              Checkout requires explicit customer confirmation in Python code before calling provider order APIs.
            </p>
          </div>
        </div>

        {/* Evaluator Documentation Link */}
        <div className="mt-10 text-center">
          <a
            href="https://github.com/kwakhare5/Grocer/blob/main/docs/REVIEWER_WALKTHROUGH.md"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 text-xs sm:text-sm font-semibold text-zinc-800 hover:text-emerald-700 transition underline underline-offset-4"
          >
            <span>Read the official Reviewer Walkthrough Guide on GitHub</span>
            <ArrowRight className="w-4 h-4" />
          </a>
        </div>
      </div>
    </section>
  );
}
