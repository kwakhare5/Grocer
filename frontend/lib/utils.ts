import { APIPrediction } from "./api";

export interface PredictionItem {
  id: string;
  name: string;
  category: string;
  days: number;
  rawDays: number;
  conf: number;
  avg: string;
  cycle: string;
  depletes: string;
  lastBuy: string;
  fillPct: number;
}

export const FALLBACK_PREDICTIONS: PredictionItem[] = [
  { id: "INS_001", name: "Amul Taza Milk 1L",          category: "Dairy",    days: 1,  rawDays: 1,  conf: 76, avg: "1.1 L/day",   cycle: "2.1 days",  depletes: "Tomorrow",        lastBuy: "2 days ago", fillPct: 30 },
  { id: "INS_003", name: "Fortune Sunflower Oil 1L",   category: "Oils",     days: 2,  rawDays: 2,  conf: 87, avg: "68 ml/day",   cycle: "14.7 days", depletes: "In 2 days",       lastBuy: "12 days ago", fillPct: 14 },
  { id: "INS_005", name: "Nandini Eggs (Pack of 12)",  category: "Protein",  days: 4,  rawDays: 4,  conf: 88, avg: "2.3 pcs/day", cycle: "6.2 days",  depletes: "In 4 days",       lastBuy: "2 days ago", fillPct: 65 },
  { id: "INS_002", name: "Aashirvaad Atta 5kg",        category: "Staples",  days: 12, rawDays: 12, conf: 68, avg: "280 g/day",   cycle: "17 days",   depletes: "In 12 days",      lastBuy: "5 days ago", fillPct: 71 },
  { id: "INS_004", name: "India Gate Basmati Rice 5kg",category: "Staples",  days: 19, rawDays: 19, conf: 71, avg: "200 g/day",   cycle: "25 days",   depletes: "In 19 days",      lastBuy: "6 days ago", fillPct: 76 },
];

export function timeAgo(dateStr: string) {
  const d = new Date(dateStr);
  const diff = Math.floor((Date.now() - d.getTime()) / 1000 / 60 / 60 / 24);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  if (diff < 7)  return `${diff} days ago`;
  if (diff < 14) return "Last week";
  if (diff < 30) return `${Math.floor(diff / 7)} weeks ago`;
  return d.toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" });
}

export function transformPredictionsData(predictions: APIPrediction[] | undefined): PredictionItem[] {
  if (!predictions || predictions.length === 0) {
    return FALLBACK_PREDICTIONS;
  }

  return predictions
    .map((p) => {
      const rawDays = p.days_remaining !== null ? p.days_remaining : 10;
      const daysLeft = Math.round(rawDays);
      const fillPct = p.stock_fill_percent !== undefined ? Math.round(p.stock_fill_percent) : 100;
      return {
        id: p.item_id,
        name: p.item_name,
        category: p.category,
        days: daysLeft,
        rawDays,
        conf: Math.round((p.confidence_score || 0.5) * 100),
        avg: `${p.avg_daily_consumption.toFixed(2)} /day`,
        cycle: `${p.consumption_cycle_days || 7} days`,
        depletes: daysLeft === 0 ? "Today" : daysLeft === 1 ? "Tomorrow" : `In ${daysLeft} days`,
        lastBuy: p.last_purchase_date ? timeAgo(p.last_purchase_date) : "Unknown",
        fillPct,
      };
    })
    .sort((a, b) => a.rawDays - b.rawDays);
}
