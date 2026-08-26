"use client";

import React from "react";
import { Users, Clock, Zap, CheckCircle2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { usePantryEngine } from "../../hooks/usePantryEngine";
import { CardSurface } from "../ui/CardSurface";

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
    <CardSurface variant="default" showDotPattern={true} className="!p-8 sm:!p-10 space-y-8">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-gray-100 pb-6">
        <div>
          <span className="text-[11px] font-semibold text-sky-700 uppercase tracking-widest flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5 text-sky-600" /> Interactive Stockout Engine • Prophet ML Forecast
          </span>
          <h3 className="font-serif font-normal text-2xl sm:text-3xl text-gray-950 tracking-tight">
            Pantry Depletion Velocity Simulator
          </h3>
          <p className="text-xs text-gray-500 font-normal mt-1">
            Adjust household size or staple stock levels to watch Prophet ML recalculate depletion velocity in real time.
          </p>
        </div>

        <div className="flex items-center gap-2 bg-gray-50 p-2 rounded-full border border-gray-200/80 shrink-0">
          <Users className="w-4 h-4 text-gray-500 ml-2" />
          <span className="text-xs font-bold text-gray-900 pr-1">Household Size:</span>
          {[2, 3, 5].map((size) => (
            <button
              key={size}
              onClick={() => setHouseholdMembers(size)}
              className={`w-7.5 h-7.5 rounded-full text-xs font-bold transition-all cursor-pointer ${
                householdMembers === size
                  ? "bg-gray-950 text-white shadow-2xs"
                  : "bg-white text-gray-600 hover:text-gray-950 border border-gray-200/80"
              }`}
            >
              {size}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
        {/* Left Column: Interactive Item Stock Sliders */}
        <div className="lg:col-span-6 space-y-4">
          {items.map((item) => (
            <div key={item.id} className="space-y-2 bg-gray-50/80 p-4 rounded-2xl border border-gray-100">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-gray-900 font-display">{item.name}</span>
                <span className="font-mono text-gray-600 font-medium">
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
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-sky-600"
              />
            </div>
          ))}
        </div>

        {/* Right Column: Real-Time Prophet ML Depletion Forecast Curve Graph */}
        <div className="lg:col-span-6 bg-sky-50/70 p-6 rounded-2xl border border-sky-200/80 space-y-4 text-center">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-sky-800 uppercase tracking-widest flex items-center gap-1.5">
              <Clock className="w-4 h-4 text-sky-600" /> Prophet Forecast Curve
            </span>
            <span className="text-[10px] font-mono font-bold text-sky-700 bg-white px-2.5 py-0.5 rounded-full border border-sky-200">
              {householdMembers} Members · {items[0]?.currentStock.toFixed(1)}L Milk
            </span>
          </div>

          {/* Interactive Depletion Curve Graph (SVG) */}
          <div className="relative w-full h-32 bg-white rounded-xl border border-sky-100 p-2 overflow-hidden shadow-2xs">
            {/* 24-Hour Restock Alert Threshold Line */}
            <div className="absolute left-0 right-0 top-[65%] border-b border-dashed border-rose-400 z-10 flex items-center justify-between px-2">
              <span className="text-[8.5px] font-mono font-bold text-rose-600 bg-rose-50 px-1 rounded">24H RESTOCK ALERT LINE</span>
            </div>

            <svg className="w-full h-full overflow-visible" viewBox="0 0 300 100" preserveAspectRatio="none">
              <defs>
                <linearGradient id="depletionGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#0284C7" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#0284C7" stopOpacity="0.0" />
                </linearGradient>
              </defs>

              {/* Shaded Area under Curve */}
              <path
                d={`M 0,${Math.min(90, Math.max(10, 100 - (items[0]?.currentStock || 1) * 20))} Q 150,${Math.min(95, Math.max(20, 100 - (hoursRemaining / 72) * 80))} 300,95 L 300,100 L 0,100 Z`}
                fill="url(#depletionGradient)"
              />

              {/* Prophet ML Forecast Line */}
              <path
                d={`M 0,${Math.min(90, Math.max(10, 100 - (items[0]?.currentStock || 1) * 20))} Q 150,${Math.min(95, Math.max(20, 100 - (hoursRemaining / 72) * 80))} 300,95`}
                fill="none"
                stroke="#0284C7"
                strokeWidth="2.5"
                strokeDasharray="4 2"
              />

              {/* Active Stock Data Points */}
              <circle cx="0" cy={Math.min(90, Math.max(10, 100 - (items[0]?.currentStock || 1) * 20))} r="4" fill="#0284C7" />
              <circle cx="150" cy={Math.min(95, Math.max(20, 100 - (hoursRemaining / 72) * 80))} r="4" fill="#0284C7" />
            </svg>
          </div>

          <div className="space-y-1 pt-1">
            <div className="text-4xl sm:text-5xl font-serif font-light text-gray-950 tracking-tighter flex items-center justify-center gap-1">
              <span>~</span>
              <AnimatePresence mode="wait">
                <motion.span
                  key={hoursRemaining}
                  initial={{ y: 8, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  exit={{ y: -8, opacity: 0 }}
                  transition={{ type: "spring", stiffness: 350, damping: 25 }}
                >
                  {hoursRemaining}
                </motion.span>
              </AnimatePresence>
              <span>Hours</span>
            </div>
            <p className="text-xs text-gray-500 font-medium">Projected stockout for Fresh Milk 1L</p>
          </div>

          <div
            className={`p-3 rounded-xl border text-xs font-bold flex items-center justify-center gap-2 transition-all ${
              isAlertActive
                ? "bg-amber-100/90 text-amber-900 border-amber-200"
                : "bg-emerald-100/90 text-emerald-900 border-emerald-200"
            }`}
          >
            {isAlertActive ? (
              <>
                <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping" />
                <span>24-Hour WhatsApp Restock Alert Triggered</span>
              </>
            ) : (
              <>
                <CheckCircle2 className="w-4 h-4 text-emerald-700" />
                <span>Pantry Stock Level Safe</span>
              </>
            )}
          </div>
        </div>
      </div>
    </CardSurface>
  );
}
