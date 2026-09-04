"use client";

import React from "react";
import { motion } from "framer-motion";
import PhoneMockup from "../PhoneMockup";
import {
  Sparkles,
  RefreshCw,
  Store as StoreIcon,
  Users,
  CheckCircle,
  Zap,
} from "lucide-react";
import { CustomerPersona, CustomerOrderPayload, DarkStore } from "../../lib/types";
import { SIMULATED_CUSTOMERS, DEFAULT_CUSTOMER_PERSONA } from "../../lib/mockData";

interface CustomerReplenishmentViewProps {
  activeCustomer?: CustomerPersona;
  onCustomerChange?: (customer: CustomerPersona) => void;
  onPlaceOrder?: (payload: CustomerOrderPayload) => void;
  onScheduleReminder?: (customerId: string, delayHours: number) => void;
  onSkipRestock?: (customerId: string, reason?: string) => void;
  stores?: DarkStore[];
  isLiveApiConnected?: boolean;
}

export function CustomerReplenishmentView({
  activeCustomer = DEFAULT_CUSTOMER_PERSONA,
  onCustomerChange,
  onPlaceOrder,
  onScheduleReminder,
  onSkipRestock,
  stores = [],
  isLiveApiConnected = false,
}: CustomerReplenishmentViewProps) {
  // Find matching dark store from shared state
  const homeStore = stores.find(
    (s) => s.name.toLowerCase().includes(activeCustomer.homeStoreName.toLowerCase()) || s.code === activeCustomer.homeStoreCode
  );

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex-1 flex flex-col justify-center"
    >
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
        
        {/* Left Control & Flow Walkthrough (5 cols) */}
        <div className="lg:col-span-5 space-y-5">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold bg-blue-50 text-blue-800 border border-blue-200">
                <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                Customer WhatsApp & Pantry Simulator
              </span>
              {isLiveApiConnected && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10.5px] font-mono font-semibold bg-blue-500/10 text-blue-600 border border-blue-500/20">
                  <Zap className="w-3 h-3 text-blue-600" />
                  FastAPI Sync Active
                </span>
              )}
            </div>
            <h1 className="text-2xl lg:text-3xl font-bold tracking-tight text-zinc-950 font-sans">
              Automatic WhatsApp Restocking Connected to Local Dark Stores
            </h1>
            <p className="text-xs lg:text-sm text-zinc-600 leading-relaxed">
              When kitchen staples run low, Grocer sends a timely WhatsApp restock alert. Confirming an order reserves items at the nearest store and updates inventory instantly.
            </p>
          </div>

          {/* Customer Persona Selector */}
          <div className="p-3.5 rounded-xl bg-white border border-zinc-200 shadow-2xs space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Users className="w-4 h-4 text-zinc-700" />
                <span className="text-xs font-bold text-zinc-900">Simulated Household Persona</span>
              </div>
              <span className="text-[11px] font-mono text-zinc-500">25 Households Active</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
              {SIMULATED_CUSTOMERS.slice(0, 4).map((cust) => {
                const isSelected = cust.id === activeCustomer.id;
                return (
                  <button
                    key={cust.id}
                    onClick={() => onCustomerChange?.(cust)}
                    className={`flex items-center gap-2.5 p-2 rounded-lg border text-left transition-all cursor-pointer ${
                      isSelected
                        ? "bg-blue-50/80 border-blue-500 ring-1 ring-blue-500 text-blue-950 shadow-2xs"
                        : "bg-zinc-50 hover:bg-zinc-100 border-zinc-200 text-zinc-700"
                    }`}
                  >
                    <span className="w-6 h-6 rounded-md bg-white border border-zinc-300 flex items-center justify-center font-mono font-bold text-[10px] text-zinc-800 shrink-0">
                      {cust.avatar}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="text-[11.5px] font-bold truncate leading-tight">{cust.name}</div>
                      <div className="text-[9.5px] text-zinc-500 truncate leading-tight mt-0.5 font-mono">
                        {cust.homeStoreName} ({cust.homeStoreCode})
                      </div>
                    </div>
                    {isSelected && <CheckCircle className="w-3.5 h-3.5 text-blue-600 shrink-0" />}
                  </button>
                );
              })}
            </div>

            {/* Dynamic Staple Simulator Switcher */}
            <div className="pt-2 border-t border-zinc-100 space-y-1.5">
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-zinc-500 font-medium">Simulate Depleted Staple:</span>
                <span className="font-mono font-bold text-zinc-900 text-[10.5px]">
                  {activeCustomer.primaryDepletionItem}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-1 font-mono text-[10px]">
                {[
                  { name: "Amul Taaza Milk 1L", color: "blue" },
                  { name: "Whole Wheat Bread 400g", color: "orange" },
                  { name: "Farm Fresh Eggs (12 pcs)", color: "amber" },
                  { name: "Fresh Hybrid Tomatoes 500g", color: "rose" },
                ].map(({ name, color }) => {
                  const isActive = activeCustomer.primaryDepletionItem === name;
                  const activeClass =
                    color === "blue"
                      ? "bg-blue-100 border-blue-400 text-blue-950 font-bold shadow-2xs"
                      : color === "orange"
                      ? "bg-orange-100 border-orange-400 text-orange-950 font-bold shadow-2xs"
                      : color === "amber"
                      ? "bg-amber-100 border-amber-400 text-amber-950 font-bold shadow-2xs"
                      : "bg-rose-100 border-rose-400 text-rose-950 font-bold shadow-2xs";

                  return (
                    <button
                      key={name}
                      type="button"
                      onClick={() =>
                        onCustomerChange?.({
                          ...activeCustomer,
                          primaryDepletionItem: name,
                        })
                      }
                      className={`px-2 py-1 rounded border text-left truncate transition-colors cursor-pointer ${
                        isActive
                          ? activeClass
                          : "bg-zinc-50 hover:bg-zinc-100 border-zinc-200 text-zinc-700"
                      }`}
                    >
                      {name.split(" ").slice(0, 2).join(" ")}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Additional Customer Selector Dropdown */}
            <div className="pt-1.5 flex items-center justify-between text-[11px] border-t border-zinc-100">
              <label htmlFor="all-customers-select" className="text-zinc-500">Switch household:</label>
              <select
                id="all-customers-select"
                aria-label="Select household customer persona"
                value={activeCustomer.id}
                onChange={(e) => {
                  const found = SIMULATED_CUSTOMERS.find((c) => c.id === e.target.value);
                  if (found) onCustomerChange?.(found);
                }}
                className="text-xs font-medium text-zinc-800 bg-zinc-50 border border-zinc-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
              >
                {SIMULATED_CUSTOMERS.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} — {c.homeStoreName} ({c.homeStoreCode})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Linked Dark Store Status Card (Clean Apple Light) */}
          <div className="p-3.5 rounded-xl bg-white border border-zinc-200 shadow-2xs space-y-2 text-zinc-900">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs font-bold text-zinc-900">
                <StoreIcon className="w-4 h-4 text-blue-600" />
                <span>Linked Fulfillment Node: {activeCustomer.homeStoreName} ({activeCustomer.homeStoreCode})</span>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-blue-50 text-blue-800 border border-blue-200 font-bold">
                {homeStore?.status?.toUpperCase() || "ACTIVE"}
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-[10.5px] pt-1 border-t border-zinc-100">
              <div className="p-2 bg-zinc-50 rounded-lg border border-zinc-100">
                <span className="text-zinc-500 block text-[9.5px]">Dairy Health</span>
                <span className="font-mono font-bold text-blue-700">{homeStore?.inventoryHealth?.dairy ?? 85}%</span>
              </div>
              <div className="p-2 bg-zinc-50 rounded-lg border border-zinc-100">
                <span className="text-zinc-500 block text-[9.5px]">Bakery Health</span>
                <span className="font-mono font-bold text-zinc-800">{homeStore?.inventoryHealth?.bakery ?? 92}%</span>
              </div>
              <div className="p-2 bg-zinc-50 rounded-lg border border-zinc-100">
                <span className="text-zinc-500 block text-[9.5px]">Stockout Risk</span>
                <span className={`font-mono font-bold ${(homeStore?.stockoutRiskCount ?? 0) > 0 ? "text-rose-600" : "text-zinc-700"}`}>
                  {homeStore?.stockoutRiskCount ?? 0} SKUs
                </span>
              </div>
            </div>
          </div>

          {/* Flow Walkthrough Steps */}
          <div className="space-y-2.5 font-sans text-xs">
            <div className="p-3 rounded-xl bg-white border border-zinc-200 shadow-2xs space-y-1">
              <div className="flex items-center gap-2 font-bold text-zinc-900">
                <span className="w-5 h-5 rounded-full bg-blue-50 text-blue-800 border border-blue-200 flex items-center justify-center text-[11px] font-mono font-bold">1</span>
                <span>Depletion Threshold Trigger</span>
              </div>
              <p className="text-zinc-500 pl-7 text-[11px]">
                Consumption forecasting projects {activeCustomer.primaryDepletionItem} reaches 15% threshold.
              </p>
            </div>

            <div className="p-3 rounded-xl bg-white border border-zinc-200 shadow-2xs space-y-1">
              <div className="flex items-center gap-2 font-bold text-zinc-900">
                <span className="w-5 h-5 rounded-full bg-amber-50 text-amber-800 border border-amber-200 flex items-center justify-center text-[11px] font-mono font-bold">2</span>
                <span>WhatsApp Interactive Restock Notification</span>
              </div>
              <p className="text-zinc-500 pl-7 text-[11px]">
                Household confirms with 1 tap, adds items, schedules reminder, or skips.
              </p>
            </div>

            <div className="p-3 rounded-xl bg-white border border-zinc-200 shadow-2xs space-y-1">
              <div className="flex items-center gap-2 font-bold text-zinc-900">
                <span className="w-5 h-5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 flex items-center justify-center text-[11px] font-mono font-bold">3</span>
                <span>Dark Store Fleet Inventory Sync</span>
              </div>
              <p className="text-zinc-500 pl-7 text-[11px]">
                Confirmed order decrements {activeCustomer.homeStoreName} node inventory in the Operations Deck.
              </p>
            </div>
          </div>

          <div className="p-3 rounded-xl bg-zinc-50 border border-zinc-200/80 text-[11px] text-zinc-600 flex items-center gap-2">
            <RefreshCw className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
            <span>
              Interact with the phone simulator on the right to test restock and order dispatch flows.
            </span>
          </div>
        </div>

        {/* Right Phone Mockup Container (7 cols) */}
        <div className="lg:col-span-7 flex justify-center items-center py-4">
          <div className="w-[290px] h-[593px] aspect-[1800/3680] shrink-0 relative z-10 mx-auto">
            <PhoneMockup
              activeScenario="milk_shortage"
              initialViewMode="whatsapp"
              activeCustomer={activeCustomer}
              onCustomerChange={onCustomerChange}
              onPlaceOrder={onPlaceOrder}
              onScheduleReminder={onScheduleReminder}
              onSkipRestock={onSkipRestock}
            />
          </div>
        </div>

      </div>
    </motion.div>
  );
}
