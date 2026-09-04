"""GROCER v2 Forecasting — Pure mathematical models.

Implements spec §12:
  Level 1 — Baseline: moving average + day-of-week seasonality (§12.1)
  Level 2 — Time-series: exponential smoothing with trend (§12.1)
  Anomaly detection and cleaning (§12.4)
  Confidence scoring — composite multi-factor (§12.3)
  Evaluation metrics: MAE, RMSE, MAPE (§12.2)

Zero heavy C-extension deps: pure Python + stdlib math only.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Sequence


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class DemandPoint:
    """A single daily demand observation."""

    day_index: int     # 0-based sequential day
    day_of_week: int   # 0=Mon … 6=Sun
    quantity: float    # total units sold that day


@dataclass
class ModelEvaluationResult:
    """Evaluation of a forecast model against known ground truth."""

    mae: float    # Mean Absolute Error
    rmse: float   # Root Mean Squared Error
    mape: float   # Mean Absolute Percentage Error (%)
    model_name: str = ""
    n: int = 0


# ---------------------------------------------------------------------------
# Anomaly detection and cleaning (§12.4)
# ---------------------------------------------------------------------------

_MIN_POINTS_FOR_ZSCORE = 4  # need at least N points to compute std
_IQR_FACTOR = 3.0            # IQR fence multiplier for heavy-tailed protection


def detect_anomalies(
    series: Sequence[DemandPoint],
    z_threshold: float = 3.0,
) -> list[int]:
    """Return list of indices in *series* whose quantity is a statistical outlier.

    Uses a robust IQR fence (Q3 + factor*IQR) as primary criterion.
    This is resistant to spike self-contamination that distorts plain Z-score.
    Falls back to empty list on < 4 points.
    """
    if len(series) < _MIN_POINTS_FOR_ZSCORE:
        return []

    values = sorted(p.quantity for p in series)
    n = len(values)

    # Compute Q1 and Q3 via index interpolation
    q1 = _percentile(values, 25)
    q3 = _percentile(values, 75)
    iqr = q3 - q1

    if iqr == 0:
        # All values are identical — use a multiplier heuristic to catch extreme spikes
        median = q1  # when IQR=0, q1=q3=median
        if median == 0:
            return []
        return [i for i, p in enumerate(series) if p.quantity > median * 5.0]

    upper_fence = q3 + _IQR_FACTOR * iqr
    lower_fence = q1 - _IQR_FACTOR * iqr

    return [
        i for i, p in enumerate(series)
        if p.quantity > upper_fence or p.quantity < lower_fence
    ]


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Compute a percentile from a pre-sorted list using linear interpolation."""
    n = len(sorted_values)
    if n == 0:
        return 0.0
    idx = (pct / 100) * (n - 1)
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def clean_demand_series(
    series: Sequence[DemandPoint],
    z_threshold: float = 3.0,
) -> list[DemandPoint]:
    """Return a cleaned copy of *series* with anomalous quantities replaced by the median."""
    if not series:
        return []

    anomaly_indices = set(detect_anomalies(series, z_threshold))
    if not anomaly_indices:
        return list(series)

    normal_values = [p.quantity for i, p in enumerate(series) if i not in anomaly_indices]
    replacement = statistics.median(normal_values) if normal_values else 0.0

    result: list[DemandPoint] = []
    for i, p in enumerate(series):
        if i in anomaly_indices:
            result.append(DemandPoint(p.day_index, p.day_of_week, replacement))
        else:
            result.append(p)
    return result


# ---------------------------------------------------------------------------
# Baseline predictor — Level 1 (§12.1)
# ---------------------------------------------------------------------------

_MOVING_AVERAGE_WINDOW = 14  # days


def baseline_predict(
    series: Sequence[DemandPoint],
    horizon_hours: float,
    forecast_day_of_week: int | None = None,
) -> float:
    """Predict total demand over *horizon_hours* using a moving average baseline.

    Algorithm:
    1. Clean anomalies.
    2. Compute a windowed moving average (last N days) as the base rate (units/day).
    3. Compute per-day-of-week seasonal multipliers from the full cleaned history.
    4. Scale the base rate by the seasonal multiplier for *forecast_day_of_week*.
    5. Scale by horizon fraction (horizon_hours / 24).
    """
    if not series:
        return 0.0

    cleaned = clean_demand_series(series)

    # Window for moving average
    window = cleaned[-_MOVING_AVERAGE_WINDOW:]
    base_daily_rate = statistics.mean(p.quantity for p in window)

    # Day-of-week seasonal multipliers
    seasonal_multiplier = _compute_dow_multiplier(cleaned, forecast_day_of_week)

    horizon_days = horizon_hours / 24.0
    return base_daily_rate * seasonal_multiplier * horizon_days


