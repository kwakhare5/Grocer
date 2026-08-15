"use client";

import React, { Suspense } from "react";
import { GrocerHeader } from "../components/grocer/GrocerHeader";
import { GrocerHero } from "../components/grocer/GrocerHero";
import { GrocerValueProp } from "../components/grocer/GrocerValueProp";
import { GrocerIntegrations } from "../components/grocer/GrocerIntegrations";
import { GrocerFAQ } from "../components/grocer/GrocerFAQ";
import { GrocerFooter } from "../components/grocer/GrocerFooter";

function GrocerLandingPage() {
  return (
    <div className="min-h-screen bg-white text-gray-900 font-sans flex flex-col selection:bg-gray-900 selection:text-white relative overflow-x-hidden antialiased">
      {/* 1. Sticky Header Navbar */}
      <GrocerHeader />

      {/* Main Content Stream */}
      <main className="flex-1 w-full">
        {/* 2. Hero Section (Side-by-Side with Interactive iPhone 16 Pro Demo) */}
        <GrocerHero />

        {/* 3. Core Technical Architecture Bento Grid */}
        <GrocerValueProp />

        {/* 4. Conceptual Dark Store Integration Webhooks */}
        <GrocerIntegrations />

        {/* 5. FAQ Accordion */}
        <GrocerFAQ />
      </main>

      {/* 6. Footer */}
      <GrocerFooter />
    </div>
  );
}

export default function Home() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-7xl px-4 py-12 text-center text-xs font-semibold uppercase tracking-wider text-gray-400">
          Loading Grocer...
        </div>
      }
    >
      <GrocerLandingPage />
    </Suspense>
  );
}

