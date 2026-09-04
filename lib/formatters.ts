/**
 * Currency, time, and number formatters for GROCER v2
 * Adheres to tabular monospace figures with Swiss Logistics styling.
 */

export function formatINR(amount: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatNumber(num: number, decimals: number = 0): string {
  return new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(num);
}

export function formatHours(hours: number): string {
  if (hours <= 0) return "Immediate";
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 24) return `~${Math.round(hours)}h`;
  const days = Math.floor(hours / 24);
  const remHours = Math.round(hours % 24);
  return remHours > 0 ? `${days}d ${remHours}h` : `${days}d`;
}

export function formatPercentage(pct: number): string {
  return `${Math.round(pct * 100)}%`;
}

export function formatTimeUTC(date: Date | string): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return d.toISOString().substring(11, 19);
}

export function timeAgo(dateStr: string | null | undefined): string {
  if (!dateStr) return "N/A";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return "N/A";

  const diff = Math.floor((Date.now() - d.getTime()) / (1000 * 60 * 60 * 24));
  if (diff <= 0) return "Today";
  if (diff === 1) return "Yesterday";
  if (diff < 7) return `${diff} days ago`;
  if (diff < 14) return "Last week";
  if (diff < 30) return `${Math.floor(diff / 7)} weeks ago`;
  return d.toLocaleDateString("en-US", { day: "numeric", month: "short", year: "numeric" });
}
