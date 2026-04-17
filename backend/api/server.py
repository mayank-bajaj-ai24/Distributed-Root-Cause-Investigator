"""
Flask REST API server for the Distributed Root Cause Investigator.

Endpoints:
    GET  /api/services              — List all services and current status
    GET  /api/metrics/<service>     — Get metric time-series for a service
    GET  /api/logs/<service>        — Get recent logs for a service
    GET  /api/graph                 — Get service dependency graph
    POST /api/analyze               — Run full RCA pipeline
    GET  /api/anomalies             — Get detected anomalies across all services
    GET  /api/scenarios             — List available failure scenarios
    POST /api/scenarios/<id>/inject — Inject a failure scenario
"""

import os
import sys
import json
import traceback
import numpy as np
import torch

from flask import Flask, request, jsonify
from flask_cors import CORS

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from data.synthetic_generator import generate_dataset, save_dataset
from data.scenarios import list_scenarios
from data.preprocessor import (
    normalize_metrics, create_sliding_windows, label_logs_for_training
)
from models.tokenizer import LogTokenizer
from models.log_embedder import LogEmbeddingTransformer
from models.anomaly_detector import LSTMAutoencoder, StatisticalAnomalyDetector
from models.graph_analyzer import GraphAnalyzer
from models.root_cause_engine import (
    RootCauseEngine, build_log_signals, build_metric_signals
)
from models.causal_inference import CausalInferenceEngine
from models.predictive_engine import PredictiveFailureEngine
from models.pattern_memory import FailurePatternMemory
from models.confidence_scorer import ConfidenceImpactScorer


# ── App Factory ──────────────────────────────────────────────────

def create_app():
    app = Flask(__name__)
    CORS(app, origins=config.CORS_ORIGINS)

    # State
    app.state = {
        "dataset": None,
        "active_scenario": None,
        "models_loaded": False,
        "log_embedder": None,
        "tokenizer": None,
        "anomaly_detector": None,
        "normalization_stats": None,
        "graph_analyzer": None,
        "rca_engine": RootCauseEngine(),
        "causal_engine": CausalInferenceEngine(),
        "predictive_engine": PredictiveFailureEngine(),
        "pattern_memory": FailurePatternMemory(),
        "confidence_scorer": ConfidenceImpactScorer(),
        "last_analysis": None,
    }

    _initialize(app)
    _register_routes(app)

    return app


def _initialize(app):
    """Load models and generate initial data."""
    state = app.state
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Try loading trained models
    embedder_path = os.path.join(config.MODEL_DIR, "log_embedder.pt")
    tokenizer_path = os.path.join(config.MODEL_DIR, "tokenizer.json")
    anomaly_path = os.path.join(config.MODEL_DIR, "anomaly_detector.pt")

    if os.path.exists(tokenizer_path):
        print("[Init] Loading tokenizer...")
        state["tokenizer"] = LogTokenizer()
        state["tokenizer"].load(tokenizer_path)

    if os.path.exists(embedder_path) and state["tokenizer"]:
        print("[Init] Loading log embedder...")
        model = LogEmbeddingTransformer(vocab_size=state["tokenizer"].vocab_count).to(device)
        model.load_state_dict(torch.load(embedder_path, map_location=device, weights_only=True))
        model.eval()
        state["log_embedder"] = model

    if os.path.exists(anomaly_path):
        print("[Init] Loading anomaly detector...")
        checkpoint = torch.load(anomaly_path, map_location=device, weights_only=False)
        model = LSTMAutoencoder().to(device)
        model.load_state_dict(checkpoint["model_state_dict"])
        model.threshold_mean = torch.tensor(checkpoint["threshold_mean"])
        model.threshold_std = torch.tensor(checkpoint["threshold_std"])
        model.eval()
        state["anomaly_detector"] = model
        state["normalization_stats"] = checkpoint.get("normalization_stats")

    state["models_loaded"] = state["log_embedder"] is not None or state["anomaly_detector"] is not None
    print(f"[Init] Models loaded: {state['models_loaded']}")

    # Generate initial healthy data
    print("[Init] Generating baseline data...")
    dataset = generate_dataset(scenario_id=None, duration=config.SYNTHETIC_DURATION_SECONDS)
    state["dataset"] = dataset

    # Build graph
    state["graph_analyzer"] = GraphAnalyzer(dataset["graph"])


