"""
Root Cause Engine — Multi-signal fusion + automated explanation generator.

Fuses three signal types:
1. Log Signal: anomalous log clusters per service
2. Metric Signal: LSTM autoencoder + statistical ensemble scores
3. Graph Signal: PageRank-based root cause scores

Generates human-readable failure chain explanations.
"""

import os
import sys
import json
import numpy as np
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


class RootCauseEngine:
    """
    Multi-signal fusion engine for root cause analysis.

    Combines evidence from log analysis, metric anomaly detection,
    and graph-based propagation analysis to identify and explain
    the root cause of system failures.
    """

    def __init__(self, w_log=None, w_metric=None, w_graph=None):
        self.w_log = w_log or config.FUSION_WEIGHT_LOG
        self.w_metric = w_metric or config.FUSION_WEIGHT_METRIC
        self.w_graph = w_graph or config.FUSION_WEIGHT_GRAPH

    def analyze(self, log_signals, metric_signals, graph_signals):
        """
        Run full root cause analysis by fusing all signal types.

        Args:
            log_signals: dict service -> {
                'anomaly_score': float,
                'error_count': int,
                'anomalous_logs': list of log entries,
                'log_class_distribution': {class: count}
            }
            metric_signals: dict service -> {
                'anomaly_score': float,
                'is_anomaly': bool,
                'metric_details': {metric_name: {value, baseline, deviation}}
            }
            graph_signals: list of {
                'service': str,
                'rca_score': float,
                'pagerank': float,
                'upstream_ratio': float,
                'temporal_priority': float,
                'is_source_node': bool
            }

        Returns:
            RCA result dict with ranked services and explanation
        """
        all_services = set()
        all_services.update(log_signals.keys())
        all_services.update(metric_signals.keys())
        for gs in graph_signals:
            all_services.add(gs["service"])

        # Build graph signal lookup
        graph_lookup = {gs["service"]: gs for gs in graph_signals}

        # Compute fused scores
        service_scores = {}
        for service in all_services:
            log_score = log_signals.get(service, {}).get("anomaly_score", 0.0)
            metric_score = metric_signals.get(service, {}).get("anomaly_score", 0.0)
            graph_score = graph_lookup.get(service, {}).get("rca_score", 0.0)

            # Weighted fusion
            fused = (self.w_log * log_score +
                     self.w_metric * metric_score +
                     self.w_graph * graph_score)

            service_scores[service] = {
                "service": service,
                "fused_score": fused,
                "log_score": log_score,
                "metric_score": metric_score,
                "graph_score": graph_score,
                "is_anomaly": fused > 0.3,  # threshold for reporting
                "log_details": log_signals.get(service, {}),
                "metric_details": metric_signals.get(service, {}),
                "graph_details": graph_lookup.get(service, {}),
            }

        # Rank by fused score
        ranked = sorted(service_scores.values(), key=lambda x: x["fused_score"], reverse=True)

        # Identify root cause (highest scoring)
        root_cause = ranked[0] if ranked and ranked[0]["fused_score"] > 0.3 else None

        # Generate explanation
        explanation = self._generate_explanation(root_cause, ranked)

        return {
            "root_cause": root_cause,
            "ranked_services": ranked,
            "explanation": explanation,
            "timestamp": datetime.now().isoformat(),
            "num_anomalous": sum(1 for s in ranked if s["is_anomaly"]),
        }

    def _generate_explanation(self, root_cause, ranked_services):
        """
        Generate human-readable failure chain explanation.

        Format:
            ROOT CAUSE: Service — Issue Detected
            ├── Evidence: ...
            ├── Impact: Downstream Service — Effect
            │   └── Evidence: ...
            └── Impact: ...
        """
        if not root_cause:
            return {
                "summary": "No significant anomalies detected. All services operating normally.",
                "chain": [],
                "text": "System healthy — no root cause identified.",
            }

        # Root cause info
        rc_service = root_cause["service"]
        rc_issue = self._infer_issue(root_cause)

        chain = {
            "root_cause": {
                "service": rc_service,
                "issue": rc_issue,
                "confidence": min(1.0, root_cause["fused_score"]),
                "evidence": self._collect_evidence(root_cause),
            },
            "impacts": [],
        }

        # Find impacted services
        for service_info in ranked_services[1:]:
            if service_info["fused_score"] > 0.15:
                impact = {
                    "service": service_info["service"],
                    "effect": self._infer_effect(service_info),
                    "severity": self._severity_label(service_info["fused_score"]),
                    "evidence": self._collect_evidence(service_info),
                }
                chain["impacts"].append(impact)

        # Build text explanation
        text = self._build_text_explanation(chain)

        return {
            "summary": f"Root cause identified: {rc_service} — {rc_issue}",
            "chain": chain,
            "text": text,
        }

    def _infer_issue(self, service_info):
        """Infer the primary issue type from signal details."""
        metric_details = service_info.get("metric_details", {}).get("metric_details", {})

        if metric_details:
            # Check specific metric deviations
            mem = metric_details.get("memory_percent", {})
            cpu = metric_details.get("cpu_percent", {})
            conn = metric_details.get("connections", {})
            lat = metric_details.get("latency_ms", {})
            err = metric_details.get("error_rate", {})

            if mem.get("deviation", 0) > 3:
                return "Memory Leak Detected"
            if conn.get("deviation", 0) > 3:
                return "Connection Pool Exhaustion"
            if cpu.get("deviation", 0) > 3:
                return "CPU Spike Detected"
            if err.get("deviation", 0) > 3:
                return "High Error Rate"
            if lat.get("deviation", 0) > 3:
                return "Latency Spike Detected"

        # Fall back to log-based inference
        log_details = service_info.get("log_details", {})
        anomalous_logs = log_details.get("anomalous_logs", [])
        for log in anomalous_logs[:5]:
            msg = log.get("message", "").lower()
            if "memory" in msg or "heap" in msg or "gc" in msg:
                return "Memory Leak Detected"
            if "connection" in msg and ("pool" in msg or "exhaust" in msg):
                return "Connection Pool Exhaustion"
            if "timeout" in msg:
                return "Service Timeout"
            if "network" in msg or "unreachable" in msg:
                return "Network Partition"
            if "cpu" in msg:
                return "CPU Spike Detected"

        return "Anomaly Detected"

    def _infer_effect(self, service_info):
        """Infer the downstream effect on a service."""
        metric_details = service_info.get("metric_details", {}).get("metric_details", {})

        effects = []
        if metric_details:
            lat = metric_details.get("latency_ms", {})
            err = metric_details.get("error_rate", {})

            if lat.get("deviation", 0) > 2:
                value = lat.get("value", 0)
                baseline = lat.get("baseline", 0)
                if baseline > 0:
                    pct_increase = ((value - baseline) / baseline) * 100
                    effects.append(f"Latency increased {pct_increase:.0f}%")

            if err.get("deviation", 0) > 2:
                value = err.get("value", 0)
                effects.append(f"Error rate: {value:.1%}")

        if not effects:
            effects.append("Performance degradation detected")

        return "; ".join(effects)

    def _severity_label(self, score):
        """Convert fused score to severity label."""
        if score > 0.7:
            return "CRITICAL"
        if score > 0.5:
            return "HIGH"
        if score > 0.3:
            return "MEDIUM"
        return "LOW"

    def _collect_evidence(self, service_info):
        """Collect evidence items for a service."""
        evidence = []

        # Metric evidence
        metric_details = service_info.get("metric_details", {}).get("metric_details", {})
        for metric_name, details in metric_details.items():
            if details.get("deviation", 0) > 2:
                evidence.append({
                    "type": "metric",
                    "metric": metric_name,
                    "value": details.get("value", 0),
                    "baseline": details.get("baseline", 0),
                    "deviation": details.get("deviation", 0),
                    "description": f"{metric_name}: {details.get('value', 0):.2f} "
                                   f"(baseline: {details.get('baseline', 0):.2f}, "
                                   f"{details.get('deviation', 0):.1f}σ deviation)"
                })

        # Log evidence
        log_details = service_info.get("log_details", {})
        error_count = log_details.get("error_count", 0)
        if error_count > 0:
            evidence.append({
                "type": "log",
                "error_count": error_count,
                "description": f"{error_count} ERROR/FATAL log entries detected",
            })

        # Sample anomalous logs
        anomalous_logs = log_details.get("anomalous_logs", [])
        for log in anomalous_logs[:3]:
            evidence.append({
                "type": "log_sample",
                "level": log.get("level", "ERROR"),
                "message": log.get("message", ""),
                "description": f'{log.get("level", "ERROR")}: "{log.get("message", "")}"',
            })

        # Graph evidence
        graph_details = service_info.get("graph_details", {})
        if graph_details.get("is_source_node"):
            evidence.append({
                "type": "graph",
                "description": "Identified as source node — no anomalous upstream dependencies",
            })
        if graph_details.get("upstream_ratio", 0) > 0.5:
            evidence.append({
                "type": "graph",
                "description": f"Upstream ratio: {graph_details['upstream_ratio']:.0%} of downstream "
                               f"services also anomalous — failure propagation confirmed",
            })

        return evidence

    def _build_text_explanation(self, chain):
        """Build a tree-formatted text explanation."""
        lines = []
        rc = chain["root_cause"]
        lines.append(f"ROOT CAUSE: {rc['service']} — {rc['issue']} "
                      f"(confidence: {rc['confidence']:.0%})")

        for ev in rc["evidence"]:
            lines.append(f"├── Evidence: {ev['description']}")

        for i, impact in enumerate(chain["impacts"]):
            is_last = i == len(chain["impacts"]) - 1
            prefix = "└──" if is_last else "├──"
            lines.append(f"{prefix} Impact: {impact['service']} [{impact['severity']}] — {impact['effect']}")

            ev_prefix = "    " if is_last else "│   "
            for ev in impact["evidence"][:2]:
                lines.append(f"{ev_prefix}└── Evidence: {ev['description']}")

        return "\n".join(lines)


