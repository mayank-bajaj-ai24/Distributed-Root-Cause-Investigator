"""
Predictive Failure Engine — Predicts failures before they happen.

Algorithms:
1. Linear Regression Trend Analysis — slope & acceleration of metric series
2. Time-to-Threshold Extrapolation — when will this metric hit critical?
3. Multi-Metric Risk Assessment — combines all metric trends per service

Zero external APIs — pure numpy linear algebra.
"""

import numpy as np
from datetime import datetime, timedelta

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


# Critical thresholds for each metric
FAILURE_THRESHOLDS = {
    "memory_percent": {"critical": 90.0, "warning": 80.0, "label": "OOM Risk"},
    "cpu_percent": {"critical": 92.0, "warning": 80.0, "label": "CPU Saturation"},
    "connections": {"critical": 45.0, "warning": 35.0, "label": "Connection Pool Exhaustion"},
    "error_rate": {"critical": 0.10, "warning": 0.05, "label": "Service Degradation"},
    "latency_ms": {"critical": 2000.0, "warning": 1000.0, "label": "Timeout Risk"},
}


class PredictiveFailureEngine:
    """
    Predicts service failures 2-5 minutes before they occur by analyzing
    metric trends and extrapolating time-to-threshold.

    Math:
        1. Fit linear regression to recent metric window: y = mx + b
        2. Compute acceleration: d²y/dt² (is the trend accelerating?)
        3. Extrapolate: at current rate, when does y cross threshold?
        4. Risk score = f(slope, acceleration, proximity_to_threshold)
    """

    def __init__(self, trend_window=120, min_slope_threshold=0.01):
        self.trend_window = trend_window  # seconds of history to analyze
        self.min_slope_threshold = min_slope_threshold
        self.prediction_horizon = 300  # predict up to 5 minutes ahead

    def predict(self, metrics):
        """
        Analyze all services and generate failure predictions.

        Args:
            metrics: dict service -> list of metric dicts (time-series)

        Returns:
            dict with predictions list, num_warnings, earliest_failure
        """
        predictions = []

        for service, records in metrics.items():
            if not records or len(records) < 30:
                continue

            service_predictions = self._analyze_service_trends(service, records)
            predictions.extend(service_predictions)

        # Sort by urgency (earliest failure first)
        predictions.sort(key=lambda p: p.get("predicted_failure_in", float("inf")))

        # Compute summary
        num_warnings = len(predictions)
        earliest = predictions[0]["predicted_failure_in"] if predictions else None

        return {
            "predictions": predictions,
            "num_warnings": num_warnings,
            "earliest_failure": earliest,
            "prediction_horizon_seconds": self.prediction_horizon,
        }

    def _analyze_service_trends(self, service, records):
        """Analyze all metric trends for a single service."""
        predictions = []

        # Use recent window
        window = records[-self.trend_window:] if len(records) > self.trend_window else records

        for metric_name, thresholds in FAILURE_THRESHOLDS.items():
            values = np.array([r.get(metric_name, 0) for r in window], dtype=np.float64)

            if len(values) < 10:
                continue

            # Compute trend
            trend = self._compute_trend(values)

            if trend is None:
                continue

            # Check if trending toward failure
            prediction = self._check_threshold_breach(
                service, metric_name, values, trend, thresholds, records
            )

            if prediction:
                predictions.append(prediction)

        return predictions

    def _compute_trend(self, values):
        """
        Compute linear trend and acceleration.

        Returns dict with slope, intercept, acceleration, r_squared, or None if flat.
        """
        n = len(values)
        t = np.arange(n, dtype=np.float64)

        # Linear regression: y = slope * t + intercept
        # Using least squares: slope = (n*Σxy - Σx*Σy) / (n*Σx² - (Σx)²)
        sum_t = t.sum()
        sum_v = values.sum()
        sum_tv = (t * values).sum()
        sum_t2 = (t * t).sum()

        denom = n * sum_t2 - sum_t * sum_t
        if abs(denom) < 1e-10:
            return None

        slope = (n * sum_tv - sum_t * sum_v) / denom
        intercept = (sum_v - slope * sum_t) / n

        # R-squared
        predicted = slope * t + intercept
        ss_res = ((values - predicted) ** 2).sum()
        ss_tot = ((values - values.mean()) ** 2).sum()
        r_squared = 1 - (ss_res / max(ss_tot, 1e-10))

        # Acceleration: compare slope of first half vs second half
        mid = n // 2
        if mid >= 5:
            t1 = np.arange(mid, dtype=np.float64)
            v1 = values[:mid]
            slope1 = np.polyfit(t1, v1, 1)[0] if len(t1) > 1 else 0

            t2 = np.arange(n - mid, dtype=np.float64)
            v2 = values[mid:]
            slope2 = np.polyfit(t2, v2, 1)[0] if len(t2) > 1 else 0

            acceleration = slope2 - slope1
        else:
            acceleration = 0.0

        return {
            "slope": float(slope),
            "intercept": float(intercept),
            "acceleration": float(acceleration),
            "r_squared": float(r_squared),
            "current_value": float(values[-1]),
            "mean_value": float(values.mean()),
        }

    def _check_threshold_breach(self, service, metric_name, values, trend,
                                 thresholds, all_records):
        """
        Check if the current trend will breach a critical threshold
        within the prediction horizon.
        """
        slope = trend["slope"]
        current = trend["current_value"]
        critical = thresholds["critical"]
        warning = thresholds["warning"]
        accel = trend["acceleration"]

        # Only predict if trending TOWARD the threshold
        if slope < self.min_slope_threshold:
            return None  # flat or decreasing — no risk

        # Already past warning?
        already_warning = current >= warning
        already_critical = current >= critical

        if already_critical:
            return None  # already failed — detection, not prediction

        # Time to critical threshold
        remaining = critical - current
        if remaining <= 0:
            return None

        # Simple linear extrapolation
        time_to_critical = remaining / slope

        # Adjust for acceleration (quadratic extrapolation)
        if accel > 0:
            # Quadratic: t = (-slope + sqrt(slope² + 2*accel*remaining)) / accel
            discriminant = slope * slope + 2 * accel * remaining
            if discriminant > 0:
                time_to_critical = (-slope + np.sqrt(discriminant)) / max(accel, 1e-8)
                time_to_critical = max(1, time_to_critical)

        # Only report if within prediction horizon
        if time_to_critical > self.prediction_horizon:
            return None

        # Compute severity
        if time_to_critical < 60:
            severity = "CRITICAL"
        elif time_to_critical < 180:
            severity = "HIGH"
        elif time_to_critical < 300:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        # Compute risk score (0-1)
        time_factor = 1.0 - min(time_to_critical / self.prediction_horizon, 1.0)
        proximity_factor = current / critical
        trend_factor = min(abs(slope) / (critical * 0.01), 1.0)
        risk_score = 0.4 * time_factor + 0.35 * proximity_factor + 0.25 * trend_factor

        # Generate human-readable message
        minutes = int(time_to_critical // 60)
        seconds = int(time_to_critical % 60)
        if minutes > 0:
            eta_str = f"~{minutes}m {seconds}s"
        else:
            eta_str = f"~{seconds}s"

        message = (
            f"{thresholds['label']}: {metric_name} likely to exceed "
            f"{critical} in {eta_str} "
            f"(current: {current:.1f}, rate: +{slope:.3f}/sec)"
        )

        # Predicted failure time
        last_timestamp = all_records[-1].get("timestamp", "")
        try:
            last_time = datetime.fromisoformat(last_timestamp)
            predicted_time = (last_time + timedelta(seconds=time_to_critical)).isoformat()
        except (ValueError, TypeError):
            predicted_time = None

        return {
            "service": service,
            "metric": metric_name,
            "current_value": round(current, 2),
            "threshold": critical,
            "trend": "accelerating" if accel > self.min_slope_threshold else "increasing",
            "slope": round(slope, 4),
            "acceleration": round(accel, 4),
            "r_squared": round(trend["r_squared"], 3),
            "predicted_failure_in": round(time_to_critical, 1),
            "predicted_failure_time": predicted_time,
            "severity": severity,
            "risk_score": round(risk_score, 3),
            "message": message,
        }
