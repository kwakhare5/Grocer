"use client";

import { useEffect, useState } from "react";
import { Sparkles, ChevronLeft, ChevronRight } from "lucide-react";

const VARIANTS = [
  { id: "A", name: "Instrument Serif (Italic)", fontClass: "font-instrument-serif italic" },
  { id: "B", name: "Cormorant Garamond (Italic)", fontClass: "font-cormorant-garamond italic" },
  { id: "C", name: "Newsreader (Italic)", fontClass: "font-newsreader italic" },
];

export default function PrototypeSwitcher() {
  const [variant, setVariant] = useState<string>("A");

  function applyVariantStyles(v: string) {
    if (typeof document === "undefined") return;
    const root = document.documentElement;
    root.classList.remove("variant-a", "variant-b", "variant-c");
    root.classList.add(`variant-${v.toLowerCase()}`);
  }

  function updateUrl(v: string) {
    const params = new URLSearchParams(window.location.search);
    params.set("variant", v);
    window.history.replaceState(null, "", `${window.location.pathname}?${params.toString()}`);
    setVariant(v);
    applyVariantStyles(v);
  }

  useEffect(() => {
    // Run once on mount to check initial URL parameter
    const params = new URLSearchParams(window.location.search);
    const v = params.get("variant") || "A";
    setVariant(v);

    // Apply styling on initial mount after page render
    setTimeout(() => {
      applyVariantStyles(v);
    }, 50);

    // Keyboard listener (fully self-contained, no dependency on state)
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        document.activeElement?.tagName === "INPUT" ||
        document.activeElement?.tagName === "TEXTAREA" ||
        document.activeElement?.hasAttribute("contenteditable")
      ) {
        return;
      }

      const currentParams = new URLSearchParams(window.location.search);
      const currentV = currentParams.get("variant") || "A";
      const currentIndex = VARIANTS.findIndex((x) => x.id === currentV);

      if (e.key === "ArrowLeft") {
        let prevIndex = currentIndex - 1;
        if (prevIndex < 0) prevIndex = VARIANTS.length - 1;
        updateUrl(VARIANTS[prevIndex].id);
      } else if (e.key === "ArrowRight") {
        let nextIndex = currentIndex + 1;
        if (nextIndex >= VARIANTS.length) nextIndex = 0;
        updateUrl(VARIANTS[nextIndex].id);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  function cycleVariant(direction: number) {
    const currentIndex = VARIANTS.findIndex((x) => x.id === variant);
    let nextIndex = currentIndex + direction;
    if (nextIndex >= VARIANTS.length) nextIndex = 0;
    if (nextIndex < 0) nextIndex = VARIANTS.length - 1;
    updateUrl(VARIANTS[nextIndex].id);
  }

  const activeVariant = VARIANTS.find((x) => x.id === variant) || VARIANTS[0];

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[100] glass-card px-4 py-2.5 rounded-full shadow-lg border border-border/80 bg-white/95 flex items-center gap-3.5 animate-in slide-in-from-bottom-4 duration-300">
      <button
        onClick={() => cycleVariant(-1)}
        className="p-1 hover:bg-black/5 rounded-full transition-colors cursor-pointer text-muted"
        title="Previous variant (Left Arrow)"
      >
        <ChevronLeft className="h-4 w-4" />
      </button>

      <div className="flex items-center gap-2">
        <Sparkles className="h-3.5 w-3.5 text-accent animate-pulse" />
        <span className="text-xs font-semibold text-foreground whitespace-nowrap">
          Variant {activeVariant.id}: <span className="text-accent font-bold">{activeVariant.name}</span>
        </span>
      </div>

      <button
        onClick={() => cycleVariant(1)}
        className="p-1 hover:bg-black/5 rounded-full transition-colors cursor-pointer text-muted"
        title="Next variant (Right Arrow)"
      >
        <ChevronRight className="h-4 w-4" />
      </button>
    </div>
  );
}
