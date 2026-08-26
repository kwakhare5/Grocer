"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Menu, X, ArrowUpRight } from "lucide-react";
import { GrocerLogo } from "../ui/GrocerLogo";
import { PillButton } from "../ui/PillButton";
import { WorkInProgressBanner } from "./WorkInProgressBanner";

export function GrocerHeader() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navLinks = [
    { name: "Live Demo", href: "#demo" },
    { name: "Pantry Simulator", href: "#features" },
    { name: "Metrics", href: "#roi" },
    { name: "Integrations", href: "#integrations" },
    { name: "FAQ", href: "#faq" },
  ];

  return (
    <header className="sticky top-0 z-50 w-full bg-white/85 backdrop-blur-md border-b border-gray-200/50 transition-all duration-300">
      {/* 0. Top WIP Notice Banner */}
      <WorkInProgressBanner />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center justify-between">
        {/* Left: Logo & Direct Sub-Links */}
        <div className="flex items-center gap-10">
          <Link href="#demo" className="flex items-center gap-2 group shrink-0 transition-transform active:scale-95">
            <GrocerLogo size="sm" />
          </Link>

          {/* Nav Links Adjacent to Logo */}
          <nav className="hidden lg:flex items-center gap-8 text-xs font-semibold text-gray-600">
            {navLinks.map((link) => (
              <Link
                key={link.name}
                href={link.href}
                className="hover:text-gray-950 transition-colors py-1 relative after:absolute after:bottom-0 after:left-0 after:h-[2px] after:w-0 hover:after:w-full after:bg-gray-950 after:transition-all after:duration-300"
              >
                {link.name}
              </Link>
            ))}
          </nav>
        </div>

        {/* Right Actions: Clean CTA */}
        <div className="hidden sm:flex items-center gap-3 text-xs font-semibold">
          <PillButton href="#demo" variant="primary" className="!h-9 !px-4.5 text-[11px] font-bold">
            <span>Test Grocer Demo</span>
            <ArrowUpRight className="w-3.5 h-3.5 ml-1" />
          </PillButton>
        </div>

        {/* Mobile Controls */}
        <div className="flex lg:hidden items-center gap-2">
          <PillButton href="#demo" variant="primary" className="!h-8.5 !px-3.5 text-[11px] font-bold">
            Try Grocer
          </PillButton>
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-2 rounded-full text-gray-600 hover:text-gray-950 hover:bg-gray-100/80 transition-colors"
            aria-label="Toggle Menu"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer Menu */}
      {mobileMenuOpen && (
        <div className="lg:hidden bg-white/95 backdrop-blur-md border-b border-gray-200/60 px-6 py-5 space-y-4 animate-fadeIn">
          <nav className="flex flex-col space-y-3.5 text-xs font-bold text-gray-900">
            {navLinks.map((link) => (
              <Link
                key={link.name}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                className="py-2.5 border-b border-gray-100 flex items-center justify-between hover:text-sky-600 transition-colors"
              >
                <span>{link.name}</span>
                <ArrowUpRight className="w-4 h-4 text-gray-400" />
              </Link>
            ))}
          </nav>
        </div>
      )}
    </header>
  );
}
