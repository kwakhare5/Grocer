"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Copy,
  Info,
  Layers,
  Package,
  RefreshCw,
  Shield,
  Sparkles,
  Terminal,
  Zap,
} from "lucide-react";
import {
  fetchLatestDebugTelemetry,
  fetchDebugSessions,
  fetchDebugSessionById,
  type DebugLiveInspectionResponse,
  type DebugSessionSummary,
} from "../../lib/apiClient";

interface LiveDebugInspectorProps {
  onClose?: () => void;
  isStandalone?: boolean;
}

export function LiveDebugInspector({ onClose, isStandalone = false }: LiveDebugInspectorProps) {
  const [telemetry, setTelemetry] = useState<DebugLiveInspectionResponse | null>(null);
  const [sessions, setSessions] = useState<DebugSessionSummary[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string>("latest");
  const [autoPoll, setAutoPoll] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showRawJson, setShowRawJson] = useState(false);
  const [copied, setCopied] = useState(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date | null>(null);

  const executeFetch = useCallback(async (sessionId: string) => {
    try {
      setError(null);
      const [sessionList, data] = await Promise.all([
        fetchDebugSessions().catch(() => []),
        sessionId === "latest"
          ? fetchLatestDebugTelemetry()
          : fetchDebugSessionById(sessionId),
      ]);
      setSessions(sessionList);
      setTelemetry(data);
      setLastRefreshedAt(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load telemetry");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleManualRefresh = () => {
    setLoading(true);
    void executeFetch(selectedSessionId);
  };

  useEffect(() => {
    let ignore = false;
    const run = async () => {
      try {
        const [sessionList, data] = await Promise.all([
          fetchDebugSessions().catch(() => []),
          selectedSessionId === "latest"
            ? fetchLatestDebugTelemetry()
            : fetchDebugSessionById(selectedSessionId),
        ]);
        if (!ignore) {
          setSessions(sessionList);
          setTelemetry(data);
          setLastRefreshedAt(new Date());
        }
      } catch (err) {
        if (!ignore) {
          setError(err instanceof Error ? err.message : "Failed to load telemetry");
        }
      }
    };
    void run();
    return () => {
      ignore = true;
    };
  }, [selectedSessionId]);

  // Auto-poll interval (3s) for live WhatsApp observation
  useEffect(() => {
    if (!autoPoll) return;
    const interval = setInterval(() => {
      void executeFetch(selectedSessionId);
    }, 3000);
    return () => clearInterval(interval);
  }, [autoPoll, selectedSessionId, executeFetch]);

  const handleCopyJson = () => {
    if (!telemetry) return;
    void navigator.clipboard.writeText(JSON.stringify(telemetry, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const verificationStatus = telemetry?.verification_result?.status || "NOT_RUN";
  const isPass = verificationStatus === "PASS";
  const violations = telemetry?.verification_result?.violations || [];
  const deviations = telemetry?.verification_result?.deviations || [];

  return (
    <div className="flex h-full flex-col bg-zinc-950 text-zinc-100 font-sans">
      {/* Header Bar */}
      <div className="flex items-center justify-between border-b border-zinc-800/80 bg-zinc-900/90 px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
            <Terminal className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold uppercase tracking-wider text-emerald-400">
                GROCER Live Telemetry
              </span>
              <span className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-[10px] text-zinc-400">
                DEV ONLY
              </span>
              {telemetry?.is_mock && (
                <span className="rounded bg-amber-950/80 border border-amber-800 text-amber-300 px-1.5 py-0.5 font-mono text-[9px] font-semibold">
                  MOCK FALLBACK
                </span>
              )}
            </div>
            <p className="text-[11px] text-zinc-400">
              Live WhatsApp turn inspection & deterministic audit matrix
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Auto Poll Switch */}
          <button
            type="button"
            onClick={() => setAutoPoll((prev) => !prev)}
            className={`flex items-center gap-1.5 rounded-md px-2 py-1 font-mono text-[11px] transition-colors ${
              autoPoll
                ? "bg-emerald-950/80 text-emerald-300 border border-emerald-700/60"
                : "bg-zinc-800 text-zinc-400 hover:text-zinc-200"
            }`}
            title="Auto-refresh every 3s to track live WhatsApp messages"
          >
            <Zap className={`h-3 w-3 ${autoPoll ? "text-emerald-400 fill-emerald-400" : ""}`} />
            <span>{autoPoll ? "Live 3s" : "Paused"}</span>
          </button>

          {/* Manual Refresh */}
          <button
            type="button"
            onClick={handleManualRefresh}
            disabled={loading}
            className="flex items-center gap-1 rounded-md bg-zinc-800 px-2 py-1 font-mono text-[11px] text-zinc-300 hover:bg-zinc-700 disabled:opacity-50"
            title="Refresh telemetry immediately"
          >
            <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>

          {/* Close button if inside slide-over */}
          {!isStandalone && onClose && (
            <button
              type="button"
              onClick={onClose}
              className="ml-2 rounded-md bg-zinc-800 px-2.5 py-1 text-xs font-semibold text-zinc-400 hover:bg-zinc-700 hover:text-zinc-100"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Sub-Header: Session Selector & Safety Seal */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800/60 bg-zinc-900/40 px-4 py-2 sm:px-6 text-[11px] font-mono">
        <div className="flex items-center gap-2">
          <span className="text-zinc-500">Session:</span>
          <select
            value={selectedSessionId}
            onChange={(e) => setSelectedSessionId(e.target.value)}
            className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-zinc-200 focus:border-emerald-500 focus:outline-none"
          >
            <option value="latest">Latest Active Turn (Auto)</option>
            {sessions.map((s) => (
              <option key={s.session_id} value={s.session_id}>
                {s.customer_id} ({s.conversation_state}) - {s.original_user_request.slice(0, 24)}...
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-3 text-zinc-400">
          <div className="flex items-center gap-1 text-[10px] text-emerald-400">
            <Shield className="h-3 w-3 text-emerald-500" />
            <span>PII SANITIZED & CREDENTIALS STRIPPED</span>
          </div>
          <span className="text-zinc-600">|</span>
          <span className="text-[10px] text-zinc-500" suppressHydrationWarning>
            Refreshed: {lastRefreshedAt ? lastRefreshedAt.toLocaleTimeString() : "just now"}
          </span>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
        {error && (
          <div className="flex items-center gap-2 rounded-xl border border-red-900/60 bg-red-950/40 p-3 text-xs text-red-200">
            <AlertCircle className="h-4 w-4 shrink-0 text-red-400" />
            <span>{error}</span>
          </div>
        )}

        {/* 1. Request Overview Card */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="font-mono text-[11px] uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
              <Sparkles className="h-3 w-3 text-emerald-400" /> Original User Request
            </span>
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-mono font-semibold ${
              telemetry?.conversation_state === "AWAITING_CONFIRMATION"
                ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                : telemetry?.conversation_state === "NEEDS_DECISION"
                ? "bg-amber-950 text-amber-300 border border-amber-800"
                : "bg-zinc-800 text-zinc-300"
            }`}>
              {telemetry?.conversation_state || "UNKNOWN"}
            </span>
          </div>
          <div className="rounded-lg bg-zinc-950 p-3 border border-zinc-800/80 font-mono text-sm text-zinc-100">
            &ldquo;{telemetry?.original_user_request || "No active request"}&rdquo;
          </div>

          <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono">
            <div className="rounded bg-zinc-900/80 p-2 border border-zinc-800">
              <span className="text-zinc-500 block text-[10px]">Session ID</span>
              <span className="text-zinc-300 truncate block" title={telemetry?.session_id}>
                {telemetry?.session_id || "none"}
              </span>
            </div>
            <div className="rounded bg-zinc-900/80 p-2 border border-zinc-800">
              <span className="text-zinc-500 block text-[10px]">Customer ID (Masked)</span>
              <span className="text-zinc-300 truncate block">
                {telemetry?.masked_customer_id || "none"}
              </span>
            </div>
            <div className="rounded bg-zinc-900/80 p-2 border border-zinc-800">
              <span className="text-zinc-500 block text-[10px]">Turn Count</span>
              <span className="text-zinc-300 font-bold">
                {telemetry?.turn_count ?? 0}
              </span>
            </div>
            <div className="rounded bg-zinc-900/80 p-2 border border-zinc-800">
              <span className="text-zinc-500 block text-[10px]">Address (Sanitized)</span>
              <span className="text-zinc-300 truncate block">
                {telemetry?.sanitized_address || "None selected"}
              </span>
            </div>
          </div>
        </div>

        {/* 2. Item & Fulfillment Audit Matrix */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Package className="h-4 w-4 text-emerald-400" />
              <span className="font-mono text-xs font-bold uppercase tracking-wider text-zinc-200">
                Item Fulfillment Audit Matrix
              </span>
            </div>
            <span className="text-[10px] font-mono text-zinc-500">
              {telemetry?.items.length || 0} item(s) tracked
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full border-collapse font-mono text-[11px]">
              <thead>
                <tr className="border-b border-zinc-800 text-left text-zinc-400">
                  <th className="py-2 pr-3">Requested Item</th>
                  <th className="py-2 pr-3">Interpreted Quantity & Semantics</th>
                  <th className="py-2 pr-3">Selected Provider Product</th>
                  <th className="py-2 pr-3">Pack Size</th>
                  <th className="py-2 pr-3">Planned Qty</th>
                  <th className="py-2 pr-3">Actual Cart Qty</th>
                  <th className="py-2 pr-3">Fulfillment</th>
                  <th className="py-2">Provider Cap</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
                {telemetry?.items.map((it) => (
                  <tr key={it.item_id} className="hover:bg-zinc-800/30">
                    <td className="py-3 pr-3 font-semibold text-white">
                      {it.name}
                      {it.is_mock && (
                        <span className="ml-1.5 inline-block rounded bg-zinc-800 px-1 py-0.2 text-[9px] text-amber-400">
                          MOCK
                        </span>
                      )}
                    </td>
                    <td className="py-3 pr-3">
                      <span className="text-emerald-400 font-medium">{it.original_requested_quantity}</span>
                      <div className="text-[10px] text-zinc-400 mt-0.5">{it.interpreted_meaning}</div>
                    </td>
                    <td className="py-3 pr-3">
                      {it.selected_provider_product ? (
                        <div>
                          <div className="text-zinc-200 truncate max-w-[180px]" title={it.selected_provider_product}>
                            {it.selected_provider_product}
                          </div>
                          <div className="text-[9px] text-zinc-500 font-mono">
                            SKU: {it.selected_spin_id || "none"}
                          </div>
                        </div>
                      ) : (
                        <span className="text-zinc-500 italic">None selected</span>
                      )}
                    </td>
                    <td className="py-3 pr-3">
                      {it.provider_pack_size ? (
                        <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-zinc-200">
                          {it.provider_pack_size}
                        </span>
                      ) : (
                        <span className="text-zinc-500">—</span>
                      )}
                    </td>
                    <td className="py-3 pr-3 font-semibold text-zinc-200">
                      {it.planned_cart_quantity !== null ? `${it.planned_cart_quantity} packs` : "—"}
                    </td>
                    <td className="py-3 pr-3 font-semibold text-zinc-100">
                      {it.actual_canonical_cart_quantity !== null ? `${it.actual_canonical_cart_quantity} packs` : "—"}
                    </td>
                    <td className="py-3 pr-3">
                      <span className={`inline-block rounded px-1.5 py-0.5 font-semibold ${
                        it.actual_fulfillment.includes("100%")
                          ? "bg-emerald-950 text-emerald-300 border border-emerald-800/60"
                          : "bg-zinc-800 text-zinc-300"
                      }`}>
                        {it.actual_fulfillment}
                      </span>
                    </td>
                    <td className="py-3">
                      {it.provider_max_quantity !== null ? (
                        <span className="rounded bg-amber-950/60 border border-amber-800/60 text-amber-300 px-1.5 py-0.5 text-[10px]">
                          Max {it.provider_max_quantity}
                        </span>
                      ) : (
                        <span className="text-zinc-500 text-[10px]">Uncapped</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Integration point notes for items */}
          {telemetry?.items.some((it) => it.integration_note) && (
            <div className="mt-3 space-y-1 border-t border-zinc-800/80 pt-3 text-[10px] text-amber-400 font-mono">
              {telemetry.items
                .filter((it) => it.integration_note)
                .map((it) => (
                  <div key={it.item_id} className="flex items-start gap-1">
                    <Info className="h-3 w-3 shrink-0 mt-0.5 text-amber-500" />
                    <span>{it.integration_note}</span>
                  </div>
                ))}
            </div>
          )}
        </div>

        {/* 3. Verification & Recovery Two-Column Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Verification Result Card */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
            <div className="mb-3 flex items-center justify-between">
              <span className="font-mono text-xs font-bold uppercase tracking-wider text-zinc-300 flex items-center gap-1.5">
                <CheckCircle2 className={`h-4 w-4 ${isPass ? "text-emerald-400" : "text-amber-400"}`} />
                Verification Result
              </span>
              <span className={`rounded-md px-2 py-0.5 font-mono text-xs font-bold ${
                isPass
                  ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                  : "bg-amber-950 text-amber-300 border border-amber-800"
              }`}>
                {verificationStatus}
              </span>
            </div>

            <div className="space-y-2 text-[11px] font-mono">
              {violations.length === 0 && deviations.length === 0 ? (
                <div className="rounded-lg bg-zinc-950 p-3 border border-zinc-800/60 text-zinc-400">
                  Zero constraint violations or deviations detected.
                </div>
              ) : (
                <>
                  {violations.map((v, i) => (
                    <div key={`viol-${i}`} className="rounded bg-red-950/40 border border-red-900/60 p-2 text-red-200">
                      <div className="font-bold flex items-center justify-between">
                        <span>VIOLATION: {v.violation_code}</span>
                        <span className="text-[9px] uppercase px-1 rounded bg-red-900 text-white">HARD</span>
                      </div>
                      <div className="text-[10px] text-zinc-300 mt-1">{v.detail} (target: {v.target})</div>
                    </div>
                  ))}
                  {deviations.map((d, i) => (
                    <div key={`dev-${i}`} className="rounded bg-amber-950/40 border border-amber-900/60 p-2 text-amber-200">
                      <div className="font-bold">DEVIATION: {d.preference_type}</div>
                      <div className="text-[10px] text-zinc-300 mt-1">
                        Expected: {d.expected} &rarr; Actual: {d.actual}
                      </div>
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>

          {/* Recovery & Clarification Card */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
            <div className="mb-3 flex items-center justify-between">
              <span className="font-mono text-xs font-bold uppercase tracking-wider text-zinc-300 flex items-center gap-1.5">
                <Layers className="h-4 w-4 text-emerald-400" />
                Recovery & Clarification
              </span>
              <span className="rounded bg-zinc-800 px-2 py-0.5 font-mono text-[10px] text-zinc-300">
                State: {telemetry?.recovery_classification?.state || "none"}
              </span>
            </div>

            <div className="space-y-2 text-[11px] font-mono">
              <div className="flex items-center justify-between rounded bg-zinc-950 p-2 border border-zinc-800/60">
                <span className="text-zinc-500">Clarification Required</span>
                <span className={`font-bold ${telemetry?.clarification_required ? "text-amber-400" : "text-emerald-400"}`}>
                  {telemetry?.clarification_required ? "YES (Needs User Decision)" : "NO"}
                </span>
              </div>

              {telemetry?.clarification_details && (
                <div className="rounded bg-zinc-950 p-2.5 border border-zinc-800/60">
                  <div className="text-[10px] text-amber-400 font-semibold">
                    Question: {telemetry.clarification_details.question}
                  </div>
                  <div className="mt-1 text-[10px] text-zinc-400">
                    Candidate alternatives: {telemetry.clarification_details.candidate_count || 0} offered
                  </div>
                </div>
              )}

              <div className="flex items-center justify-between rounded bg-zinc-950 p-2 border border-zinc-800/60">
                <span className="text-zinc-500">Auto-Apply Safe</span>
                <span className="text-zinc-300">
                  {telemetry?.recovery_classification?.can_auto_apply ? "YES" : "NO"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* 4. Relevant Safe Event Names */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="font-mono text-xs font-bold uppercase tracking-wider text-zinc-300 flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5 text-emerald-400" /> Relevant Safe Event Names
            </span>
            <span className="text-[10px] font-mono text-zinc-500">
              {telemetry?.relevant_safe_event_names.length || 0} events recorded
            </span>
          </div>

          <div className="rounded-lg bg-zinc-950 p-3 border border-zinc-800/80 font-mono text-xs text-zinc-300 max-h-48 overflow-y-auto space-y-1">
            {telemetry?.relevant_safe_event_names && telemetry.relevant_safe_event_names.length > 0 ? (
              telemetry.relevant_safe_event_names.map((event, idx) => (
                <div key={`${event}-${idx}`} className="flex items-start gap-2">
                  <span className="text-zinc-600 select-none">{String(idx + 1).padStart(2, "0")}.</span>
                  <span className={
                    event.includes("PASS") || event.includes("CONFIRMATION") || event.includes("BUILT")
                      ? "text-emerald-400"
                      : event.includes("RECOVERY") || event.includes("DECISION")
                      ? "text-amber-400"
                      : "text-zinc-300"
                  }>
                    {event}
                  </span>
                </div>
              ))
            ) : (
              <div className="text-zinc-500 italic">No events recorded in this session.</div>
            )}
          </div>
        </div>

        {/* 5. Integration Points & Raw JSON Inspector */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => setShowRawJson((prev) => !prev)}
              className="flex items-center gap-1.5 font-mono text-xs text-zinc-400 hover:text-zinc-100"
            >
              {showRawJson ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
              <span>{showRawJson ? "Hide Raw Telemetry JSON" : "Show Raw Telemetry JSON"}</span>
            </button>

            <button
              type="button"
              onClick={handleCopyJson}
              className="flex items-center gap-1 rounded bg-zinc-800 px-2 py-1 font-mono text-[10px] text-zinc-300 hover:bg-zinc-700"
            >
              <Copy className="h-3 w-3" />
              <span>{copied ? "Copied!" : "Copy JSON"}</span>
            </button>
          </div>

          {showRawJson && (
            <pre className="max-h-64 overflow-x-auto rounded-lg bg-zinc-950 p-3 text-[10px] font-mono text-zinc-300 border border-zinc-800">
              {JSON.stringify(telemetry, null, 2)}
            </pre>
          )}

          {telemetry?.integration_points && telemetry.integration_points.length > 0 && (
            <div className="border-t border-zinc-800/80 pt-2 text-[10px] font-mono text-zinc-500">
              <span className="font-bold text-zinc-400">ACTIVE INTEGRATION POINTS:</span>
              <ul className="list-disc list-inside mt-1 space-y-0.5">
                {telemetry.integration_points.map((pt, i) => (
                  <li key={i}>{pt}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
