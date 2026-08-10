"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { TrendingUp, Users, ShieldCheck, Clock, CheckCircle2 } from "lucide-react";

export function PreFillRoiCalculator() {
  const [households, setHouseholds] = useState<number>(10);

  // Calculations
  const hoursSavedPerMonth = households * 4.5;
  const groceryBudgetProtected = households * 1450;

  return (
    <div className="bg-white rounded-[2.5rem] p-6 sm:p-8 border border-gray-200/90 shadow-xl space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-100 pb-6">
        <div className="space-y-1">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-sky-50 border border-sky-200 text-sky-800 text-xs font-semibold">
            <TrendingUp className="w-3.5 h-3.5 text-sky-600" />
            <span>Interactive Time & Savings Tool</span>
          </div>
          <h3 className="text-xl sm:text-2xl font-bold tracking-tight text-gray-950">
            Grocery Time & Savings Calculator
          </h3>
        </div>

        <div className="bg-emerald-50 px-4 py-2 rounded-2xl border border-emerald-200 flex items-center gap-3 shrink-0">
          <ShieldCheck className="w-5 h-5 text-emerald-600" />
          <div className="text-xs">
            <p className="text-emerald-800 text-[10px] uppercase font-bold">Kitchen Health</p>
            <p className="font-mono font-extrabold text-emerald-900 text-sm">100% Stocked</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
        {/* Left Column: Interactive Slider */}
        <div className="lg:col-span-6 space-y-6">
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-gray-900 flex items-center gap-2">
                <Users className="w-4 h-4 text-sky-600" /> Number of Family Members & Friends
              </span>
              <span className="font-mono font-extrabold text-sky-700 bg-sky-50 px-3 py-1 rounded-full border border-sky-200 text-xs">
                {households} People
              </span>
            </div>
            <input
              type="range"
              min="1"
              max="50"
              step="1"
              value={households}
              onChange={(e) => setHouseholds(Number(e.target.value))}
              className="w-full h-2.5 bg-gray-100 rounded-lg appearance-none cursor-pointer accent-sky-600"
            />
            <div className="flex justify-between text-[10px] font-semibold text-gray-400 font-mono">
              <span>1 Person</span>
              <span>25 People</span>
              <span>50 People</span>
            </div>
          </div>

          {/* Key ROI Bullet Points */}
          <div className="space-y-3 pt-2 text-xs font-medium text-gray-700">
            <div className="flex items-start gap-2.5">
              <CheckCircle2 className="w-4 h-4 text-sky-600 shrink-0 mt-0.5" />
              <span>Saves 4.5 hours of manual grocery app searching every month</span>
            </div>
            <div className="flex items-start gap-2.5">
              <CheckCircle2 className="w-4 h-4 text-sky-600 shrink-0 mt-0.5" />
              <span>Prevents last-minute expensive emergency trips to local stores</span>
            </div>
            <div className="flex items-start gap-2.5">
              <CheckCircle2 className="w-4 h-4 text-sky-600 shrink-0 mt-0.5" />
              <span>Confirms orders in 1 tap on WhatsApp with zero hassle</span>
            </div>
          </div>
        </div>

        {/* Right Column: Calculated Results */}
        <div className="lg:col-span-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Card 1: Hours Saved */}
          <motion.div
            key={hoursSavedPerMonth}
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.2 }}
            className="bg-gray-50 rounded-3xl p-5 border border-gray-200/90 space-y-2 flex flex-col justify-between"
          >
            <span className="text-[11px] font-bold text-gray-500 uppercase tracking-wider flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-blue-600" /> Monthly Time Saved
            </span>
            <div className="space-y-1">
              <p className="text-3xl font-extrabold text-gray-950 tracking-tight font-mono">
                {hoursSavedPerMonth} Hours
              </p>
              <p className="text-[10px] text-gray-500 font-medium">Saved every month from app browsing</p>
            </div>
          </motion.div>

          {/* Card 2: Grocery Budget Protected */}
          <motion.div
            key={groceryBudgetProtected}
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.2 }}
            className="bg-gradient-to-br from-emerald-700 to-teal-800 text-white rounded-3xl p-5 shadow-md space-y-2 flex flex-col justify-between"
          >
            <span className="text-[11px] font-bold text-emerald-200 uppercase tracking-wider flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-white" /> Emergency Spend Saved
            </span>
            <div className="space-y-1">
              <p className="text-3xl font-extrabold text-white tracking-tight font-mono">
                ₹{groceryBudgetProtected.toLocaleString()}
              </p>
              <p className="text-[10px] text-emerald-100 font-medium">Saved from emergency store runs</p>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
