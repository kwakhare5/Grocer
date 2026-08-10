"use client";

import React from "react";
import { Zap, MessageSquare, ShoppingBag, Truck, ShieldCheck, ArrowUpRight } from "lucide-react";
import { CardSurface } from "../ui/CardSurface";

export function PreFillIntegrations() {
  const integrations = [
    {
      name: "Zepto 10-Min Restock",
      category: "Dark Store Network",
      description: "Direct integration with neighborhood Zepto dark stores for under 10-minute automated deliveries.",
      icon: ShoppingBag,
      color: "text-purple-600 bg-purple-50 border-purple-100",
      badge: "LIVE INTEGRATION",
    },
    {
      name: "Blinkit Instant Delivery",
      category: "Quick Commerce",
      description: "Auto-routes grocery replenishment carts straight to Blinkit for 1-tap confirmation.",
      icon: Truck,
      color: "text-amber-600 bg-amber-50 border-amber-100",
      badge: "LIVE INTEGRATION",
    },
    {
      name: "Swiggy Instamart",
      category: "Grocery Delivery",
      description: "Predictive pantry restocking connected directly to Swiggy Instamart accounts.",
      icon: Zap,
      color: "text-orange-600 bg-orange-50 border-orange-100",
      badge: "LIVE INTEGRATION",
    },
    {
      name: "WhatsApp Business API",
      category: "1-Tap Alerts",
      description: "Sends crisp, friendly 24-hour stockout notifications straight to your family WhatsApp chat.",
      icon: MessageSquare,
      color: "text-emerald-600 bg-emerald-50 border-emerald-100",
      badge: "VERIFIED BOT",
    },
  ];

  return (
    <section id="integrations" className="py-20 md:py-28 bg-[#FAFAFA] border-t border-gray-200/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-14">
        {/* Section Header */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-end">
          <div className="lg:col-span-7 space-y-3">
            <h2 className="font-serif font-normal text-3xl sm:text-4xl lg:text-[44px] tracking-tight text-gray-950 leading-[1.15]">
              Integrates seamlessly with quick-commerce apps
            </h2>
          </div>
          <div className="lg:col-span-5">
            <p className="text-sm sm:text-base text-gray-500 font-normal leading-relaxed">
              PreFill works out of the box with India's leading 10-minute grocery apps and WhatsApp.
            </p>
          </div>
        </div>

        {/* Integration Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {integrations.map((item) => {
            const Icon = item.icon;
            return (
              <CardSurface key={item.name} variant="default">
                <div className="flex items-center justify-between">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center border ${item.color}`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <span className="text-[10px] font-bold font-mono px-2 py-0.5 rounded bg-gray-100 text-gray-600 border border-gray-200">
                    {item.badge}
                  </span>
                </div>

                <div className="space-y-2">
                  <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest block">
                    {item.category}
                  </span>
                  <h3 className="text-base font-bold text-gray-950 flex items-center justify-between">
                    <span>{item.name}</span>
                    <ArrowUpRight className="w-4 h-4 text-gray-400 group-hover:text-gray-950 transition-colors" />
                  </h3>
                  <p className="text-xs text-gray-500 font-normal leading-relaxed">
                    {item.description}
                  </p>
                </div>
              </CardSurface>
            );
          })}
        </div>
      </div>
    </section>
  );
}
