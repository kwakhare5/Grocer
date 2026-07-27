"use client";

import { useState } from "react";
import { CheckCircle2, PhoneCall, User, Wrench } from "lucide-react";

export default function PreFillPracticalUse() {
  const [activeTab, setActiveTab] = useState(0);

  const tabs = [
    {
      name: "Quick Commerce",
      title: "Quick Commerce Platforms",
      bullets: [
        "Never miss a recurring grocery order, even during peak dinner preparation hours.",
        "Reduce household stockouts by instantly predicting depletion 24h before reaching 20% remaining threshold.",
        "Increase customer 90-day retention floor to 82% by providing 1-tap WhatsApp restocking."
      ],
      user: "Lauren Chaney",
      detail: "Fresh Milk 1L & Eggs 6-pack restock",
      status: "Picked-up by PreFill",
      time: "2:31"
    },
    {
      name: "D2C Brands",
      title: "D2C Organic Grocery Brands",
      bullets: [
        "Automate recurring subscriptions for organic coffee beans, specialty oils, and dry fruits.",
        "Increase repeat purchase rate by 3.5x without pushing intrusive discount codes.",
        "Instant 1-tap WhatsApp reorder confirmation with zero friction."
      ],
      user: "Courtney Henry",
      detail: "Cold-pressed Sunflower Oil 1L reorder",
      status: "Confirmed by PreFill",
      time: "1:45"
    },
    {
      name: "Kirana Stores",
      title: "Hyperlocal Kirana Networks",
      bullets: [
        "Allow local neighborhood stores to send automated restock reminders to local families.",
        "Eliminate phone call order taking with structured 1-tap WhatsApp carts.",
        "Recapture +₹1,450 monthly spend lost to offline Kirana store leakages."
      ],
      user: "Arjun Sharma",
      detail: "Atta 5kg & Rice 10kg monthly restock",
      status: "Dispatched to Household",
      time: "3:12"
    },
    {
      name: "Family Households",
      title: "Smart Family Pantry Management",
      bullets: [
        "Zero manual inventory tracking — automated depletion modeling based on order history.",
        "Receive morning WhatsApp alerts before running out of morning tea milk or breakfast eggs.",
        "One reply ('YES') places the 10-minute restock order effortlessly."
      ],
      user: "Ananya Patel",
      detail: "Tea Leaves 250g & Butter 200g",
      status: "Delivered in 10 mins",
      time: "0:52"
    }
  ];

  return (
    <div className="w-full max-w-5xl py-12 flex flex-col items-center">
      
      {/* Badge & H2 */}
      <div className="text-center max-w-xl mx-auto flex flex-col items-center gap-2 mb-10">
        <span className="badge-droxy-pill">
          <Wrench className="h-3.5 w-3.5 text-stone-700" />
          <span>Practical use</span>
        </span>
        <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight-display text-[#252525] mt-1 font-sans">
          How does PreFill work in practice?
        </h2>
      </div>

      {/* Horizontal Pill Bar */}
      <div className="w-full flex items-center justify-center overflow-x-auto no-scrollbar py-2 mb-8">
        <div className="bg-stone-200/70 p-1.5 rounded-full flex items-center gap-1.5 shrink-0 border border-stone-300/60">
          {tabs.map((t, idx) => (
            <button
              key={t.name}
              onClick={() => setActiveTab(idx)}
              className={`px-4 py-2 rounded-full text-xs font-bold transition-all cursor-pointer select-none ${
                activeTab === idx
                  ? "bg-white text-[#252525] shadow-xs border border-stone-200"
                  : "text-stone-600 hover:text-[#252525] hover:bg-stone-200/50"
              }`}
            >
              {t.name}
            </button>
          ))}
        </div>
      </div>

      {/* Card Content (Pastel Mint Green Styled) */}
      <div className="w-full card-pastel-green p-8 sm:p-10 flex flex-col lg:flex-row items-center justify-between gap-8 bg-ascii-dotted-grid relative overflow-hidden">
        
        {/* Left Bullet Points */}
        <div className="flex-1 flex flex-col items-start gap-6">
          <h3 className="text-2xl sm:text-3xl font-extrabold font-sans tracking-tight title-accent">
            {tabs[activeTab].title}
          </h3>

          <div className="flex flex-col gap-4">
            {tabs[activeTab].bullets.map((b, i) => (
              <div key={i} className="flex items-start gap-3 text-xs sm:text-sm text-stone-700 font-medium leading-relaxed">
                <CheckCircle2 className="h-4 w-4 text-emerald-700 shrink-0 mt-0.5" />
                <span>{b}</span>
              </div>
            ))}
          </div>

          <a href="#demo-stage" className="btn-droxy-pill-primary text-xs mt-2">
            Get started today
          </a>
        </div>

        {/* Right Side Detail Card Mockup */}
        <div className="w-full max-w-[320px] bg-white rounded-2xl border border-emerald-200 p-5 shadow-sm flex flex-col gap-4">
          
          <div className="flex items-center justify-between border-b border-stone-100 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="h-9 w-9 rounded-full bg-emerald-100 text-emerald-900 flex items-center justify-center font-bold text-xs">
                <User className="h-4 w-4" />
              </div>
              <div className="flex flex-col">
                <span className="font-bold text-xs text-[#252525]">{tabs[activeTab].user}</span>
                <span className="text-[10px] text-stone-500 font-medium flex items-center gap-1">
                  <PhoneCall className="h-3 w-3 text-emerald-600" />
                  {tabs[activeTab].status} • {tabs[activeTab].time}
                </span>
              </div>
            </div>
            <span className="text-[9px] font-semibold text-stone-500 bg-stone-100 px-2 py-0.5 rounded border border-stone-200">
              Details
            </span>
          </div>

          <div className="flex flex-col gap-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-stone-400 font-medium text-[11px]">Reason:</span>
              <span className="font-bold text-[#252525] text-[11px]">{tabs[activeTab].detail}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-stone-400 font-medium text-[11px]">Channel:</span>
              <span className="font-bold text-emerald-700 text-[11px]">WhatsApp 1-Tap</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-stone-400 font-medium text-[11px]">Delivery ETA:</span>
              <span className="font-bold text-stone-900 text-[11px]">10 Minutes</span>
            </div>
          </div>

          <div className="p-2.5 rounded-xl bg-emerald-50/80 border border-emerald-200/80 text-[10px] text-emerald-800 font-semibold text-center">
            Waiting for connection within 2 mins
          </div>

        </div>

      </div>

    </div>
  );
}
