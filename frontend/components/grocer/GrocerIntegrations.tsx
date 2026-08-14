"use client";

import React from "react";
import { Database, MessageSquare, ShoppingCart, TrendingDown } from "lucide-react";
import { PillBadge } from "../ui/PillBadge";
import { CardSurface } from "../ui/CardSurface";

export function GrocerIntegrations() {
  const integrationSteps = [
    {
      step: "01",
      name: "Order Ingest Webhook",
      endpoint: "POST /api/v1/orders/ingest",
      description: "Passes order timestamps & quantity data to the Prophet ML forecaster.",
      icon: Database,
    },
    {
      step: "02",
      name: "WhatsApp Quick Reply",
      endpoint: "WhatsApp Cloud API",
      description: "Triggers 1-tap interactive confirmation alerts 24h prior to stockout.",
      icon: MessageSquare,
    },
    {
      step: "03",
      name: "Simulated Checkout",
      endpoint: "POST /api/v1/darkstore/checkout",
      description: "LangGraph agent dispatches the restock order to mock dark store APIs.",
      icon: ShoppingCart,
    },
    {
      step: "04",
      name: "Commodity Price Feed",
      endpoint: "TimescaleDB Feed",
      description: "Watches market prices & suggests stock-up alerts when staples dip.",
      icon: TrendingDown,
    },
  ];

  return (
    <section id="integrations" className="py-20 md:py-28 bg-[#FCFCFD] border-t border-gray-200/40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-14">
        {/* Header */}
        <div className="text-center space-y-3 max-w-2xl mx-auto">
          <PillBadge variant="kicker" color="sky">
            Conceptual Webhook Integration
          </PillBadge>
          <h2 className="font-serif font-normal text-3xl sm:text-4xl lg:text-[44px] tracking-tight text-gray-950 leading-[1.15]">
            How Grocer Connects to Quick Commerce Backends
          </h2>
          <p className="text-sm text-gray-500 font-normal">
            A 2-step REST webhook architecture designed for zero mobile app updates.
          </p>
        </div>

        {/* Integrations Step Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {integrationSteps.map((item) => {
            const IconComponent = item.icon;
            return (
              <CardSurface key={item.name} variant="default" className="flex flex-col justify-between h-full space-y-4">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="w-8 h-8 rounded-xl bg-sky-50 text-sky-700 flex items-center justify-center border border-sky-100">
                      <IconComponent className="w-4 h-4" />
                    </div>
                    <span className="text-[10px] font-bold text-gray-400 font-mono">
                      STEP {item.step}
                    </span>
                  </div>
                  <h3 className="text-[15px] font-bold text-gray-950">{item.name}</h3>
                  <p className="text-xs text-gray-500 font-normal leading-relaxed">{item.description}</p>
                </div>

                <div className="pt-2 border-t border-gray-100">
                  <span className="text-[9px] font-bold text-sky-800 bg-sky-50 px-2 py-1 rounded-md border border-sky-100 font-mono block truncate">
                    {item.endpoint}
                  </span>
                </div>
              </CardSurface>
            );
          })}
        </div>
      </div>
    </section>
  );
}

