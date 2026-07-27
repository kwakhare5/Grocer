"use client";

import { useState } from "react";
import { 
  MessageSquare, 
  Globe, 
  Phone, 
  MessageCircle, 
  Filter, 
  UserCheck, 
  Sparkles
} from "lucide-react";

export default function PreFillFeatureSidebar() {
  const [activeTab, setActiveTab] = useState("messaging");

  const sidebarItems = [
    { id: "website", label: "AI Web Assistant", icon: Globe },
    { id: "phone", label: "AI Voice Restocker", icon: Phone },
    { id: "messaging", label: "WhatsApp Restock Engine", icon: MessageSquare },
    { id: "commenting", label: "Social Reorder Bot", icon: MessageCircle },
    { id: "lead", label: "Household Intent Capture", icon: Filter },
    { id: "handoff", label: "Human Store Hand-off", icon: UserCheck },
    { id: "recommendations", label: "Predictive Cart Builder", icon: Sparkles },
  ];

  return (
    <div className="w-full bg-[#FFFFFF] border border-stone-200/90 rounded-3xl p-6 sm:p-10 shadow-[0_4px_24px_rgba(0,0,0,0.03)] bg-ascii-dotted-grid relative overflow-hidden">
      
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center z-10 relative">
        
        {/* Left Sidebar Menu (4 cols) */}
        <div className="lg:col-span-4 flex flex-col gap-2.5">
          {sidebarItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full px-4 py-3 rounded-full text-xs font-semibold flex items-center gap-3 transition-all cursor-pointer select-none ${
                  isActive
                    ? "bg-white text-[#252525] shadow-[0_2px_10px_rgba(0,0,0,0.08)] border border-stone-200"
                    : "text-stone-500 hover:text-[#252525] hover:bg-stone-100/60"
                }`}
              >
                <Icon className={`h-4 w-4 ${isActive ? "text-[#252525]" : "text-stone-400"}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>

        {/* Right Main Showcase Panel (8 cols - Pastel Amber Styled) */}
        <div className="lg:col-span-8 card-pastel-amber p-6 sm:p-8 flex flex-col lg:flex-row items-center justify-between gap-8 shadow-xs relative">
          
          {/* Left Text & CTA */}
          <div className="flex-1 flex flex-col items-start gap-4">
            <h3 className="text-2xl sm:text-3xl font-extrabold font-sans tracking-tight title-accent">
              Automate WhatsApp Reorders
            </h3>
            <p className="text-xs sm:text-sm text-stone-700 font-medium leading-relaxed max-w-sm">
              Deliver personalized restock prompts straight to WhatsApp. Customers confirm 10-minute grocery deliveries in a single tap.
            </p>
            <a
              href="#demo-stage"
              className="mt-2 inline-flex items-center gap-2 bg-white text-[#252525] font-bold text-xs px-5 py-2.5 rounded-full border border-stone-300 shadow-xs hover:bg-stone-50 transition-all cursor-pointer"
            >
              <span>See WhatsApp Demo</span>
              <Sparkles className="h-3.5 w-3.5 text-stone-700" />
            </a>
          </div>

          {/* Right Live Inbox UI Mockup */}
          <div className="w-full max-w-[320px] bg-white rounded-2xl border border-amber-200 p-4 shadow-sm flex flex-col gap-3 relative">
            
            {/* Header user */}
            <div className="flex items-center justify-between border-b border-stone-100 pb-3">
              <div className="flex items-center gap-2">
                <div className="h-6 w-6 rounded-full bg-[#252525] text-white flex items-center justify-center text-[10px] font-extrabold">
                  P
                </div>
                <div className="text-[11px] font-bold text-[#252525]">PreFill Restock Stream</div>
              </div>
              <span className="text-[10px] text-emerald-600 font-semibold">Active Engine</span>
            </div>

            {/* Search bar */}
            <div className="px-3 py-1.5 bg-stone-100 rounded-lg text-[11px] text-stone-400 flex items-center justify-between font-medium">
              <span>Filter household alerts...</span>
            </div>

            {/* Inbox Message List */}
            <div className="flex flex-col gap-2.5">
              
              {/* Message 1 */}
              <div className="p-2.5 rounded-xl bg-emerald-50/70 border border-emerald-100 flex items-center gap-2.5">
                <div className="h-8 w-8 rounded-full bg-emerald-100 text-emerald-800 font-bold text-xs flex items-center justify-center shrink-0">
                  J
                </div>
                <div className="flex flex-col flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-xs text-[#252525]">Josh (Bandra)</span>
                    <span className="text-[9px] text-stone-400">4:20 PM</span>
                  </div>
                  <span className="text-[11px] text-stone-700 truncate font-medium">Fresh Milk 1L at 20% threshold — reordered</span>
                </div>
              </div>

              {/* Message 2 */}
              <div className="p-2.5 rounded-xl bg-blue-50/70 border border-blue-100 flex items-center gap-2.5">
                <div className="h-8 w-8 rounded-full bg-blue-100 text-blue-800 font-bold text-xs flex items-center justify-center shrink-0">
                  T
                </div>
                <div className="flex flex-col flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-xs text-[#252525]">Theresa (Indiranagar)</span>
                    <span className="text-[9px] text-stone-400">8:30 AM</span>
                  </div>
                  <span className="text-[11px] text-stone-700 truncate font-medium">Atta 5kg restock confirmed — 10 min ETA</span>
                </div>
              </div>

              {/* Message 3 */}
              <div className="p-2.5 rounded-xl bg-amber-50/70 border border-amber-100 flex items-center gap-2.5">
                <div className="h-8 w-8 rounded-full bg-amber-100 text-amber-800 font-bold text-xs flex items-center justify-center shrink-0">
                  M
                </div>
                <div className="flex flex-col flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-xs text-[#252525]">Mark (Gachibowli)</span>
                    <span className="text-[9px] text-stone-400">Yesterday</span>
                  </div>
                  <span className="text-[11px] text-stone-700 truncate font-medium">Sunflower Oil 1L — 23% price drop applied</span>
                </div>
              </div>

            </div>

            {/* Clean Channel Badges */}
            <div className="flex items-center justify-center gap-2 mt-1">
              <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 text-[10px] font-bold">WhatsApp</span>
              <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-800 border border-blue-200 text-[10px] font-bold">Web SDK</span>
              <span className="px-2 py-0.5 rounded bg-stone-100 text-stone-700 border border-stone-200 text-[10px] font-bold">REST Webhooks</span>
            </div>

          </div>

        </div>

      </div>

    </div>
  );
}
