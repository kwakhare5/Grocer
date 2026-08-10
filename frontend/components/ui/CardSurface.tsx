"use client";

import React from "react";

export interface CardSurfaceProps {
  children: React.ReactNode;
  variant?: "default" | "accent" | "gradient" | "dark" | "mesh";
  meshColor?: "sky" | "amber" | "indigo" | "emerald";
  className?: string;
  onClick?: () => void;
  showDotPattern?: boolean;
}

export function CardSurface({
  children,
  variant = "default",
  meshColor = "sky",
  className = "",
  onClick,
  showDotPattern = false,
}: CardSurfaceProps) {
  // Base Surface Tokens & Micro-Spring Hover Motion
  const baseStyles =
    "rounded-3xl p-6 sm:p-8 transition-all duration-300 relative overflow-hidden flex flex-col justify-between hover:-translate-y-1 hover:shadow-xl active:scale-97 cursor-default";

  // Surface Variant Classes & Glassmorphism Specular Reflections
  const variantStyles = {
    default:
      "bg-white/95 backdrop-blur-sm border border-gray-200/80 shadow-[0_4px_20px_rgba(0,0,0,0.04)] text-gray-950",
    accent:
      "bg-sky-50/80 backdrop-blur-sm border border-sky-200/80 shadow-[0_4px_20px_rgba(0,0,0,0.04)] text-gray-950",
    gradient:
      "bg-gradient-to-br from-sky-500 via-blue-600 to-indigo-600 border border-sky-400/80 shadow-lg text-white",
    dark:
      "bg-gray-950 border border-gray-800 shadow-2xl text-white",
    mesh:
      "bg-white/95 backdrop-blur-sm border border-gray-200/80 shadow-[0_4px_20px_rgba(0,0,0,0.04)] text-gray-950",
  };

  // Pulsing Ambient Mesh Gradient Art Overlay Configuration
  const meshGradients = {
    sky: "from-sky-400/25 via-indigo-500/20 to-emerald-400/25",
    amber: "from-amber-400/25 via-emerald-500/20 to-sky-400/25",
    indigo: "from-indigo-400/25 via-purple-500/20 to-sky-400/25",
    emerald: "from-emerald-400/25 via-teal-500/20 to-sky-400/25",
  };

  const Component = onClick ? "button" : "div";

  return (
    <Component
      onClick={onClick}
      className={`${baseStyles} ${variantStyles[variant]} ${className}`}
    >
      {/* 21st.dev DotPattern Geometric Vector Grid Texture */}
      {showDotPattern && (
        <div className="absolute inset-0 bg-[radial-gradient(#e5e7eb_1px,transparent_1px)] [background-size:16px_16px] opacity-40 pointer-events-none z-0" />
      )}

      {/* Specular Highlight Top Edge */}
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/80 to-transparent pointer-events-none z-10" />

      <div className="relative z-10 w-full space-y-6">{children}</div>

      {/* Pulsing Ambient Mesh Gradient Blur Tile */}
      {variant === "mesh" && (
        <div
          className={`absolute -bottom-10 -right-10 w-52 h-52 bg-gradient-to-tr ${meshGradients[meshColor]} rounded-full filter blur-3xl pointer-events-none z-0 animate-pulse`}
        />
      )}
    </Component>
  );
}
