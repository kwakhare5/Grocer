"""
Confidence Scorer — Task 2.2
Scores how reliable a consumption prediction is, based on two signals:
  1. Regularity (0–1): How consistent is the purchase interval? Low std-dev = high regularity.
  2. Data Score  (0–1): How many data points do we have? More orders = higher confidence.

Formula: confidence = (regularity × 0.6) + (data_score × 0.4)
Range:   0.0 (no data) → 1.0 (perfect clock-like buyer with 20+ orders)
"""

import pandas as pd


class ConfidenceScorer:

    # Below this cycle std-dev (in days), a purchase is considered highly regular.
    # 14 days = 2 weeks; anything tighter is very predictable.
    REGULARITY_NORMALISER = 14.0

    # We consider 20 data points "fully data-rich". Fewer scales linearly.
    DATA_RICH_THRESHOLD = 20

    def score(self, purchase_dates: list, data_points: int) -> float:
        """
        Calculate prediction confidence for a single item.

        Args:
            purchase_dates: List of datetime/string values for each purchase event.
            data_points:    Number of orders used (must match len(purchase_dates)).

        Returns:
            Float in [0.0, 1.0], rounded to 3 decimal places.
            Returns 0.0 if fewer than 3 data points (not enough to compute).
            Returns 0.3 if there is only 1 interval (cannot compute std-dev yet).
        """
        if data_points < 3:
            # Why: With < 3 orders we can't reliably detect a pattern.
            return 0.0

        dates = pd.to_datetime(sorted(purchase_dates))
        diffs = dates.diff().dt.days.dropna()

        if len(diffs) < 2:
            # Only one interval — not enough to measure regularity yet.
            # Give a minimal non-zero score so the item is still tracked.
            return 0.3

        std = float(diffs.std())

        # regularity: 0 when std >= 14 days, 1 when std == 0 (perfectly regular)
        regularity = max(0.0, 1.0 - (std / self.REGULARITY_NORMALISER))

        # data_score: scales 0→1 as we get more orders, caps at 1.0 at 20 orders
        data_score = min(1.0, data_points / self.DATA_RICH_THRESHOLD)

        confidence = (regularity * 0.6) + (data_score * 0.4)
        return round(confidence, 3)

    def human_readable(self, score: float) -> str:
        """
        Convert a numeric confidence score into a display-friendly label.

        Used in the dashboard and WhatsApp messages so users understand
        why the AI is (or isn't) alerting them about an item.
        """
        if score >= 0.80:
            return "Very high"
        if score >= 0.65:
            return "High"
        if score >= 0.50:
            return "Moderate"
        if score >= 0.30:
            return "Low"
        return "Insufficient data"

    def should_alert(self, score: float, min_confidence: float = 0.50) -> bool:
        """
        Gate for whether to include an item in a restock alert.
        We only alert users on items we're reasonably confident about.
        Default threshold matches settings.MIN_CONFIDENCE = 0.50.
        """
        return score >= min_confidence