def build_log_signals(logs, log_predictions=None, services=None):
    """
    Build log signals from raw logs and optional model predictions.

    Args:
        logs: list of log entries
        log_predictions: optional list of {text, predicted_class, service}
        services: list of services to analyze

    Returns:
        dict service -> log signal dict
    """
    services = services or config.SERVICES
    signals = {}

    for service in services:
        service_logs = [l for l in logs if l["service"] == service]
        error_logs = [l for l in service_logs if l["level"] in ("ERROR", "FATAL")]

        total = len(service_logs)
        errors = len(error_logs)

        # Anomaly score based on error ratio
        error_ratio = errors / max(total, 1)
        anomaly_score = min(1.0, error_ratio * 10)  # scale up for sensitivity

        # If we have model predictions, use them
        anomalous_from_model = []
        if log_predictions:
            service_preds = [p for p in log_predictions if p["service"] == service]
            anomalous_from_model = [p for p in service_preds if p.get("predicted_class") == 3]
            if anomalous_from_model:
                anomaly_score = max(anomaly_score, len(anomalous_from_model) / max(len(service_preds), 1) * 5)
                anomaly_score = min(1.0, anomaly_score)

        signals[service] = {
            "anomaly_score": anomaly_score,
            "error_count": errors,
            "total_logs": total,
            "anomalous_logs": error_logs[-10:],  # last 10 error logs
            "log_class_distribution": _count_levels(service_logs),
        }

    return signals


