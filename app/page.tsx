"use client";

import React, { useEffect, useState } from "react";
import { AppGlobalHeader } from "../components/navigation/AppGlobalHeader";
import { HeroSection } from "../components/landing/HeroSection";
import { VideoSection } from "../components/landing/VideoSection";
import { WhatsAppSimulator } from "../components/landing/WhatsAppSimulator";
import { ArchitectureSection } from "../components/landing/ArchitectureSection";
import { FaqSection } from "../components/landing/FaqSection";
import { ConnectInstamartModal } from "../components/landing/ConnectInstamartModal";
import { Footer } from "../components/landing/Footer";

export default function Home() {
  const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [connectTicket, setConnectTicket] = useState<string | null>(null);
  const [connectError, setConnectError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const ticket = params.get("connect_ticket");
      if (ticket) {
        window.history.replaceState({}, "", window.location.pathname);
        const timer = setTimeout(() => {
          setConnectTicket(ticket);
          setIsConnectModalOpen(true);
        }, 0);
        return () => clearTimeout(timer);
      }
      const code = params.get("code");
      const state = params.get("state");
      if (code && state) {
        window.history.replaceState({}, "", window.location.pathname);
        void fetch("/api/auth/swiggy/callback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code, state }),
        }).then((response) => {
          if (!response.ok) throw new Error("Connection failed");
          setIsConnected(true);
        }).catch(() => {
          setConnectError("Connection failed. Request a fresh link in WhatsApp and try again.");
          setIsConnectModalOpen(true);
        });
        return;
      }
      if (params.get("connected") === "true") {
        const timer = setTimeout(() => setIsConnected(true), 0);
        return () => clearTimeout(timer);
      }
    }
  }, []);

  return (
    <div className="relative min-h-screen bg-matte-grain text-zinc-900 flex flex-col font-sans selection:bg-emerald-600 selection:text-white">
      {/* Global Navigation Header (Clean 4-Link Structure) */}
      <AppGlobalHeader />

      <main className="flex-1 relative z-10">
        {/* 1. Hero */}
        <HeroSection
          onOpenConnect={() => setIsConnectModalOpen(true)}
          isConnected={isConnected}
        />

        {/* 2. Video Walkthrough (Reviewer Demo) */}
        <VideoSection />

        {/* 3. WhatsApp Conversation Showcase */}
        <WhatsAppSimulator />

        {/* 3. Architecture & Swiggy MCP Pipeline */}
        <ArchitectureSection />

        {/* 4. Frequently Asked Questions */}
        <FaqSection />
      </main>

      {/* Whitelisted Swiggy Instamart OAuth Connection Modal */}
      <ConnectInstamartModal
        isOpen={isConnectModalOpen}
        onClose={() => setIsConnectModalOpen(false)}
        isConnected={isConnected}
        connectTicket={connectTicket}
        initialError={connectError}
      />

      {/* Unified 4-Column Technical Footer */}
      <Footer />
    </div>
  );
}
