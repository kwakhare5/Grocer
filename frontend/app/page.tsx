"use client";

import { useState, Suspense } from "react";
import Header from "../components/Header";
import PhoneMockup from "../components/PhoneMockup";
import ExecutivePanel from "../components/ExecutivePanel";
import PreFillFeatureSidebar from "../components/PreFillFeatureSidebar";
import PreFillPracticalUse from "../components/PreFillPracticalUse";
import PreFillBentoGrid from "../components/PreFillBentoGrid";
import { motion } from "framer-motion";
import { 
  MessageSquare, 
  Cpu, 
  ChevronDown, 
  Star, 
  PlayCircle,
  Brain,
  Rocket,
  Users,
  Code,
  ShieldCheck,
  FileText
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
        
        {/* ── 2. HERO SECTION ────────────────────────────────────────── */}
        <section id="demo" className="max-w-5xl w-full pt-12 sm:pt-20 pb-16 px-4 sm:px-6 flex flex-col items-center text-center bg-ascii-mesh-masked relative">
          
          {/* PreFill Tagline Badge */}
          <motion.div 
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="mb-5 badge-droxy-pill cursor-pointer z-10"
          >
            <Brain className="h-3.5 w-3.5 text-stone-700" />
            <span>Your AI-powered restock employee</span>
          </motion.div>

          {/* Main Display Headline */}
          <motion.h1 
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="text-4xl sm:text-6xl md:text-7xl font-extrabold tracking-tight-display text-[#252525] max-w-4xl font-sans z-10"
          >
            Build and deploy reliable AI restock agents
          </motion.h1>

          {/* Subtitle */}
          <motion.p 
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="mt-5 text-base sm:text-lg text-stone-600 max-w-2xl leading-relaxed font-medium z-10"
          >
            The all-in-one platform for customer-facing AI restocking agents across any channel. Launch and monitor your first agent in minutes.
          </motion.p>

          {/* Dual Pill Buttons */}
          <motion.div 
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.25 }}
            className="mt-8 flex flex-col sm:flex-row items-center gap-3.5 z-10"
          >
            <a href="#demo-stage" className="btn-droxy-pill-primary text-sm font-semibold">
              Start now
            </a>
            <a href="#platform-roi" className="btn-droxy-pill-secondary text-sm font-semibold">
              Simple Pricing
            </a>
          </motion.div>

          {/* Centered Hardware Product Showcase Stage (#demo-stage - Pastel Blue Backdrop) */}
          <motion.div 
            id="demo-stage"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.35 }}
            className="w-full max-w-4xl mt-12 z-10"
          >
            <div className="card-pastel-blue w-full flex flex-col lg:flex-row items-center justify-between gap-8 text-left shadow-sm">
              
              {/* Left Column: Interactive iPhone Mockup */}
              <div className="w-full max-w-[340px] flex justify-center shrink-0">
                <PhoneMockup activeScenario={activeScenario} />
              </div>

              {/* Right Column: Stage Controls & Info */}
              <div className="flex-1 flex flex-col gap-4">
                <div className="flex items-center gap-2">
                  <span className="bg-blue-100 text-blue-900 font-bold text-[11px] px-2.5 py-0.5 rounded-full border border-blue-200">
                    LIVE PROTOTYPE
                  </span>
                  <span className="text-xs text-blue-600 font-mono">Interactive Screen</span>
                </div>
                <h3 className="text-2xl font-bold text-[#252525] font-sans tracking-tight title-accent">
                  Proactive WhatsApp Restocking
                </h3>
                <p className="text-xs sm:text-sm text-stone-700 font-medium leading-relaxed">
                  Interact with the phone prototype on the left to test 1-tap WhatsApp orders, inventory stock sliders, recipe gap analysis, and price drop alerts.
                </p>
                <div className="flex flex-col gap-2.5 mt-1">
                  <div className="p-3 rounded-xl bg-white border border-blue-200/80 flex items-center gap-3 shadow-2xs">
                    <MessageSquare className="h-4 w-4 text-emerald-600 shrink-0" />
                    <span className="text-xs font-semibold text-stone-800">1-Tap WhatsApp Checkout with Zero App Browsing</span>
                  </div>
                  <div className="p-3 rounded-xl bg-white border border-blue-200/80 flex items-center gap-3 shadow-2xs">
                    <Cpu className="h-4 w-4 text-blue-600 shrink-0" />
                    <span className="text-xs font-semibold text-stone-800">20% Remaining Inventory Stockout Trigger</span>
                  </div>
                </div>
              </div>

            </div>
          </motion.div>

        </section>

        {/* ── 3. LOGO CLOUD & VIDEO EXPLAINER BANNER ──────────────── */}
        <section className="w-full py-12 border-y border-stone-200 bg-white flex justify-center px-4">
          <div className="max-w-5xl w-full flex flex-col items-center gap-6 text-center">
            
            <span className="text-xs font-semibold uppercase tracking-widest text-stone-400 font-sans">
              Trusted by 30K+ businesses & quick commerce platforms
            </span>

            {/* Quick Commerce Platform Logos */}
            <div className="flex flex-wrap items-center justify-center gap-8 sm:gap-14 text-stone-400 font-extrabold text-lg sm:text-xl tracking-tight">
              <span className="hover:text-stone-800 transition-colors">Zepto</span>
              <span className="hover:text-stone-800 transition-colors">Blinkit</span>
              <span className="hover:text-stone-800 transition-colors">Swiggy Instamart</span>
              <span className="hover:text-stone-800 transition-colors">BigBasket</span>
            </div>

            {/* Video Banner Link */}
            <div className="mt-2 inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-50 border border-blue-200 text-xs font-semibold text-blue-900 hover:bg-blue-100/70 transition-colors cursor-pointer">
              <PlayCircle className="h-4 w-4 text-blue-600" />
              <span>Learn PreFill in 4 minutes here</span>
            </div>

          </div>
        </section>

        {/* ── 4. SCREENSHOT 1: INTERACTIVE SIDEBAR FEATURE SHOWCASE ──── */}
        <section id="features" className="max-w-5xl w-full py-16 sm:py-24 px-4 sm:px-6 flex flex-col items-center">
          <div className="text-center max-w-xl mx-auto flex flex-col items-center gap-2 mb-10">
            <span className="badge-droxy-pill">
              <MessageSquare className="h-3.5 w-3.5 text-stone-700" />
              <span>Instant responses matter</span>
            </span>
            <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight-display text-[#252525] mt-1 font-sans">
              90% of customers expect an immediate response
            </h2>
          </div>
          
          <PreFillFeatureSidebar />
        </section>

        {/* ── 5. SCREENSHOT 2: PRACTICAL USE CASES SHOWCASE ─────────── */}
        <section className="w-full bg-white border-y border-stone-200 flex justify-center px-4 sm:px-6">
          <PreFillPracticalUse />
        </section>

        {/* ── 6. COMPARISON TABLE ("STAY AHEAD WITH AI") (#comparison) ──── */}
        <section id="comparison" className="max-w-5xl w-full py-20 sm:py-28 px-4 sm:px-6 flex flex-col items-center">
          
          <div className="text-center max-w-xl mx-auto flex flex-col items-center gap-2 mb-14">
            <span className="badge-droxy-pill">
              <Rocket className="h-3.5 w-3.5 text-stone-700" />
              <span>Stay ahead with AI</span>
            </span>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-[#252525] mt-1 font-sans">
              Your competitors are already using AI for a reason
            </h2>
          </div>

          {/* Comparison Table Card */}
          <div className="w-full round-card-droxy p-0 overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs sm:text-sm">
                <thead>
                  <tr className="bg-stone-100 border-b border-stone-200">
                    <th className="p-4 sm:p-5 font-bold text-stone-800">Criteria</th>
                    <th className="p-4 sm:p-5 font-bold text-rose-700 bg-rose-50/60">Without PreFill</th>
                    <th className="p-4 sm:p-5 font-bold text-emerald-800 bg-emerald-50/60">With PreFill</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-200 font-medium">
                  <tr>
                    <td className="p-4 sm:p-5 text-stone-800 font-semibold">Time spent on manual grocery reordering</td>
                    <td className="p-4 sm:p-5 text-stone-600 bg-rose-50/20">On average 2 hours per week</td>
                    <td className="p-4 sm:p-5 text-emerald-800 font-bold bg-emerald-50/20">0 hours (1-tap WhatsApp)</td>
                  </tr>
                  <tr>
                    <td className="p-4 sm:p-5 text-stone-800 font-semibold">Response time to stockouts</td>
                    <td className="p-4 sm:p-5 text-stone-600 bg-rose-50/20">1 to 3 days (after stock is empty)</td>
                    <td className="p-4 sm:p-5 text-emerald-800 font-bold bg-emerald-50/20">Instantly (24h before stockout)</td>
                  </tr>
                  <tr>
                    <td className="p-4 sm:p-5 text-stone-800 font-semibold">Kirana store leakage rate</td>
                    <td className="p-4 sm:p-5 text-stone-600 bg-rose-50/20">76% lost grocery spend</td>
                    <td className="p-4 sm:p-5 text-emerald-800 font-bold bg-emerald-50/20">0% (Recaptured via WhatsApp)</td>
                  </tr>
                  <tr>
                    <td className="p-4 sm:p-5 text-stone-800 font-semibold">Household lead retention floor</td>
                    <td className="p-4 sm:p-5 text-stone-600 bg-rose-50/20">24% 90-day retention baseline</td>
                    <td className="p-4 sm:p-5 text-emerald-800 font-bold bg-emerald-50/20">82% retention floor</td>
                  </tr>
                  <tr>
                    <td className="p-4 sm:p-5 text-stone-800 font-semibold">Cost per household lost revenue</td>
                    <td className="p-4 sm:p-5 text-stone-600 bg-rose-50/20">-₹1,450/hh lost monthly GMV</td>
                    <td className="p-4 sm:p-5 text-emerald-800 font-bold bg-emerald-50/20">+₹1,450/hh recaptured GMV</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="mt-8 flex items-center gap-4">
            <a href="#demo" className="btn-droxy-pill-primary text-xs">Start now</a>
            <a href="#platform-roi" className="btn-droxy-pill-secondary text-xs">Simple Pricing</a>
          </div>

        </section>

        {/* ── 7. HUMAN-LIKE INTERACTIONS SECTION ─────────────────────── */}
        <section className="w-full py-20 bg-white border-y border-stone-200 flex justify-center px-4">
          <div className="max-w-4xl w-full flex flex-col items-center text-center gap-6">
            <span className="badge-droxy-pill">
              <Users className="h-3.5 w-3.5 text-stone-700" />
              <span>Human-like interactions guaranteed</span>
            </span>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-[#252525] font-sans">
              PreFill conversations feel human
            </h2>

            {/* 3 Cards in Balanced Pastel Families */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 text-left mt-4 w-full">
              <div className="card-pastel-blue p-5 flex flex-col gap-2">
                <span className="font-extrabold text-sm title-accent">Brand Tone Matching</span>
                <p className="text-xs text-stone-700 font-medium leading-relaxed">
                  Customize the agent&apos;s tone and style to match your quick commerce platform brand identity.
                </p>
              </div>
              <div className="card-pastel-amber p-5 flex flex-col gap-2">
                <span className="font-extrabold text-sm title-accent">Empathetic Reorders</span>
                <p className="text-xs text-stone-700 font-medium leading-relaxed">
                  Tailor responses to be helpful and timely before families run out of morning milk or eggs.
                </p>
              </div>
              <div className="card-pastel-green p-5 flex flex-col gap-2">
                <span className="font-extrabold text-sm title-accent">Advanced LangGraph NLP</span>
                <p className="text-xs text-stone-700 font-medium leading-relaxed">
                  Uses state-of-the-art natural language processing to understand custom item quantities and natural text replies.
                </p>
              </div>
            </div>

            <a href="#demo" className="btn-droxy-pill-primary text-xs mt-2">
              Get started today
            </a>
          </div>
        </section>

        {/* ── 8. SETUP GUIDE (5-STEP ACCORDION) (#how-it-works) ──────── */}
        <section id="how-it-works" className="max-w-5xl w-full py-20 sm:py-28 px-4 sm:px-6 flex flex-col items-center">
          
          <div className="text-center max-w-xl mx-auto flex flex-col items-center gap-2 mb-14">
            <span className="badge-droxy-pill">
              <Code className="h-3.5 w-3.5 text-stone-700" />
              <span>Very simple setup</span>
            </span>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-[#252525] mt-1 font-sans">
              How easy is it to set up?
            </h2>
          </div>

          <div className="w-full flex flex-col gap-3 max-w-3xl">
            {setupSteps.map((step, idx) => (
              <div 
                key={step.num}
                onClick={() => setActiveSetupStep(idx)}
                className={`round-card-droxy p-5 cursor-pointer transition-all ${
                  activeSetupStep === idx ? "border-amber-400 bg-amber-50/30 shadow-sm" : ""
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-xs font-bold px-2 py-1 rounded bg-amber-100 text-amber-900">
                      {step.num}
                    </span>
                    <h3 className="font-bold text-sm sm:text-base text-[#252525] font-sans">
                      {step.title}
                    </h3>
                  </div>
                  <ChevronDown className={`h-4 w-4 text-stone-500 transition-transform ${activeSetupStep === idx ? "rotate-180" : ""}`} />
                </div>
                
                {activeSetupStep === idx && (
                  <p className="mt-3 text-xs sm:text-sm text-stone-600 font-medium leading-relaxed pl-10 border-l-2 border-amber-400">
                    {step.desc}
                  </p>
                )}
              </div>
            ))}
          </div>

        </section>

        {/* ── 9. SAFEGUARDS & MODEL MANAGEMENT ────────────────────── */}
        <section className="w-full py-20 bg-white border-y border-stone-200 flex justify-center px-4">
          <div className="max-w-4xl w-full flex flex-col items-center text-center gap-6">
            <div className="card-pastel-red w-full flex flex-col items-center gap-4">
              <span className="badge-red">
                <ShieldCheck className="h-3.5 w-3.5" />
                <span>Error-free performance with smart safeguards</span>
              </span>
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight title-accent font-sans">
                Robust safeguards and consumption model management
              </h2>
              <p className="text-xs sm:text-sm text-stone-700 max-w-2xl font-medium leading-relaxed">
                Ground your restock agent with your platform catalog & delivery rules, ensuring messages are accurate, non-hallucinatory, and within strict safety boundaries.
              </p>
              <a href="#demo" className="btn-droxy-pill-primary text-xs mt-2">
                Get started today
              </a>
            </div>
          </div>
        </section>

        {/* ── 10. SCREENSHOT 3: 6-CARD VISUAL BENTO GRID ──────────────── */}
        <section className="w-full bg-[#FAFBFB] border-y border-stone-200 flex justify-center px-4 sm:px-6">
          <PreFillBentoGrid />
        </section>

        {/* ── 11. PLATFORM ROI & EXECUTIVE PANEL (#platform-roi) ─────── */}
        <section id="platform-roi" className="max-w-5xl w-full py-20 sm:py-28 px-4 sm:px-6 flex flex-col items-center">
          <div className="text-center max-w-xl mx-auto flex flex-col items-center gap-2 mb-12">
            <span className="badge-droxy-pill">
              Executive ROI Dashboard
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
        </section>

        {/* ── 12. TESTIMONIALS SECTION ──────────────────────────────── */}
        <section className="w-full py-20 bg-white border-y border-stone-200 flex justify-center px-4 sm:px-6">
          <div className="max-w-5xl w-full flex flex-col items-center">
            
            <div className="text-center max-w-xl mx-auto flex flex-col items-center gap-2 mb-14">
              <span className="badge-droxy-pill">
                Customer feedback highlights
              </span>
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-[#252525] mt-1 font-sans">
                What people say about us
              </h2>
            </div>

            {/* Testimonial Cards in Balanced Pastel Families */}
            <div className="w-full grid grid-cols-1 md:grid-cols-3 gap-6">
              {[
                {
                  style: "card-pastel-blue",
                  name: "Rahul Sharma",
                  handle: "@rahul_qc",
                  text: "PreFill completely eliminated Kirana leakage for our quick commerce app. Reordering via WhatsApp is an absolute gamechanger."
                },
                {
                  style: "card-pastel-green",
                  name: "Priya Nair",
                  handle: "@priyanair_d2c",
                  text: "Our 90-day retention floor jumped from 24% to 82% within 3 weeks of setting up PreFill restock agents."
                },
                {
                  style: "card-pastel-amber",
                  name: "Vikram Mehta",
                  handle: "@vikramm_tech",
                  text: "Can't believe how accurate the 20% depletion alert is. The morning milk WhatsApp alert arrives right when we need it."
                }
              ].map((t, idx) => (
                <div key={idx} className={`${t.style} p-6 flex flex-col justify-between gap-4`}>
                  <div className="flex items-center gap-1 text-amber-500">
                    {[...Array(5)].map((_, i) => (
                      <Star key={i} className="h-4 w-4 fill-amber-400 text-amber-400" />
                    ))}
                  </div>
                  <p className="text-xs sm:text-sm text-stone-700 font-medium leading-relaxed">
                    &quot;{t.text}&quot;
                  </p>
                  <div className="flex flex-col">
                    <span className="font-extrabold text-xs text-[#252525]">{t.name}</span>
                    <span className="text-[11px] text-stone-500">{t.handle}</span>
                  </div>
                </div>
              ))}
            </div>

          </div>
        </section>

        {/* ── 13. FAQ ACCORDION (#faq) ───────────────────────────────── */}
        <section id="faq" className="max-w-4xl w-full py-20 sm:py-28 px-4 sm:px-6 flex flex-col items-center">
          
          <div className="text-center max-w-xl mx-auto flex flex-col items-center gap-2 mb-14">
            <span className="badge-droxy-pill">
              <FileText className="h-3.5 w-3.5 text-stone-700" />
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
                className="round-card-droxy p-5 cursor-pointer transition-all hover:border-blue-300"
              >
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-sm sm:text-base text-[#252525] font-sans">
                    {faq.q}
                  </h3>
                  <ChevronDown className={`h-4 w-4 text-stone-500 transition-transform ${openFaq === idx ? "rotate-180" : ""}`} />
                </div>
                
                {openFaq === idx && (
                  <p className="mt-3 text-xs sm:text-sm text-stone-600 font-medium leading-relaxed border-t border-stone-100 pt-3">
                    {faq.a}
                  </p>
                )}
              </div>
            ))}
          </div>

        </section>

        {/* ── 14. FINAL CTA BANNER & FOOTER ─────────────────────────── */}
        <section className="w-full py-16 px-4 sm:px-6 flex justify-center bg-[#252525] text-white">
          <div className="max-w-4xl w-full flex flex-col items-center text-center gap-6 py-6">
            
            <h2 className="text-3xl sm:text-5xl font-extrabold text-white max-w-2xl font-sans tracking-tight">
              Ready to automate your restocking revenue?
            </h2>

            <p className="text-xs sm:text-base text-stone-300 max-w-xl font-medium leading-relaxed">
              Join thousands of quick commerce brands using PreFill AI to capture recurring household reorders.
            </p>

            <div className="flex flex-col sm:flex-row items-center gap-4 mt-2">
              <a href="#demo-stage" className="bg-white text-[#252525] font-bold text-sm px-7 py-3 rounded-full hover:bg-stone-100 transition-all cursor-pointer">
                Start now
              </a>
              <a href="#platform-roi" className="border border-stone-600 text-white font-bold text-sm px-7 py-3 rounded-full hover:bg-stone-800 transition-all cursor-pointer">
                Simple Pricing
              </a>
            </div>

          </div>
        </section>

      </main>

      {/* PreFill Clean Footer */}
      <footer className="w-full border-t border-stone-200 bg-white py-12 px-4 text-xs text-stone-600">
        <div className="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-8">
          
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2.5 font-bold text-[#252525] font-sans text-base">
              <div className="h-6 w-6 rounded-lg bg-[#252525] text-white flex items-center justify-center text-xs font-extrabold">
                P
              </div>
              <span>PreFill</span>
            </div>
            <p className="text-xs text-stone-500 font-medium">
              The all-in-one platform for customer-facing AI restocking agents across quick commerce channels.
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
