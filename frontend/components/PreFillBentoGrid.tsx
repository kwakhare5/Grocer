"use client";

import { 
  RefreshCw, 
  Cpu, 
  Zap,
  Globe,
  BarChart2,
  Database
} from "lucide-react";

export default function PreFillBentoGrid() {
  const languages = [
    { code: "HI", name: "Hindi" },
    { code: "EN", name: "English" },
    { code: "HG", name: "Hinglish" },
    { code: "TA", name: "Tamil" },
    { code: "TE", name: "Telugu" },
    { code: "KN", name: "Kannada" },
    { code: "MR", name: "Marathi" },
    { code: "BN", name: "Bengali" },
    { code: "ES", name: "Spanish" },
    { code: "DE", name: "German" },
  ];

  return (
    <div className="w-full max-w-5xl py-12 flex flex-col items-center">
      
      {/* H2 Header */}
      <div className="text-center max-w-xl mx-auto flex flex-col items-center gap-2 mb-12">
        <span className="badge-droxy-pill">
          Unlock advanced capabilities
        </span>
        <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight-display text-[#252525] mt-1 font-sans">
          PreFill Does it All
        </h2>
      </div>

      {/* 6 Bento Grid Cards (Balanced Pastel Palette: Blue, Green, Amber, Red) */}
      <div className="w-full grid grid-cols-1 md:grid-cols-12 gap-6">
        
        {/* Card 1: Multilingual Support (Pastel Sky Blue Family) */}
        <div className="md:col-span-4 card-pastel-blue flex flex-col justify-between gap-5 bg-ascii-dotted-grid relative overflow-hidden">
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <Globe className="h-5 w-5 text-blue-700" />
              <h3 className="text-xl font-extrabold font-sans title-accent">Multilingual Support</h3>
            </div>
            <p className="text-xs text-stone-600 font-medium leading-relaxed">
              Communicate in 95+ languages instantly (Hindi, Hinglish, Tamil, Telugu), no extra setup needed.
            </p>
          </div>

          {/* Clean Language Pills */}
          <div className="flex flex-wrap gap-2 pt-2">
            {languages.map((l) => (
              <span 
                key={l.name}
                className="px-2.5 py-1 rounded-full bg-white border border-blue-200/80 text-[11px] font-bold text-blue-900 shadow-2xs flex items-center gap-1.5"
              >
                <span className="text-[10px] text-blue-500 font-mono">{l.code}</span>
                <span>{l.name}</span>
              </span>
            ))}
          </div>
        </div>

        {/* Card 2: Real-time Insights & Analysis (Pastel Sky Blue Family) */}
        <div className="md:col-span-4 card-pastel-blue flex flex-col justify-between gap-5 bg-ascii-dotted-grid relative overflow-hidden">
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <BarChart2 className="h-5 w-5 text-blue-700" />
              <h3 className="text-xl font-extrabold font-sans title-accent">Real-time Insights & analysis</h3>
            </div>
            <p className="text-xs text-stone-600 font-medium leading-relaxed">
              Analyze customer interactions in real time to uncover behavior trends and optimize your service.
            </p>
          </div>

          {/* Line Chart & Stats Box */}
          <div className="p-4 rounded-2xl bg-white border border-blue-200/80 shadow-2xs flex flex-col gap-3">
            <div className="flex items-center justify-between text-[10px] text-blue-400 font-mono">
              <span>Jan 20</span>
              <span>Jan 25</span>
              <span>Feb 1</span>
              <span>Feb 10</span>
              <span>Feb 20</span>
            </div>
            
            {/* SVG Sparkline */}
            <svg className="w-full h-8 stroke-blue-600 fill-none" viewBox="0 0 200 40">
              <path d="M 0 30 Q 30 10, 60 25 T 120 15 T 180 5 T 200 10" strokeWidth="2.5" />
            </svg>

            <div className="flex flex-col gap-1.5 pt-1 border-t border-blue-100 text-xs">
              <div className="flex items-center justify-between font-semibold">
                <span className="text-stone-600">Website Orders</span>
                <span className="text-blue-950 font-bold">2,531 <span className="text-emerald-600 text-[10px]">↗ 7.3%</span></span>
              </div>
              <div className="flex items-center justify-between font-semibold">
                <span className="text-stone-600">WhatsApp Restocks</span>
                <span className="text-blue-950 font-bold">1,291 <span className="text-emerald-600 text-[10px]">↗ 3.5%</span></span>
              </div>
            </div>
          </div>
        </div>

        {/* Card 3: Comprehensive Knowledge Integration (Pastel Mint Green Family) */}
        <div className="md:col-span-4 card-pastel-green flex flex-col justify-between gap-5 bg-ascii-dotted-grid relative overflow-hidden">
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <Database className="h-5 w-5 text-emerald-700" />
              <h3 className="text-xl font-extrabold font-sans title-accent">Order Stream Integration</h3>
            </div>
            <p className="text-xs text-stone-600 font-medium leading-relaxed">
              Build your agent&apos;s knowledge with order streams from quick commerce APIs, Zepto, Blinkit, Instamart, and Shopify.
            </p>
          </div>

          {/* Central Node Graph */}
          <div className="h-32 w-full flex items-center justify-center relative">
            <div className="h-12 w-12 rounded-full bg-emerald-700 text-white flex items-center justify-center font-extrabold text-base shadow-md z-10">
              P
            </div>
            
            <div className="absolute top-2 left-6 p-2 rounded-xl bg-white border border-emerald-200 text-xs shadow-2xs font-semibold text-emerald-900">Zepto</div>
            <div className="absolute top-2 right-6 p-2 rounded-xl bg-white border border-emerald-200 text-xs shadow-2xs font-semibold text-emerald-900">Blinkit</div>
            <div className="absolute bottom-2 left-6 p-2 rounded-xl bg-white border border-emerald-200 text-xs shadow-2xs font-semibold text-emerald-900">Instamart</div>
            <div className="absolute bottom-2 right-6 p-2 rounded-xl bg-white border border-emerald-200 text-xs shadow-2xs font-semibold text-emerald-900">Shopify</div>
          </div>
        </div>

        {/* Card 4: Automatic Sync (Pastel Warm Amber Family) */}
        <div className="md:col-span-4 card-pastel-amber flex flex-col justify-between gap-4 bg-ascii-dotted-grid relative">
          <div className="flex flex-col gap-2">
            <RefreshCw className="h-5 w-5 text-amber-700" />
            <h3 className="text-xl font-extrabold font-sans title-accent">Automatic sync</h3>
            <p className="text-xs text-stone-600 font-medium leading-relaxed">
              Keep your agent&apos;s knowledge up-to-date with automatic updates from your data sources.
            </p>
          </div>
        </div>

        {/* Card 5: Cutting-edge AI Technology (Pastel Rose Red Family) */}
        <div className="md:col-span-4 card-pastel-red flex flex-col justify-between gap-4 bg-ascii-dotted-grid relative">
          <div className="flex flex-col gap-2">
            <Cpu className="h-5 w-5 text-rose-700" />
            <h3 className="text-xl font-extrabold font-sans title-accent">Cutting-edge AI Technology</h3>
            <p className="text-xs text-stone-600 font-medium leading-relaxed">
              Powered by industry-leading forecasting models from Prophet ML, LangGraph, and DeepMind.
            </p>
          </div>
        </div>

        {/* Card 6: Zapier & PreFill API (Pastel Warm Amber Family) */}
        <div className="md:col-span-4 card-pastel-amber flex flex-col justify-between gap-4 bg-ascii-dotted-grid relative">
          <div className="flex flex-col gap-2">
            <Zap className="h-5 w-5 text-amber-700" />
            <h3 className="text-xl font-extrabold font-sans title-accent">Zapier & PreFill API</h3>
            <p className="text-xs text-stone-600 font-medium leading-relaxed">
              Use Zapier and our API to build custom integrations and workflows tailored to your needs.
            </p>
          </div>

          <div className="flex items-center gap-3 pt-2">
            <div className="h-9 w-9 rounded-full bg-[#252525] text-white flex items-center justify-center font-bold text-xs">P</div>
            <span className="text-amber-700 font-bold">+</span>
            <div className="h-9 w-9 rounded-full bg-orange-500 text-white flex items-center justify-center font-bold text-xs">zapier</div>
          </div>
        </div>

      </div>

    </div>
  );
}
