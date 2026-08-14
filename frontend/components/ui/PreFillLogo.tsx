"use client";

import React from "react";

export interface PreFillLogoProps {
  className?: string;
  iconOnly?: boolean;
  size?: "sm" | "md" | "lg";
}

export function PreFillLogo({
  className = "",
  iconOnly = false,
  size = "md",
}: PreFillLogoProps) {
  const iconSizeClasses = {
    sm: "w-7 h-7 rounded-lg",
    md: "w-8.5 h-8.5 rounded-xl",
    lg: "w-10 h-10 rounded-2xl",
  };

  const svgSizes = {
    sm: "w-4.5 h-4.5",
    md: "w-5.5 h-5.5",
    lg: "w-7 h-7",
  };

  const textSizeClasses = {
    sm: "text-lg",
    md: "text-xl",
    lg: "text-2xl",
  };

  return (
    <div className={`flex items-center gap-2.5 group cursor-pointer ${className}`}>
      {/* Official Fresh Apple Leaf Green (#22C55E) Badge Container */}
      <div
        className={`${iconSizeClasses[size]} text-white flex items-center justify-center shadow-md transition-transform group-hover:scale-105 relative overflow-hidden border border-green-600/50 shrink-0`}
        style={{ backgroundColor: "#22C55E" }}
      >
        {/* Official PreFill Bottle SVG Icon with Lowered Liquid Level (y=282) */}
        <svg
          className={`${svgSizes[size]} relative z-10`}
          viewBox="0 0 512 512"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Bottle Outer Line */}
          <rect
            x="124"
            y="116"
            width="264"
            height="304"
            rx="50"
            stroke="#FFFFFF"
            strokeWidth="32"
          />
          {/* Liquid Fill Level (Slightly below middle at y=282) */}
          <path
            d="M128 282 C170 259 205 265 238 279 C274 294 309 297 344 276 C362 266 378 263 384 263 L384 393 Q384 416 361 416 H151 Q128 416 128 393Z"
            fill="#FFFFFF"
          />
        </svg>
      </div>

      {!iconOnly && (
        <span className={`font-extrabold ${textSizeClasses[size]} tracking-tight text-gray-950 group-hover:text-gray-800 transition-colors`}>
          PreFill
        </span>
      )}
    </div>
  );
}
