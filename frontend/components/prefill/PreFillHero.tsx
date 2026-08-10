"use client";

import React from "react";
import { Sparkles, Star, ArrowUpRight, Zap, MessageSquare } from "lucide-react";
import PhoneMockup from "../PhoneMockup";
import { PillBadge } from "../ui/PillBadge";
import { PillButton } from "../ui/PillButton";

export function PreFillHero() {
  return (
    <section id="demo" className="relative pt-12 pb-20 md:pt-16 md:pb-28 overflow-hidden bg-[#FAFAFA]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
          {/* Left Column: Beside 1:1 Headline Typography & Actions */}
          <div className="lg:col-span-6 flex flex-col items-start space-y-6">
            {/* Tagline Pill Badge: Reusable PillBadge kicker */}
            <PillBadge variant="kicker" color="sky">
              <Sparkles className="w-3.5 h-3.5 text-sky-600" />
              <span>Smart Grocery Restock App</span>
            </PillBadge>

            {/* Beside 1:1 Headline Typography with 21st.dev GradientText Accent */}
            <div className="space-y-4 max-w-xl">
              <h1 className="font-serif font-normal text-4xl sm:text-5xl lg:text-[56px] tracking-tight leading-[1.12]">
                The modern{" "}
                <span className="bg-gradient-to-r from-gray-950 via-sky-800 to-indigo-950 bg-clip-text text-transparent">
                  grocery carrier
                </span>
              </h1>
              <p className="text-sm sm:text-base text-gray-500 font-normal leading-relaxed">
                PreFill tracks what's in your kitchen and sends a WhatsApp message before you run empty. Reply YES to get groceries delivered in 10 minutes.
              </p>
            </div>

            {/* Action Buttons: Reusable PillButtons with Shimmer */}
            <div className="flex flex-wrap items-center gap-3 pt-1">
              <PillButton href="#demo" variant="primary">
                <span>Try PreFill</span>
                <ArrowUpRight className="w-4 h-4" />
              </PillButton>
              <PillButton href="#features" variant="secondary">
                Calculate Pantry Stock
              </PillButton>
            </div>

            {/* Beside 1:1 Micro Subtext */}
            <p className="text-[11px] font-semibold text-gray-400">
              Available on iOS, Android, WhatsApp & Web
            </p>

            {/* Divider Line */}
            <div className="w-full max-w-md h-px bg-gray-200/80 my-1" />

            {/* Beside 1:1 Rating Ribbon */}
            <div className="space-y-1">
              <p className="text-xs font-bold text-gray-900">
                Built for modern kitchens. Trusted by 75k+ households.
              </p>
              <div className="flex items-center gap-2 text-xs text-gray-500 font-medium">
                <div className="flex items-center text-amber-500 gap-0.5">
                  <Star className="w-3.5 h-3.5 fill-amber-400" />
                  <span className="font-bold text-gray-900 ml-1">4.9 stars</span>
                </div>
                <span className="text-gray-300">|</span>
                <span className="text-sky-800 font-bold">Test the interactive phone mockup on the right</span>
              </div>
            </div>
          </div>

          {/* Right Column: Beside 1:1 Ambient Stage Container & Floating Pills */}
          <div className="lg:col-span-6 flex justify-center lg:justify-end">
            <div className="relative w-full max-w-[440px] bg-gradient-to-tr from-sky-100/90 via-blue-50/40 to-indigo-100/90 border border-sky-200/80 rounded-[2.5rem] p-6 sm:p-8 shadow-xs flex items-center justify-center">
              
              {/* Floating Pill Badge 1: Top-Left (Reusable micro PillBadge) */}
              <div className="absolute -top-3 left-4 sm:-left-2 z-20">
                <PillBadge variant="micro" color="white">
                  <Zap className="w-3.5 h-3.5 text-amber-500" />
                  <span>10-Min Delivery</span>
                </PillBadge>
              </div>

              {/* Floating Pill Badge 2: Bottom-Right (Reusable dark micro PillBadge) */}
              <div className="absolute -bottom-3 right-4 sm:-right-2 z-20">
                <PillBadge variant="micro" color="dark">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                  <MessageSquare className="w-3.5 h-3.5 text-emerald-300" />
                  <span>1-Tap WhatsApp</span>
                </PillBadge>
              </div>

              {/* 6.3" Phone Mockup Stage */}
              <div className="w-[260px] sm:w-[280px] aspect-[1800/3680] shrink-0 relative z-10">
                <PhoneMockup activeScenario="whatsapp" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
