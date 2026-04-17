"""
Causal Inference Layer — Determines cause vs effect, not just correlation.

Algorithms:
1. Time-Lag Cross-Correlation — Granger-like causality test between metric series
2. Dependency-Weighted Causal Graph — Combines statistical causality with known topology
3. Causal Chain Extraction — Topological ordering of confirmed causal relationships

Zero external APIs — pure numpy + networkx.
"""

import numpy as np
import networkx as nx
from collections import defaultdict

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


class CausalInferenceEngine:
    """
    Determines causal relationships between service failures using
    time-lag cross-correlation and dependency graph topology.

    Key insight: If service A's anomaly consistently precedes service B's
    anomaly with a stable time lag, AND A→B exists in the dependency graph,
    then A likely caused B's failure.
    """

    def __init__(self, dependency_prior_weight=0.3):
        self.dependency_prior_weight = dependency_prior_weight
        self.min_correlation = 0.3  # minimum correlation to consider causal
        self.max_lag = 60  # maximum lag in seconds to test

    def analyze_causality(self, metrics, anomalous_services, graph_analyzer, onset_times=None):
        """
        Full causal inference pipeline.

        Args:
            metrics: dict service -> list of metric dicts (time-series)
            anomalous_services: list of services with detected anomalies
            graph_analyzer: GraphAnalyzer instance with dependency graph
            onset_times: optional dict service -> onset time index

        Returns:
            dict with causal_edges, causal_chain, root_cause, causality_type
        """
        if len(anomalous_services) < 2:
            return {
                "causal_edges": [],
                "causal_chain": anomalous_services,
                "root_cause": anomalous_services[0] if anomalous_services else None,
                "causality_type": "single_service",
                "causal_graph_data": {"nodes": [], "edges": []},
            }

        # Step 1: Compute pairwise cross-correlations
        correlation_matrix = self._compute_pairwise_correlations(
            metrics, anomalous_services
        )

        # Step 2: Build causal graph with dependency priors
        causal_graph = self._build_causal_graph(
            correlation_matrix, anomalous_services, graph_analyzer, onset_times
        )

        # Step 3: Extract causal chain
        causal_chain, causal_edges = self._extract_causal_chain(causal_graph)

        # Step 4: Identify root cause and classify confidence
        root_cause = causal_chain[0] if causal_chain else None
        causality_type = self._classify_causality(causal_edges, graph_analyzer)

        # Build visualization data
        causal_graph_data = self._build_visualization_data(
            causal_edges, anomalous_services
        )

        return {
            "causal_edges": causal_edges,
            "causal_chain": causal_chain,
            "root_cause": root_cause,
            "causality_type": causality_type,
            "causal_graph_data": causal_graph_data,
        }

    def _compute_pairwise_correlations(self, metrics, anomalous_services):
        """
        Compute time-lag cross-correlation for all pairs of anomalous services.

        For each pair (A, B), finds the lag τ that maximizes:
            R(τ) = Σ_t anomaly_A(t) · anomaly_B(t + τ)

        If peak correlation is at positive τ, A's anomaly precedes B's → A may cause B.
        """
        results = {}

        # Extract anomaly signal per service (composite metric deviation)
        signals = {}
        for service in anomalous_services:
            records = metrics.get(service, [])
            if not records:
                continue
            signals[service] = self._extract_anomaly_signal(records)

        # Pairwise cross-correlation
        services_with_signals = [s for s in anomalous_services if s in signals]

        for i, svc_a in enumerate(services_with_signals):
            for j, svc_b in enumerate(services_with_signals):
                if i == j:
                    continue

                sig_a = signals[svc_a]
                sig_b = signals[svc_b]

                # Ensure equal length
                min_len = min(len(sig_a), len(sig_b))
                if min_len < 10:
                    continue

                sig_a = sig_a[:min_len]
                sig_b = sig_b[:min_len]

                # Normalize
                sig_a = (sig_a - sig_a.mean()) / max(sig_a.std(), 1e-8)
                sig_b = (sig_b - sig_b.mean()) / max(sig_b.std(), 1e-8)

                # Cross-correlation at different lags
                best_lag, best_corr = self._cross_correlate(sig_a, sig_b)

                results[(svc_a, svc_b)] = {
                    "lag": best_lag,
                    "correlation": best_corr,
                    "direction": "a_causes_b" if best_lag > 0 else "b_causes_a" if best_lag < 0 else "simultaneous",
                }

        return results

    def _extract_anomaly_signal(self, records):
        """
        Extract a composite anomaly signal from metric records.
        Combines all metrics into a single deviation signal.
        """
        feature_names = ["cpu_percent", "memory_percent", "latency_ms", "error_rate", "connections"]
        data = np.array([[r.get(f, 0) for f in feature_names] for r in records], dtype=np.float32)

        # Compute rolling deviation from baseline
        window = min(60, len(data) // 4)
        if window < 5:
            window = 5

        # Baseline: first portion of data
        baseline = data[:window]
        mean = baseline.mean(axis=0)
        std = baseline.std(axis=0)
        std[std < 1e-8] = 1.0

        # Z-score deviation
        z_scores = np.abs((data - mean) / std)

        # Composite: max deviation across features at each timestep
        composite = z_scores.max(axis=1)
        return composite

    def _cross_correlate(self, signal_a, signal_b):
        """
        Compute normalized cross-correlation and find the lag with maximum correlation.

        Positive lag → signal_a leads signal_b (A may cause B)
        Negative lag → signal_b leads signal_a (B may cause A)
        """
        n = len(signal_a)
        max_lag = min(self.max_lag, n // 3)

        best_lag = 0
        best_corr = 0.0

        for lag in range(-max_lag, max_lag + 1):
            if lag >= 0:
                a_slice = signal_a[:n - lag] if lag > 0 else signal_a
                b_slice = signal_b[lag:] if lag > 0 else signal_b
            else:
                a_slice = signal_a[-lag:]
                b_slice = signal_b[:n + lag]

            if len(a_slice) < 5:
                continue

            corr = np.corrcoef(a_slice, b_slice)[0, 1]
            if not np.isnan(corr) and abs(corr) > abs(best_corr):
                best_corr = corr
                best_lag = lag

        return best_lag, float(best_corr)

    def _build_causal_graph(self, correlation_matrix, anomalous_services,
                            graph_analyzer, onset_times):
        """
        Build a weighted causal directed graph.

        Edge weight combines:
        1. Cross-correlation strength (statistical causality)
        2. Dependency graph prior (structural causality)
        3. Temporal ordering (onset time difference)
        """
        G = nx.DiGraph()

        for service in anomalous_services:
            G.add_node(service)

        for (svc_a, svc_b), info in correlation_matrix.items():
            corr = info["correlation"]
            lag = info["lag"]

            # Only consider if A precedes B (positive lag) and correlation is meaningful
            if lag <= 0 or corr < self.min_correlation:
                continue

            # Statistical causality score
            stat_score = corr * min(1.0, lag / 5.0)  # reward small but positive lags

            # Dependency prior: check if A→B exists in dependency graph
            dep_score = 0.0
            if graph_analyzer and hasattr(graph_analyzer, 'G'):
                if graph_analyzer.G.has_edge(svc_a, svc_b):
                    dep_score = 1.0  # direct dependency
                elif nx.has_path(graph_analyzer.G, svc_a, svc_b):
                    path_len = nx.shortest_path_length(graph_analyzer.G, svc_a, svc_b)
                    dep_score = 1.0 / path_len  # indirect dependency

            # Temporal ordering bonus
            temporal_score = 0.5
            if onset_times and svc_a in onset_times and svc_b in onset_times:
                if onset_times[svc_a] < onset_times[svc_b]:
                    temporal_score = 1.0
                elif onset_times[svc_a] > onset_times[svc_b]:
                    temporal_score = 0.0

            # Combined causal weight
            weight = (
                (1 - self.dependency_prior_weight) * stat_score * 0.5
                + self.dependency_prior_weight * dep_score
                + 0.2 * temporal_score
            )

            if weight > 0.15:  # threshold
                G.add_edge(svc_a, svc_b, weight=min(1.0, weight), lag=lag,
                           correlation=corr, dep_score=dep_score)

        return G

    def _extract_causal_chain(self, causal_graph):
        """
        Extract the primary causal chain using topological sort.
        Returns ordered list from root cause → final impact.
        """
        if not causal_graph.nodes:
            return [], []

        # Remove cycles for topological sort
        try:
            cycles = list(nx.simple_cycles(causal_graph))
            for cycle in cycles:
                # Remove weakest edge in cycle
                min_weight = float("inf")
                min_edge = None
                for i in range(len(cycle)):
                    u, v = cycle[i], cycle[(i + 1) % len(cycle)]
                    if causal_graph.has_edge(u, v):
                        w = causal_graph[u][v].get("weight", 0)
                        if w < min_weight:
                            min_weight = w
                            min_edge = (u, v)
                if min_edge:
                    causal_graph.remove_edge(*min_edge)
        except Exception:
            pass

        # Topological sort
        try:
            chain = list(nx.topological_sort(causal_graph))
        except nx.NetworkXUnfeasible:
            # Fallback: sort by in-degree (fewer predecessors = more likely root cause)
            chain = sorted(causal_graph.nodes,
                           key=lambda n: causal_graph.in_degree(n))

        # Extract edge details
        causal_edges = []
        for u, v, data in causal_graph.edges(data=True):
            causal_edges.append({
                "source": u,
                "target": v,
                "lag_seconds": data.get("lag", 0),
                "strength": round(data.get("weight", 0), 3),
                "correlation": round(data.get("correlation", 0), 3),
            })

        # Sort edges by strength
        causal_edges.sort(key=lambda e: e["strength"], reverse=True)

        return chain, causal_edges

    def _classify_causality(self, causal_edges, graph_analyzer):
        """
        Classify overall causality confidence.

        confirmed: Strong correlation + dependency graph alignment
        probable: Moderate correlation or partial graph alignment
        uncertain: Weak signals, unclear direction
        """
        if not causal_edges:
            return "uncertain"

        avg_strength = np.mean([e["strength"] for e in causal_edges])
        has_dep_alignment = any(
            e["strength"] > 0.5 for e in causal_edges
        )

        if avg_strength > 0.6 and has_dep_alignment:
            return "confirmed"
        elif avg_strength > 0.35:
            return "probable"
        else:
            return "uncertain"

    def _build_visualization_data(self, causal_edges, anomalous_services):
        """Build graph data for frontend visualization."""
        nodes = [{"id": s, "anomalous": True} for s in anomalous_services]
        edges = [
            {
                "source": e["source"],
                "target": e["target"],
                "lag": e["lag_seconds"],
                "strength": e["strength"],
            }
            for e in causal_edges
        ]
        return {"nodes": nodes, "edges": edges}