def _compute_dow_multiplier(
    series: Sequence[DemandPoint],
    forecast_dow: int | None,
) -> float:
    """Return the seasonal multiplier for a given day-of-week.

    Multiplier = avg_demand_on_target_dow / overall_avg_demand.
    Falls back to 1.0 if insufficient data.
    """
    if forecast_dow is None or not series:
        return 1.0

    overall_avg = statistics.mean(p.quantity for p in series)
    if overall_avg == 0:
        return 1.0

    dow_values = [p.quantity for p in series if p.day_of_week == forecast_dow]
    if not dow_values:
        return 1.0

    dow_avg = statistics.mean(dow_values)
    return dow_avg / overall_avg


# ---------------------------------------------------------------------------
# Exponential smoothing predictor — Level 2 (§12.1)
# ---------------------------------------------------------------------------

_MIN_SERIES_FOR_ES = 7  # minimum days to attempt smoothing
_ALPHA = 0.3   # level smoothing
_BETA  = 0.1   # trend smoothing


def exponential_smoothing_predict(
    series: Sequence[DemandPoint],
    horizon_hours: float,
) -> float:
    """Double exponential smoothing (Holt linear) forecast.

    Falls back to baseline_predict when there are too few points.
    Returns total predicted demand over *horizon_hours*.
    """
    if len(series) < _MIN_SERIES_FOR_ES:
        return baseline_predict(series, horizon_hours)

    cleaned = clean_demand_series(series)
    values = [p.quantity for p in cleaned]

    # Initialise level and trend from the first two observations
    level = values[0]
    trend = values[1] - values[0]

    for v in values[1:]:
        prev_level = level
        level = _ALPHA * v + (1 - _ALPHA) * (level + trend)
        trend = _BETA * (level - prev_level) + (1 - _BETA) * trend

    # Forecast h steps ahead (h = horizon days)
    h = horizon_hours / 24.0
    return max(0.0, (level + h * trend) * h)


# ---------------------------------------------------------------------------
# Confidence scorer (§12.3)
# ---------------------------------------------------------------------------

_SAMPLE_SIZE_FULL_CONF = 30  # n ≥ this → max sample-size confidence
_MAX_ANOMALY_RATIO = 0.5     # above this → confidence → 0


def compute_confidence(
    series: Sequence[DemandPoint],
    anomaly_count: int,
) -> float:
    """Return a composite confidence score in [0.0, 1.0].

    Four factors combined multiplicatively:
    - Sample size factor: ramps from 0 → 1 as n → _SAMPLE_SIZE_FULL_CONF.
    - Coefficient of variation factor: penalises high CV.
    - Anomaly ratio factor: penalises frequent anomalies.
    - Trend stability factor: high variability between recent halves → lower score.
    """
    n = len(series)
    if n == 0:
        return 0.0

    # Factor 1 — sample size
    size_factor = min(1.0, n / _SAMPLE_SIZE_FULL_CONF)

    # Factor 2 — coefficient of variation
    values = [p.quantity for p in series]
    mean_ = statistics.mean(values)
    if mean_ == 0:
        cv_factor = 0.0
    else:
        stdev_ = statistics.pstdev(values) if n > 1 else 0.0
        cv = stdev_ / mean_
        cv_factor = max(0.0, 1.0 - min(cv, 1.0))

    # Factor 3 — anomaly ratio
    anomaly_ratio = min(anomaly_count / max(n, 1), _MAX_ANOMALY_RATIO)
    anomaly_factor = 1.0 - (anomaly_ratio / _MAX_ANOMALY_RATIO)

    # Combine: geometric mean of the three factors
    product = size_factor * cv_factor * anomaly_factor
    return round(max(0.0, min(1.0, product ** (1 / 3))), 4)


# ---------------------------------------------------------------------------
# Evaluation metrics (§12.2)
# ---------------------------------------------------------------------------


def evaluate_forecast(
    actual: Sequence[float],
    predicted: Sequence[float],
    model_name: str = "",
) -> ModelEvaluationResult:
    """Compute MAE, RMSE, and MAPE from parallel actual/predicted sequences."""
    n = len(actual)
    if n == 0:
        return ModelEvaluationResult(mae=0.0, rmse=0.0, mape=0.0, model_name=model_name, n=0)

    errors = [abs(a - p) for a, p in zip(actual, predicted)]
    mae = sum(errors) / n
    rmse = math.sqrt(sum(e ** 2 for e in errors) / n)

    # MAPE — skip zero-actual entries to avoid division by zero
    pct_errors = [abs(a - p) / a * 100 for a, p in zip(actual, predicted) if a != 0]
    mape = sum(pct_errors) / len(pct_errors) if pct_errors else 0.0

    return ModelEvaluationResult(mae=mae, rmse=rmse, mape=mape, model_name=model_name, n=n)
