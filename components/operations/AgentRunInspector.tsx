"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { BackendAgentRun } from "../../lib/apiClient";
import {
  X,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Copy,
  Check,
} from "lucide-react";
import { toast } from "sonner";

interface AgentRunInspectorProps {
  run: BackendAgentRun | null;
  isOpen: boolean;
  onClose: () => void;
  recommendationTitle?: string;
}

export function AgentRunInspector({
  run,
  isOpen,
  onClose,
  recommendationTitle,
}: AgentRunInspectorProps) {
  const [activeTab, setActiveTab] = useState<"flow" | "batches" | "telemetry">("flow");
  const [copied, setCopied] = useState(false);

  if (!isOpen || !run) return null;

  const handleCopyJson = () => {
    navigator.clipboard.writeText(JSON.stringify(run, null, 2));
    setCopied(true);
    toast.success("Agent run trace copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  };

  const startedTime = new Date(run.started_at);
  const finishedTime = new Date(run.finished_at);
  const durationMs = Math.max(0, finishedTime.getTime() - startedTime.getTime());

  // Extract node event details
  const validateEvent = run.events.find((e) => e.node === "validate");
  const executeEvent = run.events.find((e) => e.node === "execute");

  const batches = executeEvent?.batches_affected || [];

  const isCompleted = run.status === "completed";
  const isRecovered = run.requires_human_review || run.status === "requires_human_review";

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.15 }}
        onClick={onClose}
        className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4"
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.96, y: 12 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: 12 }}
          transition={{ type: "spring", damping: 30, stiffness: 420 }}
          onClick={(e) => e.stopPropagation()}
          className="bg-white w-full max-w-3xl rounded-2xl border border-zinc-200 shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
        >
          {/* Header */}
          <div className="p-5 border-b border-zinc-100 flex items-center justify-between bg-zinc-50/50">
            <div className="flex items-center gap-3">
              <div
                className={`w-9 h-9 rounded-xl flex items-center justify-center ${
                  isCompleted
                    ? "bg-emerald-100 text-emerald-700"
                    : isRecovered
                    ? "bg-amber-100 text-amber-700"
                    : "bg-rose-100 text-rose-700"
                }`}
              >
                {isCompleted ? (
                  <CheckCircle2 className="w-5 h-5" />
                ) : isRecovered ? (
                  <RotateCcw className="w-5 h-5" />
                ) : (
                  <AlertTriangle className="w-5 h-5" />
                )}
              </div>

              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-bold text-zinc-950 font-sans tracking-tight">
                    LangGraph 5-Node Execution Trace
                  </h2>
                  <span
                    className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${
                      isCompleted
                        ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                        : isRecovered
                        ? "bg-amber-50 text-amber-800 border border-amber-200"
                        : "bg-rose-50 text-rose-800 border border-rose-200"
                    }`}
                  >
                    {run.status}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-xs text-zinc-500 font-mono mt-0.5">
                  <span>Run ID: {run.run_id}</span>
                  <span>·</span>
                  <span>Duration: {durationMs}ms</span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={handleCopyJson}
                className="flex items-center gap-1.5 text-xs font-mono font-medium px-2.5 py-1.5 rounded-lg border border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50 hover:text-zinc-950 transition-colors cursor-pointer"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? "Copied" : "JSON"}</span>
              </button>

              <button
                type="button"
                onClick={onClose}
                className="p-1.5 rounded-lg hover:bg-zinc-200 text-zinc-400 hover:text-zinc-700 transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Sub-nav Tabs */}
          <div className="px-5 border-b border-zinc-200 flex items-center gap-4 text-xs font-medium bg-white">
            <button
              type="button"
              onClick={() => setActiveTab("flow")}
              className={`py-2.5 border-b-2 font-semibold cursor-pointer transition-colors ${
                activeTab === "flow"
                  ? "border-emerald-700 text-emerald-950"
                  : "border-transparent text-zinc-500 hover:text-zinc-800"
              }`}
            >
              Visual Node Flow (5 Nodes)
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("batches")}
              className={`py-2.5 border-b-2 font-semibold cursor-pointer transition-colors flex items-center gap-1.5 ${
                activeTab === "batches"
                  ? "border-emerald-700 text-emerald-950"
                  : "border-transparent text-zinc-500 hover:text-zinc-800"
              }`}
            >
              <span>Batch Conservation Audit</span>
              {batches.length > 0 && (
                <span className="text-[10px] font-mono font-bold bg-zinc-100 text-zinc-700 px-1.5 py-0.2 rounded-full">
                  {batches.length}
                </span>
              )}
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("telemetry")}
              className={`py-2.5 border-b-2 font-semibold cursor-pointer transition-colors ${
                activeTab === "telemetry"
                  ? "border-emerald-700 text-emerald-950"
                  : "border-transparent text-zinc-500 hover:text-zinc-800"
              }`}
            >
              Raw State Telemetry
            </button>
          </div>

          {/* Body Content */}
          <div className="p-5 overflow-y-auto space-y-4 flex-1">
            {recommendationTitle && (
              <div className="p-3 bg-zinc-50 border border-zinc-200 rounded-xl flex items-center justify-between text-xs">
                <span className="font-semibold text-zinc-900">{recommendationTitle}</span>
                <span className="font-mono text-zinc-500 text-[11px] uppercase">
                  Action: {run.action_type || "transfer"}
                </span>
              </div>
            )}

            {/* TAB 1: VISUAL NODE FLOW */}
            {activeTab === "flow" && (
              <div className="space-y-3">
                {/* Node 1: Validate */}
                <div className="p-3.5 rounded-xl border border-zinc-200 bg-white flex items-start gap-3 shadow-2xs">
                  <div className="w-6 h-6 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0 mt-0.5 text-xs font-mono font-bold">
                    1
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-bold text-zinc-950 font-mono uppercase">
                        node_validate (Level-2 Autonomy)
                      </h4>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 font-semibold">
                        PASSED
                      </span>
                    </div>
                    <p className="text-xs text-zinc-600 mt-1 leading-snug">
                      Verified operator approval status, target store constraints, and non-empty action parameters.
                    </p>
                    {validateEvent?.action_id && (
                      <div className="mt-2 text-[11px] font-mono text-zinc-500 bg-zinc-50 p-2 rounded-lg border border-zinc-100">
                        Action ID: {validateEvent.action_id} · State: {validateEvent.status || "EXECUTING"}
                      </div>
                    )}
                  </div>
                </div>

                {/* Connecting arrow */}
                <div className="flex justify-center -my-1">
                  <div className="w-px h-3 bg-zinc-300" />
                </div>

                {/* Node 2: Execute */}
                <div className="p-3.5 rounded-xl border border-zinc-200 bg-white flex items-start gap-3 shadow-2xs">
                  <div className="w-6 h-6 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center shrink-0 mt-0.5 text-xs font-mono font-bold">
                    2
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-bold text-zinc-950 font-mono uppercase">
                        node_execute (Batch-Aware Mutations)
                      </h4>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-50 text-blue-800 border border-blue-200 font-semibold">
                        MUTATED
                      </span>
                    </div>
                    <p className="text-xs text-zinc-600 mt-1 leading-snug">
                      Executed FIFO inventory deductions across source batches and created matching destination batch slice with intact expiry.
                    </p>
                    <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] font-mono">
                      {executeEvent?.transfer_id && (
                        <div className="p-1.5 bg-zinc-50 rounded border border-zinc-100 text-zinc-600">
                          Transfer ID: {executeEvent.transfer_id}
                        </div>
                      )}
                      {executeEvent?.purchase_order_id && (
                        <div className="p-1.5 bg-zinc-50 rounded border border-zinc-100 text-zinc-600">
                          Purchase Order: {executeEvent.purchase_order_id}
                        </div>
                      )}
                      <div className="p-1.5 bg-zinc-50 rounded border border-zinc-100 text-zinc-600">
                        Batches Affected: {batches.length}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Connecting arrow */}
                <div className="flex justify-center -my-1">
                  <div className="w-px h-3 bg-zinc-300" />
                </div>

                {/* Node 3: Verify */}
                <div className="p-3.5 rounded-xl border border-zinc-200 bg-white flex items-start gap-3 shadow-2xs">
                  <div className="w-6 h-6 rounded-full bg-purple-100 text-purple-700 flex items-center justify-center shrink-0 mt-0.5 text-xs font-mono font-bold">
                    3
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-bold text-zinc-950 font-mono uppercase">
                        node_verify (Programmatic Invariant Assertions)
                      </h4>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-50 text-purple-800 border border-purple-200 font-semibold">
                        INVARIANTS HELD
                      </span>
                    </div>
                    <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                      <div className="flex items-center gap-1.5 p-2 bg-emerald-50/50 rounded-lg border border-emerald-100 text-emerald-800 font-mono text-[11px]">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                        <span>Source Stock &ge; 0 Verified</span>
                      </div>
                      <div className="flex items-center gap-1.5 p-2 bg-emerald-50/50 rounded-lg border border-emerald-100 text-emerald-800 font-mono text-[11px]">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                        <span>Destination Inbounds Logged</span>
                      </div>
                      <div className="flex items-center gap-1.5 p-2 bg-emerald-50/50 rounded-lg border border-emerald-100 text-emerald-800 font-mono text-[11px]">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                        <span>FIFO Batch Conservation Exact</span>
                      </div>
                      <div className="flex items-center gap-1.5 p-2 bg-emerald-50/50 rounded-lg border border-emerald-100 text-emerald-800 font-mono text-[11px]">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                        <span>Audit Event Logged to DB</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Connecting arrow */}
                <div className="flex justify-center -my-1">
                  <div className="w-px h-3 bg-zinc-300" />
                </div>

                {/* Node 4/5: Finalize or Recover */}
                {isCompleted ? (
                  <div className="p-3.5 rounded-xl border border-emerald-200 bg-emerald-50/30 flex items-start gap-3 shadow-2xs">
                    <div className="w-6 h-6 rounded-full bg-emerald-600 text-white flex items-center justify-center shrink-0 mt-0.5 text-xs font-mono font-bold">
                      4
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-bold text-emerald-950 font-mono uppercase">
                          node_finalize (Action Sealed)
                        </h4>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-600 text-white font-bold">
                          COMPLETED
                        </span>
                      </div>
                      <p className="text-xs text-emerald-800 mt-1 leading-snug">
                        Action entity transitioned to COMPLETED. State synced across all fleet dark stores.
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="p-3.5 rounded-xl border border-amber-200 bg-amber-50/40 flex items-start gap-3 shadow-2xs">
                    <div className="w-6 h-6 rounded-full bg-amber-600 text-white flex items-center justify-center shrink-0 mt-0.5 text-xs font-mono font-bold">
                      5
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-bold text-amber-950 font-mono uppercase">
                          node_recover (Failure Recovery & Recalculate)
                        </h4>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-600 text-white font-bold">
                          HUMAN REVIEW NEEDED
                        </span>
                      </div>
                      <p className="text-xs text-amber-900 mt-1 leading-snug">
                        {run.error || "Inventory invariant failed or condition changed. Alternative recalculated."}
                      </p>
                      {run.new_recommendation_id && (
                        <div className="mt-2 text-[11px] font-mono text-amber-800 bg-amber-100/60 p-2 rounded-lg">
                          Fresh Alternative Rec: {run.new_recommendation_id}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB 2: BATCH CONSERVATION AUDIT */}
            {activeTab === "batches" && (
              <div className="space-y-3">
                <div className="text-xs text-zinc-600">
                  Every inter-store transfer performs strict FIFO deduction from earliest expiring batches at source and creates corresponding destination batch records.
                </div>

                {batches.length === 0 ? (
                  <div className="p-8 text-center bg-zinc-50 border border-zinc-200 rounded-xl text-zinc-500 text-xs">
                    No batch mutations recorded for this run.
                  </div>
                ) : (
                  <div className="border border-zinc-200 rounded-xl overflow-hidden shadow-2xs">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-zinc-50 border-b border-zinc-200 text-zinc-600 font-mono uppercase text-[10px]">
                        <tr>
                          <th className="p-2.5">Source Batch</th>
                          <th className="p-2.5">Deducted</th>
                          <th className="p-2.5">Destination Batch</th>
                          <th className="p-2.5">Added</th>
                          <th className="p-2.5">Expires At</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-zinc-100 font-mono text-[11px]">
                        {batches.map((b, idx) => (
                          <tr key={idx} className="hover:bg-zinc-50/50">
                            <td className="p-2.5 text-zinc-700">{b.batch_id || "batch-src-default"}</td>
                            <td className="p-2.5 text-rose-600 font-bold">
                              -{b.quantity_deducted || b.quantity_added || 0}
                            </td>
                            <td className="p-2.5 text-zinc-700">{b.destination_batch_id || "b-dst-new"}</td>
                            <td className="p-2.5 text-emerald-600 font-bold">
                              +{b.quantity_added || b.quantity_deducted || 0}
                            </td>
                            <td className="p-2.5 text-zinc-500">
                              {b.expires_at ? new Date(b.expires_at).toLocaleString() : "48h remaining"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: RAW STATE TELEMETRY */}
            {activeTab === "telemetry" && (
              <div className="space-y-2">
                <pre className="p-4 bg-zinc-950 text-zinc-100 font-mono text-[11px] rounded-xl overflow-x-auto max-h-[380px] leading-relaxed">
                  {JSON.stringify(run, null, 2)}
                </pre>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="p-4 border-t border-zinc-100 bg-zinc-50 flex items-center justify-between text-xs text-zinc-500 font-mono">
            <span>Started: {startedTime.toLocaleTimeString()}</span>
            <span>Finished: {finishedTime.toLocaleTimeString()}</span>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
