"use client";

import React from "react";

interface PreFillLogoProps {
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
      {/* Official Deep Forest Emerald Badge Container */}
      <div
        className={`${iconSizeClasses[size]} text-white flex items-center justify-center shadow-md transition-transform group-hover:scale-105 relative overflow-hidden border border-emerald-950/80 shrink-0`}
        style={{ backgroundColor: "#064E3B" }}
      >
        {/* Official PreFill Deep Forest Emerald Refill Arc SVG */}
        <svg
          className={`${svgSizes[size]} relative z-10`}
          viewBox="0 0 128 128"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Background Track Circle */}
          <circle
            cx="64"
            cy="64"
            r="36"
            fill="none"
            stroke="#A7F3D0"
            strokeWidth="8"
            opacity="0.3"
          />
          {/* Active Refill Arc Ring */}
          <path
            d="M 64 28 A 36 36 0 1 1 38.5 89.5"
            fill="none"
            stroke="#ECFDF5"
            strokeWidth="8"
            strokeLinecap="round"
          />
          {/* Status Indicator Dot */}
          <circle cx="38.5" cy="89.5" r="7.5" fill="#F59E0B" />
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
