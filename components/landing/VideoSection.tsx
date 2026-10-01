"use client";

import React, { useState } from "react";
import { Video, Play } from "lucide-react";

export function VideoSection() {
  const [hasVideoError, setHasVideoError] = useState(false);

  return (
    <section id="demo" className="py-16 sm:py-20 bg-transparent border-b border-zinc-200/80 scroll-mt-16">
      <div className="max-w-6xl mx-auto px-3.5 sm:px-5">
        {/* Section Header */}
        <div className="text-center max-w-2xl mx-auto mb-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold mb-3">
            <Video className="w-3.5 h-3.5 text-emerald-600" />
            <span>Product Walkthrough</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-editorial font-bold text-zinc-950 tracking-tight">
            See Grocer in action
          </h2>
          <p className="mt-2.5 text-sm sm:text-base text-zinc-600 leading-relaxed font-normal">
            A 2-minute walkthrough showing upfront address routing, recipe search, cart merge, hesitation hold, and gated checkout.
          </p>
        </div>

        {/* Video Player Container */}
        <div className="relative rounded-2xl overflow-hidden bg-zinc-50 border border-zinc-200 shadow-xs aspect-video max-w-4xl mx-auto flex items-center justify-center">
          {!hasVideoError ? (
            <video
              controls
              playsInline
              preload="metadata"
              poster="/video-poster.jpg"
              className="w-full h-full object-cover"
              onError={() => setHasVideoError(true)}
            >
              <source src="/demo.mp4" type="video/mp4" />
              Your browser does not support the video tag.
            </video>
          ) : (
            /* Standalone Clean Fallback when /demo.mp4 is pending recording */
            <div className="p-6 sm:p-8 text-center max-w-md space-y-3">
              <div className="w-12 h-12 rounded-xl bg-white border border-zinc-200 flex items-center justify-center mx-auto text-emerald-600 shadow-2xs">
                <Play className="w-5 h-5 ml-0.5" />
              </div>
              <div className="space-y-1">
                <h3 className="text-sm sm:text-base font-bold text-zinc-950">
                  Demo Walkthrough Video
                </h3>
                <p className="text-xs text-zinc-600 leading-relaxed">
                  Recording the live WhatsApp journey. Step through the verified 6-turn interactive conversation below.
                </p>
              </div>

              <div className="pt-2 flex flex-wrap items-center justify-center gap-1.5 text-xs">
                <span className="px-2.5 py-1 rounded-lg bg-white border border-zinc-200 text-zinc-700">
                  1. Address Prompt
                </span>
                <span className="px-2.5 py-1 rounded-lg bg-white border border-zinc-200 text-zinc-700">
                  2. Recipe Search
                </span>
                <span className="px-2.5 py-1 rounded-lg bg-white border border-zinc-200 text-zinc-700">
                  3. Cart Merge
                </span>
                <span className="px-2.5 py-1 rounded-lg bg-white border border-zinc-200 text-zinc-700">
                  4. Gated Checkout
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
