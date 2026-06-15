from datetime import datetime

class AnomalyDetector:

    def detect_travel(self, order_dates: list[datetime]) -> dict:
        """Gaps of 5+ days between consecutive orders = likely travel."""
        if len(order_dates) < 2:
            return {"detected": False, "type": "travel"}
        
        # Sort dates to ensure chronological order
        sorted_dates = sorted(order_dates)
        gaps = []
        
        for i in range(1, len(sorted_dates)):
            gap = (sorted_dates[i] - sorted_dates[i-1]).days
            if gap >= 5:
                gaps.append({"start": sorted_dates[i-1], "end": sorted_dates[i], "duration_days": gap})
                
        if not gaps:
            return {"detected": False, "type": "travel"}
            
        return {
            "detected": True, 
            "type": "travel", 
            "gaps": gaps,
            "total_travel_days": sum(g["duration_days"] for g in gaps)
        }

    def detect_guest_visit(self, purchase_history: list, baseline_qty: float) -> dict:
        """Single order quantity >2.5x baseline = guests visited. Exclude from model."""
        spikes = []
        for p in purchase_history:
            ratio = p["standard_quantity"] / max(baseline_qty, 0.001)
            if ratio >= 2.5:
                spikes.append({
                    "date": p["placed_at"], 
                    "quantity": p["standard_quantity"],
                    "spike_factor": round(ratio, 1)
                })
                
        if spikes:
            return {
                "detected": True, 
                "type": "guest_visit",
                "events": spikes, 
                "action": "exclude_from_model"
            }
            
        return {"detected": False, "type": "guest_visit"}

    def detect_dietary_change(self, category_monthly_counts: dict) -> dict:
        """Category purchase count drops >60% in most recent month vs prior average."""
        changes = []
        for cat, counts in category_monthly_counts.items():
            if len(counts) < 3:
                continue
                
            prior_avg = sum(counts[:-1]) / len(counts[:-1])
            recent = counts[-1]
            
            if prior_avg == 0:
                continue
                
            drop_pct = ((prior_avg - recent) / prior_avg) * 100
            
            if drop_pct > 60:
                changes.append({
                    "category": cat, 
                    "drop_pct": round(drop_pct, 1),
                    "prior_avg": round(prior_avg, 1), 
                    "recent": recent
                })
                
        return {
            "detected": bool(changes), 
            "type": "dietary_change",
            "changes": changes, 
            "action": "confirm_with_user" if changes else None
        }
