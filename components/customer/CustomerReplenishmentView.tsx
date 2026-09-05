"use client";

import React, { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import PhoneMockup from "../PhoneMockup";
import { WhatsAppIcon } from "../ui/WhatsAppIcon";
import {
  Sliders,
  BookOpen,
  Sparkles,
  Users,
  CheckCircle2,
  RotateCcw,
  Copy,
  Check,
  Clock,
  ArrowRight,
  ArrowLeft,
  Play,
  Pause,
  MapPin,
  Truck,
  Zap,
  ShoppingBag,
  Milk,
  Wheat,
  Egg,
  Apple,
} from "lucide-react";
import {
  CustomerPersona,
  CustomerOrderPayload,
  DarkStore,
} from "../../lib/types";
import {
  SIMULATED_CUSTOMERS,
  DEFAULT_CUSTOMER_PERSONA,
} from "../../lib/mockData";
import { toast } from "sonner";

type DemoLayoutMode = "workbench" | "storyboard" | "showcase";

interface CustomerReplenishmentViewProps {
  activeCustomer?: CustomerPersona;
  onCustomerChange?: (customer: CustomerPersona) => void;
  onPlaceOrder?: (payload: CustomerOrderPayload) => void;
  onScheduleReminder?: (customerId: string, delayHours: number) => void;
  onSkipRestock?: (customerId: string, reason?: string) => void;
  stores?: DarkStore[];
  isLiveApiConnected?: boolean;
}

const PANTRY_ITEMS = [
  {
    name: "Amul Taaza Milk 1L",
    shortName: "Milk",
    category: "Dairy",
    price: 66,
    icon: Milk,
    defaultPct: 12,
    threshold: 15,
  },
  {
    name: "Whole Wheat Bread 400g",
    shortName: "Bread",
    category: "Bakery",
    price: 50,
    icon: Wheat,
    defaultPct: 10,
    threshold: 20,
  },
  {
    name: "Farm Fresh Eggs (12 pcs)",
    shortName: "Eggs",
    category: "Poultry",
    price: 90,
    icon: Egg,
    defaultPct: 35,
    threshold: 25,
  },
  {
    name: "Fresh Hybrid Tomatoes 500g",
    shortName: "Tomatoes",
    category: "Produce",
    price: 32,
    icon: Apple,
    defaultPct: 14,
    threshold: 20,
  },
];

export function CustomerReplenishmentView({
  activeCustomer = DEFAULT_CUSTOMER_PERSONA,
  onCustomerChange,
  onPlaceOrder,
  onScheduleReminder,
  onSkipRestock,
}: CustomerReplenishmentViewProps) {
  const [layoutMode, setLayoutMode] = useState<DemoLayoutMode>("workbench");
  const [resetKey, setResetKey] = useState(0);
  const [lastOrder, setLastOrder] = useState<CustomerOrderPayload | null>(null);
  const [copied, setCopied] = useState(false);

  // Storyboard mode step tracking (0 to 3)
  const [storyStep, setStoryStep] = useState(0);
  const [isAutoPlaying, setIsAutoPlaying] = useState(false);

  // Handle order placement
  const handleOrderConfirmed = useCallback(
    (payload: CustomerOrderPayload) => {
      setLastOrder(payload);
      onPlaceOrder?.(payload);
    },
    [onPlaceOrder]
  );

  // Reset phone simulation
  const handleResetSimulator = useCallback(() => {
    setResetKey((prev) => prev + 1);
    setLastOrder(null);
    toast.info("WhatsApp conversation reset");
  }, []);

  // Copy bot text
  const handleCopyMessage = () => {
    const firstName = activeCustomer.name.split(" ")[0];
    const item = activeCustomer.primaryDepletionItem || "Amul Taaza Milk 1L";
    const text = `Hi ${firstName}, your ${item} is almost finished. Tap below to order now.`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    toast.success("WhatsApp message copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  };

  // Deplete an item to trigger phone alert
  const handleTriggerDepletion = (itemName: string) => {
    if (onCustomerChange) {
      onCustomerChange({
        ...activeCustomer,
        primaryDepletionItem: itemName,
      });
    }
    setResetKey((prev) => prev + 1);
    setLastOrder(null);
    toast.success(`Simulated depletion for ${itemName.split(" ")[0]}`);
  };

  // Auto-play for storyboard mode
  useEffect(() => {
    if (!isAutoPlaying || layoutMode !== "storyboard") return;
    const interval = setInterval(() => {
      setStoryStep((prev) => (prev + 1) % 4);
    }, 4500);
    return () => clearInterval(interval);
  }, [isAutoPlaying, layoutMode]);

  const firstName = activeCustomer.name.split(" ")[0];
  const primaryItemName = activeCustomer.primaryDepletionItem || "Amul Taaza Milk 1L";

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
      className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6"
    >
      {/* 1. Header & Sub-Navigation Segmented Switcher */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-5 border-b border-zinc-200">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
            <WhatsAppIcon className="w-3.5 h-3.5 shrink-0" />
            <span>Customer Replenishment Engine</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-zinc-950 font-sans mt-2">
            Pantry-Aware Reordering via WhatsApp
          </h1>
          <p className="text-xs sm:text-sm text-zinc-600 max-w-2xl mt-1">
            Predicts when household essentials run low and sends a timely WhatsApp message.
            Households reorder in one tap without opening an app or searching catalogs.
          </p>
        </div>

        {/* Segmented Layout Mode Switcher */}
        <div className="flex items-center bg-zinc-100 p-1 rounded-lg border border-zinc-200 shrink-0 self-start md:self-auto">
          <button
            type="button"
            onClick={() => setLayoutMode("workbench")}
            className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-md transition-all cursor-pointer ${
              layoutMode === "workbench"
                ? "bg-white text-zinc-950 shadow-xs border border-zinc-200/80 font-bold"
                : "text-zinc-600 hover:text-zinc-900"
            }`}
          >
            <Sliders className="w-3.5 h-3.5" />
            <span>Studio Workbench</span>
          </button>
          <button
            type="button"
            onClick={() => setLayoutMode("storyboard")}
            className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-md transition-all cursor-pointer ${
              layoutMode === "storyboard"
                ? "bg-white text-zinc-950 shadow-xs border border-zinc-200/80 font-bold"
                : "text-zinc-600 hover:text-zinc-900"
            }`}
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>Guided Storyboard</span>
          </button>
          <button
            type="button"
            onClick={() => setLayoutMode("showcase")}
            className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-md transition-all cursor-pointer ${
              layoutMode === "showcase"
                ? "bg-white text-zinc-950 shadow-xs border border-zinc-200/80 font-bold"
                : "text-zinc-600 hover:text-zinc-900"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Hero Showcase</span>
          </button>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* MODE 1: STUDIO WORKBENCH (3-Column Layout) */}
      {/* ========================================================================= */}
      {layoutMode === "workbench" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          
          {/* Column A: Household & Pantry Depletion Controls (4 cols) */}
          <div className="lg:col-span-4 space-y-4">
            
            {/* Household Persona Card */}
            <div className="p-4 rounded-xl bg-white border border-zinc-200 shadow-2xs space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Users className="w-4 h-4 text-zinc-700" />
                  <span className="text-xs font-bold text-zinc-900">Active Household</span>
                </div>
                <span className="text-[11px] font-mono text-zinc-500">25 Profiles</span>
              </div>

              {/* Persona Quick Grid */}
              <div className="grid grid-cols-2 gap-2">
                {SIMULATED_CUSTOMERS.slice(0, 4).map((cust) => {
                  const isSelected = cust.id === activeCustomer.id;
                  return (
                    <button
                      key={cust.id}
                      type="button"
                      onClick={() => {
                        onCustomerChange?.(cust);
                        setResetKey((prev) => prev + 1);
                        setLastOrder(null);
                      }}
                      className={`p-2 rounded-lg border text-left transition-all cursor-pointer ${
                        isSelected
                          ? "bg-blue-50/80 border-blue-500 ring-1 ring-blue-500 text-blue-950"
                          : "bg-zinc-50 hover:bg-zinc-100 border-zinc-200 text-zinc-700"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="w-5 h-5 rounded-md bg-white border border-zinc-300 flex items-center justify-center font-mono font-bold text-[9px] text-zinc-800 shrink-0">
                          {cust.avatar}
                        </span>
                        <div className="min-w-0 flex-1">
                          <div className="text-[11px] font-bold truncate leading-tight">{cust.name}</div>
                          <div className="text-[9px] text-zinc-500 truncate leading-tight mt-0.5 font-mono">
                            {cust.householdSize} People
                          </div>
                        </div>
                        {isSelected && <CheckCircle2 className="w-3 h-3 text-blue-600 shrink-0" />}
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Household Metadata */}
              <div className="pt-2 border-t border-zinc-100 flex items-center justify-between text-[11px] text-zinc-600">
                <div className="flex items-center gap-1.5 truncate">
                  <MapPin className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
                  <span className="truncate">{activeCustomer.address}</span>
                </div>
                <span className="font-mono font-medium shrink-0 ml-2">Every {activeCustomer.orderFrequencyDays}d</span>
              </div>
            </div>

            {/* Household Fridge & Pantry Monitor */}
            <div className="p-4 rounded-xl bg-white border border-zinc-200 shadow-2xs space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs font-bold text-zinc-900 block">Fridge & Pantry Levels</span>
                  <span className="text-[10px] text-zinc-500">Tap an item to simulate running out</span>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-zinc-100 text-zinc-700 font-semibold">
                  Live Gauges
                </span>
              </div>

              {/* Pantry Gauges List */}
              <div className="space-y-2.5">
                {PANTRY_ITEMS.map((item) => {
                  const isDepleted = activeCustomer.primaryDepletionItem === item.name;
                  const Icon = item.icon;
                  const levelPct = isDepleted ? item.defaultPct : 75;
                  const isLow = levelPct <= item.threshold;

                  return (
                    <div
                      key={item.name}
                      onClick={() => handleTriggerDepletion(item.name)}
                      className={`p-2.5 rounded-lg border transition-all cursor-pointer ${
                        isDepleted
                          ? "bg-amber-50/70 border-amber-300 ring-1 ring-amber-300"
                          : "bg-zinc-50 hover:bg-zinc-100/80 border-zinc-200"
                      }`}
                    >
                      <div className="flex items-center justify-between text-xs mb-1.5">
                        <div className="flex items-center gap-2">
                          <div className={`w-6 h-6 rounded-md flex items-center justify-center ${
                            isDepleted ? "bg-amber-100 text-amber-800" : "bg-white text-zinc-600 border border-zinc-200"
                          }`}>
                            <Icon className="w-3.5 h-3.5" />
                          </div>
                          <div>
                            <span className="font-semibold text-zinc-900 text-[11px] block leading-tight">
                              {item.shortName}
                            </span>
                            <span className="text-[9px] text-zinc-500 font-mono">₹{item.price}</span>
                          </div>
                        </div>

                        <div className="text-right">
                          <span className={`text-[10.5px] font-mono font-bold ${
                            isLow ? "text-amber-700" : "text-emerald-700"
                          }`}>
                            {levelPct}%
                          </span>
                          <span className="text-[9px] text-zinc-400 block font-sans">
                            {isLow ? "⚠️ Reorder Alert" : "Adequate"}
                          </span>
                        </div>
                      </div>

                      {/* Level Progress Bar */}
                      <div className="w-full bg-zinc-200 h-1.5 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-300 ${
                            isLow ? "bg-amber-500" : "bg-emerald-500"
                          }`}
                          style={{ width: `${levelPct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Quick Scenario Triggers */}
              <div className="pt-2 border-t border-zinc-100 space-y-1.5">
                <span className="text-[10.5px] font-medium text-zinc-500 block">Simulate Morning Scenarios:</span>
                <div className="grid grid-cols-2 gap-1.5 text-[10px]">
                  <button
                    type="button"
                    onClick={() => handleTriggerDepletion("Amul Taaza Milk 1L")}
                    className="p-1.5 rounded-md bg-zinc-50 hover:bg-zinc-100 border border-zinc-200 text-zinc-800 text-left font-medium transition-colors cursor-pointer truncate"
                  >
                    🥛 Morning Tea Rush
                  </button>
                  <button
                    type="button"
                    onClick={() => handleTriggerDepletion("Whole Wheat Bread 400g")}
                    className="p-1.5 rounded-md bg-zinc-50 hover:bg-zinc-100 border border-zinc-200 text-zinc-800 text-left font-medium transition-colors cursor-pointer truncate"
                  >
                    🍞 Breakfast Toast Alert
                  </button>
                </div>
              </div>
            </div>

            {/* Consumer Experience Highlights */}
            <div className="p-3.5 rounded-xl bg-zinc-50 border border-zinc-200/80 space-y-2 text-xs">
              <div className="flex items-center gap-2 font-bold text-zinc-900">
                <Zap className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                <span>Zero-App Friction</span>
              </div>
              <p className="text-[11px] text-zinc-600 leading-relaxed">
                Households never have to unlock an app, search 50 brands, or remember to reorder milk. The notification arrives at their usual morning tea time.
              </p>
            </div>
          </div>

          {/* Column B: Authentic iPhone 17 Pro Spotlight (4 cols) */}
          <div className="lg:col-span-4 flex flex-col items-center">
            
            {/* Top Device Control Strip */}
            <div className="w-[290px] mb-2.5 flex items-center justify-between px-2.5 py-1.5 bg-white rounded-lg border border-zinc-200 shadow-2xs text-xs">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-[11px] font-semibold text-zinc-800">WhatsApp Simulator</span>
              </div>

              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={handleCopyMessage}
                  title="Copy WhatsApp Message"
                  className="p-1 rounded hover:bg-zinc-100 text-zinc-500 hover:text-zinc-800 transition-colors cursor-pointer"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
                <button
                  type="button"
                  onClick={handleResetSimulator}
                  title="Reset WhatsApp Conversation"
                  className="p-1 rounded hover:bg-zinc-100 text-zinc-500 hover:text-zinc-800 transition-colors cursor-pointer"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* Calibrated iPhone 17 Pro Frame */}
            <div className="w-[290px] h-[593px] aspect-[1800/3680] shrink-0 relative z-10">
              <PhoneMockup
                key={`${activeCustomer.id}-${activeCustomer.primaryDepletionItem}-${resetKey}`}
                activeScenario="milk_shortage"
                initialViewMode="whatsapp"
                activeCustomer={activeCustomer}
                onCustomerChange={onCustomerChange}
                onPlaceOrder={handleOrderConfirmed}
                onScheduleReminder={onScheduleReminder}
                onSkipRestock={onSkipRestock}
              />
            </div>
          </div>

          {/* Column C: Consumer Order Receipt & Express ETA (4 cols) */}
          <div className="lg:col-span-4 space-y-4">
            
            {/* Live Order Confirmation Card */}
            <div className="p-4 rounded-xl bg-white border border-zinc-200 shadow-2xs space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShoppingBag className="w-4 h-4 text-emerald-600" />
                  <span className="text-xs font-bold text-zinc-900">Consumer Order Status</span>
                </div>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full font-bold ${
                  lastOrder ? "bg-emerald-50 text-emerald-800 border border-emerald-200" : "bg-zinc-100 text-zinc-600"
                }`}>
                  {lastOrder ? "DISPATCHED" : "AWAITING ACTION"}
                </span>
              </div>

              {lastOrder ? (
                <div className="space-y-3 pt-1">
                  {/* Delivery ETA Pill */}
                  <div className="p-3 bg-emerald-50/80 rounded-lg border border-emerald-200 space-y-1">
                    <div className="flex items-center gap-1.5 text-emerald-950 font-bold text-xs">
                      <Truck className="w-4 h-4 text-emerald-700" />
                      <span>Arriving in 11 Mins</span>
                    </div>
                    <p className="text-[10.5px] text-emerald-800 leading-snug">
                      Order dispatched via express rider to {lastOrder.address || activeCustomer.address}.
                    </p>
                  </div>

                  {/* Itemized Breakdown */}
                  <div className="p-3 bg-zinc-50 rounded-lg border border-zinc-100 space-y-2">
                    <span className="text-[10px] font-mono text-zinc-500 block uppercase tracking-wider">
                      Itemized Receipt
                    </span>
                    <div className="space-y-1.5">
                      {lastOrder.items.map((item, idx) => (
                        <div key={idx} className="flex items-center justify-between text-xs">
                          <span className="text-zinc-800 font-medium">
                            {item.quantity}× {item.productName.split(" ").slice(0, 3).join(" ")}
                          </span>
                          <span className="font-mono font-semibold text-zinc-900">
                            ₹{item.priceINR * item.quantity}
                          </span>
                        </div>
                      ))}
                    </div>

                    <div className="pt-2 border-t border-zinc-200 flex items-center justify-between text-xs font-bold text-zinc-950">
                      <span>Total (Cash / UPI on Delivery)</span>
                      <span className="font-mono text-emerald-700">₹{lastOrder.totalINR}</span>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={handleResetSimulator}
                    className="w-full py-2 rounded-lg bg-zinc-100 hover:bg-zinc-200 text-zinc-800 text-xs font-semibold transition-colors cursor-pointer flex items-center justify-center gap-1.5"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>Test Another Order</span>
                  </button>
                </div>
              ) : (
                <div className="py-6 px-3 text-center space-y-2.5">
                  <div className="w-10 h-10 rounded-full bg-zinc-100 flex items-center justify-center mx-auto text-zinc-400">
                    <Clock className="w-5 h-5" />
                  </div>
                  <div>
                    <span className="text-xs font-semibold text-zinc-800 block">No Order Placed Yet</span>
                    <p className="text-[11px] text-zinc-500 max-w-xs mx-auto mt-0.5 leading-snug">
                      Tap <strong className="text-zinc-700 font-bold">Confirm Restock</strong> inside the phone simulator to test the 1-tap reordering flow.
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* How It Replaces Traditional Apps */}
            <div className="p-4 rounded-xl bg-white border border-zinc-200 shadow-2xs space-y-3">
              <span className="text-xs font-bold text-zinc-900 block">Why WhatsApp Works Better</span>
              
              <div className="space-y-2 text-[11px]">
                <div className="flex items-start gap-2">
                  <span className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-800 flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5">✓</span>
                  <div>
                    <strong className="text-zinc-900 block font-semibold">1-Tap Quick Action</strong>
                    <span className="text-zinc-500">Native buttons inside WhatsApp — no password, no OTP, no cart checkout screen.</span>
                  </div>
                </div>

                <div className="flex items-start gap-2">
                  <span className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-800 flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5">✓</span>
                  <div>
                    <strong className="text-zinc-900 block font-semibold">Smart Complementary Suggestion</strong>
                    <span className="text-zinc-500">Pairs frequently consumed items like Fresh Bread with milk automatically.</span>
                  </div>
                </div>

                <div className="flex items-start gap-2">
                  <span className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-800 flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5">✓</span>
                  <div>
                    <strong className="text-zinc-900 block font-semibold">Flexible Snooze</strong>
                    <span className="text-zinc-500">Customer not home? Tap &apos;Remind Later&apos; to defer notification by 2 hours.</span>
                  </div>
                </div>
              </div>
            </div>

          </div>

        </div>
      )}

      {/* ========================================================================= */}
      {/* MODE 2: GUIDED STORYBOARD (Staged 4-Step Interactive Tour) */}
      {/* ========================================================================= */}
      {layoutMode === "storyboard" && (
        <div className="space-y-6">
          {/* Step Progress Bar */}
          <div className="grid grid-cols-4 gap-2">
            {[
              { num: "01", title: "Pantry Depletion", desc: "Milk drops < 15%" },
              { num: "02", title: "WhatsApp Ping", desc: "Timely morning alert" },
              { num: "03", title: "1-Tap Action", desc: "Add bread & confirm" },
              { num: "04", title: "Express Dispatch", desc: "Doorstep in 11 mins" },
            ].map((step, idx) => {
              const isActive = storyStep === idx;
              const isPast = storyStep > idx;
              return (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setStoryStep(idx)}
                  className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                    isActive
                      ? "bg-emerald-50/80 border-emerald-500 ring-1 ring-emerald-500 text-emerald-950 shadow-2xs"
                      : isPast
                      ? "bg-zinc-50 border-zinc-200 text-zinc-900"
                      : "bg-white border-zinc-200 text-zinc-500"
                  }`}
                >
                  <div className="flex items-center justify-between text-xs font-mono font-bold mb-1">
                    <span>{step.num}</span>
                    {isPast && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />}
                  </div>
                  <div className="text-xs font-bold leading-tight truncate">{step.title}</div>
                  <div className="text-[10px] text-zinc-500 truncate mt-0.5">{step.desc}</div>
                </button>
              );
            })}
          </div>

          {/* Storyboard Split Content */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center bg-white p-6 sm:p-8 rounded-2xl border border-zinc-200 shadow-2xs">
            
            {/* Left Story Narrative (6 cols) */}
            <div className="lg:col-span-6 space-y-5">
              <div className="space-y-2">
                <span className="text-xs font-mono font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200 inline-block">
                  Phase {storyStep + 1} of 4
                </span>
                
                {storyStep === 0 && (
                  <div className="space-y-3">
                    <h2 className="text-2xl font-bold tracking-tight text-zinc-950 font-sans">
                      Predictive Depletion Detection in the Household
                    </h2>
                    <p className="text-sm text-zinc-600 leading-relaxed">
                      {firstName}&apos;s household of {activeCustomer.householdSize} consumes milk every {activeCustomer.orderFrequencyDays} days. Grocer calculates consumption velocity based on past replenishment history. At 7:55 AM, the pantry level drops below the 15% safety threshold.
                    </p>
                    <div className="p-3.5 bg-zinc-50 rounded-xl border border-zinc-200 space-y-1.5 text-xs text-zinc-700">
                      <div className="font-semibold text-zinc-900">Why this matters:</div>
                      <p className="text-zinc-600 text-[11.5px]">
                        Traditional grocery apps wait for the customer to open the fridge, discover they are out of milk, get frustrated, and open a competing quick-commerce app. Grocer anticipates the need beforehand.
                      </p>
                    </div>
                  </div>
                )}

                {storyStep === 1 && (
                  <div className="space-y-3">
                    <h2 className="text-2xl font-bold tracking-tight text-zinc-950 font-sans">
                      Proactive WhatsApp Notification Ping
                    </h2>
                    <p className="text-sm text-zinc-600 leading-relaxed">
                      Instead of a noisy generic push notification that gets swiped away, Grocer sends a personalized WhatsApp message directly from the verified business account at 8:00 AM.
                    </p>
                    <div className="p-3.5 bg-emerald-50/70 rounded-xl border border-emerald-200 space-y-1 text-xs text-emerald-950">
                      <div className="font-bold">Message preview:</div>
                      <p className="font-mono text-[11px] text-emerald-900">
                        &quot;Hi {firstName}, your {primaryItemName} is almost finished. Tap below to order now.&quot;
                      </p>
                    </div>
                  </div>
                )}

                {storyStep === 2 && (
                  <div className="space-y-3">
                    <h2 className="text-2xl font-bold tracking-tight text-zinc-950 font-sans">
                      Frictionless 1-Tap Quick Action Buttons
                    </h2>
                    <p className="text-sm text-zinc-600 leading-relaxed">
                      WhatsApp interactive quick-reply buttons allow {firstName} to take instant action directly within the chat screen.
                    </p>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="p-2.5 bg-zinc-50 rounded-lg border border-zinc-200">
                        <span className="font-bold block text-zinc-900">1-Tap Reorder</span>
                        <span className="text-[10.5px] text-zinc-500">Confirms {primaryItemName} in 1 tap</span>
                      </div>
                      <div className="p-2.5 bg-zinc-50 rounded-lg border border-zinc-200">
                        <span className="font-bold block text-zinc-900">Smart Complementary</span>
                        <span className="text-[10.5px] text-zinc-500">+ Add Bread (₹50) in 1 tap</span>
                      </div>
                      <div className="p-2.5 bg-zinc-50 rounded-lg border border-zinc-200">
                        <span className="font-bold block text-zinc-900">Remind Later</span>
                        <span className="text-[10.5px] text-zinc-500">Snooze alert by 2 hours</span>
                      </div>
                      <div className="p-2.5 bg-zinc-50 rounded-lg border border-zinc-200">
                        <span className="font-bold block text-zinc-900">Not Now</span>
                        <span className="text-[10.5px] text-zinc-500">Polite skip without spam</span>
                      </div>
                    </div>
                  </div>
                )}

                {storyStep === 3 && (
                  <div className="space-y-3">
                    <h2 className="text-2xl font-bold tracking-tight text-zinc-950 font-sans">
                      Instant 11-Minute Doorstep Fulfillment
                    </h2>
                    <p className="text-sm text-zinc-600 leading-relaxed">
                      The moment {firstName} taps confirm, the order is routed directly to the fulfillment rider and arrives at {activeCustomer.address} within 11 minutes.
                    </p>
                    <div className="p-3.5 bg-zinc-50 rounded-xl border border-zinc-200 space-y-2 text-xs">
                      <div className="flex items-center justify-between font-bold text-zinc-950">
                        <span className="flex items-center gap-1.5">
                          <Truck className="w-4 h-4 text-emerald-600" />
                          <span>Express Dispatch</span>
                        </span>
                        <span className="font-mono text-emerald-700">11 Mins ETA</span>
                      </div>
                      <p className="text-[11px] text-zinc-500">
                        Household pantry replenished automatically before breakfast without opening a shopping cart once.
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* Tour Controls */}
              <div className="flex items-center gap-3 pt-2">
                <button
                  type="button"
                  disabled={storyStep === 0}
                  onClick={() => setStoryStep((prev) => Math.max(0, prev - 1))}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-200 text-zinc-700 hover:bg-zinc-50 text-xs font-semibold disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  <span>Previous</span>
                </button>

                <button
                  type="button"
                  disabled={storyStep === 3}
                  onClick={() => setStoryStep((prev) => Math.min(3, prev + 1))}
                  className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer shadow-2xs"
                >
                  <span>Next Step</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>

                <button
                  type="button"
                  onClick={() => setIsAutoPlaying(!isAutoPlaying)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-semibold transition-colors cursor-pointer ml-auto ${
                    isAutoPlaying
                      ? "bg-amber-50 border-amber-300 text-amber-900"
                      : "bg-zinc-50 border-zinc-200 text-zinc-700 hover:bg-zinc-100"
                  }`}
                >
                  {isAutoPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                  <span>{isAutoPlaying ? "Pause Auto-Tour" : "Auto-Tour"}</span>
                </button>
              </div>
            </div>

            {/* Right Phone Mockup (6 cols) */}
            <div className="lg:col-span-6 flex justify-center items-center">
              <div className="w-[290px] h-[593px] aspect-[1800/3680] shrink-0 relative z-10">
                <PhoneMockup
                  key={`story-${storyStep}-${activeCustomer.id}`}
                  activeScenario="milk_shortage"
                  initialViewMode="whatsapp"
                  activeCustomer={activeCustomer}
                  onCustomerChange={onCustomerChange}
                  onPlaceOrder={handleOrderConfirmed}
                  onScheduleReminder={onScheduleReminder}
                  onSkipRestock={onSkipRestock}
                />
              </div>
            </div>

          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODE 3: HERO SHOWCASE (Apple-Style Clean Spotlight) */}
      {/* ========================================================================= */}
      {layoutMode === "showcase" && (
        <div className="py-6 flex flex-col items-center justify-center space-y-8">
          
          {/* Centered Device Presentation with Floating Badges */}
          <div className="relative flex flex-col items-center">
            
            {/* Floating Context Card 1: Top Left */}
            <div className="hidden lg:block absolute -left-64 top-16 w-56 p-3.5 rounded-xl bg-white/95 backdrop-blur-md border border-zinc-200 shadow-sm space-y-1 text-left">
              <div className="flex items-center gap-1.5 text-xs font-bold text-zinc-900">
                <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                <span>Pantry-Aware Intelligence</span>
              </div>
              <p className="text-[11px] text-zinc-500 leading-snug">
                Predicts kitchen depletion based on family size ({activeCustomer.householdSize} people) and past order velocity.
              </p>
            </div>

            {/* Floating Context Card 2: Bottom Left */}
            <div className="hidden lg:block absolute -left-64 bottom-24 w-56 p-3.5 rounded-xl bg-white/95 backdrop-blur-md border border-zinc-200 shadow-sm space-y-1 text-left">
              <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-900">
                <WhatsAppIcon className="w-3.5 h-3.5" />
                <span>1-Tap WhatsApp Reorder</span>
              </div>
              <p className="text-[11px] text-zinc-500 leading-snug">
                Zero friction. Native interactive buttons right inside WhatsApp with no checkout screens.
              </p>
            </div>

            {/* Floating Context Card 3: Top Right */}
            <div className="hidden lg:block absolute -right-64 top-16 w-56 p-3.5 rounded-xl bg-white/95 backdrop-blur-md border border-zinc-200 shadow-sm space-y-1 text-left">
              <div className="flex items-center gap-1.5 text-xs font-bold text-zinc-900">
                <Truck className="w-3.5 h-3.5 text-emerald-600" />
                <span>11-Minute Doorstep Delivery</span>
              </div>
              <p className="text-[11px] text-zinc-500 leading-snug">
                Fulfills directly to {activeCustomer.address} before morning breakfast.
              </p>
            </div>

            {/* Floating Context Card 4: Bottom Right */}
            <div className="hidden lg:block absolute -right-64 bottom-24 w-56 p-3.5 rounded-xl bg-white/95 backdrop-blur-md border border-zinc-200 shadow-sm space-y-1 text-left">
              <div className="flex items-center gap-1.5 text-xs font-bold text-zinc-900">
                <ShoppingBag className="w-3.5 h-3.5 text-amber-600" />
                <span>Smart Cross-Sell</span>
              </div>
              <p className="text-[11px] text-zinc-500 leading-snug">
                Suggested complementary staple (+ Add Bread for ₹50) increases average basket size naturally.
              </p>
            </div>

            {/* Phone Mockup Canvas */}
            <div className="w-[290px] h-[593px] aspect-[1800/3680] shrink-0 relative z-10 mx-auto">
              <PhoneMockup
                key={`showcase-${activeCustomer.id}-${resetKey}`}
                activeScenario="milk_shortage"
                initialViewMode="whatsapp"
                activeCustomer={activeCustomer}
                onCustomerChange={onCustomerChange}
                onPlaceOrder={handleOrderConfirmed}
                onScheduleReminder={onScheduleReminder}
                onSkipRestock={onSkipRestock}
              />
            </div>
          </div>

          {/* Quick Household Switcher Bar */}
          <div className="flex flex-wrap items-center justify-center gap-2 max-w-xl">
            <span className="text-xs text-zinc-500 font-medium">Switch household:</span>
            {SIMULATED_CUSTOMERS.slice(0, 4).map((cust) => (
              <button
                key={cust.id}
                type="button"
                onClick={() => {
                  onCustomerChange?.(cust);
                  setResetKey((prev) => prev + 1);
                  setLastOrder(null);
                }}
                className={`px-3 py-1 rounded-full text-xs font-semibold border transition-all cursor-pointer ${
                  cust.id === activeCustomer.id
                    ? "bg-zinc-900 text-white border-zinc-900 shadow-2xs"
                    : "bg-white hover:bg-zinc-50 text-zinc-700 border-zinc-200"
                }`}
              >
                {cust.name}
              </button>
            ))}
          </div>

        </div>
      )}

    </motion.div>
  );
}
