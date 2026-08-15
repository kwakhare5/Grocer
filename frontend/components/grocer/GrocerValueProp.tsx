"use client";

import React, { useState } from "react";
import { RefreshCw, ShieldAlert, Cpu, BookOpen, CheckCircle2, Play } from "lucide-react";
import { motion } from "framer-motion";
import { GrocerVelocityCalculator } from "./GrocerVelocityCalculator";
import { PillBadge } from "../ui/PillBadge";
import { CardSurface } from "../ui/CardSurface";
import { toast } from "sonner";

export function GrocerValueProp() {
  // Card 1: Prophet ML Depletion Engine Interactive State
  const [stockLevel, setStockLevel] = useState<"stocked" | "low">("low");

  // Card 2: Anomaly Exclusion Filter State
  const [anomalyFiltered, setAnomalyFiltered] = useState(true);

  // Card 3: 5-Node LangGraph Agent Step Tracer State
  const [agentStep, setAgentStep] = useState(0);
  const agentNodes = [
    { id: "check_pantry", name: "1. check_pantry", status: "Queries Prophet ML forecast" },
    { id: "generate_alert", name: "2. generate_alert", status: "Triggers WhatsApp 24h restock payload" },
    { id: "parse_user_reply", name: "3. parse_user_reply", status: "Parses user 'YES' quick reply" },
    { id: "build_cart", name: "4. build_cart", status: "Assembles cart with recipe items" },
    { id: "execute_order", name: "5. execute_order", status: "Dispatches mock dark store checkout" },
  ];

  // Card 4: Recipe Pantry Fulfiller State
  const [selectedDish, setSelectedDish] = useState<"biryani" | "dal" | "paneer">("paneer");
  const recipes = {
    paneer: { name: "Paneer Butter Masala", missing: 2, price: 140 },
    biryani: { name: "Hyderabadi Biryani", missing: 3, price: 210 },
    dal: { name: "Dal Tadka", missing: 1, price: 65 },
  };

  const handleStepAgent = () => {
    setAgentStep((prev) => (prev + 1) % agentNodes.length);
  };

  return (
    <section id="features" className="py-20 md:py-28 bg-[#FCFCFD] border-t border-gray-200/40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-14">
        {/* Two-Column Header */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-end">
          <div className="lg:col-span-7 space-y-3">
            <PillBadge variant="kicker" color="sky">
              Interactive Feature Showcase
            </PillBadge>
            <h2 className="font-serif font-normal text-3xl sm:text-4xl lg:text-[44px] tracking-tight text-gray-950 leading-[1.15]">
              Core Backend Engine & Agent Capabilities
            </h2>
          </div>
          <div className="lg:col-span-5">
            <p className="text-sm sm:text-base text-gray-500 font-normal leading-relaxed">
              Explore interactive live simulations of Prophet ML forecasts, anomaly filtering, 5-node agent execution, and 1-tap recipe fulfillment.
            </p>
          </div>
        </div>

        {/* Interactive Depletion Velocity Calculator */}
        <GrocerVelocityCalculator />

        {/* Asymmetric 2x2 Bento Grid System */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Card 1: Prophet ML Depletion Engine (Hero 7-Column Card) */}
          <CardSurface variant="default" className="lg:col-span-7 flex flex-col justify-between h-full space-y-4 !rounded-3xl hover:shadow-md transition-all duration-300">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-sky-700 uppercase tracking-widest flex items-center gap-1.5 font-display">
                  <RefreshCw className="w-3.5 h-3.5 text-sky-600" /> Prophet ML Engine
                </span>
                <span className="text-[9px] font-bold text-sky-800 bg-sky-50 px-2 py-0.5 rounded-full border border-sky-100 font-mono">
                  0.48L / day
                </span>
              </div>
              <h3 className="text-base sm:text-lg font-bold text-gray-950 leading-snug font-display">
                Depletion Velocity Forecasting
              </h3>
              <p className="text-xs text-gray-500 font-normal leading-relaxed">
                Calculates daily usage rates per staple and projects exact stockout dates 24 hours in advance.
              </p>
            </div>

            {/* Interactive Motion Graphic Box */}
            <div className="bg-slate-50/90 rounded-2xl p-4 border border-gray-200/80 space-y-2.5 text-xs mt-4">
              <div className="flex items-center justify-between">
                <span className="font-bold text-gray-900 text-xs font-display">Fresh Milk 1L</span>
                <button
                  onClick={() => setStockLevel((prev) => (prev === "low" ? "stocked" : "low"))}
                  className="text-[10px] font-mono text-sky-700 font-bold hover:underline cursor-pointer"
                >
                  Toggle Level
                </button>
              </div>

              <div className="w-full h-2.5 bg-gray-200 rounded-full overflow-hidden border border-gray-300/40">
                <motion.div
                  className={`h-full rounded-full transition-all duration-500 ${
                    stockLevel === "low" ? "bg-[#BE123C]" : "bg-[#15803D]"
                  }`}
                  animate={{ width: stockLevel === "low" ? "20%" : "100%" }}
                  transition={{ type: "spring", stiffness: 200, damping: 20 }}
                />
              </div>

              <div className="flex items-center justify-between pt-1">
                <span className="text-[10px] text-gray-500 font-mono font-medium">
                  {stockLevel === "low" ? "Stock: 0.2L Remaining" : "Stock: 1.0L Full"}
                </span>
                {stockLevel === "low" ? (
                  <span className="text-[9.5px] text-rose-600 font-bold bg-rose-50 px-2 py-0.5 rounded border border-rose-200 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping" /> 24H ALERT
                  </span>
                ) : (
                  <span className="text-[9.5px] text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3 text-emerald-600" /> STOCKED
                  </span>
                )}
              </div>
            </div>
          </CardSurface>

          {/* Card 2: Anomaly Exclusion Filter (Secondary 5-Column Card) */}
          <CardSurface variant="default" className="lg:col-span-5 flex flex-col justify-between h-full space-y-4 !rounded-3xl hover:shadow-md transition-all duration-300">
            <div className="space-y-3">
              <span className="text-[11px] font-semibold text-amber-700 uppercase tracking-widest flex items-center gap-1.5 font-display">
                <ShieldAlert className="w-3.5 h-3.5 text-amber-600" /> Anomaly Exclusion
              </span>
              <h3 className="text-base sm:text-lg font-bold text-gray-950 leading-snug font-display">
                Filters Out Spikes
              </h3>
              <p className="text-xs text-gray-500 font-normal leading-relaxed">
                Automatically ignores guest visits (&gt;2.5x baseline) and travel gaps (&gt;5 days) so models stay clean.
              </p>
            </div>

            {/* Interactive Motion Graphic Box */}
            <div className="bg-amber-50/70 p-4 rounded-2xl border border-amber-200/80 text-xs mt-4 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-amber-900 uppercase tracking-wider font-display">
                  Guest Visit Test (+5L)
                </span>
                <button
                  onClick={() => setAnomalyFiltered((prev) => !prev)}
                  className="text-[9.5px] font-bold text-amber-800 bg-white px-2.5 py-1 rounded border border-amber-300 shadow-2xs hover:bg-amber-100 transition-all cursor-pointer"
                >
                  {anomalyFiltered ? "Simulate Raw Spike" : "Apply Gate Filter"}
                </button>
              </div>

              <div className="p-2.5 rounded-xl bg-white border border-amber-200/60 flex items-center justify-between">
                <span className="text-[11px] font-bold text-gray-900 font-mono">Bulk Order: 5.0L</span>
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
              <p className="text-[10px] text-amber-800 font-medium leading-tight">
                {anomalyFiltered ? "Baseline velocity preserved at 0.48L/day." : "Warning: Model corrupted by 5x guest spike!"}
              </p>
            </div>
          </CardSurface>

          {/* Card 3: 5-Node LangGraph Agent (Secondary 5-Column Accent Card) */}
          <CardSurface variant="accent" className="lg:col-span-5 flex flex-col justify-between h-full space-y-4 !rounded-3xl hover:shadow-md transition-all duration-300">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-sky-700 uppercase tracking-widest flex items-center gap-1.5 font-display">
                  <Cpu className="w-3.5 h-3.5 text-sky-600" /> LangGraph Agent
                </span>
                <button
                  onClick={handleStepAgent}
                  className="text-[9.5px] font-bold text-white bg-sky-700 hover:bg-sky-800 px-2.5 py-1 rounded-full shadow-2xs flex items-center gap-1 transition-all cursor-pointer"
                >
                  <Play className="w-2.5 h-2.5 fill-current" /> Step Node
                </button>
              </div>
              <h3 className="text-base sm:text-lg font-bold text-gray-950 leading-snug font-display">
                5-Node Execution Graph
              </h3>
              <p className="text-xs text-gray-600 font-medium leading-relaxed">
                Runs check_pantry → generate_alert → parse_reply → build_cart → execute_order.
              </p>
            </div>

            {/* Interactive Motion Graphic Box */}
            <div className="bg-white p-4 rounded-2xl border border-sky-200/80 text-left space-y-2.5 mt-4">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-sky-900 font-mono">ACTIVE EXECUTION NODE</span>
                <span className="text-[9px] font-mono text-sky-700 font-bold bg-sky-50 px-2 py-0.5 rounded border border-sky-100">
                  {agentStep + 1} / 5
                </span>
              </div>

              <div className="p-2.5 rounded-xl bg-sky-50/70 border border-sky-200 text-xs font-mono font-bold text-sky-950">
                {agentNodes[agentStep].name}
              </div>

              <p className="text-[10px] text-gray-500 font-sans font-medium">
                {agentNodes[agentStep].status}
              </p>
            </div>
          </CardSurface>

          {/* Card 4: Recipe Pantry Fulfiller (Hero 7-Column Card) */}
          <CardSurface variant="default" className="lg:col-span-7 flex flex-col justify-between h-full space-y-4 !rounded-3xl hover:shadow-md transition-all duration-300">
            <div className="space-y-3">
              <span className="text-[11px] font-semibold text-emerald-700 uppercase tracking-widest flex items-center gap-1.5 font-display">
                <BookOpen className="w-3.5 h-3.5 text-emerald-600" /> Recipe Agent
              </span>
              <h3 className="text-base sm:text-lg font-bold text-gray-950 leading-snug font-display">
                Recipe Pantry Fulfiller
              </h3>
              <p className="text-xs text-gray-500 font-normal leading-relaxed">
                Parses recipes, cross-checks pantry inventory, and adds only missing ingredients to cart in 1 tap.
              </p>
            </div>

            {/* Interactive Motion Graphic Box */}
            <div className="bg-emerald-50/70 p-4 rounded-2xl border border-emerald-200/80 text-xs mt-4 space-y-2.5">
              <div className="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar">
                {(["paneer", "biryani", "dal"] as const).map((dishKey) => (
                  <button
                    key={dishKey}
                    onClick={() => setSelectedDish(dishKey)}
                    className={`text-[9.5px] font-bold font-display px-2.5 py-1 rounded-md border capitalize cursor-pointer transition-all ${
                      selectedDish === dishKey
                        ? "bg-[#09090B] text-white border-[#09090B]"
                        : "bg-white text-gray-700 border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    {dishKey}
                  </button>
                ))}
              </div>

              <button
                onClick={() => toast.success(`Added missing ingredients for ${recipes[selectedDish].name} to cart!`)}
                className="w-full bg-[#15803D] hover:bg-emerald-700 text-white p-2.5 rounded-xl font-bold text-[10.5px] font-display flex items-center justify-between active:scale-[0.98] transition-all shadow-2xs cursor-pointer"
              >
                <span>{recipes[selectedDish].name}</span>
                <span className="bg-black/20 text-white px-2.5 py-0.5 rounded-full text-[9.5px]">
                  +{recipes[selectedDish].missing} to Cart (₹{recipes[selectedDish].price})
                </span>
              </button>
            </div>
          </CardSurface>
        </div>
      </div>
    </section>
  );
}



