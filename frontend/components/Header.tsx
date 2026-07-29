"use client";

import { useState } from "react";
import { Menu, X } from "lucide-react";

// ponytail: static nav array mapped over to reduce JSX repetition (-25 lines)
const NAV_LINKS = [
  { href: "#bento", label: "Architecture" },
  { href: "#features", label: "Features" },
  { href: "#comparison", label: "Why PreFill" },
  { href: "#platform-roi", label: "Platform ROI" },
  { href: "#how-it-works", label: "How It Works" },
  { href: "#faq", label: "FAQ" },
];

export default function Header() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <header className="w-full bg-[#F6F7F8]/90 backdrop-blur-md border-b border-stone-200/90 fixed top-0 left-0 right-0 z-50 transition-all">
      <div className="max-w-7xl mx-auto px-5 sm:px-8 lg:px-12 h-15 flex items-center justify-between">
        
        {/* Brand Logo */}
        <a href="#demo" className="flex items-center gap-2.5 group select-none">
          <div className="h-8 w-8 rounded-xl bg-[#252525] text-white flex items-center justify-center font-extrabold text-sm shadow-xs group-hover:scale-105 transition-transform">
            P
          </div>
          <span className="font-bold text-[#252525] tracking-tight text-lg leading-none font-sans">
            PreFill
          </span>
        </a>

        {/* Center Navigation Links */}
        <nav className="hidden md:flex items-center gap-7">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm font-medium text-stone-600 hover:text-[#252525] transition-colors font-sans"
            >
              {link.label}
            </a>
          ))}
        </nav>

        {/* Right CTA Group */}
        <div className="hidden md:flex items-center gap-5">
          <a
            href="#demo"
            className="text-sm font-semibold text-[#252525] hover:opacity-80 transition-opacity font-sans"
          >
            Log in
          </a>
          <a
            href="#demo"
            className="btn-droxy-pill-primary text-xs tracking-tight"
          >
            Start
          </a>
        </div>

        {/* Mobile Hamburger Toggle */}
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="md:hidden p-2 text-[#252525] hover:bg-stone-200/50 rounded-lg transition-colors cursor-pointer"
          aria-label="Toggle Navigation Menu"
        >
          {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>

      </div>

      {/* Mobile Slide-down Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden bg-[#F6F7F8] border-b border-stone-200 px-6 py-5 flex flex-col gap-4 shadow-lg animate-in slide-in-from-top-2">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              onClick={() => setMobileMenuOpen(false)}
              className="text-sm font-medium text-[#252525] hover:text-stone-600 transition-colors py-1 font-sans"
            >
              {link.label}
            </a>
          ))}
          <div className="pt-2 border-t border-stone-200 flex flex-col gap-3">
            <a
              href="#demo"
              onClick={() => setMobileMenuOpen(false)}
              className="text-sm font-semibold text-[#252525] py-1 font-sans"
            >
              Log in
            </a>
            <a
              href="#demo"
              onClick={() => setMobileMenuOpen(false)}
              className="btn-droxy-pill-primary text-xs text-center"
            >
              Start
            </a>
          </div>
        </div>
      )}
    </header>
  );
}
