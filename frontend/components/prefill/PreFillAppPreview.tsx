"use client";

import React, { useState } from "react";
import { MessageSquare, PhoneCall, ShieldCheck, Zap, ArrowRight, CheckCircle2 } from "lucide-react";

export function PreFillAppPreview() {
  const [activeTab, setActiveTab] = useState("preview");

  const tabs = [
    { id: "preview", label: "App Preview" },
    { id: "inbox", label: "WhatsApp Inbox" },
    { id: "security", label: "Data Privacy" },
    { id: "apps", label: "10-Min Apps" },
  ];

  return (
    <section className="py-20 md:py-28 bg-[#FAFAFA] border-t border-gray-200/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-14">
        {/* Beside 1:1 Two-Column Section Header */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-end">
          <div className="lg:col-span-7 space-y-3">
            <h2 className="font-serif font-normal text-3xl sm:text-4xl lg:text-[44px] tracking-tight text-gray-950 leading-[1.15]">
              AI restock preview for leading households & local stores
            </h2>
          </div>
          <div className="lg:col-span-5">
            <p className="text-sm sm:text-base text-gray-500 font-normal leading-relaxed">
              PreFill integrates with your favorite quick-commerce apps and WhatsApp to handle daily household grocery replenishment.
            </p>
          </div>
        </div>

        {/* Beside Sub-Nav Pill Tab Bar (h-9 px-5) */}
        <div className="flex items-center justify-center gap-2 overflow-x-auto pb-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`h-9 px-5 rounded-full text-xs font-bold transition-all cursor-pointer shrink-0 flex items-center justify-center ${
                activeTab === tab.id
                  ? "bg-gray-950 text-white shadow-xs"
                  : "bg-white text-gray-600 hover:text-gray-950 border border-gray-200/80"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Beside 1:1 Large App UI Preview Box */}
        <div className="bg-[#F3F4F6] rounded-[2.5rem] p-6 sm:p-10 border border-gray-200/60 shadow-xs space-y-8">
          <div className="bg-white rounded-3xl p-6 sm:p-8 border border-gray-200/60 shadow-[0_2px_12px_rgba(0,0,0,0.04)] grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
            {/* Left Column: Interactive Chat Item */}
            <div className="lg:col-span-6 space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-emerald-100 text-emerald-800 flex items-center justify-center font-bold text-sm">
                  PF
                </div>
                <div>
                  <h4 className="font-bold text-sm text-gray-950">PreFill Kitchen Agent</h4>
                  <p className="text-xs text-gray-400 font-mono">+91 99999 99999 • Verified Bot</p>
                </div>
              </div>

              <div className="bg-emerald-50/80 p-4 rounded-2xl border border-emerald-100 text-xs space-y-2">
                <p className="text-emerald-950 font-medium leading-relaxed">
                  "Good morning Karan! Your <span className="font-bold text-amber-700">Fresh Milk 1L</span> & <span className="font-bold text-gray-950 font-mono">Organic Tomatoes 500g</span> run low tomorrow. Total: <span className="font-extrabold text-gray-950">₹98</span>. Reply 'YES' to deliver in 10 mins!"
                </p>
                <div className="flex items-center justify-between pt-1 text-[10px] text-emerald-800 font-bold">
                  <span>Status: Waiting for 1-Tap Response</span>
                  <span className="bg-[#064E3B] text-white px-2.5 py-0.5 rounded-full">Active Alert</span>
                </div>
              </div>
            </div>

            {/* Right Column: Live Order Status Card */}
            <div className="lg:col-span-6 bg-gray-50 p-6 rounded-2xl border border-gray-200/80 space-y-4">
              <div className="flex items-center justify-between text-xs font-bold text-gray-900">
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" /> Auto-Restock Confirmation
                </span>
                <span className="text-[10px] font-mono bg-emerald-50 text-emerald-800 px-2 py-0.5 rounded border border-emerald-200">
                  10-MIN EXPRESS
                </span>
              </div>

              <div className="space-y-2 text-xs text-gray-600 font-medium">
                <div className="flex justify-between py-1 border-b border-gray-200/60">
                  <span>Fresh Milk 1L (Nandini)</span>
                  <span className="font-mono font-bold text-gray-950">₹32</span>
                </div>
                <div className="flex justify-between py-1 border-b border-gray-200/60">
                  <span>Organic Tomatoes 500g</span>
                  <span className="font-mono font-bold text-gray-950">₹66</span>
                </div>
                <div className="flex justify-between pt-1 font-bold text-gray-950">
                  <span>Total Cart</span>
                  <span className="font-mono text-emerald-800">₹98</span>
                </div>
              </div>
            </div>
          </div>

          {/* Beside 1:1 Bottom Client Logo Ribbon */}
          <div className="pt-4 border-t border-gray-200/80 space-y-4 text-center">
            <p className="text-xs font-bold text-gray-500 uppercase tracking-widest">
              The leading AI restock app for the modern economy. Trusted by 400+ households & local stores
            </p>

            <div className="flex flex-wrap items-center justify-center gap-8 md:gap-12 opacity-60 text-xs font-bold font-mono text-gray-700 grayscale">
              <span>ZEPTO</span>
              <span>BLINKIT</span>
              <span>INSTAMART</span>
              <span>BIGBASKET</span>
              <span>SWIGGY</span>
              <span>WHATSAPP</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
