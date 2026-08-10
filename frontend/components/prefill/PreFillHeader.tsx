"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Menu, X, ArrowUpRight } from "lucide-react";
import { PreFillLogo } from "../ui/PreFillLogo";
import { PillButton } from "../ui/PillButton";

export function PreFillHeader() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navLinks = [
    { name: "Details", href: "#demo" },
    { name: "Features", href: "#features" },
    { name: "Savings", href: "#roi" },
    { name: "Integrations", href: "#integrations" },
    { name: "FAQ", href: "#faq" },
  ];

  return (
    <header className="sticky top-0 z-50 w-full bg-white/95 backdrop-blur-md border-b border-gray-200/80 transition-all">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center justify-between">
        {/* Left: Logo & Direct Sub-Links */}
        <div className="flex items-center gap-8">
          <Link href="#demo" className="flex items-center gap-2 group shrink-0">
            <PreFillLogo size="sm" />
          </Link>

          {/* Nav Links Adjacent to Logo */}
          <nav className="hidden lg:flex items-center gap-6 text-xs font-semibold text-gray-700">
            {navLinks.map((link) => (
              <Link
                key={link.name}
                href={link.href}
                className="hover:text-gray-950 transition-colors py-1 relative"
              >
                {link.name}
              </Link>
            ))}
          </nav>
        </div>

        {/* Right Actions: Beside 1:1 Spec / Try PreFill / Sign In */}
        <div className="hidden sm:flex items-center gap-3 text-xs font-semibold">
          <a
            href="#features"
            className="px-3.5 py-1.5 rounded-full border border-gray-200 text-gray-700 hover:text-gray-950 hover:bg-gray-50 transition-all"
          >
            Compare Spec
          </a>
          <PillButton href="#demo" variant="primary" className="!h-8 !px-4 text-[11px]">
            <span>Try PreFill</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </PillButton>
          <a
            href="#demo"
            className="text-gray-600 hover:text-gray-950 transition-colors ml-1"
          >
            Sign In
          </a>
        </div>

        {/* Mobile Controls */}
        <div className="flex lg:hidden items-center gap-2">
          <PillButton href="#demo" variant="primary" className="!h-8 !px-3 text-[11px]">
            Try PreFill
          </PillButton>
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-1.5 rounded-full text-gray-700 hover:text-gray-950 hover:bg-gray-100 transition-colors"
            aria-label="Toggle Menu"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer Menu */}
      {mobileMenuOpen && (
        <div className="lg:hidden bg-white border-b border-gray-200/80 px-6 py-4 space-y-3 animate-fadeIn">
          <nav className="flex flex-col space-y-2 text-xs font-bold text-gray-900">
            {navLinks.map((link) => (
              <Link
                key={link.name}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                className="py-2 border-b border-gray-100 flex items-center justify-between"
              >
                <span>{link.name}</span>
                <ArrowUpRight className="w-3.5 h-3.5 text-gray-400" />
              </Link>
            ))}
          </nav>
          <div className="pt-2 flex items-center justify-between text-xs">
            <a href="#features" className="text-gray-600 font-semibold">Compare Spec</a>
            <a href="#demo" className="text-sky-700 font-bold">Sign In</a>
          </div>
        </div>
      )}
    </header>
  );
}
