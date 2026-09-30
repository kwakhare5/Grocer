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
    <section id="architecture" className="py-16 sm:py-20 bg-white border-b border-zinc-200 scroll-mt-16">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-2xl mx-auto mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-zinc-100 text-zinc-800 text-xs font-semibold mb-3 border border-zinc-200">
            <Layers className="w-3.5 h-3.5" />
            <span>Technical Architecture</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-editorial font-bold text-zinc-950">
            Decoupled CommercePort &amp; Swiggy MCP pipeline
          </h2>
          <p className="mt-3 text-base sm:text-lg text-zinc-600 leading-relaxed font-normal">
            A provider-agnostic replenishment engine pairing autonomous reasoning with deterministic safety guards.
          </p>
        </div>

        {/* ─── Interactive Visual Pipeline Flow Diagram ──────────────── */}
        <div className="bg-zinc-50/70 rounded-3xl p-6 sm:p-8 border border-zinc-200 shadow-2xs max-w-5xl mx-auto mb-10">
          <div className="flex items-center justify-between pb-4 border-b border-zinc-200/80 mb-6">
            <div className="flex items-center gap-2 text-xs font-semibold text-zinc-800">
              <Zap className="w-4 h-4 text-emerald-600" />
              <span>Interactive Pipeline • Click any stage to inspect technical specs</span>
            </div>
            <span className="text-xs font-mono text-zinc-500 font-medium">
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
                      ? "bg-white text-zinc-950 border-emerald-600 shadow-md ring-2 ring-emerald-500/20"
                      : "bg-white hover:bg-zinc-50 text-zinc-800 border-zinc-200 shadow-2xs"
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between text-xs mb-2">
                      <span className={`font-mono font-bold ${isSelected ? "text-emerald-700" : "text-zinc-400"}`}>
                        {node.stepNumber}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                          isSelected
                            ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                            : "bg-zinc-100 text-zinc-700 border border-zinc-200"
                        }`}
                      >
                        {node.badge}
                      </span>
                    </div>

                    <h4 className="font-bold text-xs sm:text-sm leading-tight mb-1 text-zinc-950">
                      {node.title}
                    </h4>
                    <p className="text-xs text-zinc-500">
                      {node.subtitle}
                    </p>
                  </div>

                  <div className="mt-4 pt-2 border-t border-zinc-100 flex items-center justify-between text-xs">
                    <span className="font-mono font-semibold text-emerald-700">
                      {node.metric}
                    </span>
                    {index < PIPELINE_NODES.length - 1 && (
                      <ArrowRight className="w-3.5 h-3.5 hidden lg:block text-zinc-400" />
                    )}
                  </div>
                </button>
              );
            })}
          </div>

          {/* ─── Unified Light Technical Inspector (Zero Black Boxes) ─── */}
          <div className="mt-6 p-5 sm:p-6 rounded-2xl bg-white text-zinc-950 border border-zinc-200 shadow-2xs">
            <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-zinc-100 mb-4">
              <div className="flex items-center gap-2">
                <Code className="w-4 h-4 text-emerald-700" />
                <span className="text-xs sm:text-sm font-bold font-mono text-zinc-950">
                  Stage {activeNode.stepNumber}: {activeNode.title}
                </span>
                <span className="text-xs px-2.5 py-0.5 rounded bg-zinc-100 text-zinc-700 font-mono border border-zinc-200">
                  {activeNode.technicalDetails.protocol}
                </span>
              </div>
              <span className="text-xs text-zinc-500 font-mono truncate max-w-xs">
                {activeNode.technicalDetails.endpointOrFile}
              </span>
            </div>

            <p className="text-xs sm:text-sm text-zinc-600 mb-4 leading-relaxed font-sans">
              {activeNode.description}
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Enforced Invariants */}
              <div>
                <div className="text-xs font-mono uppercase tracking-wider text-zinc-500 mb-2 font-semibold">
                  Enforced Invariants
                </div>
                <ul className="space-y-2 text-xs sm:text-sm text-zinc-700 font-sans">
                  {activeNode.technicalDetails.invariants.map((inv, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                      <span>{inv}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Sample Payload Inspection */}
              <div>
                <div className="text-xs font-mono uppercase tracking-wider text-zinc-500 mb-2 font-semibold">
                  Runtime Payload Schema
                </div>
                <pre className="p-3 rounded-xl bg-zinc-50 text-zinc-800 text-xs font-mono overflow-x-auto border border-zinc-200 max-h-36">
                  {JSON.stringify(activeNode.technicalDetails.samplePayload, null, 2)}
                </pre>
              </div>
            </div>
          </div>

          {/* Test & Verification Summary Stats */}
          <div className="mt-6 pt-6 border-t border-zinc-200/80 grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-zinc-950 font-mono">62 / 62</div>
              <div className="text-xs text-zinc-600 mt-1 font-medium">Automated Invariant Tests Passed</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-zinc-950 font-mono">6 / 6</div>
              <div className="text-xs text-zinc-600 mt-1 font-medium">Failure Modes Verified Live</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-zinc-950 font-mono">~1.0s</div>
              <div className="text-xs text-zinc-600 mt-1 font-medium">Gemini HTTP/2 Pooled Generation</div>
            </div>
          </div>
        </div>

        {/* ─── Swiggy Instamart Live MCP Tool Contract Grid ──────────── */}
        <div className="bg-zinc-50/70 rounded-3xl p-6 sm:p-8 border border-zinc-200 shadow-2xs max-w-5xl mx-auto mb-10">
          <div className="mb-6">
            <h3 className="text-lg sm:text-xl font-bold text-zinc-950">
              Swiggy Instamart Live MCP Tool Contract
            </h3>
            <p className="text-xs sm:text-sm text-zinc-600 mt-1 leading-relaxed font-normal">
              Implements official Model Context Protocol tools exposed at <code className="font-mono text-xs bg-white border border-zinc-200 px-1.5 py-0.5 rounded text-zinc-800">https://mcp.swiggy.com/im</code>.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-xs sm:text-sm font-sans">
            <div className="p-4 rounded-2xl bg-white border border-zinc-200">
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono font-bold text-zinc-950 text-sm">search_products</span>
                <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 font-mono text-xs">Read</span>
              </div>
              <p className="text-zinc-600 leading-relaxed text-xs">
                Queries dark store stock, prices, and pack sizes in parallel using <code className="font-mono text-zinc-800">asyncio.gather</code>.
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-white border border-zinc-200">
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono font-bold text-zinc-950 text-sm">update_cart</span>
                <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-800 border border-blue-200 font-mono text-xs">Delta</span>
              </div>
              <p className="text-zinc-600 leading-relaxed text-xs">
                Adds or updates items while keeping existing basket contents intact and respecting store minimums.
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-white border border-zinc-200">
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono font-bold text-zinc-950 text-sm">get_cart</span>
                <span className="px-2 py-0.5 rounded bg-zinc-100 text-zinc-800 border border-zinc-200 font-mono text-xs">Verify</span>
              </div>
              <p className="text-zinc-600 leading-relaxed text-xs">
                Reads verified provider subtotals, packaging, and delivery fees directly from dark-store billing.
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-white border border-zinc-200">
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono font-bold text-zinc-950 text-sm">checkout</span>
                <span className="px-2 py-0.5 rounded bg-purple-50 text-purple-800 border border-purple-200 font-mono text-xs">Gated</span>
              </div>
              <p className="text-zinc-600 leading-relaxed text-xs">
                Requires server-side confirmation before execution. Returns dynamic UPI QR payment link.
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-white border border-zinc-200">
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono font-bold text-zinc-950 text-sm">track_order</span>
                <span className="px-2 py-0.5 rounded bg-orange-50 text-orange-800 border border-orange-200 font-mono text-xs">Tracking</span>
              </div>
              <p className="text-zinc-600 leading-relaxed text-xs">
                Reports live delivery boy status, vehicle details, contact number, and ETA directly on WhatsApp.
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-white border border-zinc-200 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono font-bold text-zinc-950 text-sm">Payment Poller</span>
                  <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 font-mono text-xs">Daemon</span>
                </div>
                <p className="text-zinc-600 leading-relaxed text-xs">
                  Polls order status every 5s for 60s after UPI link generation, sending instant confirmation upon payment.
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
              Detects multiple saved addresses and asks for explicit selection upfront so groceries route to the right dark store.
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
            <span>Reviewer Walkthrough Guide on GitHub</span>
            <ArrowRight className="w-4 h-4" />
          </a>
        </div>
      </div>
    </section>
  );
}
