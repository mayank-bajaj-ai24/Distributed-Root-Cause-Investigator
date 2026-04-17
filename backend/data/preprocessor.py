"""
Data preprocessor — normalization, windowing, and feature extraction
for feeding into ML models.
"""

import numpy as np
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


# ── Metric Preprocessing ─────────────────────────────────────────

def normalize_metrics(metrics_dict, fit=True, stats=None):
    """
    Normalize metric time-series per service using z-score normalization.

    Args:
        metrics_dict: dict mapping service -> list of metric dicts
        fit: if True, compute mean/std from data; if False, use provided stats
        stats: pre-computed {service: {metric: (mean, std)}}

    Returns:
        normalized: dict mapping service -> np.array [T, num_features]
        stats: computed statistics for later use
    """
    feature_names = ["cpu_percent", "memory_percent", "latency_ms", "error_rate", "connections"]
    normalized = {}
    computed_stats = stats or {}

    for service, records in metrics_dict.items():
        # Extract feature matrix
        data = np.array([
            [r[f] for f in feature_names]
            for r in records
        ], dtype=np.float32)

        if fit:
            mean = data.mean(axis=0)
            std = data.std(axis=0)
            std[std < 1e-8] = 1.0  # avoid division by zero
            computed_stats[service] = {"mean": mean.tolist(), "std": std.tolist()}
        else:
            s = computed_stats[service]
            mean = np.array(s["mean"], dtype=np.float32)
            std = np.array(s["std"], dtype=np.float32)

        normalized[service] = (data - mean) / std

    return normalized, computed_stats


def create_sliding_windows(data, window_size=None, stride=1):
    """
    Create sliding windows from time-series data.

    Args:
        data: np.array [T, features]
        window_size: window length (default from config)
        stride: step between windows

    Returns:
        windows: np.array [num_windows, window_size, features]
    """
    window_size = window_size or config.METRIC_WINDOW_SIZE
    T, F = data.shape

    if T < window_size:
        # Pad with zeros if too short
        padded = np.zeros((window_size, F), dtype=np.float32)
        padded[:T] = data
        return padded.reshape(1, window_size, F)

    num_windows = (T - window_size) // stride + 1
    windows = np.zeros((num_windows, window_size, F), dtype=np.float32)

    for i in range(num_windows):
        start = i * stride
        windows[i] = data[start:start + window_size]

    return windows


# ── Log Preprocessing ────────────────────────────────────────────

def extract_log_features(logs, service=None):
    """
    Extract log entries, optionally filtered by service.

    Returns list of dicts with 'text', 'level', 'service', 'timestamp'.
    """
    filtered = logs if service is None else [l for l in logs if l["service"] == service]

    result = []
    for log in filtered:
        result.append({
            "text": log["message"],
            "level": log["level"],
            "service": log["service"],
            "timestamp": log["timestamp"],
        })
    return result


def compute_log_level_counts(logs, services=None, window_seconds=60):
    """
    Compute log level counts per service per time window.

    Returns dict: service -> list of {window_start, INFO, WARN, ERROR, FATAL}
    """
    from datetime import datetime

    services = services or list({l["service"] for l in logs})
    counts = {s: {} for s in services}

    for log in logs:
        service = log["service"]
        if service not in counts:
            continue
        # Round timestamp to window
        ts = datetime.fromisoformat(log["timestamp"])
        window_key = ts.replace(second=(ts.second // window_seconds) * window_seconds, microsecond=0).isoformat()

        if window_key not in counts[service]:
            counts[service][window_key] = {"INFO": 0, "DEBUG": 0, "WARN": 0, "ERROR": 0, "FATAL": 0}

        level = log["level"]
        if level in counts[service][window_key]:
            counts[service][window_key][level] += 1

    # Convert to lists
    result = {}
    for service in services:
        result[service] = [
            {"window_start": k, **v}
            for k, v in sorted(counts[service].items())
        ]
    return result


def label_logs_for_training(logs, scenario_info=None):
    """
    Label logs for supervised classification.
    Categories: 0=normal, 1=warning, 2=error, 3=anomaly

    If scenario_info is provided, ERROR/FATAL logs from affected services
    during the failure window are labeled as 'anomaly' (3) instead of 'error' (2).
    """
    labeled = []
    for log in logs:
        level = log["level"]

        if level in ("INFO", "DEBUG"):
            label = 0  # normal
        elif level == "WARN":
            label = 1  # warning
        elif level in ("ERROR", "FATAL"):
            # Check if this is within a failure scenario window
            if scenario_info and _is_in_failure_window(log, scenario_info):
                label = 3  # anomaly
            else:
                label = 2  # error
        else:
            label = 0

        labeled.append({
            "text": log["message"],
            "label": label,
            "service": log["service"],
            "level": level,
        })
    return labeled


def _is_in_failure_window(log, scenario_info):
    """Check if a log entry falls within the failure scenario window."""
    from datetime import datetime

    if log["service"] not in scenario_info.get("affected_services", []):
        return False

    base_time = datetime(2025, 6, 15, 10, 0, 0)
    log_time = datetime.fromisoformat(log["timestamp"])
    elapsed = (log_time - base_time).total_seconds()

    start = scenario_info.get("start_time", 0)
    duration = scenario_info.get("duration", 0)

    return start <= elapsed <= start + duration


def prepare_training_data(dataset):
    """
    Prepare complete training data from a generated dataset.

    Returns:
        metric_windows: dict service -> np.array [N, window_size, features]
        labeled_logs: list of {text, label, service}
        metric_stats: normalization statistics
    """
    # Metrics
    normalized, stats = normalize_metrics(dataset["metrics"])
    windows = {}
    for service, data in normalized.items():
        windows[service] = create_sliding_windows(data)

    # Logs
    labeled = label_logs_for_training(dataset["logs"], dataset.get("scenario_info"))

    return windows, labeled, stats
