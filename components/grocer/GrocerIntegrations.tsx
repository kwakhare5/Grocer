"use client";

import React, { useState } from "react";
import { Database, MessageSquare, ShoppingCart, Cpu, Check, Copy, Terminal, Play, CheckCircle2 } from "lucide-react";
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
      description: "Logs order timestamps and item quantities to update household consumption estimates.",
      icon: Database,
      payload: `curl -X POST "http://localhost:8000/api/v1/orders/ingest" \\
  -H "Content-Type: application/json" \\
  -d '{
    "user_id": "demo_user_001",
    "order_id": "ORD-9281",
    "items": [{"item_id": "milk_1l", "quantity": 1, "unit": "L"}]
  }'`
    },
    {
      step: "02",
      name: "WhatsApp Restock Alert",
      endpoint: "WhatsApp Cloud API Webhook",
      description: "Sends quick-reply restock reminders to customers 24 hours before staples run out.",
      icon: MessageSquare,
      payload: `curl -X POST "http://localhost:8000/api/webhook/whatsapp" \\
  -H "Content-Type: application/json" \\
  -d '{
    "phone": "+919820192831",
    "message": "YES"
  }'`
    },
    {
      step: "03",
      name: "Dark Store Order Queue",
      endpoint: "POST /api/restock/order",
      description: "Routes approved customer orders directly to the nearest store fulfillment queue.",
      icon: ShoppingCart,
      payload: `curl -X POST "http://localhost:8000/api/restock/order" \\
  -H "Content-Type: application/json" \\
  -d '{
    "household_id": "hh_bandra_01",
    "store_code": "MUM-BW-01",
    "items": ["amul_milk_1l", "wheat_bread_400g"]
  }'`
    },
    {
      step: "04",
      name: "Store Stock Transfer",
      endpoint: "POST /api/recommendations/{id}/approve",
      description: "Authorizes and schedules inventory transfers between nearby stores.",
      icon: Cpu,
      payload: `curl -X POST "http://localhost:8000/api/recommendations/rec_04_transfer/approve" \\
  -H "Content-Type: application/json" \\
  -d '{
    "operator_id": "ops_lead",
    "action_type": "TRANSFER",
    "quantity": 20,
    "source_store": "Store 02",
    "destination_store": "Store 04"
  }'`
    },
  ];

  const currentStep = integrationSteps[activeStepIndex];

  const handleCopy = () => {
    navigator.clipboard.writeText(currentStep.payload);
    setCopied(true);
    toast.success("cURL command copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  };

  const handleRunLiveApi = async () => {
    setIsRunning(true);
    setLiveResponse(null);
    const start = performance.now();

    await new Promise((resolve) => setTimeout(resolve, 300));
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
          milk_1l: { daily_rate: "0.48L/day", confidence: 0.94, hours_to_stockout: 28 }
        },
        timestamp: new Date().toISOString()
      };
    } else if (activeStepIndex === 1) {
      sampleData = {
        status: "success",
        channel: "whatsapp_cloud_api",
        recipient: "+919820192831",
        template: "staple_depletion_alert_v2",
        dispatched_items: ["Fresh Milk 1L", "Whole Wheat Bread 400g"],
        quick_reply_buttons: ["YES", "REMIND_LATER", "SKIP"],
        delivery_status: "delivered",
        timestamp: new Date().toISOString()
      };
    } else if (activeStepIndex === 2) {
      sampleData = {
        status: "confirmed",
        order_id: "ZEP-ORD-8821",
        fulfillment_store: "Bandra West Dark Store (MUM-BW-01)",
        cart_total: 116.00,
        items: [
          { sku: "amul_milk_1l", qty: 1, price: 66.00 },
          { sku: "wheat_bread_400g", qty: 1, price: 50.00 }
        ],
        eta_minutes: 10,
        timestamp: new Date().toISOString()
      };
    } else {
      sampleData = {
        status: "APPROVED_AND_EXECUTED",
        recommendation_id: "rec_04_transfer",
        action: "TRANSFER",
        quantity: 20,
        source: "St 02 (Bandra West)",
        destination: "St 04 (Lower Parel)",
        agent_precheck: "PASSED (Safe excess verified: 35L available)",
        agent_nodes_executed: [
          "1. validate_approval",
          "2. check_inventory_freshness",
          "3. dispatch_fleet_courier",
          "4. verify_stock_balance"
        ],
        stockout_prevented: true,
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
    <section id="integrations" className="py-16 md:py-24 bg-[#FAFAFA] border-t border-zinc-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10">
        
        {/* Two-Column Header */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-end">
          <div className="lg:col-span-7 space-y-2">
            <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-blue-800 bg-blue-50 px-2.5 py-0.5 rounded border border-blue-200 inline-block">
              Developer Endpoints
            </span>
            <h2 className="font-sans font-bold text-2xl sm:text-3xl lg:text-4xl tracking-tight text-zinc-950">
              API & Webhook Integrations
            </h2>
          </div>
          <div className="lg:col-span-5">
            <p className="text-xs sm:text-sm text-zinc-600 font-normal leading-relaxed">
              Connect your store inventory, order processing, and WhatsApp messaging.
            </p>
          </div>
        </div>

        {/* Interactive 4-Step Terminal Switcher */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          
          {/* Left Column: 4 Clean Tabs */}
          <div className="lg:col-span-4 space-y-2.5">
            {integrationSteps.map((step, idx) => {
              const Icon = step.icon;
              const isActive = activeStepIndex === idx;
              return (
                <button
                  key={step.step}
                  type="button"
                  onClick={() => {
                    setActiveStepIndex(idx);
                    setLiveResponse(null);
                  }}
                  className={`w-full text-left p-3.5 rounded-xl border transition-all cursor-pointer ${
                    isActive
                      ? "bg-white border-blue-600 shadow-2xs ring-1 ring-blue-500"
                      : "bg-white border-zinc-200 hover:border-zinc-300 hover:bg-zinc-50"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-bold text-zinc-400 font-mono">
                      STEP {step.step}
                    </span>
                    <Icon className={`w-3.5 h-3.5 ${isActive ? "text-blue-600" : "text-zinc-400"}`} />
                  </div>
                  <h4 className="text-xs font-bold text-zinc-950 mb-0.5">
                    {step.name}
                  </h4>
                  <span className="text-[9.5px] font-bold text-zinc-700 bg-zinc-50 px-2 py-0.5 rounded border border-zinc-200 font-mono block truncate">
                    {step.endpoint}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Right Column: Code Payload & Live Execution Terminal */}
          <div className="lg:col-span-8 bg-white rounded-xl border border-zinc-200 shadow-2xs overflow-hidden">
            
            {/* Terminal Top Bar */}
            <div className="px-4 py-3 bg-zinc-50 border-b border-zinc-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Terminal className="w-3.5 h-3.5 text-zinc-500" />
                <span className="text-xs font-bold text-zinc-900 font-mono">
                  {currentStep.endpoint}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleCopy}
                  className="flex items-center gap-1 text-[10px] font-bold text-zinc-700 bg-white hover:bg-zinc-100 border border-zinc-200 px-2.5 py-1 rounded transition-all cursor-pointer"
                >
                  {copied ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                  <span>{copied ? "Copied" : "Copy cURL"}</span>
                </button>
                <button
                  type="button"
                  onClick={handleRunLiveApi}
                  disabled={isRunning}
                  className="flex items-center gap-1.5 text-[10px] font-bold text-white bg-blue-600 hover:bg-blue-700 px-3 py-1 rounded shadow-2xs transition-all cursor-pointer disabled:opacity-50"
                >
                  <Play className={`w-2.5 h-2.5 fill-current ${isRunning ? "animate-spin text-blue-200" : "text-white"}`} />
                  <span>{isRunning ? "Sending..." : "Test Endpoint"}</span>
                </button>
              </div>
            </div>

            {/* Code Payload Editor */}
            <div className="p-4 sm:p-5 overflow-x-auto font-mono text-xs text-zinc-900 leading-relaxed bg-[#FBFBFC]">
              <pre className="text-[11.5px] text-zinc-800 leading-normal">
                <code>{currentStep.payload}</code>
              </pre>
            </div>

            {/* Live Response Drawer */}
            {liveResponse && (
              <div className="border-t border-zinc-200 bg-blue-50/40 p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-blue-900 font-mono flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    Response Received (HTTP {liveResponse.status} OK)
                  </span>
                  <span className="text-[10px] font-mono font-bold text-blue-800 bg-white px-2 py-0.5 rounded border border-blue-200">
                    Latency: {liveResponse.latency}ms
                  </span>
                </div>
                <pre className="p-3 bg-white rounded-lg border border-blue-200/80 font-mono text-[11px] text-zinc-800 overflow-x-auto">
                  <code>{liveResponse.data}</code>
                </pre>
              </div>
            )}
          </div>

        </div>

      </div>
    </section>
  );
}
