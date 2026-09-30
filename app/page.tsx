"use client";

import React, { useEffect, useState } from "react";
import { AppGlobalHeader } from "../components/navigation/AppGlobalHeader";
import { HeroSection } from "../components/landing/HeroSection";
import { WhyWhatsAppSection } from "../components/landing/WhyWhatsAppSection";
import { CapabilitiesSection } from "../components/landing/CapabilitiesSection";
import { WhatsAppSimulator } from "../components/landing/WhatsAppSimulator";
import { ArchitectureSection } from "../components/landing/ArchitectureSection";
import { FaqSection } from "../components/landing/FaqSection";
import { ConnectInstamartModal } from "../components/landing/ConnectInstamartModal";

export default function Home() {
  const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      if (params.get("connected") === "true") {
        const timer = setTimeout(() => setIsConnected(true), 0);
        return () => clearTimeout(timer);
      }
    }
  }, []);

  return (
    <div className="min-h-screen bg-[#FAFAFA] text-zinc-900 flex flex-col font-sans selection:bg-emerald-600 selection:text-white">
      {/* Global Navigation Header (Clean 5-Link Structure) */}
      <AppGlobalHeader
        onOpenConnect={() => setIsConnectModalOpen(true)}
        isConnected={isConnected}
      />

      <main className="flex-1">
        {/* 1. Hero & Video Showcase */}
        <HeroSection
          onOpenConnect={() => setIsConnectModalOpen(true)}
          isConnected={isConnected}
        />

        {/* 2. Problem vs Solution: Why WhatsApp Beats App Scrolling */}
        <WhyWhatsAppSection />

        {/* 3. Core Capabilities (4 Replenishment Superpowers) */}
        <CapabilitiesSection />

        {/* 4. Dual-Interactive WhatsApp Simulator & Live MCP Inspector */}
        <WhatsAppSimulator />

        {/* 5. Decoupled Architecture & Swiggy MCP Interactive Pipeline */}
        <ArchitectureSection />

        {/* 6. Commerce Safety & Frequently Asked Questions */}
        <FaqSection />
      </main>

      {/* Whitelisted Swiggy Instamart OAuth Connection Modal */}
      <ConnectInstamartModal
        isOpen={isConnectModalOpen}
        onClose={() => setIsConnectModalOpen(false)}
        isConnected={isConnected}
      />

      {/* Unified Landing Page Footer */}
      <footer className="border-t border-zinc-200 py-12 px-4 sm:px-6 lg:px-8 bg-zinc-50 text-xs text-zinc-500 font-sans">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex flex-col sm:flex-row items-center gap-2 sm:gap-4">
            <span className="font-bold text-zinc-900 text-sm">Grocer</span>
            <span>•</span>
            <span>Official Swiggy Builders Club Submission</span>
            <span>•</span>
            <span>Powered by Instamart MCP &amp; Gemini 3.5</span>
          </div>
          <div className="flex items-center gap-4 text-xs font-medium">
            <a
              href="https://github.com/kwakhare5/Grocer"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-zinc-950 transition-colors underline"
            >
              GitHub Repository
            </a>
            <a
              href="https://github.com/kwakhare5/Grocer/blob/main/docs/REVIEWER_WALKTHROUGH.md"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-zinc-950 transition-colors underline"
            >
              Reviewer Walkthrough
            </a>
            <a
              href="https://mcp.swiggy.com/builders"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-zinc-950 transition-colors underline"
            >
              Swiggy Builders Club
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
