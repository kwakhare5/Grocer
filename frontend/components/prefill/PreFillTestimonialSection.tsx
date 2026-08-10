"use client";

import React from "react";
import { Star } from "lucide-react";

export function PreFillTestimonialSection() {
  return (
    <section className="py-20 md:py-28 bg-[#FAFAFA] border-t border-gray-200/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
        {/* Beside 1:1 Asymmetric Split Card 1: 3x Stat Tile + Customer Quote */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
          {/* Left Stat Square Card with Soft Mesh Gradient Background */}
          <div className="lg:col-span-4 bg-white rounded-3xl p-8 border border-gray-200/60 shadow-[0_2px_12px_rgba(0,0,0,0.04)] flex flex-col justify-between relative overflow-hidden space-y-6">
            <div className="space-y-2 relative z-10">
              <span className="text-6xl sm:text-7xl font-serif font-light tracking-tighter text-gray-950 block">
                3x
              </span>
              <p className="text-xs font-bold text-gray-500 uppercase tracking-widest">
                Faster Kitchen Restocks
              </p>
            </div>

            {/* Soft Ambient Mesh Gradient Blur Tile */}
            <div className="absolute -bottom-10 -right-10 w-48 h-48 bg-gradient-to-tr from-amber-400/30 via-emerald-500/20 to-sky-400/30 rounded-full filter blur-2xl pointer-events-none" />
          </div>

          {/* Right Quote Card */}
          <div className="lg:col-span-8 bg-white rounded-3xl p-8 sm:p-10 border border-gray-200/60 shadow-[0_2px_12px_rgba(0,0,0,0.04)] flex flex-col justify-between space-y-6">
            <div className="space-y-4">
              <span className="text-xs font-bold font-mono text-emerald-800 uppercase tracking-widest bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200 inline-block">
                ZEPTO VERIFIED USER
              </span>
              <h3 className="font-serif font-normal text-xl sm:text-2xl text-gray-950 leading-relaxed italic">
                "I went from ordering groceries 4 times a week on 3 different apps to confirming everything in 1 tap on WhatsApp. It has completely changed our family routine."
              </h3>
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-gray-100">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-emerald-950 text-white font-serif text-sm flex items-center justify-center font-bold">
                  AP
                </div>
                <div>
                  <h4 className="font-bold text-sm text-gray-950">Ananya Patel</h4>
                  <p className="text-xs text-gray-400 font-medium">Head of Product & Mother of 2</p>
                </div>
              </div>

              <div className="flex items-center gap-1 text-amber-400">
                <Star className="w-4 h-4 fill-amber-400" />
                <Star className="w-4 h-4 fill-amber-400" />
                <Star className="w-4 h-4 fill-amber-400" />
                <Star className="w-4 h-4 fill-amber-400" />
                <Star className="w-4 h-4 fill-amber-400" />
              </div>
            </div>
          </div>
        </div>

        {/* Beside 1:1 Asymmetric Split Card 2: 2x Stat Tile + Customer Quote */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
          {/* Left Stat Square Card */}
          <div className="lg:col-span-4 bg-white rounded-3xl p-8 border border-gray-200/60 shadow-[0_2px_12px_rgba(0,0,0,0.04)] flex flex-col justify-between relative overflow-hidden space-y-6">
            <div className="space-y-2 relative z-10">
              <span className="text-6xl sm:text-7xl font-serif font-light tracking-tighter text-gray-950 block">
                2x
              </span>
              <p className="text-xs font-bold text-gray-500 uppercase tracking-widest">
                Time Saved Every Month
              </p>
            </div>

            {/* Soft Ambient Mesh Gradient Blur Tile */}
            <div className="absolute -bottom-10 -right-10 w-48 h-48 bg-gradient-to-tr from-sky-400/30 via-indigo-500/20 to-emerald-400/30 rounded-full filter blur-2xl pointer-events-none" />
          </div>

          {/* Right Quote Card */}
          <div className="lg:col-span-8 bg-white rounded-3xl p-8 sm:p-10 border border-gray-200/60 shadow-[0_2px_12px_rgba(0,0,0,0.04)] flex flex-col justify-between space-y-6">
            <div className="space-y-4">
              <span className="text-xs font-bold font-mono text-sky-800 uppercase tracking-widest bg-sky-50 px-3 py-1 rounded-full border border-sky-200 inline-block">
                BLINKIT USER
              </span>
              <h3 className="font-serif font-normal text-xl sm:text-2xl text-gray-950 leading-relaxed italic">
                "Before PreFill I had to stop what I was doing every morning to check the fridge for milk and coffee. Now it just arrives before I even notice."
              </h3>
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-gray-100">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-sky-950 text-white font-serif text-sm flex items-center justify-center font-bold">
                  RK
                </div>
                <div>
                  <h4 className="font-bold text-sm text-gray-950">Rohan Kumar</h4>
                  <p className="text-xs text-gray-400 font-medium">Software Engineer, Bangalore</p>
                </div>
              </div>

              <div className="flex items-center gap-1 text-amber-400">
                <Star className="w-4 h-4 fill-amber-400" />
                <Star className="w-4 h-4 fill-amber-400" />
                <Star className="w-4 h-4 fill-amber-400" />
                <Star className="w-4 h-4 fill-amber-400" />
                <Star className="w-4 h-4 fill-amber-400" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
