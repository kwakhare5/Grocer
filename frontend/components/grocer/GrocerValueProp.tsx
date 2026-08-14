"use client";

import React, { useState } from "react";
import { RefreshCw, ShieldAlert, Cpu, BookOpen } from "lucide-react";
import { GrocerVelocityCalculator } from "./GrocerVelocityCalculator";
import { PillBadge } from "../ui/PillBadge";
import { CardSurface } from "../ui/CardSurface";

export function GrocerValueProp() {
  const [activeTab, setActiveTab] = useState("overview");

  // Interactive Bento Item Staple Selector State
  const [itemStatuses, setItemStatuses] = useState({
    milk: "LOW",
    apples: "OK",
    bread: "OK",
  });

  const toggleItemStatus = (key: keyof typeof itemStatuses) => {
    setItemStatuses((prev) => ({
      ...prev,
      [key]: prev[key] === "LOW" ? "OK" : "LOW",
    }));
  };

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "prophet", label: "Prophet ML Engine" },
    { id: "anomaly", label: "Anomaly Filter" },
    { id: "langgraph", label: "LangGraph Agent" },
    { id: "recipe", label: "Recipe Fulfiller" },
  ];

  return (
    <section id="features" className="py-20 md:py-28 bg-[#FCFCFD] border-t border-gray-200/40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-14">
        {/* Two-Column Header */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-end">
          <div className="lg:col-span-7 space-y-3">
            <h2 className="font-serif font-normal text-3xl sm:text-4xl lg:text-[44px] tracking-tight text-gray-950 leading-[1.15]">
              Core Backend Engine & Agent Capabilities
            </h2>
          </div>
          <div className="lg:col-span-5">
            <p className="text-sm sm:text-base text-gray-500 font-normal leading-relaxed">
              Powered by Prophet ML forecasts, automated anomaly filtering, and a 5-node LangGraph execution state machine.
            </p>
          </div>
        </div>

        {/* Sub-Nav Pill Tabs */}
        <div className="flex items-center gap-2 overflow-x-auto pb-2 border-b border-gray-200/40 no-scrollbar">
          {tabs.map((tab) => (
            <PillBadge
              key={tab.id}
              variant="tab"
              active={activeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </PillBadge>
          ))}
        </div>

        {/* Interactive Depletion Velocity Calculator */}
        <GrocerVelocityCalculator />

        {/* 4-Card Bento Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Card 1: Prophet ML Depletion Engine */}
          <CardSurface variant="default" className="flex flex-col justify-between h-full">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest flex items-center gap-1.5">
                  <RefreshCw className="w-3.5 h-3.5 text-sky-600" /> Prophet ML Engine
                </span>
                <span className="text-[9px] font-bold text-sky-700 bg-sky-50 px-2 py-0.5 rounded-full border border-sky-100 font-mono">
                  0.48L / day
                </span>
              </div>
              <h3 className="text-[15px] font-bold text-gray-950 leading-snug">
                Item Depletion Forecasting
              </h3>
              <p className="text-xs text-gray-500 font-normal leading-relaxed">
                Calculates daily usage rates per staple and projects exact stockout dates 24 hours in advance.
              </p>
            </div>

            <div className="bg-gray-50/80 rounded-2xl p-3 border border-gray-100 space-y-2 text-xs mt-4">
              <button
                onClick={() => toggleItemStatus("milk")}
                className="w-full p-2.5 rounded-xl bg-white flex items-center justify-between border border-gray-200/80 shadow-2xs hover:border-sky-300 transition-all text-left cursor-pointer"
              >
                <div>
                  <p className="font-bold text-gray-900 text-xs">Fresh Milk 1L</p>
                  <p className="text-gray-400 text-[10px] font-mono">Tap to simulate depletion</p>
                </div>
                {itemStatuses.milk === "LOW" ? (
                  <span className="text-[10px] text-rose-600 font-bold bg-rose-50 px-2 py-0.5 rounded border border-rose-100 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping" /> 24H ALERT
                  </span>
                ) : (
                  <span className="text-[10px] text-emerald-600 font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-100">
                    STOCKED
                  </span>
                )}
              </button>
            </div>
          </CardSurface>

          {/* Card 2: Anomaly Exclusion Filter */}
          <CardSurface variant="default" className="flex flex-col justify-between h-full">
            <div className="space-y-3">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest flex items-center gap-1.5">
                <ShieldAlert className="w-3.5 h-3.5 text-amber-600" /> Anomaly Exclusion
              </span>
              <h3 className="text-[15px] font-bold text-gray-950 leading-snug">
                Filters Out Temporary Spikes
              </h3>
              <p className="text-xs text-gray-500 font-normal leading-relaxed">
                Automatically ignores guest visits (&gt;2.5x baseline) and travel gaps (&gt;5 days) so models stay clean.
              </p>
            </div>

            <div className="bg-amber-50/40 p-3 rounded-2xl border border-amber-100 text-xs mt-4 space-y-1">
              <span className="text-[10px] font-bold text-amber-900 uppercase tracking-wider block">
                Rule: Baseline Gate
              </span>
              <p className="text-[11px] text-amber-800 font-medium">
                Bulk purchases &gt; 2.5x are marked as guests and excluded from model.
              </p>
            </div>
          </CardSurface>

          {/* Card 3: 5-Node LangGraph Agent */}
          <CardSurface variant="accent" className="flex flex-col justify-between h-full">
            <div className="space-y-3">
              <span className="text-[11px] font-semibold text-sky-700 uppercase tracking-widest flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5 text-sky-600" /> LangGraph Agent
              </span>
              <h3 className="text-[15px] font-bold text-gray-950 leading-snug">
                5-Node Agent Execution Graph
              </h3>
              <p className="text-xs text-gray-600 font-medium leading-relaxed">
                Runs check_pantry → generate_alert → parse_user_reply → build_cart → execute_order.
              </p>
            </div>

            <div className="bg-white p-3 rounded-2xl border border-sky-200/60 text-center space-y-1 mt-4">
              <span className="text-sm font-bold text-sky-800 font-mono block">
                5-Node LangGraph
              </span>
              <p className="text-[10px] text-gray-400 font-medium">
                Postgres Checkpointer State
              </p>
            </div>
          </CardSurface>

          {/* Card 4: Recipe Pantry Fulfiller */}
          <CardSurface variant="default" className="flex flex-col justify-between h-full">
            <div className="space-y-3">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest flex items-center gap-1.5">
                <BookOpen className="w-3.5 h-3.5 text-emerald-600" /> Recipe Agent
              </span>
              <h3 className="text-[15px] font-bold text-gray-950 leading-snug">
                Recipe Pantry Fulfiller
              </h3>
              <p className="text-xs text-gray-500 font-normal leading-relaxed">
                Parses recipes, cross-checks pantry inventory, and adds only missing ingredients to cart in 1 tap.
              </p>
            </div>

            <div className="bg-emerald-50/40 p-3 rounded-2xl border border-emerald-100 text-xs mt-4 flex items-center justify-between text-emerald-900 font-bold">
              <span>Paneer Butter Masala</span>
              <span className="text-[9px] bg-emerald-600 text-white px-2 py-0.5 rounded-full font-mono">
                +2 Missing to Cart
              </span>
            </div>
          </CardSurface>
        </div>
      </div>
    </section>
  );
}



