import React from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { LiveDebugInspector } from "../../components/debug/LiveDebugInspector";

export default function DebugPage() {
  return (
    <div className="flex h-screen w-screen flex-col bg-zinc-950 text-zinc-100 overflow-hidden">
      {/* Top Bar with Back Link */}
      <div className="flex items-center justify-between border-b border-zinc-800 bg-zinc-900/80 px-4 py-2 text-xs font-mono">
        <Link
          href="/"
          className="flex items-center gap-1.5 text-zinc-400 hover:text-emerald-400 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to Workbench</span>
        </Link>
        <span className="text-zinc-500">Standalone Live WhatsApp Test Monitor</span>
      </div>

      {/* Main Inspector Viewport */}
      <div className="flex-1 overflow-hidden">
        <LiveDebugInspector isStandalone={true} />
      </div>
    </div>
  );
}
