"use client";

import React from "react";
import {
  Phone,
  Video,
  Plus,
  Camera,
  Mic,
  CheckCheck,
  Clock,
  CheckCircle2,
  Sparkles,
  Check,
  CreditCard,
  Truck,
  RotateCcw,
  ChevronLeft,
} from "lucide-react";
import { IphoneFrame } from "./ui/IphoneFrame";
import { PhoneMockupProps } from "../lib/types";
import { usePhoneDemoEngine } from "../hooks/usePhoneDemoEngine";
import { DEFAULT_CUSTOMER_PERSONA, DEFAULT_PANTRY_STAPLES } from "../lib/mockData";

export default function PhoneMockup({
  activeScenario,
  initialViewMode,
  activeCustomer = DEFAULT_CUSTOMER_PERSONA,
  onPlaceOrder,
  onScheduleReminder,
  onSkipRestock,
  className,
}: PhoneMockupProps) {
  const {
    orderStage,
    setOrderStage,
    restockedState,
    addedBread,
    setAddedBread,
    chatContainerRef,
    confirmOrder,
    scheduleReminder,
    skipRestock,
  } = usePhoneDemoEngine(
    activeScenario,
    initialViewMode,
    activeCustomer,
    onPlaceOrder,
    onScheduleReminder,
    onSkipRestock
  );

  const firstName = activeCustomer.name.split(" ")[0];
  const primaryItemName = activeCustomer.primaryDepletionItem || "Amul Taaza Milk 1L";
  const primaryStaple = DEFAULT_PANTRY_STAPLES.find(
    (s) => s.name.toLowerCase() === primaryItemName.toLowerCase()
  ) || {
    id: "primary",
    name: primaryItemName,
    price: 66,
  };
  const primaryPrice = primaryStaple.price;
  const isBreadPrimary = primaryItemName.toLowerCase().includes("bread");
  const totalRestockPrice = primaryPrice + (addedBread && !isBreadPrimary ? 50 : 0);
  const shortPrimaryName = primaryItemName.split(" ").slice(0, 3).join(" ");

  return (
    <div
      className={`flex flex-col items-center w-[275px] aspect-[1800/3680] shrink-0 mx-auto select-none overflow-hidden bg-transparent antialiased font-['SF_Pro_Display','SF_Pro_Text',-apple-system,BlinkMacSystemFont,sans-serif] ${className || ""}`}
      style={{ transform: "translateZ(0)", WebkitFontSmoothing: "antialiased" }}
    >
      {/* iPhone 16 Pro Hardware Frame */}
      <IphoneFrame className="w-full h-full bg-transparent">
        <div className="w-full h-full bg-white flex flex-col relative overflow-hidden select-none">

          {/* MAIN IN-APP CONTENT AREA */}
          <div className="flex-1 overflow-hidden relative flex flex-col bg-[#EFEAE2]">

            {/* AUTHENTIC WHATSAPP LIGHT IOS INTERFACE */}
            <div className="w-full h-full flex flex-col bg-[#EFEAE2] relative">

              {/* iOS WhatsApp Header with Dynamic Island clearance */}
              <div className="bg-[#F6F6F6] text-gray-900 border-b border-gray-200/80 pt-9 px-2.5 pb-1.5 flex items-center justify-between shrink-0 z-10 shadow-2xs">
                <div className="flex items-center gap-1.5">
                  <ChevronLeft className="w-3.5 h-3.5 text-blue-600 -ml-0.5 shrink-0" />
                  <div className="h-7 w-7 rounded-full bg-blue-600 flex items-center justify-center font-bold text-white text-[10px] border border-blue-500 shadow-2xs shrink-0 font-mono">
                    <span>GR</span>
                  </div>
                  <div className="flex flex-col leading-tight ml-0.5">
                    <div className="flex items-center gap-1">
                      <span className="text-[10.5px] font-semibold text-zinc-950 font-sans tracking-tight">
                        Grocer Assistant
                      </span>
                      <span className="text-[7px] bg-blue-100 text-blue-800 font-bold px-1 rounded-full">
                        ✓
                      </span>
                    </div>
                    <span className="text-[8px] text-emerald-600 font-sans font-medium">
                      Online
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2.5 text-blue-600">
                  <Video className="w-3.5 h-3.5" />
                  <Phone className="w-3.5 h-3.5" />
                </div>
              </div>

              {/* Chat Messages Container */}
              <div
                ref={chatContainerRef}
                className="flex-1 overflow-y-auto p-2 space-y-2 text-[10px] font-sans z-10"
              >
                {/* Date Stamp */}
                <div className="flex justify-center">
                  <span className="bg-white/85 text-gray-600 px-2 py-0.5 rounded-md text-[8px] font-semibold uppercase shadow-2xs font-mono">
                    Today · 08:00 AM
                  </span>
                </div>

                {/* Message 1: Depletion Alert with In-Bubble Quick Replies */}
                <div className="mr-auto bg-white rounded-2xl rounded-tl-xs shadow-2xs max-w-[92%] border border-black/5 overflow-hidden">
                  <div className="p-2.5 space-y-1.5">
                    <p className="text-zinc-900 text-[10px] leading-snug">
                      Hi {firstName}, your <b>{primaryItemName}</b> is almost finished. Tap below to order now.
                    </p>
                    <div className="bg-amber-50/80 border border-amber-200/70 rounded p-1.5 flex items-center justify-between text-[8.5px]">
                      <span className="text-amber-950 font-medium">{primaryItemName}</span>
                      <span className="text-rose-600 font-bold font-mono text-[8px] tracking-wide">Low Stock</span>
                    </div>
                    <div className="flex justify-end text-[7.5px] text-zinc-400 font-mono pt-0.5">
                      08:00 AM
                    </div>
                  </div>

                  {/* Attached WhatsApp Business Quick Reply Actions */}
                  {orderStage === "initial" && (
                    <div className="border-t border-zinc-150 divide-y divide-zinc-150 bg-zinc-50/50">
                      <button
                        type="button"
                        onClick={() => {
                          setAddedBread(false);
                          setOrderStage("breakdown");
                        }}
                        className="w-full py-1.5 px-2.5 text-center text-[9.5px] font-semibold text-blue-600 hover:bg-blue-50/60 active:bg-blue-100/60 transition-colors flex items-center justify-center gap-1 cursor-pointer"
                      >
                        <Check className="w-3 h-3 text-blue-600" />
                        <span>Deliver {shortPrimaryName} (₹{primaryPrice})</span>
                      </button>

                      {!isBreadPrimary && (
                        <button
                          type="button"
                          onClick={() => {
                            setAddedBread(true);
                            setOrderStage("breakdown");
                          }}
                          className="w-full py-1.5 px-2.5 text-center text-[9px] font-medium text-orange-600 hover:bg-orange-50/60 active:bg-orange-100/60 transition-colors flex items-center justify-center gap-1 cursor-pointer"
                        >
                          <Plus className="w-3 h-3 text-orange-600" />
                          <span>+ Bread (₹50)</span>
                        </button>
                      )}

                      <div className="grid grid-cols-2 divide-x divide-zinc-150">
                        <button
                          type="button"
                          onClick={() => scheduleReminder(24)}
                          className="py-1 px-1.5 text-center text-[8.5px] font-medium text-zinc-600 hover:bg-zinc-100 active:bg-zinc-200 transition-colors flex items-center justify-center gap-1 cursor-pointer"
                        >
                          <Clock className="w-2.5 h-2.5 text-zinc-500" />
                          <span>Remind Later</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => skipRestock("user_skipped")}
                          className="py-1 px-1.5 text-center text-[8.5px] font-medium text-zinc-500 hover:bg-zinc-100 active:bg-zinc-200 transition-colors cursor-pointer"
                        >
                          <span>Not Now</span>
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                {/* Message 2: Order Summary Card */}
                {(orderStage === "breakdown" || orderStage === "confirmed" || addedBread) && (
                  <>
                    {/* User Outgoing Reply Bubble */}
                    <div className="ml-auto bg-[#D9FDD3] text-zinc-900 rounded-2xl rounded-tr-xs px-2.5 py-1 shadow-2xs max-w-[85%] text-[10px] font-medium flex items-center justify-between gap-1.5 border border-emerald-200/40">
                      <span>
                        {addedBread && !isBreadPrimary
                          ? "Added Whole Wheat Bread (+₹50)"
                          : `Deliver ${shortPrimaryName} (₹${primaryPrice})`}
                      </span>
                      <div className="flex items-center gap-1 shrink-0">
                        <span className="text-[7.5px] text-zinc-500">08:01 AM</span>
                        <CheckCheck className="h-3 w-3 text-[#53BDEB]" />
                      </div>
                    </div>

                    {/* Bot Order Summary Card with In-Bubble Quick Replies */}
                    <div className="mr-auto bg-white rounded-2xl rounded-tl-xs shadow-2xs max-w-[95%] border border-black/5 overflow-hidden">
                      <div className="p-2.5 space-y-1.5">
                        <div className="flex items-center justify-between border-b border-zinc-100 pb-1">
                          <span className="font-bold text-[10.5px] text-zinc-900 font-sans">
                            Order Summary
                          </span>
                          <span className="bg-blue-50 text-blue-800 border border-blue-200 text-[8px] font-bold px-1.5 py-0.5 rounded font-mono">
                            {activeCustomer.homeStoreName} Hub
                          </span>
                        </div>

                        <div className="space-y-1 text-[9.5px]">
                          <div className="flex justify-between text-zinc-700">
                            <span>1× {primaryItemName}</span>
                            <span className="font-mono font-semibold">₹{primaryPrice}</span>
                          </div>
                          {addedBread && !isBreadPrimary && (
                            <div className="flex justify-between text-zinc-700">
                              <span>1× Whole Wheat Bread 400g</span>
                              <span className="font-mono font-semibold">₹50</span>
                            </div>
                          )}
                          <div className="border-t border-dashed border-zinc-200 pt-1 flex justify-between font-bold text-zinc-900 text-[10px]">
                            <span>Subtotal</span>
                            <span className="font-mono">₹{totalRestockPrice}</span>
                          </div>
                          <div className="flex justify-between text-blue-600 font-semibold text-[9px]">
                            <span>Delivery Fee</span>
                            <span>FREE</span>
                          </div>
                        </div>

                        <div className="bg-zinc-50 rounded p-1.5 space-y-0.5 border border-zinc-100 text-[8.5px]">
                          <div className="flex items-center justify-between text-zinc-600">
                            <span>Delivery Hub:</span>
                            <span className="font-semibold text-zinc-800">
                              {activeCustomer.homeStoreName}
                            </span>
                          </div>
                          <div className="flex items-center justify-between text-zinc-600">
                            <span>Target ETA:</span>
                            <span className="font-bold text-zinc-900">10 Mins</span>
                          </div>
                        </div>
                        <div className="flex justify-end text-[7.5px] text-zinc-400 font-mono">
                          08:01 AM
                        </div>
                      </div>

                      {/* Attached In-Chat Quick Reply Buttons for Checkout */}
                      {orderStage === "breakdown" && (
                        <div className="border-t border-zinc-150 divide-y divide-zinc-150 bg-zinc-50/50">
                          <button
                            type="button"
                            onClick={() => confirmOrder("UPI")}
                            className="w-full py-1.5 px-2.5 text-center text-[10px] font-bold text-blue-600 hover:bg-blue-50/60 active:bg-blue-100/60 transition-colors flex items-center justify-center gap-1 cursor-pointer"
                          >
                            <CreditCard className="w-3 h-3 text-blue-600" />
                            <span>Pay with UPI (₹{totalRestockPrice})</span>
                          </button>

                          <button
                            type="button"
                            onClick={() => confirmOrder("COD")}
                            className="w-full py-1.5 px-2.5 text-center text-[9.5px] font-semibold text-zinc-700 hover:bg-zinc-100 active:bg-zinc-200 transition-colors flex items-center justify-center gap-1 cursor-pointer"
                          >
                            <Truck className="w-3 h-3 text-zinc-600" />
                            <span>Cash on Delivery</span>
                          </button>

                          <button
                            type="button"
                            onClick={() => scheduleReminder(24)}
                            className="w-full py-1 px-2.5 text-center text-[8.5px] font-medium text-zinc-500 hover:bg-zinc-100 active:bg-zinc-200 transition-colors flex items-center justify-center gap-1 cursor-pointer"
                          >
                            <Clock className="w-2.5 h-2.5 text-zinc-400" />
                            <span>Remind me tomorrow</span>
                          </button>
                        </div>
                      )}
                    </div>
                  </>
                )}

                {/* Message 3: Order Confirmed */}
                {(orderStage === "confirmed" || restockedState) && (
                  <>
                    <div className="ml-auto bg-[#D9FDD3] text-zinc-900 rounded-2xl rounded-tr-xs px-2.5 py-1 shadow-2xs max-w-[85%] text-[10px] font-medium flex items-center justify-between gap-1.5 border border-emerald-200/40">
                      <span>Paid ₹{totalRestockPrice} via UPI</span>
                      <div className="flex items-center gap-1 shrink-0">
                        <span className="text-[7.5px] text-zinc-500">08:02 AM</span>
                        <CheckCheck className="h-3 w-3 text-[#53BDEB]" />
                      </div>
                    </div>
                    <div className="mr-auto bg-white rounded-2xl rounded-tl-xs shadow-2xs max-w-[92%] border border-emerald-200 overflow-hidden">
                      <div className="p-2.5 space-y-1.5">
                        <div className="flex items-center gap-1 text-emerald-700 font-bold text-[10.5px]">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                          <span>Order Confirmed!</span>
                        </div>
                        <p className="text-[9.5px] text-zinc-700 leading-snug">
                          Arriving in 10 mins from <b>{activeCustomer.homeStoreName}</b> Hub.
                        </p>
                        <div className="bg-emerald-50 border border-emerald-200 rounded p-1 text-center">
                          <span className="text-[9px] font-bold text-emerald-800 flex items-center justify-center gap-1">
                            <Sparkles className="w-3 h-3 text-emerald-600" />
                            Pantry Restored
                          </span>
                        </div>
                        <div className="flex justify-end text-[7.5px] text-zinc-400 font-mono">
                          08:02 AM
                        </div>
                      </div>
                      <div className="border-t border-zinc-150 bg-zinc-50/50">
                        <button
                          type="button"
                          onClick={() => setOrderStage("initial")}
                          className="w-full py-1.5 px-2.5 text-center text-[9.5px] font-semibold text-zinc-600 hover:bg-zinc-100 active:bg-zinc-200 transition-colors flex items-center justify-center gap-1 cursor-pointer"
                        >
                          <RotateCcw className="w-3 h-3 text-zinc-500" />
                          <span>Restart Demo</span>
                        </button>
                      </div>
                    </div>
                  </>
                )}

                {/* Message: Remind Scheduled */}
                {orderStage === "reminded" && (
                  <>
                    <div className="ml-auto bg-[#D9FDD3] text-zinc-900 rounded-2xl rounded-tr-xs px-2.5 py-1 shadow-2xs max-w-[85%] text-[10px] font-medium flex items-center justify-between gap-1.5 border border-emerald-200/40">
                      <span>Remind tomorrow morning</span>
                      <div className="flex items-center gap-1 shrink-0">
                        <span className="text-[7.5px] text-zinc-500">08:01 AM</span>
                        <CheckCheck className="h-3 w-3 text-[#53BDEB]" />
                      </div>
                    </div>
                    <div className="mr-auto bg-white rounded-2xl rounded-tl-xs shadow-2xs max-w-[92%] border border-amber-200 overflow-hidden">
                      <div className="p-2.5 space-y-1.5">
                        <div className="flex items-center gap-1 text-amber-800 font-bold text-[10.5px]">
                          <Clock className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                          <span>Reminder Set</span>
                        </div>
                        <p className="text-[9.5px] text-zinc-600 leading-snug">
                          Reminder set for tomorrow morning. We&apos;ll check back with you then.
                        </p>
                        <div className="flex justify-end text-[7.5px] text-zinc-400 font-mono">
                          08:01 AM
                        </div>
                      </div>
                      <div className="border-t border-zinc-150 bg-zinc-50/50 flex divide-x divide-zinc-150">
                        <button
                          type="button"
                          onClick={() => setOrderStage("breakdown")}
                          className="flex-1 py-1.5 px-2 text-center text-[9.5px] font-semibold text-blue-600 hover:bg-blue-50/60 active:bg-blue-100/60 transition-colors cursor-pointer"
                        >
                          Order Now
                        </button>
                        <button
                          type="button"
                          onClick={() => setOrderStage("initial")}
                          className="py-1.5 px-2 text-center text-[9.5px] font-medium text-zinc-500 hover:bg-zinc-100 transition-colors cursor-pointer"
                        >
                          Restart
                        </button>
                      </div>
                    </div>
                  </>
                )}

                {/* Message: Skipped */}
                {orderStage === "skipped" && (
                  <>
                    <div className="ml-auto bg-[#D9FDD3] text-zinc-900 rounded-2xl rounded-tr-xs px-2.5 py-1 shadow-2xs max-w-[85%] text-[10px] font-medium flex items-center justify-between gap-1.5 border border-emerald-200/40">
                      <span>Skipped for this week</span>
                      <div className="flex items-center gap-1 shrink-0">
                        <span className="text-[7.5px] text-zinc-500">08:01 AM</span>
                        <CheckCheck className="h-3 w-3 text-[#53BDEB]" />
                      </div>
                    </div>
                    <div className="mr-auto bg-white rounded-2xl rounded-tl-xs shadow-2xs max-w-[92%] border border-zinc-200 overflow-hidden">
                      <div className="p-2.5 space-y-1.5">
                        <div className="flex items-center gap-1 text-zinc-800 font-bold text-[10.5px]">
                          <CheckCircle2 className="w-3.5 h-3.5 text-zinc-600 shrink-0" />
                          <span>Restock Skipped</span>
                        </div>
                        <p className="text-[9.5px] text-zinc-600 leading-snug">
                          No problem, restock skipped for this week.
                        </p>
                        <div className="flex justify-end text-[7.5px] text-zinc-400 font-mono">
                          08:01 AM
                        </div>
                      </div>
                      <div className="border-t border-zinc-150 bg-zinc-50/50 flex divide-x divide-zinc-150">
                        <button
                          type="button"
                          onClick={() => setOrderStage("breakdown")}
                          className="flex-1 py-1.5 px-2 text-center text-[9.5px] font-semibold text-blue-600 hover:bg-blue-50/60 active:bg-blue-100/60 transition-colors cursor-pointer"
                        >
                          Order Now
                        </button>
                        <button
                          type="button"
                          onClick={() => setOrderStage("initial")}
                          className="py-1.5 px-2 text-center text-[9.5px] font-medium text-zinc-500 hover:bg-zinc-100 transition-colors cursor-pointer"
                        >
                          Restart
                        </button>
                      </div>
                    </div>
                  </>
                )}
              </div>

              {/* Authentic WhatsApp iOS Bottom Input Bar */}
              <div className="bg-[#F6F6F6] border-t border-gray-200/80 px-2 py-1 flex items-center gap-1.5 shrink-0 z-10">
                <div className="w-6 h-6 rounded-full bg-zinc-200/90 flex items-center justify-center text-zinc-600 select-none shrink-0 cursor-pointer hover:bg-zinc-300 transition-colors">
                  <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
                </div>
                <div className="flex-1 h-6.5 bg-white border border-gray-300/80 rounded-full px-2.5 flex items-center justify-between text-[9.5px] text-gray-400 select-none shadow-2xs">
                  <span className="font-sans">Message</span>
                </div>
                <Camera className="w-3.5 h-3.5 text-zinc-500 cursor-pointer shrink-0 hover:text-zinc-700 transition-colors" />
                <Mic className="w-3.5 h-3.5 text-[#007AFF] cursor-pointer shrink-0 hover:opacity-80 transition-opacity" />
              </div>

              {/* iOS Home Indicator Bar */}
              <div className="w-full bg-[#F6F6F6] pb-2 pt-0.5 flex justify-center shrink-0">
                <div className="w-16 h-0.75 bg-black/25 rounded-full pointer-events-none" />
              </div>
            </div>
          </div>
        </div>
      </IphoneFrame>
    </div>
  );
}