def build_metric_signals(metrics, anomaly_results=None, stats=None):
    """
    Build metric signals from raw metrics and anomaly detection results.

    Args:
        metrics: dict service -> list of metric dicts
        anomaly_results: optional dict service -> {anomaly_scores, is_anomaly}
        stats: normalization stats {service: {mean, std}}

    Returns:
        dict service -> metric signal dict
    """
    signals = {}

    for service, records in metrics.items():
        if not records:
            continue

        # Compute recent metric statistics (last 60 seconds)
        recent = records[-60:] if len(records) >= 60 else records
        overall = records[:max(len(records) - 60, 60)]  # baseline from earlier data

        metric_details = {}
        feature_names = ["cpu_percent", "memory_percent", "latency_ms", "error_rate", "connections"]

        for fname in feature_names:
            recent_values = [r[fname] for r in recent]
            baseline_values = [r[fname] for r in overall] if overall else recent_values

            current_val = np.mean(recent_values[-10:]) if recent_values else 0
            baseline_mean = np.mean(baseline_values) if baseline_values else 0
            baseline_std = np.std(baseline_values) if baseline_values else 1
            baseline_std = max(baseline_std, 1e-8)

            deviation = abs(current_val - baseline_mean) / baseline_std

            metric_details[fname] = {
                "value": float(current_val),
                "baseline": float(baseline_mean),
                "std": float(baseline_std),
                "deviation": float(deviation),
            }

        # Overall anomaly score: max deviation across metrics
        max_deviation = max(d["deviation"] for d in metric_details.values())
        anomaly_score = min(1.0, max_deviation / 5.0)  # normalize: 5σ → score 1.0

        # Override with model results if available
        if anomaly_results and service in anomaly_results:
            model_result = anomaly_results[service]
            model_score = float(np.mean(model_result.get("anomaly_scores", [0])))
            # Blend model and statistical scores
            anomaly_score = 0.6 * model_score + 0.4 * anomaly_score

        signals[service] = {
            "anomaly_score": anomaly_score,
            "is_anomaly": anomaly_score > 0.3,
            "metric_details": metric_details,
        }

    return signals


def _count_levels(logs):
    """Count log levels."""
    counts = {"INFO": 0, "DEBUG": 0, "WARN": 0, "ERROR": 0, "FATAL": 0}
    for log in logs:
        level = log.get("level", "INFO")
        if level in counts:
            counts[level] += 1
    return counts
