import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { RecommendationItem } from "../../lib/types";
import {
  ArrowRight,
  Clock,
  Truck,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronUp,
  Zap,
  AlertTriangle,
  Flame,
  RotateCw,
  ShieldAlert,
  Layers,
} from "lucide-react";
import { formatHours, formatINR, formatPercentage } from "../../lib/formatters";

interface RecommendationCardProps {
  item: RecommendationItem;
  isSelected: boolean;
  onSelect: () => void;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onViewTrace?: (id: string) => void;
  index?: number;
}

export function RecommendationCard({
  item,
  isSelected,
  onSelect,
  onApprove,
  onReject,
  onViewTrace,
  index = 0,
}: RecommendationCardProps) {
  const [isWhyExpanded, setIsWhyExpanded] = useState(false);

  const isCritical = item.severity === "critical";
  const isWarning = item.severity === "warning";
  const isCompleted = item.status === "completed";
  const isExecuting = item.status === "executing";
  const isRejected = item.status === "rejected";
  const isFailed = item.status === "failed";

  // Action badge color styles with semantic color mapping
  const actionBadgeStyles: Record<string, string> = {
    transfer: "bg-sky-50 text-sky-800 border-sky-200",
    reorder: "bg-orange-50 text-orange-800 border-orange-200",
    discount: "bg-purple-50 text-purple-800 border-purple-200",
    hold: "bg-zinc-100 text-zinc-800 border-zinc-200",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, delay: index * 0.04, ease: [0.16, 1, 0.3, 1] }}
      whileHover={{ y: -1 }}
      onClick={onSelect}
      className={`rounded-xl p-4 border transition-all duration-180 cursor-pointer ${
        isSelected
          ? "border-blue-600 bg-blue-50/15 shadow-xs ring-1 ring-blue-500"
          : "border-zinc-200 bg-white hover:border-zinc-300 shadow-2xs"
      } ${isCompleted ? "opacity-75 bg-zinc-50/70" : ""} ${isFailed ? "border-rose-300 bg-rose-50/40" : ""}`}
    >
      {/* 1. Header: Severity Alert + Action Badge + Net Benefit */}
      <div className="flex items-center justify-between gap-2 mb-2.5">
        <div className="flex items-center gap-1.5">
          {isCritical ? (
            <span className="flex items-center gap-1 text-[10.5px] font-mono font-bold uppercase tracking-wider text-rose-700 bg-rose-50 px-2 py-0.5 rounded-full border border-rose-200">
              <Flame className="w-3 h-3 text-rose-600 animate-pulse" />
              Stockout Risk
            </span>
          ) : isWarning ? (
            <span className="flex items-center gap-1 text-[10.5px] font-mono font-bold uppercase tracking-wider text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200">
              <AlertTriangle className="w-3 h-3 text-amber-600" />
              Spoilage Risk
            </span>
          ) : (
            <span className="text-[10.5px] font-mono font-bold uppercase tracking-wider text-zinc-600 bg-zinc-100 px-2 py-0.5 rounded-full">
              Optimisation
            </span>
          )}

          <span
            className={`text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md border font-sans ${
              actionBadgeStyles[item.actionType] || "bg-zinc-100 text-zinc-700 border-zinc-200"
            }`}
          >
            {item.actionType}
          </span>
        </div>

        {/* Net Financial Impact Pill */}
        {item.tradeoffAnalysis?.netBenefitINR > 0 && (
          <span className="text-[11px] font-mono font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-md">
            +{formatINR(item.tradeoffAnalysis.netBenefitINR)} Net
          </span>
        )}
      </div>

      {/* 2. Destination & Product Headline */}
      <div className="mb-2.5">
        <div className="text-xs font-semibold text-zinc-500 font-mono">
          {item.destinationStore.code} · {item.destinationStore.name}
        </div>
        <h3 className="text-sm font-bold text-zinc-950 tracking-tight">{item.title}</h3>
      </div>

      {/* 3. Recommended Intervention Details */}
      <div className="p-3 rounded-xl bg-zinc-50 border border-zinc-100 text-xs mb-3 space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="font-bold text-zinc-950">
            {item.actionType === "transfer" && `Transfer ${item.quantity} ${item.unit}`}
            {item.actionType === "discount" && `Apply ${item.discountPct}% Discount (${item.quantity} ${item.unit})`}
            {item.actionType === "reorder" && `Reorder ${item.quantity} ${item.unit}`}
            {item.actionType === "hold" && `Hold & Absorb Stock Variance`}
          </span>
          {item.distanceKm && (
            <span className="text-[11px] font-mono font-semibold text-zinc-600 bg-white px-2 py-0.5 rounded border border-zinc-200">
              {item.distanceKm} km · 14 min ETA
            </span>
          )}
        </div>

        {item.sourceStore && (
          <div className="flex items-center gap-1.5 text-zinc-700 text-xs pt-0.5">
            <span className="font-semibold text-zinc-900">{item.sourceStore.name} ({item.sourceStore.code})</span>
            <ArrowRight className="w-3.5 h-3.5 text-zinc-400" />
            <span className="font-semibold text-zinc-900">{item.destinationStore.name}</span>
          </div>
        )}
      </div>

      {/* 4. Telemetry Key Facts Grid */}
      <div className="grid grid-cols-2 gap-2 text-[11px] font-mono text-zinc-600 mb-3 pt-1 border-t border-zinc-100">
        <div className="flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5 text-zinc-400" />
          <span>Stockout: <strong className="text-zinc-900">{formatHours(item.stockoutInHours)}</strong></span>
        </div>
        <div className="flex items-center gap-1.5">
          <Truck className="w-3.5 h-3.5 text-zinc-400" />
          <span>Supplier ETA: <strong className="text-zinc-900">{formatHours(item.supplierEtaHours)}</strong></span>
        </div>
      </div>

      {/* 5. Inline Expandable "WHY REASON ENGINE" Accordion */}
      <div className="mb-3.5">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setIsWhyExpanded(!isWhyExpanded);
          }}
          className="w-full flex items-center justify-between text-[11.5px] font-semibold text-zinc-600 hover:text-zinc-950 py-1 px-2 rounded-lg bg-zinc-50 hover:bg-zinc-100 border border-zinc-200/80 transition-colors"
        >
          <span className="flex items-center gap-1.5">
            <ShieldAlert className="w-3.5 h-3.5 text-emerald-600" />
            <span>Explainable Reasoning & Tradeoffs</span>
          </span>
          {isWhyExpanded ? (
            <ChevronUp className="w-3.5 h-3.5 text-zinc-500" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-zinc-500" />
          )}
        </button>

        <AnimatePresence>
          {isWhyExpanded && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-2 p-3 bg-zinc-50/90 rounded-xl border border-zinc-200 space-y-2.5 text-xs"
            >
              {/* Reason Codes */}
              <div>
                <span className="text-[10px] font-mono font-bold uppercase text-zinc-400 block mb-1">
                  Root Causes
                </span>
                <ul className="space-y-1">
                  {item.reasonCodes.map((code, i) => (
                    <li key={i} className="flex items-start gap-1.5 text-zinc-700 text-[11.5px]">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 shrink-0 mt-1.5" />
                      <span>{code.replace(/_/g, " ")}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Evaluated Policies */}
              <div>
                <span className="text-[10px] font-mono font-bold uppercase text-zinc-400 block mb-1">
                  Alternative Policies Evaluated
                </span>
                <div className="space-y-1.5">
                  {item.alternatives.map((alt, i) => (
                    <div
                      key={i}
                      className={`p-2 rounded-lg border text-[11px] ${
                        alt.isRecommended
                          ? "bg-white border-emerald-300 text-emerald-950 shadow-2xs"
                          : "bg-zinc-100/60 border-zinc-200 text-zinc-600"
                      }`}
                    >
                      <div className="flex items-center justify-between font-semibold">
                        <span>{alt.label}</span>
                        <span className="font-mono">Score {alt.score}</span>
                      </div>
                      <p className="text-[10.5px] text-zinc-500 mt-0.5">{alt.reason}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Financial Breakdown */}
              <div className="p-2.5 bg-emerald-50/50 border border-emerald-200 rounded-lg font-mono text-[11px] space-y-1 text-zinc-900">
                <div className="flex justify-between text-zinc-600">
                  <span>Stockout Loss Avoided:</span>
                  <span className="text-emerald-700 font-bold">+{formatINR(item.tradeoffAnalysis.stockoutLossAvoidedINR)}</span>
                </div>
                {item.tradeoffAnalysis.transportCostINR > 0 && (
                  <div className="flex justify-between text-zinc-600">
                    <span>Logistics Courier Cost:</span>
                    <span className="text-rose-700 font-bold">-{formatINR(item.tradeoffAnalysis.transportCostINR)}</span>
                  </div>
                )}
                <div className="border-t border-emerald-200 pt-1 flex justify-between font-bold text-xs">
                  <span className="text-zinc-900">Net Benefit:</span>
                  <span className="text-emerald-800 font-extrabold">+{formatINR(item.tradeoffAnalysis.netBenefitINR)}</span>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* 6. Action Execution Controls */}
      <div className="flex items-center justify-between gap-2 pt-2 border-t border-zinc-100">
        <span className="text-[11px] font-mono text-zinc-400">
          Confidence: <strong className="text-zinc-700">{formatPercentage(item.confidence)}</strong>
        </span>

        <div className="flex items-center gap-1.5">
          {isCompleted ? (
            <div className="flex items-center gap-1.5">
              <span className="flex items-center gap-1 text-xs font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-1.5 rounded-lg">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                Verified
              </span>
              {onViewTrace && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onViewTrace(item.id);
                  }}
                  className="flex items-center gap-1 text-xs font-mono font-semibold text-zinc-700 bg-zinc-100 hover:bg-zinc-200 border border-zinc-200 px-2.5 py-1.5 rounded-lg transition-colors cursor-pointer"
                >
                  <Layers className="w-3.5 h-3.5 text-zinc-500" />
                  <span>Trace</span>
                </button>
              )}
            </div>
          ) : isExecuting ? (
            <span className="flex items-center gap-1.5 text-xs font-bold text-sky-700 bg-sky-50 border border-sky-200 px-3 py-1.5 rounded-lg">
              <RotateCw className="w-3.5 h-3.5 animate-spin" />
              <span>LangGraph Executing...</span>
            </span>
          ) : isFailed ? (
            <div className="flex items-center gap-1.5">
              <span className="flex items-center gap-1 text-xs font-bold text-rose-700 bg-rose-50 border border-rose-200 px-2.5 py-1.5 rounded-lg">
                <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
                Recovered
              </span>
              {onViewTrace && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onViewTrace(item.id);
                  }}
                  className="flex items-center gap-1 text-xs font-mono font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 px-2.5 py-1.5 rounded-lg transition-colors cursor-pointer"
                >
                  <Layers className="w-3.5 h-3.5" />
                  <span>Trace</span>
                </button>
              )}
            </div>
          ) : isRejected ? (
            <span className="flex items-center gap-1 text-xs font-bold text-zinc-500 bg-zinc-100 border border-zinc-200 px-3 py-1.5 rounded-lg">
              <XCircle className="w-3.5 h-3.5" />
              Dismissed
            </span>
          ) : (
            <>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onReject(item.id);
                }}
                className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-white hover:bg-rose-50 text-zinc-600 hover:text-rose-700 border border-zinc-200 transition-all duration-150 active:scale-97 cursor-pointer shrink-0"
              >
                Dismiss
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onApprove(item.id);
                }}
                className="flex items-center gap-1.5 text-xs font-bold px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white shadow-2xs transition-all duration-150 active:scale-97 cursor-pointer shrink-0"
              >
                <Zap className="w-3.5 h-3.5 text-blue-200" />
                <span>Approve</span>
              </button>
            </>
          )}
        </div>
      </div>
    </motion.div>
  );
}

