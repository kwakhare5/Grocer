import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { RecommendationItem } from "../../lib/types";
import { formatINR, formatHours, formatPercentage } from "../../lib/formatters";
import {
  HelpCircle,
  Zap,
  XCircle,
  CheckCircle2,
  ShieldAlert,
  Scale,
  Info,
  ArrowLeft,
  Layers,
  RotateCw,
  AlertTriangle,
} from "lucide-react";

interface WhyInspectorPanelProps {
  selectedRecommendation: RecommendationItem | null;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onViewTrace?: (id: string) => void;
}

export function WhyInspectorPanel({
  selectedRecommendation: item,
  onApprove,
  onReject,
  onViewTrace,
}: WhyInspectorPanelProps) {
  if (!item) {
    return (
      <div className="bg-white rounded-xl border border-zinc-200 p-6 shadow-2xs h-full flex flex-col items-center justify-center text-center">
        <div className="w-12 h-12 rounded-full bg-zinc-100 flex items-center justify-center text-zinc-400 mb-3">
          <HelpCircle className="w-6 h-6" />
        </div>
        <h3 className="text-sm font-bold text-zinc-900 mb-1">No Action Selected</h3>
        <p className="text-xs text-zinc-500 max-w-[240px] mb-4">
          Select any decision card in the stream to inspect root causes, evaluated alternatives, and financial tradeoffs.
        </p>
        <div className="flex items-center gap-1.5 text-[11px] font-mono text-zinc-400 bg-zinc-50 border border-zinc-200/80 px-3 py-1.5 rounded-full">
          <ArrowLeft className="w-3 h-3" />
          <span>Select any recommendation card</span>
        </div>
      </div>
    );
  }

  const isCompleted = item.status === "completed";
  const isRejected = item.status === "rejected";

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={item.id}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
        className="bg-white rounded-xl border border-zinc-200 p-4 shadow-2xs flex flex-col gap-4 h-full overflow-y-auto"
      >
      {/* 1. Header */}
      <div className="border-b border-zinc-100 pb-3">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-zinc-500">
            Decision Explainability & Root Cause
          </span>
          <span className="text-[10.5px] font-mono px-2 py-0.5 bg-zinc-100 text-zinc-700 font-semibold rounded">
            Score: {item.alternatives[0]?.score || 90}/100
          </span>
        </div>
        <h3 className="text-sm font-bold text-zinc-950 font-sans">{item.title}</h3>
        <div className="text-xs text-zinc-500 font-mono mt-0.5">
          Target: {item.destinationStore.code} · {item.destinationStore.name}
        </div>
      </div>

      {/* 2. Quantitative Root Cause Telemetry */}
      <div className="p-3 bg-zinc-50 rounded-xl border border-zinc-100 space-y-2">
        <div className="text-[11px] font-bold text-zinc-900 uppercase tracking-wider font-mono flex items-center gap-1">
          <ShieldAlert className="w-3.5 h-3.5 text-zinc-600" />
          <span>Underlying Telemetry Facts</span>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs font-mono">
          <div className="p-2 bg-white rounded-lg border border-zinc-200/70">
            <span className="text-[10px] text-zinc-500 block">Stockout Risk</span>
            <span className="text-sm font-bold text-rose-600 font-mono">
              {formatPercentage(item.probability)}
            </span>
          </div>
          <div className="p-2 bg-white rounded-lg border border-zinc-200/70">
            <span className="text-[10px] text-zinc-500 block">Predicted Runout</span>
            <span className="text-sm font-bold text-zinc-900 font-mono">
              {formatHours(item.stockoutInHours)}
            </span>
          </div>
          <div className="p-2 bg-white rounded-lg border border-zinc-200/70">
            <span className="text-[10px] text-zinc-500 block">Supplier ETA</span>
            <span className="text-sm font-bold text-zinc-900 font-mono">
              {formatHours(item.supplierEtaHours)}
            </span>
          </div>
          <div className="p-2 bg-white rounded-lg border border-zinc-200/70">
            <span className="text-[10px] text-zinc-500 block">Model Confidence</span>
            <span className="text-sm font-bold text-emerald-600 font-mono">
              {formatPercentage(item.confidence)}
            </span>
          </div>
        </div>
      </div>

      {/* 3. Structured Reason Codes */}
      <div className="space-y-2">
        <div className="text-[11px] font-bold text-zinc-900 uppercase tracking-wider font-mono flex items-center gap-1">
          <Info className="w-3.5 h-3.5 text-zinc-600" />
          <span>Structured Reason Codes</span>
        </div>
        <ul className="space-y-1.5 text-xs text-zinc-700">
          {item.reasonCodes.map((code, i) => (
            <li key={i} className="flex items-start gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 shrink-0 mt-1.5" />
              <span className="leading-snug">{code.replace(/_/g, " ")}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* 4. Ranked Alternatives Evaluation */}
      <div className="space-y-2">
        <div className="text-[11px] font-bold text-zinc-900 uppercase tracking-wider font-mono flex items-center gap-1">
          <Scale className="w-3.5 h-3.5 text-zinc-600" />
          <span>Evaluated Alternative Policies</span>
        </div>

        <div className="space-y-2 text-xs">
          {item.alternatives.map((alt, i) => (
            <div
              key={i}
              className={`p-2.5 rounded-xl border ${
                alt.isRecommended
                  ? "bg-sky-50/70 border-sky-200 text-sky-950"
                  : "bg-zinc-50/70 border-zinc-100 text-zinc-600"
              }`}
            >
              <div className="flex items-center justify-between font-semibold mb-1">
                <span className="flex items-center gap-1.5">
                  {alt.isRecommended && (
                    <span className="text-[9.5px] font-mono font-bold bg-sky-600 text-white px-1.5 py-0.2 rounded">
                      RECOMMENDED
                    </span>
                  )}
                  <span>{alt.label}</span>
                </span>
                <span className="font-mono text-[11px] font-bold">Score {alt.score}</span>
              </div>
              <p className="text-[11px] text-zinc-600 leading-snug">{alt.reason}</p>
            </div>
          ))}
        </div>
      </div>

      {/* 5. Financial Tradeoff Analysis (Light Surface with Semantic Highlights) */}
      <div className="p-3.5 bg-emerald-50/40 border border-emerald-200/80 rounded-xl space-y-2.5">
        <div className="flex items-center justify-between text-xs font-mono">
          <span className="font-bold text-zinc-700">Financial Tradeoff Impact</span>
          <span className="text-emerald-800 font-bold bg-emerald-100 px-2 py-0.5 rounded text-[11px]">
            +{formatINR(item.tradeoffAnalysis.netBenefitINR)} Net Gain
          </span>
        </div>

        <div className="space-y-1.5 text-xs font-mono">
          <div className="flex justify-between text-zinc-600">
            <span>Stockout Loss Avoided</span>
            <span className="text-emerald-700 font-bold">+{formatINR(item.tradeoffAnalysis.stockoutLossAvoidedINR)}</span>
          </div>
          {item.tradeoffAnalysis.spoilageAvoidanceINR > 0 && (
            <div className="flex justify-between text-zinc-600">
              <span>Spoilage Write-Off Avoided</span>
              <span className="text-amber-700 font-bold">+{formatINR(item.tradeoffAnalysis.spoilageAvoidanceINR)}</span>
            </div>
          )}
          {item.tradeoffAnalysis.transportCostINR > 0 && (
            <div className="flex justify-between text-zinc-500">
              <span>Transfer Logistics Cost</span>
              <span className="text-rose-600 font-bold">-{formatINR(item.tradeoffAnalysis.transportCostINR)}</span>
            </div>
          )}
          <div className="border-t border-emerald-200 pt-2 flex justify-between font-bold text-sm text-zinc-900">
            <span>Net Financial Benefit</span>
            <span className="text-emerald-800">+{formatINR(item.tradeoffAnalysis.netBenefitINR)}</span>
          </div>
        </div>
      </div>

      {/* 6. Big Tactile Approval Controls */}
      <div className="pt-2 mt-auto border-t border-zinc-100 flex flex-col gap-2">
        {isCompleted ? (
          <div className="flex flex-col gap-2">
            <div className="w-full py-2.5 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-xl font-bold text-center text-xs flex items-center justify-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>Action Successfully Executed</span>
            </div>
            {onViewTrace && (
              <button
                type="button"
                onClick={() => onViewTrace(item.id)}
                className="w-full py-2 bg-zinc-900 hover:bg-zinc-800 text-white rounded-lg font-mono font-semibold text-xs flex items-center justify-center gap-2 shadow-2xs transition-all duration-150 active:scale-97 cursor-pointer"
              >
                <Layers className="w-4 h-4 text-emerald-400" />
                <span>Inspect LangGraph 5-Node Trace</span>
              </button>
            )}
          </div>
        ) : item.status === "executing" ? (
          <div className="w-full py-3 bg-sky-50 text-sky-800 border border-sky-200 rounded-xl font-bold text-center text-xs flex items-center justify-center gap-2">
            <RotateCw className="w-4 h-4 text-sky-600 animate-spin" />
            <span>LangGraph Execution in Progress...</span>
          </div>
        ) : item.status === "failed" ? (
          <div className="flex flex-col gap-2">
            <div className="w-full py-2.5 bg-rose-50 text-rose-800 border border-rose-200 rounded-xl font-bold text-center text-xs flex items-center justify-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-600" />
              <span>Execution Invariant Failed (Recovered)</span>
            </div>
            {onViewTrace && (
              <button
                type="button"
                onClick={() => onViewTrace(item.id)}
                className="w-full py-2 bg-rose-900 hover:bg-rose-800 text-white rounded-lg font-mono font-semibold text-xs flex items-center justify-center gap-2 shadow-2xs transition-all duration-150 active:scale-97 cursor-pointer"
              >
                <Layers className="w-4 h-4" />
                <span>Inspect Recovery Trace & Alternative</span>
              </button>
            )}
          </div>
        ) : isRejected ? (
          <div className="w-full py-3 bg-zinc-100 text-zinc-600 border border-zinc-200 rounded-xl font-bold text-center text-xs flex items-center justify-center gap-2">
            <XCircle className="w-4 h-4 text-zinc-500" />
            <span>Recommendation Dismissed</span>
          </div>
        ) : (
          <>
            <button
              onClick={() => onApprove(item.id)}
              className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-bold text-xs flex items-center justify-center gap-2 shadow-2xs transition-all duration-150 active:scale-97 cursor-pointer"
            >
              <Zap className="w-4 h-4 text-blue-200" />
              <span>Approve Recommended Action</span>
            </button>

            <button
              onClick={() => onReject(item.id)}
              className="w-full py-2 bg-white hover:bg-rose-50 hover:text-rose-700 hover:border-rose-200 border border-zinc-200 text-zinc-700 rounded-lg font-semibold text-xs transition-all duration-150 active:scale-97 cursor-pointer flex items-center justify-center gap-1.5"
            >
              <XCircle className="w-3.5 h-3.5" />
              <span>Dismiss Recommendation</span>
            </button>
          </>
        )}
      </div>
      </motion.div>
    </AnimatePresence>
  );
}
