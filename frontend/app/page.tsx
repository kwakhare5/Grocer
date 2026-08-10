"use client";

import React, { Suspense } from "react";
import { PreFillHeader } from "../components/prefill/PreFillHeader";
import { PreFillHero } from "../components/prefill/PreFillHero";
import { PreFillValueProp } from "../components/prefill/PreFillValueProp";
import { PreFillMeasurableValue } from "../components/prefill/PreFillMeasurableValue";
import { PreFillAppPreview } from "../components/prefill/PreFillAppPreview";
import { PreFillTestimonialSection } from "../components/prefill/PreFillTestimonialSection";
import { PreFillIntegrations } from "../components/prefill/PreFillIntegrations";
import { PreFillFAQ } from "../components/prefill/PreFillFAQ";
import { PreFillFooter } from "../components/prefill/PreFillFooter";

function PreFillLandingPage() {
  return (
    <div className="min-h-screen bg-white text-gray-900 font-sans flex flex-col selection:bg-gray-900 selection:text-white relative overflow-x-hidden antialiased">
      {/* 1. Beside 1:1 Top Sticky Header Navbar */}
      <PreFillHeader />

      {/* Main Content Stream */}
      <main className="flex-1 w-full">
        {/* 2. Hero Section (Cambo Serif Headline, Ambient Stage Container, Floating Pills) */}
        <PreFillHero />

        {/* 3. Section 2: 2x2 Bento Grid with Micro-UI Widgets & Saturated Emerald Card */}
        <PreFillValueProp />

        {/* 4. Section 3: 5-Card Bento Grid with Ambient Mesh Gradient Stat Tiles */}
        <PreFillMeasurableValue />

        {/* 5. Beside Section 4 1:1 Replica: App UI Preview Box & Client Logos */}
        <PreFillAppPreview />

        {/* 6. Beside Section 5 & 8 1:1 Replica: Asymmetric Split Testimonial Cards (3x & 2x) */}
        <PreFillTestimonialSection />

        {/* 7. Quick-Commerce Integrations */}
        <PreFillIntegrations />

        {/* 8. FAQ Accordion */}
        <PreFillFAQ />
      </main>

      {/* 9. Beside Section 7 1:1 Giant Split CTA Box & 5-Column Footer */}
      <PreFillFooter />
    </div>
  );
}

export default function Home() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-7xl px-4 py-12 text-center text-xs font-semibold uppercase tracking-wider text-gray-400">
          Loading PreFill...
        </div>
      }
    >
      <PreFillLandingPage />
    </Suspense>
  );
}
