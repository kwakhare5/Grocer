import React, { useState } from "react";
import { RecommendationItem, SimulationEvent } from "../../lib/types";
import { RecommendationCard } from "./RecommendationCard";
import { LiveEventFeed } from "./LiveEventFeed";

interface RecommendationStreamProps {
  recommendations: RecommendationItem[];
  selectedRecId: string | null;
  onSelectRec: (id: string) => void;
  onApproveRec: (id: string) => void;
  onRejectRec: (id: string) => void;
  onViewTrace?: (id: string) => void;
  events: SimulationEvent[];
}

export function RecommendationStream({
  recommendations,
  selectedRecId,
  onSelectRec,
  onApproveRec,
  onRejectRec,
  onViewTrace,
  events,
}: RecommendationStreamProps) {
  const [filter, setFilter] = useState<string>("all");

  const filteredRecommendations = recommendations.filter((rec) => {
    if (filter === "all") return true;
    if (filter === "stockout") return rec.severity === "critical";
    if (filter === "spoilage") return rec.severity === "warning";
    if (filter === "transfer") return rec.actionType === "transfer";
    if (filter === "reorder") return rec.actionType === "reorder";
    if (filter === "discount") return rec.actionType === "discount";
    return true;
  });

  const pendingCount = recommendations.filter((r) => r.status === "pending").length;

  return (
    <div className="flex flex-col gap-4 h-full">
      {/* Column Header & Filter Chips */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-bold text-zinc-950 tracking-tight font-sans">
              Decision Stream & Active Interventions
            </h2>
            <span className="text-xs font-mono font-bold bg-orange-100 text-orange-900 border border-orange-200 px-2.5 py-0.5 rounded-full">
              {pendingCount} Pending
            </span>
          </div>
          <span className="text-xs text-zinc-400 font-mono">Real-time Stream</span>
        </div>

        {/* Filter Chips Tray */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar text-xs font-medium text-zinc-600">
          <button
            onClick={() => setFilter("all")}
            className={`px-3 py-1 rounded-full border transition-all duration-150 cursor-pointer active:scale-97 ${
              filter === "all"
                ? "bg-emerald-700 text-white border-emerald-700 font-semibold"
                : "bg-white text-zinc-700 border-zinc-200 hover:bg-zinc-100"
            }`}
          >
            All ({recommendations.length})
          </button>
          <button
            onClick={() => setFilter("stockout")}
            className={`px-3 py-1 rounded-full border transition-all duration-150 cursor-pointer active:scale-97 ${
              filter === "stockout"
                ? "bg-rose-600 text-white border-rose-600 font-semibold"
                : "bg-white text-zinc-700 border-zinc-200 hover:bg-zinc-100"
            }`}
          >
            Stockouts
          </button>
          <button
            onClick={() => setFilter("spoilage")}
            className={`px-3 py-1 rounded-full border transition-all duration-150 cursor-pointer active:scale-97 ${
              filter === "spoilage"
                ? "bg-amber-600 text-white border-amber-600 font-semibold"
                : "bg-white text-zinc-700 border-zinc-200 hover:bg-zinc-100"
            }`}
          >
            Spoilage
          </button>
          <button
            onClick={() => setFilter("transfer")}
            className={`px-3 py-1 rounded-full border transition-all duration-150 cursor-pointer active:scale-97 ${
              filter === "transfer"
                ? "bg-sky-600 text-white border-sky-600 font-semibold"
                : "bg-white text-zinc-700 border-zinc-200 hover:bg-zinc-100"
            }`}
          >
            Transfers
          </button>
          <button
            onClick={() => setFilter("reorder")}
            className={`px-3 py-1 rounded-full border transition-all duration-150 cursor-pointer active:scale-97 ${
              filter === "reorder"
                ? "bg-orange-600 text-white border-orange-600 font-semibold"
                : "bg-white text-zinc-700 border-zinc-200 hover:bg-zinc-100"
            }`}
          >
            Reorders
          </button>
        </div>
      </div>

      {/* Decision Cards List */}
      <div className="flex flex-col gap-3 overflow-y-auto pr-1 flex-1">
        {filteredRecommendations.length === 0 ? (
          <div className="p-8 text-center bg-white rounded-2xl border border-zinc-200 text-zinc-500 text-xs flex flex-col items-center justify-center gap-2">
            <div className="w-10 h-10 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center">
              ✓
            </div>
            <span className="font-semibold text-zinc-900">Fleet Inventory Healthy</span>
            <span className="text-zinc-500 max-w-[260px] text-[11px]">
              No active stockout or spoilage risks detected for this filter. All 5 stores operating within normal safety buffers.
            </span>
          </div>
        ) : (
          filteredRecommendations.map((item, idx) => (
            <RecommendationCard
              key={item.id}
              item={item}
              isSelected={selectedRecId === item.id}
              onSelect={() => onSelectRec(item.id)}
              onApprove={onApproveRec}
              onReject={onRejectRec}
              onViewTrace={onViewTrace}
              index={idx}
            />
          ))
        )}
      </div>

      {/* Embedded Live Simulation Event Feed */}
      <LiveEventFeed events={events} />
    </div>
  );
}
