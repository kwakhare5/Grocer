"use client";

import React from "react";

export interface PillButtonProps {
  children: React.ReactNode;
  variant?: "primary" | "secondary" | "ghost";
  href?: string;
  className?: string;
  onClick?: () => void;
}

export function PillButton({
  children,
  variant = "primary",
  href,
  className = "",
  onClick,
}: PillButtonProps) {
  const baseStyles =
    "h-10 px-5 rounded-full text-xs font-bold transition-all inline-flex items-center justify-center gap-1.5 shadow-xs active:scale-97 cursor-pointer shrink-0 relative overflow-hidden group";

  const variantStyles = {
    primary: "bg-gray-950 hover:bg-gray-800 text-white shadow-xs",
    secondary: "bg-white hover:bg-gray-50 border border-gray-200/80 text-gray-700 hover:text-gray-950",
    ghost: "bg-transparent text-gray-600 hover:text-gray-950 hover:bg-gray-100/80",
  };

  const content = (
    <>
      {/* 21st.dev Shimmer Button Border Line */}
      {variant === "primary" && (
        <span className="absolute inset-0 rounded-full p-[1px] bg-gradient-to-r from-transparent via-sky-400/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
      )}
      <span className="relative z-10 flex items-center gap-1.5">{children}</span>
    </>
  );

  if (href) {
    return (
      <a href={href} className={`${baseStyles} ${variantStyles[variant]} ${className}`}>
        {content}
      </a>
    );
  }

  return (
    <button onClick={onClick} className={`${baseStyles} ${variantStyles[variant]} ${className}`}>
      {content}
    </button>
  );
}
