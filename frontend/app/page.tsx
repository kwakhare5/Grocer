"use client";

import { useState, Suspense } from "react";
import Header from "../components/Header";
import PhoneMockup from "../components/PhoneMockup";
import ExecutivePanel from "../components/ExecutivePanel";
import PreFillFeatureSidebar from "../components/PreFillFeatureSidebar";
import PreFillPracticalUse from "../components/PreFillPracticalUse";
import PreFillBentoGrid from "../components/PreFillBentoGrid";
import { motion, AnimatePresence } from "framer-motion";
import {
  MessageSquare,
  Cpu,
  ChevronDown,
  Brain,
  Rocket,
  Code,
  ShieldCheck,
  FileText,
  Zap,
  Clock
} from "lucide-react";

function SinglePageShowcaseContent() {
  const [activeScenario, setActiveScenario] = useState("standard");

  // PreFill 5-Step Setup Accordion State
  const [activeSetupStep, setActiveSetupStep] = useState(0);

  // PreFill FAQ Accordion State
  const [openFaq, setOpenFaq] = useState<number | null>(0);

  // PreFill 5-Step Setup Guide Content
  const setupSteps = [
    {
      num: "01",
      title: "1. Connect Order Stream Data",
      desc: "Input past quick commerce order history or connect API streams. PreFill instantly models item depletion rates without manual setup."
    },
    {
      num: "02",
      title: "2. Set Restock Threshold Goals",
      desc: "Define custom stockout triggers (e.g. 20% remaining threshold) and filter anomaly spikes like weekend party orders."
    },
    {
      num: "03",
      title: "3. Deploy to WhatsApp Channel",
      desc: "Launch your automated WhatsApp restock agent in minutes. Ground it with brand voice and delivery fee rules."
    },
    {
      num: "04",
      title: "4. Monitor Depletion Trajectories",
      desc: "Track live household inventory levels and Prophet ML prediction accuracy on the real-time executive dashboard."
    },
    {
      num: "05",
      title: "5. Adapt & Scale Household LTV",
      desc: "Continuously improve reorder timing, driving 82% 90-day retention and recapturing local Kirana leakages."
    }
  ];

  // PreFill FAQ Items
  const faqItems = [
    {
      q: "How does PreFill predict when a household will run out of milk or staples?",
      a: "PreFill uses Prophet ML consumption modeling to analyze past purchase timestamps and order quantities. It calculates daily consumption velocity and predicts stock depletion 24 hours before reaching the critical 20% threshold."
    },
    {
      q: "Will PreFill work with existing quick commerce platforms (Zepto, Blinkit, Instamart)?",
      a: "Yes! PreFill is built with universal API connectors for quick commerce delivery APIs, WhatsApp Business APIs, and Shopify order webhooks."
    },
    {
      q: "How does the 1-Tap WhatsApp restock process work for customers?",
      a: "When an item hits the 20% depletion threshold, PreFill sends a WhatsApp message with the item name, price, and delivery fee. The customer simply replies 'YES' or taps the button to confirm 10-minute delivery."
    },
    {
      q: "How does PreFill filter out abnormal spikes like weekend parties or travel?",
      a: "Our LangGraph decision engine applies anomaly filtering rules. If a purchase spike deviates significantly from 30-day baseline consumption, PreFill adjusts the trajectory without miscalculating daily usage."
    },
    {
      q: "How fast can a quick commerce brand set up PreFill?",
      a: "PreFill can be integrated in under 2 hours. Simply upload historical order logs or connect your webhooks, and the AI models initialize automatically."
    }
  ];

  return (
    <div className="min-h-screen bg-[#F6F7F8] text-[#252525] font-sans flex flex-col selection:bg-[#252525] selection:text-white relative overflow-x-hidden">

      {/* ── 1. STICKY HEADER ───────────────────────────────────────── */}
      <Header />

      <main className="flex-1 w-full flex flex-col items-center pt-15">

        {/* ── 2. HERO SECTION ─────────────────────────────────────────────── */}
        <section id="demo" className="max-w-6xl w-full pt-4 sm:pt-8 pb-10 px-5 sm:px-8 lg:px-12 flex flex-col items-center text-center bg-ascii-mesh-masked relative">

          {/* PreFill Tagline Badge */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="mb-3 badge-droxy-pill cursor-pointer z-10"
          >
            <span className="p-1 rounded-full bg-blue-50 text-blue-700 shrink-0">
              <Brain className="h-3.5 w-3.5" />
            </span>
            <span>Predictive Household Inventory Engine</span>
          </motion.div>

          {/* Main Display Headline */}
          <motion.h1
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="text-3xl sm:text-5xl md:text-6xl font-extrabold tracking-tight-display text-[#252525] max-w-3xl font-sans z-10 leading-[1.08]"
          >
            Predict stockouts. Automate restocks.
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="mt-3 text-sm sm:text-base text-stone-600 max-w-lg leading-relaxed font-medium z-10"
          >
            PreFill models daily consumption velocity to trigger 1-tap WhatsApp grocery orders 24h before items run out.
          </motion.p>

          {/* Dual Pill Buttons */}
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.25 }}
            className="mt-5 flex flex-col sm:flex-row items-center gap-3 z-10"
          >
            <a href="#demo-stage" className="btn-droxy-pill-primary text-xs sm:text-sm font-semibold">
              Try Prototype
            </a>
            <a href="#platform-roi" className="btn-droxy-pill-secondary text-xs sm:text-sm font-semibold">
              View ROI
            </a>
          </motion.div>

          {/* Centered Hardware Product Showcase Stage */}
          <motion.div
            id="demo-stage"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.35 }}
            className="w-full max-w-6xl mt-6 sm:mt-8 z-10 px-0 flex justify-center"
          >
            <div className="w-full flex flex-col lg:flex-row items-center justify-center gap-6 sm:gap-10 lg:gap-32 text-left">

              {/* Left Column: Interactive iPhone Mockup */}
              <div className="w-full max-w-[285px] sm:max-w-[300px] flex justify-center shrink-0">
                <PhoneMockup activeScenario={activeScenario} />
              </div>

              {/* Right Column: Compact Interactive Micro-Rail Panel */}
              <div className="w-full max-w-md flex-1 flex flex-col gap-3.5">

                {/* Quiet Header */}
                <div className="flex items-center justify-between border-b border-stone-200/80 pb-2.5">
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
                    <span className="text-xs font-bold uppercase tracking-wider text-stone-700 font-mono">
                      Live Prototype Scenarios
                    </span>
                  </div>
                  <span className="text-[11px] font-semibold text-stone-400 font-sans hidden sm:inline-block">
                    Click row to test screen
                  </span>
                </div>

                <div className="flex flex-col gap-1">
                  <h3 className="text-xl sm:text-2xl font-extrabold text-[#252525] font-sans tracking-tight">
                    Proactive Household Restocking
                  </h3>
                  <p className="text-xs text-stone-600 font-medium leading-relaxed">
                    Select a scenario below to test real-time depletion triggers and 1-tap WhatsApp restocking:
                  </p>
                </div>

                {/* 4 Compact Clickable Scenario Micro-Rail Rows */}
                <div className="flex flex-col gap-2.5 mt-0.5">
                  {[
                    {
                      id: "whatsapp",
                      title: "1-Tap WhatsApp Checkout",
                      desc: "Pre-filled cart delivered to WhatsApp with zero app browsing.",
                      icon: MessageSquare,
                      tag: "1-Tap",
                      badgeColor: "bg-emerald-50 text-emerald-800 border-emerald-200/80"
                    },
                    {
                      id: "slider",
                      title: "20% Stockout Depletion Alert",
                      desc: "Models consumption velocity & alerts 24h before stockout.",
                      icon: Cpu,
                      tag: "24h Alert",
                      badgeColor: "bg-blue-50 text-blue-800 border-blue-200/80"
                    },
                    {
                      id: "recipe",
                      title: "Recipe Gap Analysis",
                      desc: "Scans meal plans & auto-fills missing recipe ingredients.",
                      icon: Brain,
                      tag: "Recipe Gaps",
                      badgeColor: "bg-amber-50 text-amber-800 border-amber-200/80"
                    },
                    {
                      id: "pricedrop",
                      title: "Dynamic Price Drop Alerts",
                      desc: "Monitors commodity price signals & orders on historic dips.",
                      icon: Zap,
                      tag: "Price Signal",
                      badgeColor: "bg-rose-50 text-rose-800 border-rose-200/80"
                    }
                  ].map((sc) => {
                    const Icon = sc.icon;
                    const isActive = activeScenario === sc.id;
                    return (
                      <div
                        key={sc.id}
                        onClick={() => setActiveScenario(sc.id)}
                        className={`p-3 sm:p-3.5 rounded-2xl border transition-all cursor-pointer flex items-start gap-3 select-none ${
                          isActive
                            ? "bg-white border-[#252525] shadow-sm -translate-y-0.5 ring-1 ring-[#252525]/10"
                            : "bg-stone-50/60 border-stone-200/80 hover:border-stone-400 hover:bg-white"
                        }`}
                      >
                        <span className={`p-2 rounded-xl shrink-0 border ${sc.badgeColor} mt-0.5`}>
                          <Icon className="h-4 w-4" />
                        </span>

                        <div className="flex flex-col gap-0.5 flex-1">
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-extrabold text-xs text-[#252525] font-sans">
                              {sc.title}
                            </span>

                            <div className="flex items-center gap-1.5">
                              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full border border-stone-200 bg-stone-100/70 text-stone-700 font-mono hidden sm:inline-block">
                                {sc.tag}
                              </span>
                              {isActive && (
                                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                              )}
                            </div>
                          </div>
                          <p className="text-[11px] text-stone-600 font-medium leading-normal">
                            {sc.desc}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Bottom Clean Trust Ribbon */}
                <div className="pt-2 border-t border-stone-200/80 flex items-center justify-between text-[11px] font-semibold text-stone-500 font-sans">
                  <div className="flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5 text-stone-500 shrink-0" />
                    <span>Average setup time: &lt;3 minutes</span>
                  </div>
                  <span className="text-stone-400 font-normal">Zero app download</span>
                </div>

              </div>

            </div>
          </motion.div>

        </section>

        {/* ── 3. 6-CARD VISUAL BENTO GRID ARCHITECTURE (#bento) ──────────── */}
        <section id="bento" className="w-full bg-[#FAFBFB] border-y border-stone-200 flex justify-center px-5 sm:px-8 lg:px-12">
          <PreFillBentoGrid />
        </section>

        {/* ── 4. INTERACTIVE SIDEBAR FEATURE SHOWCASE (#features) ─────────── */}
        <section id="features" className="max-w-6xl w-full py-14 sm:py-20 px-5 sm:px-8 lg:px-12 flex flex-col items-center">
          <div className="text-center max-w-xl mx-auto flex flex-col items-center gap-2 mb-8 sm:mb-10">
            <span className="badge-droxy-pill">
              <span className="p-1 rounded-full bg-blue-50 text-blue-700 shrink-0">
                <MessageSquare className="h-3.5 w-3.5" />
              </span>
              <span>Proactive Grocery Automation</span>
            </span>
            <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight-display text-[#252525] mt-1 font-sans">
              Automate grocery reordering before stock runs out
            </h2>
          </div>

          <PreFillFeatureSidebar />
        </section>

        {/* ── 5. PRACTICAL USE CASES SHOWCASE ─────────── */}
        <section className="w-full bg-white border-y border-stone-200 flex justify-center px-5 sm:px-8 lg:px-12">
          <PreFillPracticalUse />
        </section>

        {/* ── 6. PERFORMANCE COMPARISON (#comparison) ──── */}
        <motion.section 
          id="comparison" 
          initial={{ opacity: 0, y: 25 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="max-w-6xl w-full py-14 sm:py-20 px-5 sm:px-8 lg:px-12 flex flex-col items-center"
        >

          <div className="text-center max-w-xl mx-auto flex flex-col items-center gap-2 mb-8 sm:mb-10">
            <span className="badge-droxy-pill">
              <span className="p-1 rounded-full bg-rose-50 text-rose-700 shrink-0">
                <Rocket className="h-3.5 w-3.5" />
              </span>
              <span>Performance Comparison</span>
            </span>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-[#252525] mt-1 font-sans">
              Manual Grocery Restocking vs PreFill Automation
            </h2>
          </div>

          {/* Comparison Table Card */}
          <div className="w-full round-card-droxy p-0 overflow-hidden shadow-sm hover:border-stone-400 transition-all">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs sm:text-sm">
                <thead>
                  <tr className="bg-stone-100 border-b border-stone-200">
                    <th className="p-4 sm:p-5 font-bold text-stone-800">Criteria</th>
                    <th className="p-4 sm:p-5 font-bold text-stone-700 bg-stone-50">Manual Restocking</th>
                    <th className="p-4 sm:p-5 font-bold text-[#252525] bg-stone-100/80">With PreFill Engine</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-200 font-medium">
                  <tr>
                    <td className="p-4 sm:p-5 text-stone-800 font-semibold">Time spent on grocery reordering</td>
                    <td className="p-4 sm:p-5 text-stone-600">Manual app browsing & searching</td>
                    <td className="p-4 sm:p-5 text-stone-900 font-bold bg-stone-50/50">
                      <span className="px-2 py-0.5 rounded status-pill-green font-bold text-xs">1-tap WhatsApp confirmation</span>
                    </td>
                  </tr>
                  <tr>
                    <td className="p-4 sm:p-5 text-stone-800 font-semibold">Stockout warning timing</td>
                    <td className="p-4 sm:p-5 text-stone-600">After items are already empty</td>
                    <td className="p-4 sm:p-5 text-stone-900 font-bold bg-stone-50/50">
                      <span className="px-2 py-0.5 rounded status-pill-green font-bold text-xs">24h before stockout trigger</span>
                    </td>
                  </tr>
                  <tr>
                    <td className="p-4 sm:p-5 text-stone-800 font-semibold">Recipe ingredient completeness</td>
                    <td className="p-4 sm:p-5 text-stone-600">Manual ingredient checking</td>
                    <td className="p-4 sm:p-5 text-stone-900 font-bold bg-stone-50/50">
                      <span className="px-2 py-0.5 rounded status-pill-green font-bold text-xs">Automated recipe gap scan</span>
                    </td>
                  </tr>
                  <tr>
                    <td className="p-4 sm:p-5 text-stone-800 font-semibold">Price optimization alerts</td>
                    <td className="p-4 sm:p-5 text-stone-600">No automated tracking</td>
                    <td className="p-4 sm:p-5 text-stone-900 font-bold bg-stone-50/50">
                      <span className="px-2 py-0.5 rounded status-pill-green font-bold text-xs">Automated price dip reorder</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="mt-8 flex items-center gap-4">
            <a href="#demo" className="btn-droxy-pill-primary text-xs">Try Prototype</a>
            <a href="#platform-roi" className="btn-droxy-pill-secondary text-xs">View ROI</a>
          </div>

        </motion.section>

        {/* ── 7. PLATFORM ROI & EXECUTIVE PANEL (#platform-roi) ─────── */}
        <motion.section 
          id="platform-roi" 
          initial={{ opacity: 0, y: 25 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="max-w-6xl w-full py-14 sm:py-20 px-5 sm:px-8 lg:px-12 flex flex-col items-center"
        >
          <div className="text-center max-w-xl mx-auto flex flex-col items-center gap-2 mb-8 sm:mb-10">
            <span className="badge-droxy-pill">
              <span className="p-1 rounded-full bg-emerald-50 text-emerald-700 shrink-0 font-extrabold text-[10px]">
                ₹
              </span>
              <span>Executive ROI Dashboard</span>
            </span>
            <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight-display text-[#252525] font-sans">
              Real-time Analytics & Unit Economics
            </h2>
          </div>

          <div className="w-full">
            <ExecutivePanel
              activeScenario={activeScenario}
              onScenarioChange={(s) => setActiveScenario(s)}
            />
          </div>
        </motion.section>

        {/* ── 8. SETUP GUIDE (5-STEP ACCORDION) (#how-it-works) ──────── */}
        <motion.section 
          id="how-it-works" 
          initial={{ opacity: 0, y: 25 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="max-w-6xl w-full py-14 sm:py-20 px-5 sm:px-8 lg:px-12 flex flex-col items-center"
        >

          <div className="text-center max-w-xl mx-auto flex flex-col items-center gap-2 mb-8 sm:mb-10">
            <span className="badge-droxy-pill">
              <span className="p-1 rounded-full bg-blue-50 text-blue-700 shrink-0">
                <Code className="h-3.5 w-3.5" />
              </span>
              <span>Simple Setup</span>
            </span>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-[#252525] mt-1 font-sans">
              How PreFill Works
            </h2>
          </div>

          <div className="w-full flex flex-col gap-3 max-w-3xl">
            {setupSteps.map((step, idx) => (
              <div
                key={step.num}
                onClick={() => setActiveSetupStep(idx)}
                className={`round-card-droxy p-5 sm:p-6 cursor-pointer transition-all ${
                  activeSetupStep === idx ? "border-stone-400 bg-white shadow-sm" : ""
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className={`font-mono text-xs font-bold px-2.5 py-1 rounded-full border ${
                      idx === 0 ? "bg-blue-50 text-blue-800 border-blue-200/80" :
                      idx === 1 ? "bg-amber-50 text-amber-800 border-amber-200/80" :
                      idx === 2 ? "bg-emerald-50 text-emerald-800 border-emerald-200/80" :
                      idx === 3 ? "bg-rose-50 text-rose-800 border-rose-200/80" :
                      "bg-indigo-50 text-indigo-800 border-indigo-200/80"
                    }`}>
                      {step.num}
                    </span>
                    <h3 className="font-bold text-sm sm:text-base text-[#252525] font-sans">
                      {step.title}
                    </h3>
                  </div>
                  <ChevronDown className={`h-4 w-4 text-stone-500 transition-transform ${activeSetupStep === idx ? "rotate-180" : ""}`} />
                </div>

                <AnimatePresence>
                  {activeSetupStep === idx && (
                    <motion.p 
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.2 }}
                      className="mt-3 text-xs sm:text-sm text-stone-600 font-medium leading-relaxed pl-10 border-l-2 border-stone-800"
                    >
                      {step.desc}
                    </motion.p>
                  )}
                </AnimatePresence>
              </div>
            ))}
          </div>

        </motion.section>

        {/* ── 9. SAFEGUARDS & MODEL MANAGEMENT ─────────────────────── */}
        <motion.section 
          initial={{ opacity: 0, y: 25 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="w-full py-14 sm:py-20 bg-white border-y border-stone-200 flex justify-center px-5 sm:px-8 lg:px-12"
        >
          <div className="max-w-5xl w-full flex flex-col items-center text-center gap-6">
            <div className="round-card-droxy p-8 sm:p-10 w-full flex flex-col items-center gap-4 bg-ascii-dotted-grid hover:border-stone-400 transition-all">
              <span className="badge-droxy-pill">
                <span className="p-1 rounded-full bg-emerald-50 text-emerald-700 shrink-0">
                  <ShieldCheck className="h-3.5 w-3.5" />
                </span>
                <span>Safeguards Engine</span>
              </span>
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-[#252525] font-sans">
                Safeguards & Consumption Model Management
              </h2>
              <p className="text-xs sm:text-sm text-stone-600 max-w-2xl font-medium leading-relaxed">
                Ground your restock agent with platform catalog & delivery rules, ensuring messages remain accurate and within strict safety boundaries.
              </p>
              <a href="#demo" className="btn-droxy-pill-primary text-xs mt-2">
                Try Prototype
              </a>
            </div>
          </div>
        </motion.section>

        {/* ── 10. FAQ ACCORDION (#faq) ───────────────────────────────── */}
        <motion.section 
          id="faq" 
          initial={{ opacity: 0, y: 25 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="max-w-5xl w-full py-14 sm:py-20 px-5 sm:px-8 lg:px-12 flex flex-col items-center"
        >

          <div className="text-center max-w-xl mx-auto flex flex-col items-center gap-2 mb-8 sm:mb-10">
            <span className="badge-droxy-pill">
              <span className="p-1 rounded-full bg-blue-50 text-blue-700 shrink-0">
                <FileText className="h-3.5 w-3.5" />
              </span>
              <span>Common inquiries answered</span>
            </span>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-[#252525] mt-1 font-sans">
              Frequently asked questions
            </h2>
          </div>

          <div className="w-full flex flex-col gap-3">
            {faqItems.map((faq, idx) => (
              <div
                key={idx}
                onClick={() => setOpenFaq(openFaq === idx ? null : idx)}
                className="round-card-droxy p-5 sm:p-6 cursor-pointer transition-all hover:border-stone-400"
              >
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-sm sm:text-base text-[#252525] font-sans">
                    {faq.q}
                  </h3>
                  <span className={`p-1 rounded-lg transition-transform ${openFaq === idx ? "rotate-180 bg-blue-50 text-blue-700" : "bg-stone-100 text-stone-500"}`}>
                    <ChevronDown className="h-4 w-4" />
                  </span>
                </div>

                <AnimatePresence>
                  {openFaq === idx && (
                    <motion.p 
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.2 }}
                      className="mt-3 text-xs sm:text-sm text-stone-600 font-medium leading-relaxed border-t border-stone-100 pt-3"
                    >
                      {faq.a}
                    </motion.p>
                  )}
                </AnimatePresence>
              </div>
            ))}
          </div>

        </motion.section>

        {/* ── 11. FINAL CTA BANNER & FOOTER ─────────────────────────── */}
        <motion.section 
          initial={{ opacity: 0, y: 25 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="w-full py-14 sm:py-16 px-5 sm:px-8 lg:px-12 flex justify-center bg-[#252525] text-white"
        >
          <div className="max-w-5xl w-full flex flex-col items-center text-center gap-5 py-4">

            <h2 className="text-3xl sm:text-5xl font-extrabold text-white max-w-2xl font-sans tracking-tight">
              Ready to test PreFill restocking?
            </h2>

            <p className="text-xs sm:text-base text-stone-300 max-w-xl font-medium leading-relaxed">
              Explore the interactive prototype stage or inspect unit economics on the executive dashboard.
            </p>

            <div className="flex flex-col sm:flex-row items-center gap-4 mt-2">
              <a href="#demo-stage" className="bg-white text-[#252525] font-bold text-sm px-7 py-3 rounded-full hover:bg-stone-100 transition-all cursor-pointer">
                Try Prototype
              </a>
              <a href="#platform-roi" className="border border-stone-600 text-white font-bold text-sm px-7 py-3 rounded-full hover:bg-stone-800 transition-all cursor-pointer">
                View ROI
              </a>
            </div>

          </div>
        </motion.section>

      </main>

      {/* PreFill Clean Footer */}
      <footer className="w-full border-t border-stone-200 bg-white py-8 px-5 sm:px-8 lg:px-12 text-xs text-stone-600">
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-6">

          <div className="flex flex-col gap-2.5">
            <div className="flex items-center gap-2.5 font-bold text-[#252525] font-sans text-base">
              <div className="h-6 w-6 rounded-lg bg-[#252525] text-white flex items-center justify-center text-xs font-extrabold">
                P
              </div>
              <span>PreFill</span>
            </div>
            <p className="text-xs text-stone-500 font-medium">
              Predictive grocery depletion modeling and 1-tap WhatsApp restocking engine.
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <span className="font-bold text-[#252525] text-sm font-sans mb-1">Quick Links</span>
            <a href="#features" className="hover:text-[#252525] transition-colors font-medium">Features</a>
            <a href="#how-it-works" className="hover:text-[#252525] transition-colors font-medium">How It Works</a>
            <a href="#comparison" className="hover:text-[#252525] transition-colors font-medium">Why PreFill</a>
            <a href="#platform-roi" className="hover:text-[#252525] transition-colors font-medium">Platform ROI</a>
          </div>

          <div className="flex flex-col gap-2">
            <span className="font-bold text-[#252525] text-sm font-sans mb-1">Legal & Support</span>
            <a href="#faq" className="hover:text-[#252525] transition-colors font-medium">FAQ & Support</a>
            <a href="#faq" className="hover:text-[#252525] transition-colors font-medium font-mono">contact@prefill.ai</a>
            <span className="text-stone-400 mt-2 font-medium">© 2026 PreFill Inc. All rights reserved.</span>
          </div>

        </div>
      </footer>

    </div>
  );
}

export default function Home() {
  return (
    <Suspense fallback={
      <div className="mx-auto max-w-7xl px-4 py-12 text-center text-xs font-semibold uppercase tracking-wider text-stone-500">
        Loading PreFill Showcase...
      </div>
    }>
      <SinglePageShowcaseContent />
    </Suspense>
  );
}
