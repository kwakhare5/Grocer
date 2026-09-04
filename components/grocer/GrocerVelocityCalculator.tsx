"use client";

import React from "react";
import { Users, Clock, Zap, CheckCircle2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { usePantryEngine } from "../../hooks/usePantryEngine";

export function GrocerVelocityCalculator() {
  const {
    householdMembers,
    setHouseholdMembers,
    items,
    updateItemStock,
    hoursRemaining,
    isAlertActive,
  } = usePantryEngine(3);

  return (
    <div className="bg-white rounded-xl border border-zinc-200 p-6 sm:p-8 space-y-6 shadow-2xs">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-zinc-100 pb-5">
        <div className="space-y-1">
          <span className="text-[11px] font-mono font-bold text-blue-800 uppercase tracking-wider flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5 text-blue-600" /> Household Consumption Estimator
          </span>
          <h3 className="font-sans font-bold text-xl sm:text-2xl text-zinc-950 tracking-tight">
            Estimate Staple Runout Times
          </h3>
          <p className="text-xs text-zinc-500 font-normal">
            Adjust household members or staple levels to see estimated days remaining.
          </p>
        </div>

        <div className="flex items-center gap-2 bg-zinc-50 p-1.5 rounded-lg border border-zinc-200 shrink-0">
          <Users className="w-4 h-4 text-zinc-500 ml-1.5" />
          <span className="text-xs font-bold text-zinc-800 pr-1">Household:</span>
          {[2, 3, 5].map((size) => (
            <button
              key={size}
              type="button"
              onClick={() => setHouseholdMembers(size)}
              className={`w-7 h-7 rounded text-xs font-bold transition-all cursor-pointer ${
                householdMembers === size
                  ? "bg-blue-600 text-white shadow-2xs font-bold"
                  : "bg-white text-zinc-700 hover:bg-zinc-100 border border-zinc-200"
              }`}
            >
              {size}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
        {/* Left Column: Interactive Item Stock Sliders */}
        <div className="lg:col-span-6 space-y-3">
          {items.map((item) => (
            <div key={item.id} className="space-y-1.5 bg-zinc-50 p-3.5 rounded-lg border border-zinc-200">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-zinc-900">{item.name}</span>
                <span className="font-mono text-zinc-600 font-medium">
                  {item.currentStock.toFixed(1)} / {item.maxCapacity} {item.unit}
                </span>
              </div>
              <input
                type="range"
                min={0.1}
                max={item.maxCapacity}
                step={0.1}
                value={item.currentStock}
                onChange={(e) => updateItemStock(item.id, parseFloat(e.target.value))}
                className="w-full h-1.5 bg-zinc-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
              />
            </div>
          ))}
        </div>

        {/* Right Column: Real-Time Depletion Forecast Curve Graph */}
        <div className="lg:col-span-6 bg-zinc-50 p-5 rounded-lg border border-zinc-200 space-y-4 text-center">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-zinc-800 uppercase tracking-wider flex items-center gap-1.5 font-mono">
              <Clock className="w-3.5 h-3.5 text-blue-600" /> Forecast Curve
            </span>
            <span className="text-[10px] font-mono font-bold text-zinc-700 bg-white px-2 py-0.5 rounded border border-zinc-200">
              {householdMembers} Members · {items[0]?.currentStock.toFixed(1)}L Milk
            </span>
          </div>

          {/* Interactive Depletion Curve Graph (SVG) */}
          <div className="relative w-full h-28 bg-white rounded-md border border-zinc-200 p-2 overflow-hidden">
            {/* 24-Hour Restock Alert Threshold Line */}
            <div className="absolute left-0 right-0 top-[65%] border-b border-dashed border-rose-400 z-10 flex items-center justify-between px-2">
              <span className="text-[8.5px] font-mono font-bold text-rose-700 bg-rose-50 px-1 rounded">24H RESTOCK ALERT LINE</span>
            </div>

            <svg className="w-full h-full overflow-visible" viewBox="0 0 300 100" preserveAspectRatio="none">
              <defs>
                <linearGradient id="depletionGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#2563EB" stopOpacity="0.20" />
                  <stop offset="100%" stopColor="#2563EB" stopOpacity="0.0" />
                </linearGradient>
              </defs>

              {/* Shaded Area under Curve */}
              <path
                d={`M 0,${Math.min(90, Math.max(10, 100 - (items[0]?.currentStock || 1) * 20))} Q 150,${Math.min(95, Math.max(20, 100 - (hoursRemaining / 72) * 80))} 300,95 L 300,100 L 0,100 Z`}
                fill="url(#depletionGradient)"
              />

              {/* Forecast Line */}
              <path
                d={`M 0,${Math.min(90, Math.max(10, 100 - (items[0]?.currentStock || 1) * 20))} Q 150,${Math.min(95, Math.max(20, 100 - (hoursRemaining / 72) * 80))} 300,95`}
                fill="none"
                stroke="#2563EB"
                strokeWidth="2"
                strokeDasharray="4 2"
              />

              {/* Active Stock Data Points */}
              <circle cx="0" cy={Math.min(90, Math.max(10, 100 - (items[0]?.currentStock || 1) * 20))} r="3.5" fill="#2563EB" />
              <circle cx="150" cy={Math.min(95, Math.max(20, 100 - (hoursRemaining / 72) * 80))} r="3.5" fill="#2563EB" />
            </svg>
          </div>

          <div className="space-y-1">
            <div className="text-3xl sm:text-4xl font-mono font-bold text-zinc-950 tracking-tight flex items-center justify-center gap-1">
              <span>~</span>
              <AnimatePresence mode="wait">
                <motion.span
                  key={hoursRemaining}
                  initial={{ y: 6, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  exit={{ y: -6, opacity: 0 }}
                  transition={{ type: "spring", stiffness: 350, damping: 25 }}
                >
                  {hoursRemaining}
                </motion.span>
              </AnimatePresence>
              <span className="text-xl text-zinc-500 font-sans font-normal ml-1">Hours</span>
            </div>
            <p className="text-xs text-zinc-500 font-medium">Projected stockout for Fresh Milk 1L</p>
          </div>

          <div
            className={`p-2.5 rounded-lg border text-xs font-bold flex items-center justify-center gap-2 transition-all ${
              isAlertActive
                ? "bg-amber-50 text-amber-900 border-amber-200"
                : "bg-emerald-50 text-emerald-900 border-emerald-200"
            }`}
          >
            {isAlertActive ? (
              <>
                <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                <span>24-Hour WhatsApp Restock Alert Triggered</span>
              </>
            ) : (
              <>
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-700" />
                <span>Pantry Stock Level Safe</span>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

