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
