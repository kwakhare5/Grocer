"use client";

import React from "react";

export function WorkInProgressBanner() {
  return (
    <div className="w-full bg-amber-500/10 border-b border-amber-500/20 text-amber-950 px-4 py-2 text-xs font-medium backdrop-blur-md">
      <div className="max-w-7xl mx-auto flex items-center justify-center gap-2 text-center">
        <span className="inline-block shrink-0 text-sm">🚧</span>
        <p className="leading-snug">
          <strong className="font-semibold text-amber-900">Under construction:</strong> This prototype was submitted for review and is still being actively built, so some things may not work. Sorry about that, and thank you for checking it out!
        </p>
      </div>
    </div>
  );
}
