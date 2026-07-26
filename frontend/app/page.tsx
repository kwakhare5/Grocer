"use client";

import { useState, Suspense } from "react";
import PhoneMockup from "../components/PhoneMockup";
import ExecutivePanel from "../components/ExecutivePanel";
import { 
  Layers, 
  ShieldCheck, 
  Sparkles, 
  Cpu, 
  Database, 
  MessageSquare, 
  TrendingUp, 
  BarChart3, 
  Zap, 
  CheckCircle2,
  ArrowRight
} from "lucide-react";
import { toast } from "sonner";

function SinglePageShowcaseContent() {
  const [activeScenario, setActiveScenario] = useState("standard");

  const handlePitchClick = () => {
    toast.success("Executive Pitch Requested! Connecting with PreFill Founder.");
  };

  return (
    <div className="flex flex-col gap-12 sm:gap-16 relative">

      {/* ── SECTION 1: HERO SHOWCASE (#demo) ───────────────────── */}
      <section id="demo" className="flex flex-col gap-6 pt-2">
        
        {/* Banner Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-slate-200 pb-5">
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-2">
              <span className="pill-subtle-green font-mono text-[10px] flex items-center gap-1">
                <Sparkles className="h-3 w-3" />
                PROPHET ML + LANGGRAPH ENGINE
              </span>
            </div>
            
            <h1 className="text-2xl sm:text-4xl font-bold tracking-tight font-display text-slate-900 mt-0.5">
              PreFill <span className="font-serif-accent text-slate-600 font-normal">Autonomous Household Restocking</span>
            </h1>

            <p className="text-xs sm:text-sm text-slate-600 font-medium max-w-2xl leading-relaxed">
              Eliminating quick commerce customer churn before stockouts occur with proactive, WhatsApp-integrated consumption forecasting.
            </p>
          </div>

          {/* Status Pill */}
          <div className="flex items-center gap-2 shrink-0 bg-white border border-slate-200 px-3 py-1.5 rounded-full shadow-2xs">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-semibold font-mono text-slate-700">
              Postgres Checkpoint Active
            </span>
          </div>
        </div>

        {/* 2-Column Responsive Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          
          {/* Left Column: Interactive Phone Device Frame (5 cols) */}
          <div className="lg:col-span-5 flex flex-col gap-3">
            <div className="flex items-center justify-between px-1">
              <span className="text-xs font-semibold text-slate-800 uppercase tracking-wider font-display flex items-center gap-1.5">
                <Layers className="h-3.5 w-3.5 text-slate-700" />
                Consumer Experience
              </span>
              <span className="text-[10px] text-slate-500 font-mono">Magic UI iPhone Frame</span>
            </div>

            <PhoneMockup activeScenario={activeScenario} />
          </div>

          {/* Right Column: Executive Intelligence & Analytics Panel (7 cols) */}
          <div className="lg:col-span-7 flex flex-col gap-3">
            <div className="flex items-center justify-between px-1">
              <span className="text-xs font-semibold text-slate-800 uppercase tracking-wider font-display flex items-center gap-1.5">
                <ShieldCheck className="h-3.5 w-3.5 text-slate-700" />
                Executive Financial & Retention Impact
              </span>
              <span className="text-[10px] text-slate-500 font-mono">Quick Commerce Platform ROI</span>
            </div>

            <ExecutivePanel 
              activeScenario={activeScenario} 
              onScenarioChange={(s) => setActiveScenario(s)} 
            />
          </div>

        </div>
      </section>

      {/* ── SECTION 2: HOW IT WORKS (#how-it-works) ─────────────── */}
      <section id="how-it-works" className="flex flex-col gap-6 pt-4 border-t border-slate-200">
        <div className="flex flex-col gap-1">
          <span className="pill-subtle-dark font-mono text-[10px] self-start">
            SYSTEM ARCHITECTURE
          </span>
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight font-display text-slate-900 mt-1">
            3-Step <span className="font-serif-accent text-slate-600 font-normal">Predictive Restocking Pipeline</span>
          </h2>
          <p className="text-xs text-slate-500 font-medium max-w-xl">
            How PreFill turns raw order history into zero-friction automated household reorders.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {[
            {
              step: "01",
              title: "Prophet Time-Series ML",
              desc: "Analyzes recurring order frequency and filters anomaly spikes (parties, travel gaps) to build precise depletion curves per staple item.",
              icon: Cpu
            },
            {
              step: "02",
              title: "LangGraph State Machine",
              desc: "Stateful agents manage depletion thresholds, household composition inference, and checkpoint state to PostgreSQL across server restarts.",
              icon: Database
            },
            {
              step: "03",
              title: "WhatsApp 1-Tap Reorder",
              desc: "Sends contextual WhatsApp alerts 24 hours before stockout. Users reply 'YES' or tap chips to instantly trigger 10-minute delivery.",
              icon: MessageSquare
            }
          ].map((item) => {
            const Icon = item.icon;
            return (
              <div key={item.step} className="saas-card p-5 flex flex-col gap-3 relative">
                <div className="flex items-center justify-between">
                  <div className="p-2 rounded-lg bg-slate-100 text-slate-800 border border-slate-200 shrink-0">
                    <Icon className="h-4 w-4" />
                  </div>
                  <span className="text-xs font-mono font-bold text-slate-400">{item.step}</span>
                </div>
                <div className="flex flex-col gap-1">
                  <h3 className="font-bold text-sm text-slate-900 font-display">{item.title}</h3>
                  <p className="text-xs text-slate-600 font-medium leading-relaxed">{item.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ── SECTION 3: PLATFORM ROI (#roi) ───────────────────────── */}
      <section id="roi" className="flex flex-col gap-6 pt-4 border-t border-slate-200">
        <div className="flex flex-col gap-1">
          <span className="pill-subtle-green font-mono text-[10px] self-start">
            PLATFORM UNIT ECONOMICS
          </span>
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight font-display text-slate-900 mt-1">
            Built for <span className="font-serif-accent text-slate-600 font-normal">Quick Commerce Leadership</span>
          </h2>
          <p className="text-xs text-slate-500 font-medium max-w-xl">
            Unlocking incremental GMV and customer retention for quick commerce platforms.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          <div className="saas-card p-5 flex flex-col justify-between gap-4">
            <div className="flex items-center gap-2 text-emerald-600">
              <BarChart3 className="h-4 w-4" />
              <span className="text-xs font-semibold uppercase tracking-wider font-display text-slate-900">Kirana GMV Recaptured</span>
            </div>
            <div className="flex flex-col">
              <span className="text-3xl font-extrabold text-slate-900 font-display">+₹1,450</span>
              <span className="text-xs text-slate-500 font-medium mt-0.5">Incremental monthly spend per household</span>
            </div>
          </div>

          <div className="saas-card p-5 flex flex-col justify-between gap-4">
            <div className="flex items-center gap-2 text-slate-800">
              <TrendingUp className="h-4 w-4" />
              <span className="text-xs font-semibold uppercase tracking-wider font-display text-slate-900">90-Day Retention Floor</span>
            </div>
            <div className="flex flex-col">
              <span className="text-3xl font-extrabold text-slate-900 font-display">82%</span>
              <span className="text-xs text-slate-500 font-medium mt-0.5">vs 24% baseline quick commerce churn</span>
            </div>
          </div>

          <div className="saas-card p-5 flex flex-col justify-between gap-4 sm:col-span-2 lg:col-span-1">
            <div className="flex items-center gap-2 text-slate-800">
              <ShieldCheck className="h-4 w-4" />
              <span className="text-xs font-semibold uppercase tracking-wider font-display text-slate-900">Switching Cost Moat</span>
            </div>
            <div className="flex flex-col">
              <span className="text-3xl font-extrabold text-slate-900 font-display">6 Months</span>
              <span className="text-xs text-slate-500 font-medium mt-0.5">Household consumption model history</span>
            </div>
          </div>
        </div>
      </section>

      {/* ── SECTION 4: CALL TO ACTION (#pitch) ────────────────────── */}
      <section id="pitch" className="bg-slate-900 text-white rounded-2xl p-6 sm:p-8 flex flex-col md:flex-row md:items-center justify-between gap-6 shadow-md border border-slate-800">
        <div className="flex flex-col gap-2 max-w-xl">
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded bg-emerald-950 text-emerald-400 text-[10px] font-mono font-bold border border-emerald-800/60">
              READY FOR DEPLOYMENT
            </span>
          </div>
          <h2 className="text-xl sm:text-2xl font-bold font-display tracking-tight text-white mt-1">
            Schedule an Executive Demo & Pilot
          </h2>
          <p className="text-xs sm:text-sm text-slate-300 font-medium leading-relaxed">
            Integrate PreFill into your quick commerce catalog pipeline to test autonomous restocking across 1,000 pilot households.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 shrink-0">
          <button
            onClick={handlePitchClick}
            className="px-6 py-3 rounded-xl bg-white text-slate-900 font-bold text-xs font-display flex items-center justify-center gap-2 hover:bg-slate-100 transition-transform duration-150 active:scale-95 cursor-pointer shadow-sm"
          >
            <Zap className="h-4 w-4 text-amber-500 fill-amber-500" />
            <span>Schedule Founder Pitch</span>
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </section>

    </div>
  );
}

export default function Home() {
  return (
    <Suspense fallback={
      <div className="mx-auto max-w-7xl px-4 py-12 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 font-display">
        Loading PreFill Single-Page Showcase...
      </div>
    }>
      <SinglePageShowcaseContent />
    </Suspense>
  );
}
