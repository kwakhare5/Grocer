"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Home" },
  { href: "/household", label: "Profile" },
  { href: "/predictions", label: "Inventory" },
  { href: "/recipes", label: "Recipes", hideMobile: true },
  { href: "/price-alerts", label: "Price Alerts", hideMobile: true },
];

export default function Header() {
  const pathname = usePathname();

  return (
    <header className="w-full border-b border-border/70 bg-white/90 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 md:px-8 h-16 flex items-center justify-between">
        
        {/* Brand Logo */}
        <div className="flex items-center">
          <Link
            href="/"
            className="flex items-center group transition-opacity hover:opacity-90 font-display text-[16px] font-black text-[#1C1917] tracking-tight"
          >
            PreFill
          </Link>
        </div>

        {/* Floating Menu Tabs */}
        <nav className="flex items-center gap-1.5 md:gap-3 text-[11px] md:text-xs font-bold font-display uppercase tracking-wider">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`relative px-3.5 py-2 rounded-md transition-all duration-300 flex items-center justify-center cursor-pointer active:scale-95 ${
                  item.hideMobile ? "hidden sm:inline-flex" : "inline-flex"
                } ${
                  isActive
                    ? "bg-accent/8 text-accent font-extrabold"
                    : "text-muted hover:text-foreground hover:bg-neutral-100/50 dark:hover:bg-neutral-800/40"
                }`}
              >
                <span>{item.label}</span>
                
              </Link>
            );
          })}
        </nav>

      </div>
    </header>
  );
}
