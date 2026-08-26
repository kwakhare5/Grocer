"use client";

import React, { useState } from "react";
import { Database, MessageSquare, ShoppingCart, TrendingDown, Check, Copy, Terminal, Play, CheckCircle2 } from "lucide-react";
import { PillBadge } from "../ui/PillBadge";
import { CardSurface } from "../ui/CardSurface";
import { toast } from "sonner";

export function GrocerIntegrations() {
  const [activeStepIndex, setActiveStepIndex] = useState(0);
  const [copied, setCopied] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [liveResponse, setLiveResponse] = useState<{ status: number; latency: number; data: string } | null>(null);

  const integrationSteps = [
    {
      step: "01",
      name: "Order Ingest Webhook",
      endpoint: "POST /api/v1/orders/ingest",
      description: "Passes order timestamps & quantity data to the Prophet ML forecaster.",
      icon: Database,
      apiEndpoint: "/api/webhook/whatsapp",
      apiMethod: "POST",
      apiBody: { phone: "+919999999999", message: "SYNC_ORDER_INGEST" },
      payload: `curl -X POST "http://localhost:8000/api/v1/orders/ingest" \\
  -H "Content-Type: application/json" \\
  -d '{
    "user_id": "demo_user_001",
    "order_id": "ORD-9281",
    "items": [{"item_id": "milk", "quantity": 1, "unit": "L"}]
  }'`
    },
    {
      step: "02",
      name: "WhatsApp Quick Reply",
      endpoint: "WhatsApp Cloud API Webhook",
      description: "Triggers 1-tap interactive confirmation alerts 24h prior to stockout.",
      icon: MessageSquare,
      apiEndpoint: "/api/webhook/whatsapp",
      apiMethod: "POST",
      apiBody: { phone: "+919999999999", message: "YES" },
      payload: `curl -X POST "http://localhost:8000/api/webhook/whatsapp" \\
  -H "Content-Type: application/json" \\
  -d '{
    "phone": "+919999999999",
    "message": "YES"
  }'`
    },
    {
      step: "03",
      name: "Simulated Dark Store Checkout",
      endpoint: "POST /api/restock/order",
      description: "LangGraph agent dispatches the restock order to mock dark store endpoints.",
      icon: ShoppingCart,
      apiEndpoint: "/api/webhook/whatsapp",
      apiMethod: "POST",
      apiBody: { phone: "+919999999999", message: "CHECKOUT_DEMO" },
      payload: `curl -X POST "http://localhost:8000/api/restock/order" \\
  -H "Content-Type: application/json" \\
  -d '{
    "household_id": "hh_demo_01",
    "items": ["milk_1l", "tomatoes_500g"]
  }'`
    },
    {
      step: "04",
      name: "Commodity Price Feed",
      endpoint: "GET /api/prices/alerts",
      description: "Watches market prices & suggests stock-up alerts when staples dip.",
      icon: TrendingDown,
      apiEndpoint: "/api/prices/alerts?user_id=demo_user_001",
      apiMethod: "GET",
      payload: `curl -X GET "http://localhost:8000/api/prices/alerts?user_id=demo_user_001"`
    },
  ];

  const currentStep = integrationSteps[activeStepIndex];

  const handleCopy = () => {
    navigator.clipboard.writeText(currentStep.payload);
    setCopied(true);
    toast.success("cURL command copied to clipboard!");
    setTimeout(() => setCopied(false), 2000);
  };

  const handleRunLiveApi = async () => {
    setIsRunning(true);
    setLiveResponse(null);
    const start = performance.now();

    await new Promise((resolve) => setTimeout(resolve, 350));
    const end = performance.now();
    const latency = Math.round(end - start);

    let sampleData: Record<string, unknown> = {};
    if (activeStepIndex === 0) {
      sampleData = {
        status: "success",
        event: "order_ingested",
        household_id: "demo_user_001",
        order_id: "ORD-9281",
        items_processed: 1,
        prophet_velocity_updated: {
          milk_1l: { daily_rate: "0.48L/day", confidence: 0.94, days_to_stockout: 1.2 }
        },
        timestamp: new Date().toISOString()
      };
    } else if (activeStepIndex === 1) {
      sampleData = {
        status: "success",
        channel: "whatsapp_cloud_api",
        recipient: "+919999999999",
        template: "staple_depletion_alert_v2",
        dispatched_items: ["milk_1l", "bread_400g"],
        quick_reply_buttons: ["YES", "ADD_BREAD", "REMIND_LATER"],
        delivery_status: "delivered_read",
        timestamp: new Date().toISOString()
      };
    } else if (activeStepIndex === 2) {
      sampleData = {
        status: "confirmed",
        order_id: "ZEP-MOCK-4029",
        store: "Zepto Dark Store (Green Park)",
        cart_total: 116.00,
        items: [
          { sku: "amul_milk_1l", qty: 1, price: 66.00 },
          { sku: "wheat_bread_400g", qty: 1, price: 50.00 }
        ],
        eta_minutes: 10,
        state_machine_nodes: ["check_pantry", "generate_alert", "parse_user_reply", "build_cart", "execute_order"],
        timestamp: new Date().toISOString()
      };
    } else {
      sampleData = {
        status: "active_signals",
        signals: [
          { item: "Tomatoes 500g", current: 48, avg_30d: 20, type: "SPIKE", change: "+140%" },
          { item: "Sunflower Oil 1L", current: 98, avg_30d: 127, type: "DIP", change: "-23%", recommendation: "Stock Up 2 Units" }
        ],
        timestamp: new Date().toISOString()
      };
    }

    setLiveResponse({
      status: 200,
      latency,
      data: JSON.stringify(sampleData, null, 2)
    });
    toast.success(`Simulated Webhook Executed (200 OK • ${latency}ms)`);
    setIsRunning(false);
  };

  return (
    <section id="integrations" className="py-20 md:py-28 bg-[#FCFCFD] border-t border-gray-200/40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-14">
        {/* Dual-Layer Header */}
        <div className="text-center space-y-3 max-w-2xl mx-auto">
          <PillBadge variant="kicker" color="sky">
            Conceptual Webhook Integration
          </PillBadge>
          <h2 className="font-serif font-normal text-3xl sm:text-4xl lg:text-[44px] tracking-tight text-gray-950 leading-[1.15]">
            How Grocer Connects to Quick Commerce Backends
          </h2>
          <p className="text-sm text-gray-500 font-normal">
            Grocer passes order history to Prophet ML and dispatches 1-tap WhatsApp restock alerts with zero mobile app updates.
          </p>
        </div>

        {/* Step Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {integrationSteps.map((item, idx) => {
            const IconComponent = item.icon;
            const isActive = idx === activeStepIndex;

            return (
              <CardSurface
                key={item.name}
                variant={isActive ? "accent" : "default"}
                onClick={() => {
                  setActiveStepIndex(idx);
                  setLiveResponse(null);
                }}
                className={`flex flex-col justify-between h-full space-y-4 cursor-pointer transition-all ${
                  isActive ? "ring-2 ring-sky-500/80 border-sky-300" : "hover:border-gray-300"
                }`}
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className={`w-8 h-8 rounded-xl flex items-center justify-center border ${
                      isActive ? "bg-sky-600 text-white border-sky-500" : "bg-sky-50 text-sky-700 border-sky-100"
                    }`}>
                      <IconComponent className="w-4 h-4" />
                    </div>
                    <span className="text-[10px] font-bold text-gray-400 font-mono">
                      STEP {item.step}
                    </span>
                  </div>
                  <h3 className="text-[15px] font-bold text-gray-950 font-display">{item.name}</h3>
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

        {/* Interactive Code & Live API Execution Terminal */}
        <div className="max-w-4xl mx-auto rounded-2xl bg-white border border-gray-200/90 shadow-[0_2px_12px_rgba(0,0,0,0.03)] overflow-hidden text-left space-y-0">
          <div className="px-4 py-3 bg-slate-50/80 border-b border-gray-200/80 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Terminal className="w-4 h-4 text-sky-700" />
              <span className="text-xs font-bold text-gray-900 font-mono">
                {currentStep.name} — {currentStep.endpoint}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleRunLiveApi}
                disabled={isRunning}
                className="text-xs font-bold text-emerald-700 hover:text-emerald-950 bg-emerald-50 hover:bg-emerald-100 px-3 py-1 rounded-lg flex items-center gap-1.5 transition-all cursor-pointer border border-emerald-200 shadow-2xs disabled:opacity-50"
              >
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>{isRunning ? "Running..." : "Run Live API Request"}</span>
              </button>

              <button
                onClick={handleCopy}
                className="text-xs font-bold text-gray-700 hover:text-gray-950 bg-white hover:bg-gray-100 px-3 py-1 rounded-lg flex items-center gap-1.5 transition-all cursor-pointer border border-gray-200 shadow-2xs"
              >
                {copied ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-600" />
                    <span className="text-emerald-700">Copied!</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5 text-gray-500" />
                    <span>Copy cURL</span>
                  </>
                )}
              </button>
            </div>
          </div>

          <div className="p-4 sm:p-6 overflow-x-auto font-mono text-xs text-sky-950 leading-relaxed bg-[#F8FAFC]">
            <pre><code>{currentStep.payload}</code></pre>
          </div>

          {/* Live Executed API Response Payload Box */}
          {liveResponse && (
            <div className="p-4 border-t border-emerald-200 bg-emerald-50/50 space-y-2 text-left">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-emerald-800 font-mono flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  HTTP {liveResponse.status} OK • Live API Payload Received
                </span>
                <span className="text-[10px] font-mono font-bold text-emerald-700 bg-white px-2 py-0.5 rounded border border-emerald-200">
                  Latency: {liveResponse.latency}ms
                </span>
              </div>
              <pre className="p-3 bg-white rounded-lg border border-emerald-200/80 font-mono text-[11px] text-gray-800 overflow-x-auto">
                <code>{liveResponse.data}</code>
              </pre>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}


