"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { UtensilsCrossed } from "lucide-react";

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
    <header className="sticky top-4 mx-auto w-[calc(100%-2rem)] xl:w-full max-w-7xl z-50">
      <div className="glass-card rounded-full px-6 md:px-8 h-16 flex items-center justify-between shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-border/80 bg-surface/90 backdrop-blur-md transition-all duration-300">
        
        {/* Brand Logo with micro-interactions */}
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="font-display font-black tracking-tight text-sm md:text-base flex items-center gap-2 group transition-opacity hover:opacity-90"
          >
            <div className="p-2 bg-accent/8 rounded-full text-accent group-hover:rotate-12 transition-transform duration-300 ease-out">
              <UtensilsCrossed className="h-4 w-4" />
            </div>
            <span className="font-bold">
              <span className="text-foreground dark:text-neutral-200">Pre</span>
              <span className="text-accent">Fill</span>
            </span>
          </Link>
          <span className="text-[10px] text-muted/70 hidden lg:flex items-center gap-1.5 font-bold uppercase tracking-wider pl-2 border-l border-border/60">
            <span className="h-1.5 w-1.5 rounded-full bg-ok animate-pulse" />
            Pantry Active
          </span>
        </div>

        {/* Floating Menu Tabs */}
        <nav className="flex items-center gap-1.5 md:gap-3 text-[11px] md:text-xs font-bold font-display uppercase tracking-wider">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`relative px-3.5 py-2 rounded-full transition-all duration-300 flex items-center justify-center cursor-pointer active:scale-95 ${
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
