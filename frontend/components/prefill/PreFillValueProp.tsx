"use client";

import React, { useState } from "react";
import { RefreshCw, ShoppingCart, Globe, Mic, Volume2 } from "lucide-react";
import { PreFillVelocityCalculator } from "./PreFillVelocityCalculator";
import { PillBadge } from "../ui/PillBadge";
import { CardSurface } from "../ui/CardSurface";

export function PreFillValueProp() {
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
    { id: "alerts", label: "Live Alert" },
    { id: "velocity", label: "Pantry Velocity" },
    { id: "whatsapp", label: "WhatsApp Restock" },
  ];

  return (
    <section id="features" className="py-20 md:py-28 bg-[#FAFAFA] border-t border-gray-200/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-14">
        {/* Beside 1:1 Two-Column Header */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-end">
          <div className="lg:col-span-7 space-y-3">
            <h2 className="font-serif font-normal text-3xl sm:text-4xl lg:text-[44px] tracking-tight text-gray-950 leading-[1.15]">
              PreFill is the best smart pantry phone app for your household
            </h2>
          </div>
          <div className="lg:col-span-5">
            <p className="text-sm sm:text-base text-gray-500 font-normal leading-relaxed">
              No more opening shopping apps or making grocery lists. PreFill does the thinking for you with 1-tap WhatsApp notifications.
            </p>
          </div>
        </div>

        {/* Beside Sub-Nav Pill Tabs (Reusable PillBadge variant="tab") */}
        <div className="flex items-center gap-2 overflow-x-auto pb-2 border-b border-gray-200/80">
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
        <PreFillVelocityCalculator />

        {/* Beside 1:1 4-Card 2x2 Bento Grid with Deep CardSurface Primitives */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Card 1: Interactive Multi-Item Staple Selector Widget */}
          <CardSurface variant="default">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest flex items-center gap-1.5">
                  <RefreshCw className="w-3.5 h-3.5 text-sky-600" /> Multi-Item Selector
                </span>
                <span className="text-[10px] font-bold text-sky-600 bg-sky-50 px-2 py-0.5 rounded-full border border-sky-100">
                  Click items below
                </span>
              </div>
              <h3 className="text-[15px] font-bold text-gray-950 leading-snug">
                Operate multiple items with your household
              </h3>
              <p className="text-xs text-gray-500 font-normal leading-relaxed">
                PreFill manages milk, eggs, bread, and fruits across all family members.
              </p>
            </div>

            {/* Micro-UI Widget: Clickable Active Item Selector */}
            <div className="bg-gray-50 rounded-2xl p-3 border border-gray-100 space-y-2 text-xs">
              <button
                onClick={() => toggleItemStatus("milk")}
                className="w-full p-2.5 rounded-xl bg-white flex items-center justify-between border border-gray-200/80 shadow-2xs hover:border-sky-300 transition-all text-left cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-full bg-sky-500 text-white font-bold text-[10px] flex items-center justify-center border border-sky-600">
                    KW
                  </div>
                  <div>
                    <p className="font-bold text-gray-900 text-xs">Fresh Milk 1L</p>
                    <p className="text-gray-400 text-[10px] font-mono">+91 99999 • Click to toggle</p>
                  </div>
                </div>
                {itemStatuses.milk === "LOW" ? (
                  <span className="text-[10px] text-rose-600 font-bold bg-rose-50 px-2 py-0.5 rounded border border-rose-100 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping" /> LOW
                  </span>
                ) : (
                  <span className="text-[10px] text-emerald-600 font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-100">
                    OK
                  </span>
                )}
              </button>

              <button
                onClick={() => toggleItemStatus("apples")}
                className="w-full p-2.5 rounded-xl bg-white flex items-center justify-between border border-gray-200/80 hover:border-sky-300 transition-all text-left cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-full bg-indigo-500 text-white font-bold text-[10px] flex items-center justify-center border border-indigo-600">
                    AP
                  </div>
                  <div>
                    <p className="font-bold text-gray-900 text-xs">Organic Apples</p>
                    <p className="text-gray-400 text-[10px] font-mono">+91 88888 • Click to toggle</p>
                  </div>
                </div>
                {itemStatuses.apples === "LOW" ? (
                  <span className="text-[10px] text-rose-600 font-bold bg-rose-50 px-2 py-0.5 rounded border border-rose-100 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping" /> LOW
                  </span>
                ) : (
                  <span className="text-[10px] text-emerald-600 font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-100">
                    OK
                  </span>
                )}
              </button>
            </div>
          </CardSurface>

          {/* Card 2: 3D Vector Wireframe Globe Widget */}
          <CardSurface variant="default">
            <div className="space-y-3">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest flex items-center gap-1.5">
                <Globe className="w-3.5 h-3.5 text-indigo-600" /> Citywide Quick Delivery
              </span>
              <h3 className="text-[15px] font-bold text-gray-950 leading-snug">
                Unlimited 24h alerts across all neighborhoods
              </h3>
              <p className="text-xs text-gray-500 font-normal leading-relaxed">
                Connects with local quick-commerce dark stores in under 10 minutes.
              </p>
            </div>

            {/* Micro-UI Widget: 3D Dotted Vector Globe with Ping Dots */}
            <div className="h-32 bg-indigo-50/50 rounded-2xl border border-indigo-100/80 flex items-center justify-center relative overflow-hidden">
              <div className="w-20 h-20 rounded-full border border-dashed border-indigo-300 flex items-center justify-center animate-spin-slow">
                <div className="w-12 h-12 rounded-full border border-indigo-400/80 flex items-center justify-center relative">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 absolute top-1 right-2 animate-ping" />
                  <Globe className="w-6 h-6 text-indigo-600" />
                </div>
              </div>
            </div>
          </CardSurface>

          {/* Card 3: Light Clean Sky-Blue Accent Card */}
          <CardSurface variant="accent">
            <div className="space-y-3">
              <span className="text-[11px] font-semibold text-sky-700 uppercase tracking-widest flex items-center gap-1.5">
                <ShoppingCart className="w-3.5 h-3.5 text-sky-600" /> Light Accent
              </span>
              <h3 className="text-[15px] font-bold text-gray-950 leading-snug">
                "Deliver fresh milk before breakfast — 1 tap on WhatsApp!"
              </h3>
              <p className="text-xs text-gray-600 font-medium leading-relaxed">
                Good morning Karan! Your milk will run empty in 24 hours.
              </p>
            </div>

            <div className="bg-white p-4 rounded-2xl border border-sky-200/80 shadow-2xs text-center space-y-1">
              <span className="text-2xl font-extrabold text-sky-700 tracking-tight block font-mono">
                24-Hour Notice
              </span>
              <p className="text-[10px] text-gray-500 font-bold">
                Triggered before fridge is empty
              </p>
            </div>
          </CardSurface>

          {/* Card 4: Audio Waveform & Timeline UI Widget */}
          <CardSurface variant="default">
            <div className="space-y-3">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest flex items-center gap-1.5">
                <Mic className="w-3.5 h-3.5 text-purple-600" /> Voice & Text Assistant
              </span>
              <h3 className="text-[15px] font-bold text-gray-950 leading-snug">
                Transcribe, summarize, and auto-restock all staples
              </h3>
              <p className="text-xs text-gray-500 font-normal leading-relaxed">
                Send voice notes or text on WhatsApp to adjust your daily consumption.
              </p>
            </div>

            {/* Micro-UI Widget: Audio Waveform & Timestamp 0:14 / 1:02 */}
            <div className="bg-purple-50/60 p-3 rounded-2xl border border-purple-100 space-y-2 text-xs">
              <div className="flex items-center justify-between text-purple-900 font-bold text-[11px]">
                <div className="flex items-center gap-1.5">
                  <Volume2 className="w-3.5 h-3.5 text-purple-700 animate-pulse" />
                  <span>Voice Note: "Add 6 eggs"</span>
                </div>
                <span className="font-mono text-[10px] text-purple-600 font-normal">0:14 / 1:02</span>
              </div>
              <div className="flex items-center gap-1 h-4">
                <span className="w-1 h-3 bg-purple-500 rounded-full animate-bounce" />
                <span className="w-1 h-4 bg-purple-600 rounded-full animate-bounce [animation-delay:0.1s]" />
                <span className="w-1 h-2 bg-purple-400 rounded-full animate-bounce [animation-delay:0.2s]" />
                <span className="w-1 h-5 bg-purple-700 rounded-full animate-bounce [animation-delay:0.3s]" />
                <span className="w-1 h-3 bg-purple-500 rounded-full animate-bounce [animation-delay:0.15s]" />
              </div>
            </div>
          </CardSurface>
        </div>
      </div>
    </section>
  );
}
