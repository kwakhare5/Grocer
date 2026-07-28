"use client";

import { useState } from "react";
import { Menu, X } from "lucide-react";

export default function Header() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <header className="w-full bg-[#F6F7F8]/90 backdrop-blur-md border-b border-stone-200/90 fixed top-0 left-0 right-0 z-50 transition-all">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-15 flex items-center justify-between">
        
        {/* Brand Logo */}
        <a href="#demo" className="flex items-center gap-2.5 group select-none">
          <div className="h-8 w-8 rounded-xl bg-[#252525] text-white flex items-center justify-center font-extrabold text-sm shadow-xs group-hover:scale-105 transition-transform">
            P
          </div>
          <span className="font-bold text-[#252525] tracking-tight text-lg leading-none font-sans">
            PreFill
          </span>
        </a>

        {/* Center Navigation Links (Exact Droxy style) */}
        <nav className="hidden md:flex items-center gap-7">
          <a
            href="#features"
            className="text-sm font-medium text-stone-600 hover:text-[#252525] transition-colors font-sans"
          >
            Features
          </a>
          <a
            href="#how-it-works"
            className="text-sm font-medium text-stone-600 hover:text-[#252525] transition-colors font-sans"
          >
            How It Works
          </a>
          <a
            href="#comparison"
            className="text-sm font-medium text-stone-600 hover:text-[#252525] transition-colors font-sans"
          >
            Why PreFill
          </a>
          <a
            href="#platform-roi"
            className="text-sm font-medium text-stone-600 hover:text-[#252525] transition-colors font-sans"
          >
            Platform ROI
          </a>
          <a
            href="#faq"
            className="text-sm font-medium text-stone-600 hover:text-[#252525] transition-colors font-sans"
          >
            Docs
          </a>
        </nav>

        {/* Right CTA Group (Exact Droxy style: Log in + Start Pill) */}
        <div className="hidden md:flex items-center gap-5">
          <a
            href="#demo"
            className="text-sm font-medium text-stone-700 hover:text-[#252525] transition-colors font-sans"
          >
            Log in
          </a>
          <a
            href="#demo"
            className="btn-droxy-pill-primary text-xs font-semibold cursor-pointer select-none"
          >
            Start
          </a>
        </div>

        {/* Mobile Menu Toggle */}
        <div className="flex md:hidden items-center">
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-1.5 rounded-lg text-stone-700 hover:bg-stone-200/60 active:scale-95 transition-all"
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>

      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden border-b border-stone-200 bg-white px-4 py-4 flex flex-col gap-2 shadow-lg">
          <a
            href="#features"
            onClick={() => setMobileMenuOpen(false)}
            className="px-3 py-2 rounded-lg text-sm font-medium text-stone-700 hover:bg-stone-100"
          >
            Features
          </a>
          <a
            href="#how-it-works"
            onClick={() => setMobileMenuOpen(false)}
            className="px-3 py-2 rounded-lg text-sm font-medium text-stone-700 hover:bg-stone-100"
          >
            How It Works
          </a>
          <a
            href="#comparison"
            onClick={() => setMobileMenuOpen(false)}
            className="px-3 py-2 rounded-lg text-sm font-medium text-stone-700 hover:bg-stone-100"
          >
            Why PreFill
          </a>
          <a
            href="#platform-roi"
            onClick={() => setMobileMenuOpen(false)}
            className="px-3 py-2 rounded-lg text-sm font-medium text-stone-700 hover:bg-stone-100"
          >
            Platform ROI
          </a>
          <div className="flex items-center justify-between pt-2 border-t border-stone-100">
            <a
              href="#demo"
              onClick={() => setMobileMenuOpen(false)}
              className="text-sm font-medium text-stone-700"
            >
              Log in
            </a>
            <a
              href="#demo"
              onClick={() => setMobileMenuOpen(false)}
              className="btn-droxy-pill-primary text-xs"
            >
              Start
            </a>
          </div>
        </div>
      )}
    </header>
  );
}