def _register_routes(app):
    """Register all API routes."""

    @app.route("/api/services", methods=["GET"])
    def get_services():
        """List all services and their current status."""
        dataset = app.state["dataset"]
        if not dataset:
            return jsonify({"error": "No data loaded"}), 500

        services = []
        for svc in config.SERVICES:
            metrics = dataset["metrics"].get(svc, [])
            recent = metrics[-10:] if metrics else []

            # Service health
            avg_error_rate = np.mean([m["error_rate"] for m in recent]) if recent else 0
            avg_latency = np.mean([m["latency_ms"] for m in recent]) if recent else 0
            avg_cpu = np.mean([m["cpu_percent"] for m in recent]) if recent else 0

            # Determine service health using multiple metrics
            if avg_error_rate > 0.1 or avg_latency > 1500 or avg_cpu > 85:
                status = "critical"
            elif avg_error_rate > 0.03 or avg_latency > 500 or avg_cpu > 70:
                status = "warning"
            else:
                status = "healthy"

            services.append({
                "id": svc,
                "status": status,
                "metrics": {
                    "cpu_percent": round(recent[-1]["cpu_percent"], 1) if recent else 0,
                    "memory_percent": round(recent[-1]["memory_percent"], 1) if recent else 0,
                    "latency_ms": round(avg_latency, 1),
                    "error_rate": round(avg_error_rate, 4),
                },
            })

        return jsonify({
            "services": services,
            "active_scenario": dataset.get("scenario_info"),
        })

    @app.route("/api/metrics/<service>", methods=["GET"])
    def get_metrics(service):
        """Get metric time-series for a specific service."""
        dataset = app.state["dataset"]
        if not dataset:
            return jsonify({"error": "No data loaded"}), 500

        metrics = dataset["metrics"].get(service)
        if metrics is None:
            return jsonify({"error": f"Service '{service}' not found"}), 404

        # Optional: limit to last N seconds
        limit = request.args.get("limit", type=int, default=None)
        if limit:
            metrics = metrics[-limit:]

        return jsonify({
            "service": service,
            "metrics": metrics,
            "count": len(metrics),
        })

    @app.route("/api/logs/<service>", methods=["GET"])
    def get_logs(service):
        """Get recent logs for a service."""
        dataset = app.state["dataset"]
        if not dataset:
            return jsonify({"error": "No data loaded"}), 500

        all_logs = dataset["logs"]
        service_logs = [l for l in all_logs if l["service"] == service]

        # Filter by level if specified
        level = request.args.get("level", type=str, default=None)
        if level:
            service_logs = [l for l in service_logs if l["level"] == level.upper()]

        # Limit
        limit = request.args.get("limit", type=int, default=100)
        service_logs = service_logs[-limit:]

        return jsonify({
            "service": service,
            "logs": service_logs,
            "count": len(service_logs),
        })

    @app.route("/api/graph", methods=["GET"])
    def get_graph():
        """Get service dependency graph."""
        analyzer = app.state["graph_analyzer"]
        if not analyzer:
            return jsonify({"error": "Graph not loaded"}), 500

        return jsonify(analyzer.get_graph_data())

    @app.route("/api/analyze", methods=["POST"])
    def run_analysis():
        """Run full RCA pipeline on current dataset."""
        try:
            dataset = app.state["dataset"]
            if not dataset:
                return jsonify({"error": "No data loaded"}), 500

            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

            # ── 1. Build log signals ──────────────────────────────
            log_predictions = None
            if app.state["log_embedder"] and app.state["tokenizer"]:
                log_predictions = _run_log_inference(
                    app.state["log_embedder"],
                    app.state["tokenizer"],
                    dataset["logs"],
                    device,
                )

            log_signals = build_log_signals(
                dataset["logs"],
                log_predictions=log_predictions,
            )

            # ── 2. Build metric signals ───────────────────────────
            anomaly_results = None
            if app.state["anomaly_detector"]:
                anomaly_results = _run_anomaly_inference(
                    app.state["anomaly_detector"],
                    dataset["metrics"],
                    app.state.get("normalization_stats"),
                    device,
                )

            metric_signals = build_metric_signals(
                dataset["metrics"],
                anomaly_results=anomaly_results,
            )

            # ── 3. Build graph signals ────────────────────────────
            analyzer = app.state["graph_analyzer"]
            anomalous_services = [
                s for s, sig in metric_signals.items()
                if sig.get("is_anomaly")
            ]

            # Add services with high log anomaly scores
            for s, sig in log_signals.items():
                if sig.get("anomaly_score", 0) > 0.3 and s not in anomalous_services:
                    anomalous_services.append(s)

            anomaly_scores = {
                s: max(
                    log_signals.get(s, {}).get("anomaly_score", 0),
                    metric_signals.get(s, {}).get("anomaly_score", 0)
                )
                for s in anomalous_services
            }

            # Estimate onset times from metrics
            onset_times = _estimate_onset_times(dataset["metrics"], anomalous_services)

            graph_signals = analyzer.compute_root_cause_scores(
                anomalous_services,
                anomaly_scores=anomaly_scores,
                anomaly_onset_times=onset_times,
            )

            # ── 4. Fuse and generate explanation ──────────────────
            engine = app.state["rca_engine"]
            result = engine.analyze(log_signals, metric_signals, graph_signals)

            # ── 5. Causal Inference ──────────────────────────────
            try:
                causal_engine = app.state["causal_engine"]
                causal_result = causal_engine.analyze_causality(
                    dataset["metrics"],
                    anomalous_services,
                    app.state["graph_analyzer"],
                    onset_times=onset_times,
                )
                result["causal_analysis"] = causal_result
            except Exception as ce:
                print(f"[Causal] Error: {ce}")
                result["causal_analysis"] = None

            # ── 6. Predictive Failure ────────────────────────────
            try:
                pred_engine = app.state["predictive_engine"]
                predictions = pred_engine.predict(dataset["metrics"])
                result["predictions"] = predictions
            except Exception as pe:
                print(f"[Predict] Error: {pe}")
                result["predictions"] = None

            # ── 7. Pattern Memory Match ──────────────────────────
            try:
                pattern_mem = app.state["pattern_memory"]
                pattern_result = pattern_mem.match_pattern(result)
                result["pattern_matches"] = pattern_result
                # Auto-store this incident
                pattern_mem.store_incident(result)
            except Exception as pm:
                print(f"[Pattern] Error: {pm}")
                result["pattern_matches"] = None

            # ── 8. Confidence & Impact Scoring ───────────────────
            try:
                scorer = app.state["confidence_scorer"]
                ci_result = scorer.compute_all(
                    result,
                    causal_result=result.get("causal_analysis"),
                    pattern_result=result.get("pattern_matches"),
                    graph_analyzer=app.state["graph_analyzer"],
                )
                result["confidence_impact"] = ci_result
            except Exception as ci:
                print(f"[Confidence] Error: {ci}")
                result["confidence_impact"] = None

            app.state["last_analysis"] = result
            return jsonify(result)

        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route("/api/anomalies", methods=["GET"])
    def get_anomalies():
        """Get detected anomalies — runs statistical detection on current data."""
        dataset = app.state["dataset"]
        if not dataset:
            return jsonify({"error": "No data loaded"}), 500

        stat_detector = StatisticalAnomalyDetector()
        anomalies = {}

        for service, records in dataset["metrics"].items():
            feature_names = ["cpu_percent", "memory_percent", "latency_ms", "error_rate", "connections"]
            data = np.array([[r[f] for f in feature_names] for r in records], dtype=np.float32)

            combined_scores, individual = stat_detector.ensemble_detect(data)

            # Filter out services that only have normal statistical noise
            # Z-score > 3.0 generally indicates a true anomaly
            if individual["z_score"].max() < 3.0:
                continue

            # Find anomalous time ranges from the combined scores
            threshold = 0.7  # high confidence
            anomalous_indices = np.where(combined_scores > threshold)[0]

            if len(anomalous_indices) > 0:
                anomalies[service] = {
                    "num_anomalous_points": len(anomalous_indices),
                    "max_score": float(combined_scores.max()),
                    "anomaly_start_idx": int(anomalous_indices[0]),
                    "anomaly_end_idx": int(anomalous_indices[-1]),
                    "scores": combined_scores[::10].tolist(),  # downsample for API
                }

        return jsonify({
            "anomalies": anomalies,
            "num_services_affected": len(anomalies),
        })

    @app.route("/api/scenarios", methods=["GET"])
    def get_scenarios():
        """List available failure scenarios."""
        return jsonify({"scenarios": list_scenarios()})

    @app.route("/api/scenarios/<scenario_id>/inject", methods=["POST"])
    def inject_scenario(scenario_id):
        """Inject a failure scenario and regenerate data."""
        try:
            valid_ids = ["memory_leak", "db_connection_exhaustion", "network_partition", "cpu_spike"]
            if scenario_id not in valid_ids:
                return jsonify({"error": f"Unknown scenario: {scenario_id}"}), 400

            print(f"[Inject] Injecting scenario: {scenario_id}")

            # Generate new dataset with failure
            dataset = generate_dataset(
                scenario_id=scenario_id,
                duration=config.SYNTHETIC_DURATION_SECONDS,
            )
            app.state["dataset"] = dataset
            app.state["active_scenario"] = scenario_id
            app.state["last_analysis"] = None

            # Rebuild graph
            app.state["graph_analyzer"] = GraphAnalyzer(dataset["graph"])

            return jsonify({
                "status": "injected",
                "scenario": dataset.get("scenario_info"),
            })

        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route("/api/predictions", methods=["GET"])
    def get_predictions():
        """Get failure predictions based on current metric trends."""
        dataset = app.state["dataset"]
        if not dataset:
            return jsonify({"error": "No data loaded"}), 500

        try:
            pred_engine = app.state["predictive_engine"]
            predictions = pred_engine.predict(dataset["metrics"])
            return jsonify(predictions)
        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route("/api/knowledge-base/resolve", methods=["POST"])
    def resolve_incident():
        """Mark an incident as resolved with a resolution note."""
        try:
            data = request.get_json() or {}
            incident_id = data.get("incident_id")
            resolution = data.get("resolution", "Resolved")
            ttr = data.get("time_to_resolve")

            if not incident_id:
                return jsonify({"error": "incident_id required"}), 400

            pattern_mem = app.state["pattern_memory"]
            updated = pattern_mem.resolve_incident(incident_id, resolution, ttr)

            if updated:
                return jsonify({"status": "resolved", "incident": updated})
            return jsonify({"error": "Incident not found"}), 404

        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route("/api/reset", methods=["POST"])
    def reset():
        """Reset to healthy baseline data."""
        dataset = generate_dataset(scenario_id=None, duration=config.SYNTHETIC_DURATION_SECONDS)
        app.state["dataset"] = dataset
        app.state["active_scenario"] = None
        app.state["last_analysis"] = None
        app.state["graph_analyzer"] = GraphAnalyzer(dataset["graph"])

        return jsonify({"status": "reset", "message": "System reset to healthy baseline"})

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "ok",
            "models_loaded": app.state["models_loaded"],
            "has_data": app.state["dataset"] is not None,
        })


