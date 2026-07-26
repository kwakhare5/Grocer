import Link from "next/link";
import { Zap } from "lucide-react";

export default function Header() {
  return (
    <header className="w-full border-b border-slate-200/80 bg-white/90 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 md:px-8 h-14 flex items-center justify-between">
        
        {/* Brand Logo */}
        <div className="flex items-center gap-2">
          <Link
            href="/"
            className="flex items-center gap-2 font-display text-base font-bold text-slate-900 tracking-tight group"
          >
            <div className="h-6 w-6 rounded-md bg-slate-900 text-white flex items-center justify-center font-extrabold text-xs transition-transform duration-150 active:scale-95">
              P
            </div>
            <span>PreFill</span>
          </Link>
        </div>

        {/* Section Smooth Anchor Navigation */}
        <nav className="flex items-center gap-1 text-xs font-medium font-display">
          <a
            href="#demo"
            className="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition-colors"
          >
            Showcase
          </a>
          <a
            href="#how-it-works"
            className="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition-colors hidden sm:inline-flex"
          >
            How It Works
          </a>
          <a
            href="#roi"
            className="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition-colors hidden sm:inline-flex"
          >
            Platform ROI
          </a>

          <a
            href="#pitch"
            className="ml-2 btn-saas-primary flex items-center gap-1.5 shadow-2xs"
          >
            <Zap className="h-3 w-3 text-amber-400" />
            <span>Schedule Pitch</span>
          </a>
        </nav>

      </div>
    </header>
  );
}
