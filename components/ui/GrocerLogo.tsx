"use client";

import React from "react";

export interface GrocerLogoProps {
  className?: string;
  iconOnly?: boolean;
  size?: "sm" | "md" | "lg" | "xl";
}

export function GrocerLogo({
  className = "",
  iconOnly = false,
  size = "md",
}: GrocerLogoProps) {
  // Apple Standard App Icon Squircle Sizing
  const iconSizeClasses = {
    sm: "w-8 h-8 rounded-xl",
    md: "w-10 h-10 rounded-2xl",
    lg: "w-12 h-12 rounded-2xl",
    xl: "w-16 h-16 rounded-3xl",
  };

  const textSizeClasses = {
    sm: "text-lg",
    md: "text-xl",
    lg: "text-2xl",
    xl: "text-3xl",
  };

  return (
    <div className={`flex items-center gap-2.5 group cursor-pointer select-none ${className}`}>
      {/* Official Solid White Squircle Container with Spring Hover */}
      <div
        className={`${iconSizeClasses[size]} bg-white text-white flex items-center justify-center shadow-md transition-transform duration-200 group-hover:scale-105 relative overflow-hidden border border-gray-200/80 shrink-0`}
      >
        {/* Full-Bleed Gradient Mesh Shopping Bag Mascot Clipped to Apple Squircle */}
        <svg className="w-full h-full" viewBox="0 0 512 512" fill="none" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <clipPath id="grocerLogoSquircleClip">
              <rect width="512" height="512" rx="116" />
            </clipPath>

            <linearGradient id="grocerAmbientCascade" x1="20%" y1="0%" x2="80%" y2="100%">
              <stop offset="0%" stopColor="#4ADE80" />
              <stop offset="35%" stopColor="#30D158" />
              <stop offset="75%" stopColor="#22C55E" />
              <stop offset="100%" stopColor="#16A34A" />
            </linearGradient>
          </defs>

          <g clipPath="url(#grocerLogoSquircleClip)">
            {/* Solid Titanium White Base Canvas */}
            <rect width="512" height="512" fill="#FFFFFF" />
            <rect width="512" height="512" rx="116" ry="116" fill="none" stroke="#E5E7EB" strokeWidth="2" />

            {/* Floor Contact Grounding Shadow */}
            <ellipse cx="256" cy="445" rx="126" ry="13" fill="rgba(16,185,129,0.18)" />

            {/* Centered Gradient Mesh Grocery Bag (1.26x Scale, Equal 52px Margins) */}
            <g transform="translate(256, 233) rotate(-4.5) scale(1.26)">
              {/* Handles */}
              <path d="M -50 -45 C -50 -130 50 -130 50 -45" fill="none" stroke="url(#grocerAmbientCascade)" strokeWidth="28" strokeLinecap="round" />
              {/* Symmetrical Bag Body */}
              <path d="M -95 -45 L 95 -45 C 115 -45 130 -25 125 0 L 105 145 C 100 168 82 180 58 180 L -58 180 C -82 180 -100 168 -105 145 L -125 0 C -130 -25 -115 -45 -95 -45 Z" fill="url(#grocerAmbientCascade)" />

              {/* Golden Ratio Face */}
              <g transform="translate(0, 35)">
                <ellipse cx="-44" cy="0" rx="11" ry="17" fill="#FFFFFF" />
                <ellipse cx="44" cy="0" rx="11" ry="17" fill="#FFFFFF" />
                {/* Micro-Smile Arc */}
                <path d="M -15.5 40 Q 0 52 15.5 40" fill="none" stroke="#FFFFFF" strokeWidth="5.5" strokeLinecap="round" />
              </g>
            </g>
          </g>
        </svg>
      </div>

      {!iconOnly && (
        <span className={`font-extrabold ${textSizeClasses[size]} tracking-tight text-gray-950 group-hover:text-gray-800 transition-colors`}>
          Grocer
        </span>
      )}
    </div>
  );
}
