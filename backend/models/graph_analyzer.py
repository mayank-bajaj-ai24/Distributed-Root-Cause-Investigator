"""
Graph-based root cause analyzer using NetworkX.

Algorithms:
1. Personalized PageRank — biased random walk from anomalous nodes
2. Anomalous Subgraph Extraction — identify source nodes
3. Temporal Correlation Analysis — cross-correlation of anomaly onset times
4. Root Cause Score fusion: α·PageRank + β·upstream_ratio + γ·temporal_priority
"""

import numpy as np
import networkx as nx
from collections import defaultdict

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


class GraphAnalyzer:
    """
    Service dependency graph analyzer for root cause identification.

    Uses the dependency graph topology combined with anomaly signals
    to identify the most likely root cause of cascading failures.
    """

    def __init__(self, graph_data=None):
        """
        Args:
            graph_data: dict with 'nodes' and 'edges' from synthetic generator
        """
        self.G = nx.DiGraph()
        self.alpha = config.RCA_ALPHA      # PageRank weight
        self.beta = config.RCA_BETA        # Upstream ratio weight
        self.gamma = config.RCA_GAMMA      # Temporal priority weight

        if graph_data:
            self.build_graph(graph_data)

    def build_graph(self, graph_data):
        """Build NetworkX directed graph from data."""
        self.G.clear()

        for node in graph_data["nodes"]:
            self.G.add_node(node["id"], node_type=node.get("type", "service"))

        for edge in graph_data["edges"]:
            self.G.add_edge(edge["source"], edge["target"])

        print(f"Graph built: {self.G.number_of_nodes()} nodes, {self.G.number_of_edges()} edges")

    # ── 1. Personalized PageRank ──────────────────────────────────

    def personalized_pagerank(self, anomalous_services, anomaly_scores=None):
        """
        Compute Personalized PageRank biased toward anomalous services.

        PR(v) = (1-d)/N + d · Σ_{u∈B(v)} PR(u)/L(u)

        The teleportation probability is biased toward services with
        higher anomaly scores.

        Args:
            anomalous_services: list of service names with detected anomalies
            anomaly_scores: optional dict service -> anomaly score

        Returns:
            dict service -> PageRank score
        """
        if not anomalous_services:
            return {n: 0.0 for n in self.G.nodes}

        # Build personalization vector (teleportation bias)
        personalization = {}
        for node in self.G.nodes:
            if node in anomalous_services:
                score = anomaly_scores.get(node, 1.0) if anomaly_scores else 1.0
                personalization[node] = score
            else:
                personalization[node] = 0.01  # small probability for non-anomalous

        # Normalize
        total = sum(personalization.values())
        personalization = {k: v / total for k, v in personalization.items()}

        # Compute PageRank on the REVERSED graph
        # We reverse because we want to find upstream root causes
        G_reversed = self.G.reverse()
        pagerank = nx.pagerank(
            G_reversed,
            alpha=config.PAGERANK_DAMPING,
            personalization=personalization,
            max_iter=100,
            tol=1e-6,
        )

        return pagerank

    # ── 2. Anomalous Subgraph Extraction ──────────────────────────

    def extract_anomalous_subgraph(self, anomalous_services):
        """
        Extract the connected subgraph of anomalous services.
        Identify "source" nodes (no anomalous predecessors) as root cause candidates.

        Args:
            anomalous_services: set of anomalous service names

        Returns:
            dict with:
                - subgraph_nodes: list of nodes in anomalous subgraph
                - source_nodes: nodes with no anomalous predecessors
                - propagation_paths: paths from sources to downstream affected services
        """
        anomalous_set = set(anomalous_services)

        if not anomalous_set:
            return {"subgraph_nodes": [], "source_nodes": [], "propagation_paths": []}

        # Find source nodes: anomalous nodes with no anomalous predecessors
        source_nodes = []
        for node in anomalous_set:
            if node in self.G:
                predecessors = set(self.G.predecessors(node))
                anomalous_predecessors = predecessors & anomalous_set
                if not anomalous_predecessors:
                    source_nodes.append(node)

        # If no clear source found, fall back to all anomalous nodes
        if not source_nodes:
            source_nodes = list(anomalous_set)

        # Find propagation paths
        propagation_paths = []
        for source in source_nodes:
            for target in anomalous_set:
                if source != target:
                    try:
                        paths = list(nx.all_simple_paths(self.G, source, target, cutoff=5))
                        for path in paths:
                            propagation_paths.append({
                                "source": source,
                                "target": target,
                                "path": path,
                                "length": len(path),
                            })
                    except nx.NetworkXNoPath:
                        pass

        return {
            "subgraph_nodes": list(anomalous_set),
            "source_nodes": source_nodes,
            "propagation_paths": propagation_paths,
        }

    # ── 3. Temporal Correlation Analysis ──────────────────────────

    def temporal_correlation(self, anomaly_onset_times):
        """
        Analyze temporal ordering of anomaly onsets to determine causation direction.

        If A's anomaly precedes B's and A→B in the dependency graph,
        then A is likely the upstream cause.

        Args:
            anomaly_onset_times: dict service -> onset timestamp (seconds)

        Returns:
            temporal_scores: dict service -> temporal priority score
        """
        if len(anomaly_onset_times) < 2:
            return {s: 1.0 for s in anomaly_onset_times}

        scores = defaultdict(float)
        comparisons = defaultdict(int)

        for edge in self.G.edges:
            source, target = edge
            if source in anomaly_onset_times and target in anomaly_onset_times:
                source_time = anomaly_onset_times[source]
                target_time = anomaly_onset_times[target]

                # If source anomaly came first → supports source as cause
                if source_time < target_time:
                    time_diff = target_time - source_time
                    # Score inversely proportional to time difference
                    # Earlier onset → higher score
                    score = 1.0 / (1.0 + time_diff / 60.0)  # normalize by 60s
                    scores[source] += score
                    comparisons[source] += 1
                elif target_time < source_time:
                    # Reverse direction suggests target might be causal
                    time_diff = source_time - target_time
                    score = 1.0 / (1.0 + time_diff / 60.0)
                    scores[target] += score
                    comparisons[target] += 1

        # Normalize scores
        temporal_scores = {}
        for service in anomaly_onset_times:
            if service in scores and comparisons[service] > 0:
                temporal_scores[service] = scores[service] / comparisons[service]
            else:
                temporal_scores[service] = 0.5  # neutral score

        # Normalize to [0, 1]
        max_score = max(temporal_scores.values()) if temporal_scores else 1.0
        if max_score > 0:
            temporal_scores = {k: v / max_score for k, v in temporal_scores.items()}

        return temporal_scores

    # ── 4. Upstream Ratio ─────────────────────────────────────────

    def compute_upstream_ratio(self, anomalous_services):
        """
        For each anomalous service, compute the ratio of downstream
        services that are also anomalous.

        Higher ratio → more likely to be a root cause (its failures propagated).

        Args:
            anomalous_services: set of anomalous service names

        Returns:
            dict service -> upstream_ratio score [0, 1]
        """
        anomalous_set = set(anomalous_services)
        ratios = {}

        for service in anomalous_set:
            if service not in self.G:
                ratios[service] = 0.0
                continue

            # Get all downstream services (descendants)
            try:
                descendants = nx.descendants(self.G, service)
            except nx.NetworkXError:
                descendants = set()

            if not descendants:
                ratios[service] = 0.0
                continue

            # Fraction of descendants that are anomalous
            anomalous_descendants = descendants & anomalous_set
            ratios[service] = len(anomalous_descendants) / len(descendants)

        return ratios

    # ── Combined Root Cause Score ─────────────────────────────────

    def compute_root_cause_scores(self, anomalous_services, anomaly_scores=None,
                                   anomaly_onset_times=None):
        """
        Compute the final root cause score for each service:
            RCA_score(v) = α·PageRank(v) + β·upstream_ratio(v) + γ·temporal_priority(v)

        Args:
            anomalous_services: list of service names with anomalies
            anomaly_scores: dict service -> raw anomaly score
            anomaly_onset_times: dict service -> onset time in seconds

        Returns:
            ranked_services: list of (service, score, details) sorted by score DESC
        """
        if not anomalous_services:
            return []

        # 1. Personalized PageRank
        pagerank_scores = self.personalized_pagerank(anomalous_services, anomaly_scores)

        # Normalize PageRank to [0, 1]
        pr_values = [pagerank_scores.get(s, 0) for s in anomalous_services]
        pr_max = max(pr_values) if pr_values else 1.0
        if pr_max > 0:
            pr_normalized = {s: pagerank_scores.get(s, 0) / pr_max for s in anomalous_services}
        else:
            pr_normalized = {s: 0 for s in anomalous_services}

        # 2. Upstream ratio
        upstream_ratios = self.compute_upstream_ratio(anomalous_services)

        # 3. Temporal correlation
        if anomaly_onset_times:
            temporal_scores = self.temporal_correlation(anomaly_onset_times)
        else:
            temporal_scores = {s: 0.5 for s in anomalous_services}

        # 4. Extract anomalous subgraph for path info
        subgraph_info = self.extract_anomalous_subgraph(anomalous_services)

        # 5. Fuse scores
        results = []
        for service in anomalous_services:
            pr = pr_normalized.get(service, 0)
            ur = upstream_ratios.get(service, 0)
            tp = temporal_scores.get(service, 0.5)

            combined = self.alpha * pr + self.beta * ur + self.gamma * tp

            # Bonus for being identified as a source node
            if service in subgraph_info["source_nodes"]:
                combined *= 1.2  # 20% bonus

            results.append({
                "service": service,
                "rca_score": min(1.0, combined),
                "pagerank": pr,
                "upstream_ratio": ur,
                "temporal_priority": tp,
                "is_source_node": service in subgraph_info["source_nodes"],
            })

        # Sort by RCA score descending
        results.sort(key=lambda x: x["rca_score"], reverse=True)
        return results

    def get_graph_data(self):
        """Return graph data for API/visualization."""
        return {
            "nodes": [
                {
                    "id": n,
                    "type": self.G.nodes[n].get("node_type", "service"),
                    "degree": self.G.degree(n),
                    "in_degree": self.G.in_degree(n),
                    "out_degree": self.G.out_degree(n),
                }
                for n in self.G.nodes
            ],
            "edges": [
                {"source": u, "target": v}
                for u, v in self.G.edges
            ],
        }
