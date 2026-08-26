"use client";

import React from "react";
import {
  BarChart3,
  ChevronLeft,
  Phone,
  Video,
  Plus,
  Camera,
  Mic,
  CheckCheck
} from "lucide-react";
import { IphoneFrame } from "./ui/IphoneFrame";
import { motion } from "framer-motion";
import clsx from "clsx";
import { PhoneMockupProps, StapleItem } from "../lib/types";
import { usePhoneDemoEngine } from "../hooks/usePhoneDemoEngine";
import { WhatsAppIcon } from "./ui/WhatsAppIcon";
import { IosNotificationBanner } from "./mockup/IosNotificationBanner";
import { toast } from "sonner";

export default function PhoneMockup({ activeScenario, initialViewMode }: PhoneMockupProps) {
  const {
    viewMode,
    setViewMode,
    orderStage,
    setOrderStage,
    restockedState,
    setRestockedState,
    addedBread,
    setAddedBread,
    setIsWhatsAppOpen,
    depleting,
    chatContainerRef,
    searchQuery
  } = usePhoneDemoEngine(activeScenario, initialViewMode);

  const filteredStaples = depleting.filter((item: StapleItem) =>
    item.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex flex-col items-center gap-2 w-[295px] aspect-[1800/3680] shrink-0 mx-auto select-none overflow-hidden bg-transparent antialiased font-['SF_Pro_Display','SF_Pro_Text',-apple-system,BlinkMacSystemFont,sans-serif]" style={{ transform: "translateZ(0)", WebkitFontSmoothing: "antialiased" }}>
      {/* iPhone 16 Pro Hardware Frame */}
      <IphoneFrame className="w-full h-full bg-transparent">
        <div className="w-full h-full bg-transparent flex flex-col relative overflow-hidden select-none">

          {/* VIEW 1: IOS LOCK SCREEN WITH EDGE-TO-EDGE WALLPAPER & FIGMA-EXPORTED COLLAPSED NOTIFICATION */}
          {viewMode === "lockscreen" && (
            <div className="absolute inset-0 size-full z-10 bg-[url('/wallpaper.png')] bg-cover bg-center text-white px-3.5 pt-12 pb-[95px] flex flex-col justify-end items-center overflow-hidden select-none">
              <motion.div
                initial={{ y: 15, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ duration: 0.35, ease: "easeOut" }}
                className="w-full mb-2"
              >
                <IosNotificationBanner
                  title="WhatsApp"
                  message="🥛 Amul Milk 1L is down to 15% (runs out tomorrow). Tap to restock →"
                  time="now"
                  onClick={() => {
                    setViewMode("whatsapp");
                    setIsWhatsAppOpen(true);
                  }}
                />
              </motion.div>
            </div>
          )}

          {/* MAIN IN-APP CONTENT AREA (WITH TOP/BOTTOM PADDING FOR STATUS BAR & HOME BAR) */}
          <div className="flex-1 overflow-y-auto no-scrollbar relative flex flex-col pt-[40px] pb-[20px] bg-[#F6F7F8]">

            {/* VIEW 2: AUTHENTIC WHATSAPP LIGHT IOS CHAT WITH APPLE EMOJIS */}
            {viewMode === "whatsapp" && (
              <div className="w-full h-full flex flex-col bg-[#E5DDD5] relative">
                <div className="absolute inset-0 bg-[#E5DDD5]/85 backdrop-blur-[1px] pointer-events-none" />

                {/* Authentic iOS WhatsApp Header */}
                <div className="bg-[#F6F6F6]/95 backdrop-blur-md text-gray-900 border-b border-gray-200/80 px-2.5 py-1.5 flex items-center justify-between shrink-0 z-10 shadow-2xs">
                  <div className="flex items-center gap-1.5">
                    <button onClick={() => setViewMode("lockscreen")} className="text-emerald-600 font-semibold p-0.5 cursor-pointer">
                      <ChevronLeft className="h-4 w-4" />
                    </button>
                    <div className="h-7 w-7 rounded-full bg-emerald-600 flex items-center justify-center font-bold text-white text-xs border border-emerald-500 shadow-2xs">
                      🤖
                    </div>
                    <div className="flex flex-col leading-tight">
                      <div className="flex items-center gap-1">
                        <span className="text-[11px] font-bold text-gray-950 font-sans">WhatsApp</span>
                        <span className="text-[8px] bg-emerald-100 text-emerald-800 font-bold px-1 rounded-full">✓</span>
                      </div>
                      <span className="text-[8px] text-gray-500 font-sans">Verified Quick Commerce</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 text-emerald-600">
                    <Video className="h-4 w-4" />
                    <Phone className="h-3.5 w-3.5" />
                  </div>
                </div>

                {/* Chat Messages Container */}
                <div ref={chatContainerRef} className="flex-1 overflow-y-auto p-2 space-y-2 text-[10px] font-sans z-10">
                  <div className="flex justify-center">
                    <span className="bg-white/80 text-gray-600 px-2 py-0.5 rounded-md text-[8px] font-semibold uppercase shadow-2xs">
                      Today • 08:00 AM
                    </span>
                  </div>

                  {/* Message 1: Proactive Depletion Nudge */}
                  <div className="mr-auto bg-white rounded-xl rounded-tl-none p-2 shadow-2xs max-w-[92%] border border-gray-100 space-y-1 relative">
                    <p className="font-medium text-gray-800 leading-snug">
                      👋 Good morning, Karan!
                    </p>
                    <p className="text-gray-900 leading-snug">
                      Prophet ML detected your <b>1L Amul Milk 🥛</b> is running out tomorrow morning (15% stock left).
                    </p>
                    <div className="bg-amber-50 border border-amber-200/80 rounded-lg p-1.5 flex items-center justify-between text-[9px]">
                      <span className="text-amber-900 font-semibold">🥛 Amul Milk 1L</span>
                      <span className="text-rose-600 font-bold font-mono">15% LOW ⚠️</span>
                    </div>
                    <div className="flex justify-end text-[7.5px] text-gray-400 font-mono pt-0.5">
                      08:00 AM
                    </div>
                  </div>

                  {/* Message 2: Order Breakdown Card */}
                  {(orderStage === "breakdown" || orderStage === "confirmed" || addedBread) && (
                    <>
                      <div className="ml-auto bg-[#DCF8C6] text-gray-900 rounded-xl rounded-tr-none px-2.5 py-1 shadow-2xs max-w-[85%] text-[9.5px] font-medium flex items-center justify-between gap-1 border border-emerald-200/60">
                        <span>➕ Added Wheat Bread 400g 🍞 (+₹50)</span>
                        <CheckCheck className="h-3 w-3 text-emerald-600 shrink-0" />
                      </div>

                      <div className="mr-auto bg-white rounded-xl rounded-tl-none p-2 shadow-sm max-w-[95%] border border-emerald-200 space-y-1.5">
                        <div className="flex items-center justify-between border-b border-gray-100 pb-1">
                          <span className="font-bold text-[10px] text-gray-900 flex items-center gap-1 font-display">
                            🛒 Order Breakdown
                          </span>
                          <span className="bg-emerald-100 text-emerald-800 text-[8px] font-bold px-1.5 py-0.5 rounded">
                            Zepto Dark Store ⚡
                          </span>
                        </div>

                        <div className="space-y-1 text-[9px]">
                          <div className="flex justify-between text-gray-700">
                            <span>🥛 1× Amul Taza Milk 1L</span>
                            <span className="font-mono font-semibold">₹66</span>
                          </div>
                          <div className="flex justify-between text-gray-700">
                            <span>🍞 1× Wheat Bread 400g</span>
                            <span className="font-mono font-semibold">₹50</span>
                          </div>
                          <div className="border-t border-dashed border-gray-200 pt-1 flex justify-between font-bold text-gray-900">
                            <span>Subtotal</span>
                            <span className="font-mono">₹116</span>
                          </div>
                          <div className="flex justify-between text-emerald-600 font-semibold text-[8.5px]">
                            <span>Delivery Fee (&gt;₹99) 🚚</span>
                            <span>FREE</span>
                          </div>
                        </div>

                        <div className="bg-gray-50 rounded-lg p-1.5 space-y-1 border border-gray-100 text-[8.5px]">
                          <div className="flex items-center justify-between text-gray-600">
                            <span className="flex items-center gap-1">
                              🚚 Arrival:
                            </span>
                            <span className="font-bold text-gray-900">10 Mins (6:15 AM)</span>
                          </div>
                          <div className="flex items-center justify-between text-gray-600">
                            <span className="flex items-center gap-1">
                              💳 Payment:
                            </span>
                            <span className="font-semibold text-purple-700">UPI / COD</span>
                          </div>
                        </div>
                      </div>
                    </>
                  )}

                  {/* Message 3: Order Confirmed */}
                  {(orderStage === "confirmed" || restockedState) && (
                    <>
                      <div className="ml-auto bg-[#DCF8C6] text-gray-900 rounded-xl rounded-tr-none px-2.5 py-1 shadow-2xs max-w-[85%] text-[9.5px] font-medium flex items-center justify-between gap-1 border border-emerald-200/60">
                        <span>💳 Paid via UPI ⚡ (₹116)</span>
                        <CheckCheck className="h-3 w-3 text-emerald-600 shrink-0" />
                      </div>
                      <div className="mr-auto bg-white rounded-xl rounded-tl-none p-2 shadow-sm max-w-[92%] border border-emerald-300 space-y-1">
                        <div className="flex items-center gap-1.5 text-emerald-700 font-bold text-[10px]">
                          🎉 Order #ORD-4029 Confirmed!
                        </div>
                        <p className="text-[9px] text-gray-700 leading-snug">
                          Dispatched from Dark Store. Driver assigned. Delivery in 8 mins 🚚.
                        </p>
                        <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-1 text-center">
                          <span className="text-[9px] font-bold text-emerald-800">
                            ✨ Household Pantry Restored to 100% 🥛🍞
                          </span>
                        </div>
                      </div>
                    </>
                  )}
                </div>

                {/* WhatsApp Interactive Action Buttons */}
                <div className="p-1.5 bg-white border-t border-gray-200 space-y-1 shrink-0 z-10">
                  {orderStage === "initial" && (
                    <div className="grid grid-cols-2 gap-1">
                      <button
                        onClick={() => {
                          setAddedBread(true);
                          setOrderStage("breakdown");
                        }}
                        className="bg-emerald-50 hover:bg-emerald-100 text-[#075E54] border border-[#075E54]/30 p-1.5 rounded-lg text-[9px] font-bold flex items-center justify-center gap-1 active:scale-95 transition-all cursor-pointer shadow-2xs"
                      >
                        <span>➕ Add Bread 🍞 (+₹50)</span>
                      </button>
                      <button
                        onClick={() => {
                          setOrderStage("breakdown");
                        }}
                        className="bg-[#075E54] text-white p-1.5 rounded-lg text-[9px] font-bold flex items-center justify-center gap-1 active:scale-95 transition-all cursor-pointer shadow-2xs"
                      >
                        <span>✅ Restock Milk Only 🥛</span>
                      </button>
                    </div>
                  )}

                  {orderStage === "breakdown" && (
                    <div className="grid grid-cols-2 gap-1">
                      <button
                        onClick={() => {
                          setOrderStage("confirmed");
                          setRestockedState(true);
                          toast.success("Order #ORD-4029 Confirmed via UPI!");
                        }}
                        className="bg-[#075E54] text-white p-1.5 rounded-lg text-[9px] font-bold flex items-center justify-center gap-1 active:scale-95 transition-all cursor-pointer shadow-2xs"
                      >
                        <span>💳 Pay via UPI ⚡ (₹116)</span>
                      </button>
                      <button
                        onClick={() => {
                          setOrderStage("confirmed");
                          setRestockedState(true);
                          toast.success("Order #ORD-4029 Confirmed via COD!");
                        }}
                        className="bg-gray-800 text-white p-1.5 rounded-lg text-[9px] font-bold flex items-center justify-center gap-1 active:scale-95 transition-all cursor-pointer shadow-2xs"
                      >
                        <span>💵 Cash on Delivery 🚚</span>
                      </button>
                    </div>
                  )}

                  {orderStage === "confirmed" && (
                    <button
                      onClick={() => {
                        setViewMode("pantry");
                      }}
                      className="w-full bg-emerald-700 text-white p-1.5 rounded-lg text-[9.5px] font-bold flex items-center justify-center gap-1 cursor-pointer"
                    >
                      <BarChart3 className="h-3.5 w-3.5" />
                      <span>View Pantry Health Dashboard (100% Full)</span>
                    </button>
                  )}
                </div>

                {/* Authentic WhatsApp iOS Bottom Bar */}
                <div className="bg-[#F6F6F6] border-t border-gray-200 px-2 py-1 flex items-center gap-2 shrink-0 text-gray-500 z-10">
                  <Plus className="h-4 w-4" />
                  <div className="flex-1 bg-white border border-gray-300 rounded-full px-2.5 py-1 text-[9.5px] text-gray-400">
                    Type a message...
                  </div>
                  <Camera className="h-4 w-4" />
                  <Mic className="h-4 w-4 text-emerald-600" />
                </div>
              </div>
            )}

            {/* VIEW 3: PANTRY HEALTH DASHBOARD */}
            {viewMode === "pantry" && (
              <div className="p-2.5 flex flex-col gap-2 pb-16">
                <div className="flex items-center justify-between border-b border-gray-200 pb-1.5">
                  <div>
                    <span className="text-[10.5px] font-bold text-gray-950 font-display">Pantry Stock Depletion</span>
                    <p className="text-[8.5px] text-gray-500">Synced with Household ML Engine</p>
                  </div>
                  <span className={clsx("text-[8.5px] px-2 py-0.5 font-bold rounded-full border", restockedState ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-rose-50 text-rose-700 border-rose-200")}>
                    {restockedState ? "100% Restocked ✨" : "Milk Low (15%) ⚠️"}
                  </span>
                </div>

                {filteredStaples.map((item: StapleItem) => {
                  const isDanger = item.fillPct < 25;
                  const isWarning = item.fillPct >= 25 && item.fillPct < 50;
                  const IconComponent = item.icon;

                  return (
                    <div key={item.id} className="rounded-xl border border-gray-200/90 bg-white p-2 flex items-center justify-between gap-2 shadow-2xs">
                      <div className="flex items-center gap-2 min-w-0">
                        <div className={clsx("h-7 w-7 rounded-lg shrink-0 border flex items-center justify-center", item.category === "dairy" ? "bg-blue-50 text-blue-600 border-blue-100" : item.category === "produce" ? "bg-rose-50 text-rose-600 border-rose-100" : item.category === "poultry" ? "bg-amber-50 text-amber-600 border-amber-100" : "bg-emerald-50 text-emerald-600 border-emerald-100")}>
                          <IconComponent className="h-3.5 w-3.5" />
                        </div>
                        <div className="flex flex-col min-w-0 justify-center">
                          <span className="font-bold text-[10.5px] text-[#252525] font-display truncate leading-tight">{item.name}</span>
                          <span className="text-[8.5px] font-semibold text-[#64717E] truncate leading-tight mt-0.5">{item.avg} · {item.days}d left</span>

                          <div className="flex items-center gap-1.5 mt-1">
                            <div className="w-16 h-1.5 bg-[#F3F4F6] rounded-full overflow-hidden border border-stone-200/60">
                              <div
                                className={clsx("h-full rounded-full transition-all duration-500", isDanger ? "bg-[#BE123C]" : isWarning ? "bg-[#C2410C]" : "bg-[#15803D]")}
                                style={{ width: `${item.fillPct}%` }}
                              />
                            </div>
                            <span className={clsx("text-[9px] px-1.5 py-0.2 font-mono font-bold rounded-full border leading-none", isDanger ? "bg-rose-50 text-rose-700 border-rose-200" : isWarning ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-emerald-50 text-emerald-700 border-emerald-200")}>
                              {item.fillPct}%
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}

                <button
                  onClick={() => setViewMode("whatsapp")}
                  className="mt-2 w-full bg-[#075E54] text-white p-2 rounded-xl text-[9.5px] font-bold flex items-center justify-center gap-1.5 shadow-2xs cursor-pointer"
                >
                  <WhatsAppIcon className="h-3.5 w-3.5" />
                  <span>Return to WhatsApp Restock Flow</span>
                </button>
              </div>
            )}

          </div>

        </div>
      </IphoneFrame>
    </div>
  );
}
