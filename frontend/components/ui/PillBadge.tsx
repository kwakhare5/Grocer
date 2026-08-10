"use client";

import React from "react";
import { motion } from "framer-motion";

export interface PillBadgeProps {
  children: React.ReactNode;
  variant?: "kicker" | "micro" | "tab";
  color?: "sky" | "emerald" | "indigo" | "purple" | "dark" | "white";
  className?: string;
  onClick?: () => void;
  active?: boolean;
  layoutId?: string;
}

export function PillBadge({
  children,
  variant = "kicker",
  color = "sky",
  className = "",
  onClick,
  active = false,
  layoutId,
}: PillBadgeProps) {
  // Height & Padding Variants
  const variantStyles = {
    kicker: "h-7 px-3.5 rounded-full text-[12px] font-semibold inline-flex items-center gap-2 shadow-2xs relative z-10",
    micro: "h-8 px-3.5 rounded-full text-[11px] font-bold inline-flex items-center gap-1.5 backdrop-blur-md shadow-md relative z-10",
    tab: "h-9 px-5 rounded-full text-[12px] font-bold inline-flex items-center justify-center gap-2 shadow-2xs shrink-0 transition-all cursor-pointer relative",
  };

  // Color Palette Themes
  const colorStyles = {
    sky: "bg-sky-50 border border-sky-200/80 text-sky-900",
    emerald: "bg-emerald-50 border border-emerald-200/80 text-emerald-900",
    indigo: "bg-indigo-50 border border-indigo-200/80 text-indigo-900",
    purple: "bg-purple-50 border border-purple-200/80 text-purple-900",
    dark: "bg-gray-950 text-white border border-gray-800",
    white: "bg-white/95 border border-gray-200/90 text-gray-900",
  };

  if (variant === "tab") {
    return (
      <button
        onClick={onClick}
        className={`${variantStyles.tab} ${
          active
            ? "text-white"
            : "bg-white text-gray-600 hover:text-gray-950 border border-gray-200/80"
        } ${className}`}
      >
        {active && (
          <motion.div
            layoutId={layoutId || "activeTab"}
            className="absolute inset-0 bg-gray-950 rounded-full shadow-xs z-0"
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
          />
        )}
        <span className="relative z-10">{children}</span>
      </button>
    );
  }

  const Component = onClick ? "button" : "div";

  return (
    <Component
      onClick={onClick}
      className={`${variantStyles[variant]} ${colorStyles[color]} ${className}`}
    >
      {children}
    </Component>
  );
}
