"use client";

import React, { useState } from "react";
import { RefreshCw, ShieldAlert, Cpu, CheckCircle2, Play, Tag, ArrowRightLeft } from "lucide-react";
import { motion } from "framer-motion";
import { GrocerVelocityCalculator } from "./GrocerVelocityCalculator";
import { toast } from "sonner";

export function GrocerValueProp() {
  // Card 1: Consumption Velocity Forecaster Interactive State
  const [stockLevel, setStockLevel] = useState<"stocked" | "low">("low");

  // Card 2: Anomaly Exclusion Filter State
  const [anomalyFiltered, setAnomalyFiltered] = useState(true);

  // Card 3: 5-Node Execution Pipeline Step Tracer State
  const [agentStep, setAgentStep] = useState(0);
  const agentNodes = [
    { id: "check_pantry", name: "1. check_pantry", status: "Calculates consumption velocity" },
    { id: "generate_alert", name: "2. generate_alert", status: "Formulates WhatsApp 24h restock payload" },
    { id: "parse_user_reply", name: "3. parse_user_reply", status: "Parses customer confirmation" },
    { id: "build_cart", name: "4. build_cart", status: "Assembles cart with depletion items" },
    { id: "execute_order", name: "5. execute_order", status: "Dispatches dark store delivery queue" },
  ];

  // Card 4: Perishable Spoilage & Dynamic Markdown Engine State
  const [expiryHours, setExpiryHours] = useState<4 | 10 | 18 | 36>(4);
  const discountTiers = {
    4: { tier: "30% Markdown", action: "DISCOUNT & TRANSFER", unitsAtRisk: 42, salvageVal: "₹2,100 rescued", badgeColor: "bg-rose-50 text-rose-700 border-rose-200" },
    10: { tier: "20% Flash Discount", action: "APPLY DISCOUNT", unitsAtRisk: 28, salvageVal: "₹1,400 rescued", badgeColor: "bg-amber-50 text-amber-800 border-amber-200" },
    18: { tier: "10% Early Markdown", action: "APPLY DISCOUNT", unitsAtRisk: 14, salvageVal: "₹700 rescued", badgeColor: "bg-sky-50 text-sky-800 border-sky-200" },
    36: { tier: "0% Standard Price", action: "HOLD", unitsAtRisk: 0, salvageVal: "Zero risk", badgeColor: "bg-emerald-50 text-emerald-800 border-emerald-200" },
  };

  const handleStepAgent = () => {
    setAgentStep((prev) => (prev + 1) % agentNodes.length);
  };

  return (
    <section id="features" className="py-16 md:py-24 bg-[#FAFAFA] border-t border-zinc-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
        {/* Two-Column Header */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-end">
          <div className="lg:col-span-7 space-y-2">
            <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-blue-800 bg-blue-50 px-2.5 py-0.5 rounded border border-blue-200 inline-block">
              How It Works
            </span>
            <h2 className="font-sans font-bold text-2xl sm:text-3xl lg:text-4xl tracking-tight text-zinc-950">
              How Grocer Keeps Stores and Kitchens Stocked
            </h2>
          </div>
          <div className="lg:col-span-5">
            <p className="text-xs sm:text-sm text-zinc-600 font-normal leading-relaxed">
              Track household depletion, filter demand spikes, automate customer orders, and discount expiring stock.
            </p>
          </div>
        </div>

        {/* Interactive Depletion Velocity Calculator */}
        <div id="simulator">
          <GrocerVelocityCalculator />
        </div>

        {/* 2x2 Bento Grid System (Standard 12px Card Radii) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Card 1: Depletion Engine */}
          <div className="lg:col-span-7 bg-white rounded-xl border border-zinc-200 p-5 shadow-2xs flex flex-col justify-between space-y-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-blue-800 uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <RefreshCw className="w-3.5 h-3.5 text-blue-600" /> Household Depletion
                </span>
                <span className="text-[10px] font-bold text-zinc-700 bg-zinc-100 px-2 py-0.5 rounded border border-zinc-200 font-mono">
                  0.48L / day
                </span>
              </div>
              <h3 className="text-base font-bold text-zinc-950">
                Household Consumption Tracking
              </h3>
              <p className="text-xs text-zinc-500 font-normal leading-relaxed">
                Predicts when household staples run low based on daily consumption patterns.
              </p>
            </div>

            {/* Interactive Graphic */}
            <div className="bg-zinc-50 rounded-lg p-3.5 border border-zinc-200 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-bold text-zinc-900 text-xs">Fresh Milk 1L</span>
                <button
                  type="button"
                  onClick={() => setStockLevel((prev) => (prev === "low" ? "stocked" : "low"))}
                  className="text-[10px] font-mono text-blue-700 font-bold hover:underline cursor-pointer"
                >
                  Toggle Level
                </button>
              </div>

              <div className="w-full h-2 bg-zinc-200 rounded-full overflow-hidden">
                <motion.div
                  className={`h-full rounded-full transition-all duration-300 ${
                    stockLevel === "low" ? "bg-rose-600" : "bg-emerald-600"
                  }`}
                  animate={{ width: stockLevel === "low" ? "20%" : "100%" }}
                  transition={{ type: "spring", stiffness: 200, damping: 20 }}
                />
              </div>

              <div className="flex items-center justify-between pt-0.5">
                <span className="text-[10.5px] text-zinc-500 font-mono">
                  {stockLevel === "low" ? "Stock: 0.2L Remaining" : "Stock: 1.0L Full"}
                </span>
                {stockLevel === "low" ? (
                  <span className="text-[9.5px] text-rose-700 font-mono font-bold bg-rose-50 px-2 py-0.5 rounded border border-rose-200 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" /> 24H ALERT
                  </span>
                ) : (
                  <span className="text-[9.5px] text-emerald-800 font-mono font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3 text-emerald-600" /> STOCKED
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Card 2: Anomaly Exclusion Filter */}
          <div className="lg:col-span-5 bg-white rounded-xl border border-zinc-200 p-5 shadow-2xs flex flex-col justify-between space-y-4">
            <div className="space-y-2">
              <span className="text-[11px] font-bold text-amber-800 uppercase tracking-wider flex items-center gap-1.5 font-mono">
                <ShieldAlert className="w-3.5 h-3.5 text-amber-600" /> Demand Filtering
              </span>
              <h3 className="text-base font-bold text-zinc-950">
                Smart Demand Filtering
              </h3>
              <p className="text-xs text-zinc-500 font-normal leading-relaxed">
                Ignores one-off party spikes so reorder forecasts stay accurate.
              </p>
            </div>

            {/* Interactive Graphic */}
            <div className="bg-amber-50/60 p-3.5 rounded-lg border border-amber-200 text-xs space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-amber-950 uppercase tracking-wider font-mono">
                  Guest Bulk Spike (+5L)
                </span>
                <button
                  type="button"
                  onClick={() => setAnomalyFiltered((prev) => !prev)}
                  className="text-[9.5px] font-bold text-amber-900 bg-white px-2 py-0.5 rounded border border-amber-300 shadow-2xs hover:bg-amber-100 transition-all cursor-pointer"
                >
                  {anomalyFiltered ? "Simulate Raw Spike" : "Apply Gate Filter"}
                </button>
              </div>

              <div className="p-2 rounded bg-white border border-amber-200/80 flex items-center justify-between">
                <span className="text-[11px] font-bold text-zinc-900 font-mono">Bulk Order: 5.0L</span>
                {anomalyFiltered ? (
                  <span className="text-[9.5px] text-emerald-800 font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 flex items-center gap-1 font-mono">
                    <CheckCircle2 className="w-3 h-3 text-emerald-600" /> EXCLUDED
                  </span>
                ) : (
                  <span className="text-[9.5px] text-rose-700 font-bold bg-rose-50 px-2 py-0.5 rounded border border-rose-200 font-mono">
                    RAW SPIKE INCLUDED
                  </span>
                )}
              </div>
              <p className="text-[10px] text-amber-900 font-medium leading-tight">
                {anomalyFiltered ? "Baseline velocity preserved at 0.48L/day." : "Warning: Model corrupted by 5x guest spike."}
              </p>
            </div>
          </div>

          {/* Card 3: 5-Node Execution Pipeline */}
          <div className="lg:col-span-5 bg-white rounded-xl border border-zinc-200 p-5 shadow-2xs flex flex-col justify-between space-y-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-sky-800 uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <Cpu className="w-3.5 h-3.5 text-sky-600" /> Order Workflow
                </span>
                <button
                  type="button"
                  onClick={handleStepAgent}
                  className="text-[10px] font-bold text-white bg-blue-600 hover:bg-blue-700 px-2.5 py-1 rounded shadow-2xs flex items-center gap-1 transition-all cursor-pointer"
                >
                  <Play className="w-2.5 h-2.5 fill-current text-white" />
                  <span>Next Step</span>
                </button>
              </div>
              <h3 className="text-base font-bold text-zinc-950">
                Automated Order Workflow
              </h3>
              <p className="text-xs text-zinc-500 font-normal leading-relaxed">
                Handles WhatsApp restock alerts, customer confirmations, and store order queues.
              </p>
            </div>

            {/* Interactive Graphic */}
            <div className="bg-zinc-50 p-3.5 rounded-lg border border-zinc-200 text-left space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-zinc-500 font-mono">ACTIVE PIPELINE STEP</span>
                <span className="text-[9.5px] font-mono text-zinc-700 font-bold bg-white px-2 py-0.5 rounded border border-zinc-200">
                  {agentStep + 1} / 5
                </span>
              </div>

              <div className="p-2 rounded bg-white border border-zinc-200 text-xs font-mono font-bold text-zinc-950">
                {agentNodes[agentStep].name}
              </div>

              <p className="text-[10.5px] text-zinc-500 font-sans font-medium">
                {agentNodes[agentStep].status}
              </p>
            </div>
          </div>

          {/* Card 4: Perishable Spoilage & Dynamic Markdown Ladder */}
          <div className="lg:col-span-7 bg-white rounded-xl border border-zinc-200 p-5 shadow-2xs flex flex-col justify-between space-y-4">
            <div className="space-y-2">
              <span className="text-[11px] font-bold text-purple-800 uppercase tracking-wider flex items-center gap-1.5 font-mono">
                <Tag className="w-3.5 h-3.5 text-purple-600" /> Freshness Protection
              </span>
              <h3 className="text-base font-bold text-zinc-950">
                Smart Markdowns
              </h3>
              <p className="text-xs text-zinc-500 font-normal leading-relaxed">
                Discounts short-shelf-life items like fresh milk before they spoil.
              </p>
            </div>

            {/* Interactive Graphic */}
            <div className="bg-zinc-50 p-3.5 rounded-lg border border-zinc-200 text-xs space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[10.5px] font-bold text-zinc-600">Simulate Batch Expiry:</span>
                <div className="flex items-center gap-1.5">
                  {([4, 10, 18, 36] as const).map((hours) => (
                    <button
                      key={hours}
                      type="button"
                      onClick={() => {
                        setExpiryHours(hours);
                        toast.info(`Evaluated Batch Expiry: ${hours}h remaining`);
                      }}
                      className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border cursor-pointer transition-all ${
                        expiryHours === hours
                          ? "bg-blue-600 text-white border-blue-600"
                          : "bg-white text-zinc-700 border-zinc-200 hover:bg-zinc-100"
                      }`}
                    >
                      {hours}h
                    </button>
                  ))}
                </div>
              </div>

              <div className="p-2.5 rounded bg-white border border-zinc-200 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-zinc-900 font-mono">
                    Whole Wheat Bread (80 Units)
                  </span>
                  <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${discountTiers[expiryHours].badgeColor}`}>
                    {discountTiers[expiryHours].tier}
                  </span>
                </div>

                <div className="flex items-center justify-between text-[10.5px] text-zinc-500 font-mono pt-0.5">
                  <span className="flex items-center gap-1 text-blue-800 font-bold">
                    <ArrowRightLeft className="w-3 h-3 text-blue-600" /> Action: {discountTiers[expiryHours].action}
                  </span>
                  <span className="font-bold text-zinc-900">
                    {discountTiers[expiryHours].salvageVal}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
