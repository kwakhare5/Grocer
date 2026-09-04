import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { SimulationEvent } from "../../lib/types";

interface LiveEventFeedProps {
  events: SimulationEvent[];
}

export function LiveEventFeed({ events }: LiveEventFeedProps) {
  const [filter, setFilter] = useState<string>("all");

  const filteredEvents = events.filter((ev) => {
    if (filter === "all") return true;
    if (filter === "risk") return ev.type.includes("RISK");
    if (filter === "action") return ev.type.includes("APPROVED") || ev.type.includes("TRANSFER") || ev.type.includes("EXECUTING");
    if (filter === "order") return ev.type.includes("ORDER");
    return true;
  });

  return (
    <div className="bg-white rounded-2xl border border-zinc-200 p-4 shadow-xs flex flex-col gap-3">
      {/* Header & Filter Tabs */}
      <div className="flex items-center justify-between border-b border-zinc-100 pb-2.5">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <h3 className="text-xs font-bold text-zinc-950 uppercase tracking-wider font-sans">
            Live Simulation Event Feed
          </h3>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1 text-[11px] font-medium text-zinc-500">
          <button
            onClick={() => setFilter("all")}
            className={`px-2 py-0.5 rounded-full transition-colors cursor-pointer ${
              filter === "all" ? "bg-emerald-700 text-white font-bold" : "hover:bg-zinc-100"
            }`}
          >
            All ({events.length})
          </button>
          <button
            onClick={() => setFilter("risk")}
            className={`px-2 py-0.5 rounded-full transition-colors cursor-pointer ${
              filter === "risk" ? "bg-emerald-700 text-white font-bold" : "hover:bg-zinc-100"
            }`}
          >
            Risks
          </button>
          <button
            onClick={() => setFilter("action")}
            className={`px-2 py-0.5 rounded-full transition-colors cursor-pointer ${
              filter === "action" ? "bg-emerald-700 text-white font-bold" : "hover:bg-zinc-100"
            }`}
          >
            Actions
          </button>
          <button
            onClick={() => setFilter("order")}
            className={`px-2 py-0.5 rounded-full transition-colors cursor-pointer ${
              filter === "order" ? "bg-emerald-700 text-white font-bold" : "hover:bg-zinc-100"
            }`}
          >
            Orders
          </button>
        </div>
      </div>

      {/* Events List */}
      <div className="flex flex-col gap-2 max-h-[220px] overflow-y-auto pr-1">
        {filteredEvents.length === 0 ? (
          <div className="text-center py-6 text-xs text-zinc-400 font-mono">
            No events in this category yet.
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {filteredEvents.map((ev) => {
              const isCritical = ev.severity === "critical";
              const isWarning = ev.severity === "warning";
              const isSuccess = ev.severity === "success";

              return (
                <motion.div
                  key={ev.id}
                  initial={{ opacity: 0, x: -6, y: -2 }}
                  animate={{ opacity: 1, x: 0, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                  className="flex items-start gap-2.5 text-xs p-2 rounded-lg bg-zinc-50/70 border border-zinc-100/80 hover:bg-zinc-100/70 transition-colors"
                >
                  {/* Timestamp */}
                  <span className="font-mono text-[10.5px] text-zinc-400 shrink-0 pt-0.5">
                    {ev.timestamp}
                  </span>

                  {/* Event Type Tag */}
                  <span
                    className={`text-[9.5px] font-mono font-bold uppercase tracking-wider px-1.5 py-0.5 rounded shrink-0 ${
                      isCritical
                        ? "bg-rose-100 text-rose-800"
                        : isWarning
                        ? "bg-amber-100 text-amber-800"
                        : isSuccess
                        ? "bg-emerald-100 text-emerald-800"
                        : "bg-zinc-200 text-zinc-800"
                    }`}
                  >
                    {ev.type.replace(/_/g, " ")}
                  </span>

                  {/* Description */}
                  <span className="text-zinc-700 flex-1 leading-snug">
                    {ev.description}
                  </span>

                  {/* Store badge if applicable */}
                  {ev.storeCode && (
                    <span className="text-[10px] font-mono text-zinc-500 bg-white px-1.5 py-0.5 rounded border border-zinc-200 shrink-0">
                      {ev.storeCode}
                    </span>
                  )}
                </motion.div>
              );
            })}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