# ── Helper Functions ──────────────────────────────────────────────

def _run_log_inference(model, tokenizer, logs, device):
    """Run log classification inference."""
    model.eval()
    predictions = []
    class_names = ["normal", "warning", "error", "anomaly"]

    # Process in batches
    batch_size = 128
    texts = [l["message"] for l in logs]

    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i + batch_size]
        token_ids, attention_masks = tokenizer.batch_encode(batch_texts)

        input_ids = torch.tensor(token_ids, dtype=torch.long).to(device)
        attn_mask = torch.tensor(attention_masks, dtype=torch.long).to(device)

        with torch.no_grad():
            logits = model(input_ids, attn_mask)
            preds = logits.argmax(dim=-1).cpu().tolist()

        for j, pred in enumerate(preds):
            log_idx = i + j
            predictions.append({
                "text": texts[log_idx],
                "service": logs[log_idx]["service"],
                "predicted_class": pred,
                "class_name": class_names[pred],
            })

    return predictions


def _run_anomaly_inference(model, metrics, stats, device):
    """Run LSTM autoencoder anomaly detection on current metrics."""
    model.eval()
    results = {}

    normalized, _ = normalize_metrics(metrics, fit=(stats is None), stats=stats)

    for service, data in normalized.items():
        windows = create_sliding_windows(data)
        if len(windows) == 0:
            continue

        windows_tensor = torch.tensor(windows, dtype=torch.float32).to(device)

        with torch.no_grad():
            errors = model.compute_reconstruction_error(windows_tensor)

        threshold = model.get_threshold()
        anomaly_scores = errors.cpu().numpy()

        results[service] = {
            "anomaly_scores": anomaly_scores.tolist(),
            "is_anomaly": bool(anomaly_scores.max() > threshold),
            "max_score": float(anomaly_scores.max()),
            "mean_score": float(anomaly_scores.mean()),
        }

    return results


def _estimate_onset_times(metrics, anomalous_services):
    """Estimate anomaly onset times for temporal correlation."""
    onset_times = {}
    stat_detector = StatisticalAnomalyDetector()

    for service in anomalous_services:
        records = metrics.get(service, [])
        if not records:
            continue

        feature_names = ["cpu_percent", "memory_percent", "latency_ms", "error_rate", "connections"]
        data = np.array([[r[f] for f in feature_names] for r in records], dtype=np.float32)

        combined, _ = stat_detector.ensemble_detect(data)

        # Find first time score exceeds threshold
        threshold = 0.5
        anomalous_idx = np.where(combined > threshold)[0]
        if len(anomalous_idx) > 0:
            onset_times[service] = int(anomalous_idx[0])

    return onset_times


# ── Entry Point ──────────────────────────────────────────────────

if __name__ == "__main__":
    app = create_app()
    app.run(host=config.API_HOST, port=config.API_PORT, debug=True)
