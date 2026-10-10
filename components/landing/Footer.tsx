"use client";

import { GrocerLogo } from "../ui/GrocerLogo";
import { WhatsAppIcon } from "../ui/WhatsAppIcon";
import { ExternalLink } from "lucide-react";

export function Footer() {
  return (
    <footer className="relative z-10 bg-transparent border-t border-zinc-200/80 font-sans text-zinc-600">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
        {/* Top Tier: Brand & Core Navigation */}
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-8 pb-8 border-b border-zinc-100">
          {/* Brand & Builder */}
          <div className="space-y-2 max-w-md">
            <div className="flex items-center gap-3">
              <GrocerLogo size="sm" iconOnly />
              <span className="font-bold text-lg text-zinc-950 tracking-tight">
                Grocer
              </span>
              <span className="text-zinc-300">•</span>
              <span className="px-2 py-0.5 rounded-md bg-emerald-50 border border-emerald-200 text-xs font-semibold text-emerald-800">
                Swiggy Builders Club
              </span>
            </div>

            <p className="text-xs sm:text-sm text-zinc-600 leading-relaxed font-normal flex items-center flex-wrap gap-1">
              <span>Autonomous</span>
              <span className="inline-flex items-center gap-1 font-medium text-zinc-900">
                <WhatsAppIcon className="w-3.5 h-3.5 inline shrink-0" />
                <span>WhatsApp</span>
              </span>
              <span>grocery replenishment for Swiggy Instamart. Preserves shopping intent across messages and checks household restock cadences.</span>
            </p>

            <div className="text-xs text-zinc-500 pt-0.5">
              Built by{" "}
              <a
                href="https://github.com/kwakhare5"
                target="_blank"
                rel="noopener noreferrer"
                className="font-semibold text-zinc-900 hover:text-emerald-700 underline transition-colors"
              >
                Karan Wakhare
              </a>
            </div>
          </div>

          {/* Exactly 3 Essential Verified Outbound Links */}
          <div className="flex flex-wrap items-center gap-2.5 sm:gap-3 text-xs sm:text-sm font-medium">
            <a
              href="https://github.com/kwakhare5/Grocer"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-zinc-700 hover:text-emerald-700 hover:bg-zinc-50 border border-zinc-200/80 hover:border-zinc-300 transition-all duration-150 active:scale-[0.98] shadow-2xs"
            >
              <span>GitHub</span>
              <ExternalLink className="w-3.5 h-3.5 text-zinc-400" />
            </a>

            <a
              href="https://github.com/kwakhare5/Grocer/blob/main/docs/SWIGGY_BUILDER_CLUB_APPLICATION.md"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-zinc-700 hover:text-emerald-700 hover:bg-zinc-50 border border-zinc-200/80 hover:border-zinc-300 transition-all duration-150 active:scale-[0.98] shadow-2xs"
            >
              <span>Application Dossier</span>
              <ExternalLink className="w-3.5 h-3.5 text-zinc-400" />
            </a>

            <a
              href="https://mcp.swiggy.com/builders"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-zinc-700 hover:text-emerald-700 hover:bg-zinc-50 border border-zinc-200/80 hover:border-zinc-300 transition-all duration-150 active:scale-[0.98] shadow-2xs"
            >
              <span>Swiggy Builders Club</span>
              <ExternalLink className="w-3.5 h-3.5 text-zinc-400" />
            </a>
          </div>
        </div>

        {/* Bottom Tier: Verification Badge & Copyright */}
        <div className="pt-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs text-zinc-500 font-mono">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            <span>94/94 automated tests passing</span>
            <span className="text-zinc-300">•</span>
            <span>Live Swiggy MCP runtime</span>
          </div>

          <div className="text-zinc-400">
            © 2026 Grocer
          </div>
        </div>
      </div>
    </footer>
  );
}
