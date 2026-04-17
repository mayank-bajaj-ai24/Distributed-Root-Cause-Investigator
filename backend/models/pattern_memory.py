"""
Failure Pattern Memory (Knowledge Base) — Institutional memory for incidents.

Features:
1. Store past incidents with fingerprints (metrics + logs + root cause)
2. Match new failures against stored patterns using cosine similarity
3. Generate recommendations from best matches
4. Pre-seeded with known failure patterns for demo

Zero external APIs — pure numpy cosine similarity.
"""

import json
import os
import time
import uuid
import numpy as np
from datetime import datetime

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


KB_DIR = os.path.join(config.BASE_DIR, "knowledge_base")
KB_FILE = os.path.join(KB_DIR, "incidents.json")


class FailurePatternMemory:
    """
    Stores past incidents and matches new failures against them
    using feature-vector cosine similarity.

    Like having a senior SRE with perfect recall — the system never
    forgets a past incident and instantly suggests the fix.
    """

    def __init__(self, kb_path=None):
        self.kb_path = kb_path or KB_FILE
        self.incidents = []
        self._load_kb()

    def _load_kb(self):
        """Load knowledge base from disk."""
        if os.path.exists(self.kb_path):
            try:
                with open(self.kb_path, "r") as f:
                    self.incidents = json.load(f)
                print(f"[PatternMemory] Loaded {len(self.incidents)} incidents from KB")
            except (json.JSONDecodeError, IOError):
                self.incidents = []
                self._seed_default_patterns()
        else:
            self._seed_default_patterns()

    def _save_kb(self):
        """Persist knowledge base to disk."""
        os.makedirs(os.path.dirname(self.kb_path), exist_ok=True)
        with open(self.kb_path, "w") as f:
            json.dump(self.incidents, f, indent=2)

    def store_incident(self, analysis_result, resolution=None, title=None):
        """
        Store a completed analysis as a pattern in the knowledge base.

        Args:
            analysis_result: output from the full analysis pipeline
            resolution: optional resolution description
            title: optional incident title

        Returns:
            stored incident dict
        """
        root_cause = analysis_result.get("root_cause")
        if not root_cause:
            return None

        # Extract fingerprint
        fingerprint = self._extract_fingerprint(analysis_result)

        incident = {
            "incident_id": f"INC-{uuid.uuid4().hex[:6].upper()}",
            "title": title or analysis_result.get("explanation", {}).get("summary", "Unknown Incident"),
            "timestamp": datetime.now().isoformat(),
            "root_cause_service": root_cause.get("service", ""),
            "affected_services": [
                s["service"] for s in analysis_result.get("ranked_services", [])
                if s.get("is_anomaly")
            ],
            "fingerprint": fingerprint,
            "resolution": resolution or "AI Playbook: Execute mitigation protocol for anomalous target.",
            "time_to_resolve": None,
            "occurrence_count": 1,
            "fused_score": root_cause.get("fused_score", 0),
        }

        # Check for duplicate / increment occurrence count
        existing = self._find_similar(fingerprint, threshold=0.85)
        if existing:
            existing["occurrence_count"] = existing.get("occurrence_count", 1) + 1
            existing["last_seen"] = datetime.now().isoformat()
            self._save_kb()
            return existing

        self.incidents.append(incident)
        self._save_kb()
        return incident

    def match_pattern(self, analysis_result):
        """
        Match current failure against stored patterns.

        Args:
            analysis_result: output from the analysis pipeline

        Returns:
            dict with matches list, best_match, recommendation
        """
        root_cause = analysis_result.get("root_cause")
        if not root_cause or not self.incidents:
            return {
                "matches": [],
                "best_match": None,
                "recommendation": "No similar incidents in knowledge base.",
            }

        current_fp = self._extract_fingerprint(analysis_result)

        matches = []
        for incident in self.incidents:
            stored_fp = incident.get("fingerprint", {})
            similarity = self._compute_similarity(current_fp, stored_fp)

            if similarity > 0.15:  # minimum threshold
                matched_on = self._identify_match_factors(current_fp, stored_fp)
                matches.append({
                    "incident_id": incident.get("incident_id", ""),
                    "title": incident.get("title", ""),
                    "similarity": round(similarity, 3),
                    "matched_on": matched_on,
                    "resolution": incident.get("resolution", ""),
                    "time_to_resolve": incident.get("time_to_resolve", "Unknown"),
                    "occurrence_count": incident.get("occurrence_count", 1),
                    "root_cause_service": incident.get("root_cause_service", ""),
                    "timestamp": incident.get("timestamp", ""),
                })

        # Sort by similarity
        matches.sort(key=lambda m: m["similarity"], reverse=True)
        matches = matches[:5]  # top 5

        best_match = matches[0] if matches else None

        # Generate recommendation
        recommendation = self._generate_recommendation(best_match)

        return {
            "matches": matches,
            "best_match": best_match,
            "recommendation": recommendation,
        }

    def resolve_incident(self, incident_id, resolution, time_to_resolve=None):
        """
        Mark an incident as resolved with a resolution note.

        Args:
            incident_id: ID of the incident to resolve
            resolution: description of how it was resolved
            time_to_resolve: optional time string (e.g., "5 minutes")

        Returns:
            updated incident or None
        """
        for incident in self.incidents:
            if incident.get("incident_id") == incident_id:
                incident["resolution"] = resolution
                incident["time_to_resolve"] = time_to_resolve
                incident["resolved_at"] = datetime.now().isoformat()
                self._save_kb()
                return incident
        return None

    # ── Fingerprint Extraction ───────────────────────────────────

    def _extract_fingerprint(self, analysis_result):
        """
        Extract a multi-dimensional fingerprint from an analysis result.

        Fingerprint components:
        1. affected_services: set of affected service names
        2. metric_profile: deviation profile per metric type
        3. log_patterns: keywords from error logs
        4. root_cause_type: the inferred issue type
        5. severity_distribution: count of services at each severity level
        """
        root_cause = analysis_result.get("root_cause", {})
        ranked = analysis_result.get("ranked_services", [])

        # Affected services
        affected = [s["service"] for s in ranked if s.get("is_anomaly")]

        # Metric deviation profile
        metric_profile = {}
        for s in ranked:
            if not s.get("is_anomaly"):
                continue
            details = s.get("metric_details", {}).get("metric_details", {})
            for metric_name, info in details.items():
                dev = info.get("deviation", 0)
                if dev > 2:
                    if metric_name not in metric_profile:
                        metric_profile[metric_name] = 0
                    metric_profile[metric_name] = max(metric_profile[metric_name], dev)

        # Log error keywords
        log_keywords = set()
        for s in ranked:
            if not s.get("is_anomaly"):
                continue
            logs = s.get("log_details", {}).get("anomalous_logs", [])
            for log in logs[:5]:
                msg = log.get("message", "").lower()
                for kw in ["memory", "heap", "gc", "connection", "pool",
                           "timeout", "network", "cpu", "error", "exhausted",
                           "unreachable", "overflow", "leak", "circuit",
                           "partition", "spike", "latency"]:
                    if kw in msg:
                        log_keywords.add(kw)

        # Root cause type
        explanation = analysis_result.get("explanation", {})
        chain = explanation.get("chain", {})
        rc_issue = chain.get("root_cause", {}).get("issue", "") if chain else ""

        # Severity distribution
        severity_dist = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for s in ranked:
            score = s.get("fused_score", 0)
            if score > 0.7:
                severity_dist["CRITICAL"] += 1
            elif score > 0.5:
                severity_dist["HIGH"] += 1
            elif score > 0.3:
                severity_dist["MEDIUM"] += 1
            elif score > 0.15:
                severity_dist["LOW"] += 1

        return {
            "affected_services": affected,
            "metric_profile": metric_profile,
            "log_keywords": list(log_keywords),
            "root_cause_type": rc_issue,
            "root_cause_service": root_cause.get("service", ""),
            "severity_distribution": severity_dist,
            "num_affected": len(affected),
        }

    # ── Similarity Computation ───────────────────────────────────

    def _compute_similarity(self, fp_a, fp_b):
        """
        Compute overall similarity between two fingerprints using
        weighted component similarity.
        """
        # 1. Service overlap (Jaccard similarity)
        set_a = set(fp_a.get("affected_services", []))
        set_b = set(fp_b.get("affected_services", []))
        if set_a or set_b:
            service_sim = len(set_a & set_b) / max(len(set_a | set_b), 1)
        else:
            service_sim = 0

        # 2. Root cause service match
        rc_sim = 1.0 if (
            fp_a.get("root_cause_service") == fp_b.get("root_cause_service")
            and fp_a.get("root_cause_service")
        ) else 0.0

        # 3. Metric profile similarity (cosine on deviation vectors)
        metric_sim = self._metric_profile_similarity(
            fp_a.get("metric_profile", {}),
            fp_b.get("metric_profile", {})
        )

        # 4. Log keyword overlap (Jaccard)
        kw_a = set(fp_a.get("log_keywords", []))
        kw_b = set(fp_b.get("log_keywords", []))
        if kw_a or kw_b:
            kw_sim = len(kw_a & kw_b) / max(len(kw_a | kw_b), 1)
        else:
            kw_sim = 0

        # 5. Root cause type match
        type_sim = 0.0
        type_a = fp_a.get("root_cause_type", "").lower()
        type_b = fp_b.get("root_cause_type", "").lower()
        if type_a and type_b:
            # Check for keyword overlap in issue type
            words_a = set(type_a.split())
            words_b = set(type_b.split())
            if words_a & words_b:
                type_sim = len(words_a & words_b) / max(len(words_a | words_b), 1)

        # Weighted combination — prioritize service overlap and log patterns
        similarity = (
            0.30 * service_sim
            + 0.15 * rc_sim
            + 0.20 * metric_sim
            + 0.20 * kw_sim
            + 0.15 * type_sim
        )
        return similarity

    def _metric_profile_similarity(self, profile_a, profile_b):
        """Cosine similarity between metric deviation profiles."""
        all_metrics = set(list(profile_a.keys()) + list(profile_b.keys()))
        if not all_metrics:
            return 0

        vec_a = np.array([profile_a.get(m, 0) for m in all_metrics])
        vec_b = np.array([profile_b.get(m, 0) for m in all_metrics])

        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)

        if norm_a < 1e-8 or norm_b < 1e-8:
            return 0

        return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))

    def _identify_match_factors(self, current_fp, stored_fp):
        """Identify which factors contributed to the match."""
        factors = []

        set_a = set(current_fp.get("affected_services", []))
        set_b = set(stored_fp.get("affected_services", []))
        if len(set_a & set_b) > 0:
            factors.append("affected_services")

        if (current_fp.get("root_cause_service") == stored_fp.get("root_cause_service")
                and current_fp.get("root_cause_service")):
            factors.append("root_cause_service")

        kw_a = set(current_fp.get("log_keywords", []))
        kw_b = set(stored_fp.get("log_keywords", []))
        if len(kw_a & kw_b) > 0:
            factors.append("log_patterns")

        if self._metric_profile_similarity(
            current_fp.get("metric_profile", {}),
            stored_fp.get("metric_profile", {})
        ) > 0.5:
            factors.append("metric_profile")

        return factors

    def _find_similar(self, fingerprint, threshold=0.85):
        """Find an existing incident with high similarity."""
        for incident in self.incidents:
            sim = self._compute_similarity(fingerprint, incident.get("fingerprint", {}))
            if sim >= threshold:
                return incident
        return None

    def _generate_recommendation(self, best_match):
        """Generate a human-readable recommendation from the best match."""
        if not best_match:
            return "No similar incidents found in knowledge base. This appears to be a new type of failure."

        similarity = best_match["similarity"]
        count = best_match.get("occurrence_count", 1)
        resolution = best_match.get("resolution", "Unknown")
        ttr = best_match.get("time_to_resolve", "Unknown")

        if similarity >= 0.75:
            prefix = f"🎯 Strong match ({similarity:.0%} similar)"
        elif similarity >= 0.50:
            prefix = f"🔍 Partial match ({similarity:.0%} similar)"
        else:
            prefix = f"💡 Weak match ({similarity:.0%} similar)"

        parts = [prefix]
        if count > 1:
            parts.append(f"seen {count} times before")
        parts.append(f"→ {resolution}")
        if ttr and ttr != "Unknown":
            parts.append(f"(avg resolution: {ttr})")

        return " — ".join(parts)

    # ── Pre-seeded Knowledge Base ────────────────────────────────

    def _seed_default_patterns(self):
        """
        Pre-seed the knowledge base with known failure patterns
        matching our 4 scenarios. Ensures the demo always has matches.
        """
        self.incidents = [
            {
                "incident_id": "INC-SEED01",
                "title": "Memory Leak in Inventory Service",
                "timestamp": "2025-06-14T08:30:00",
                "root_cause_service": "inventory-service",
                "affected_services": ["inventory-service", "inventory-db", "order-service", "api-gateway"],
                "fingerprint": {
                    "affected_services": ["inventory-service", "inventory-db", "order-service", "notification-service", "api-gateway"],
                    "metric_profile": {
                        "memory_percent": 8.5,
                        "cpu_percent": 5.2,
                        "latency_ms": 4.1,
                        "error_rate": 3.8,
                    },
                    "log_keywords": ["memory", "heap", "gc", "timeout", "exhausted", "leak"],
                    "root_cause_type": "Memory Leak Detected",
                    "root_cause_service": "inventory-service",
                    "severity_distribution": {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 1, "LOW": 1},
                    "num_affected": 5,
                },
                "resolution": "Restart inventory-service pods and investigate object cache leak in InventoryCache.getAll()",
                "time_to_resolve": "5 minutes",
                "occurrence_count": 3,
            },
            {
                "incident_id": "INC-SEED05",
                "title": "Cascading Timeout from Inventory Leak",
                "timestamp": "2025-06-10T16:00:00",
                "root_cause_service": "order-service",
                "affected_services": ["order-service", "inventory-service", "api-gateway"],
                "fingerprint": {
                    "affected_services": ["order-service", "inventory-service", "api-gateway", "inventory-db"],
                    "metric_profile": {
                        "latency_ms": 6.0,
                        "error_rate": 5.5,
                        "memory_percent": 4.5,
                        "cpu_percent": 3.5,
                    },
                    "log_keywords": ["timeout", "memory", "heap", "gc", "error", "circuit", "exhausted"],
                    "root_cause_type": "Latency Spike Detected",
                    "root_cause_service": "order-service",
                    "severity_distribution": {"CRITICAL": 1, "HIGH": 1, "MEDIUM": 1, "LOW": 0},
                    "num_affected": 3,
                },
                "resolution": "Root cause was upstream memory leak in inventory-service. Restart inventory pods, then order-service recovers automatically.",
                "time_to_resolve": "7 minutes",
                "occurrence_count": 2,
            },
            {
                "incident_id": "INC-SEED02",
                "title": "DB Connection Pool Exhaustion in User DB",
                "timestamp": "2025-06-13T14:15:00",
                "root_cause_service": "user-db",
                "affected_services": ["user-db", "auth-service", "api-gateway"],
                "fingerprint": {
                    "affected_services": ["user-db", "auth-service", "api-gateway"],
                    "metric_profile": {
                        "connections": 9.2,
                        "latency_ms": 7.5,
                        "error_rate": 5.1,
                        "cpu_percent": 3.0,
                    },
                    "log_keywords": ["connection", "pool", "exhausted", "timeout", "unreachable"],
                    "root_cause_type": "Connection Pool Exhaustion",
                    "root_cause_service": "user-db",
                    "severity_distribution": {"CRITICAL": 1, "HIGH": 1, "MEDIUM": 1, "LOW": 0},
                    "num_affected": 3,
                },
                "resolution": "Scale up DB connection pool max_connections from 50 to 100, and fix connection leak in AuthService.validateToken()",
                "time_to_resolve": "8 minutes",
                "occurrence_count": 2,
            },
            {
                "incident_id": "INC-SEED03",
                "title": "Network Partition — Payment Gateway Isolated",
                "timestamp": "2025-06-12T20:45:00",
                "root_cause_service": "payment-gateway",
                "affected_services": ["payment-gateway", "payment-service", "order-service", "api-gateway"],
                "fingerprint": {
                    "affected_services": ["payment-gateway", "payment-service", "order-service", "api-gateway"],
                    "metric_profile": {
                        "error_rate": 9.5,
                        "latency_ms": 8.0,
                    },
                    "log_keywords": ["network", "unreachable", "timeout", "connection", "circuit", "partition"],
                    "root_cause_type": "Network Partition",
                    "root_cause_service": "payment-gateway",
                    "severity_distribution": {"CRITICAL": 2, "HIGH": 1, "MEDIUM": 1, "LOW": 0},
                    "num_affected": 4,
                },
                "resolution": "Restore network route to payment-gateway subnet. Root cause: misconfigured firewall rule in VPC peering.",
                "time_to_resolve": "12 minutes",
                "occurrence_count": 1,
            },
            {
                "incident_id": "INC-SEED04",
                "title": "CPU Spike in Search Service — Runaway Query",
                "timestamp": "2025-06-11T11:20:00",
                "root_cause_service": "search-service",
                "affected_services": ["search-service", "cache-redis", "api-gateway"],
                "fingerprint": {
                    "affected_services": ["search-service", "cache-redis", "api-gateway"],
                    "metric_profile": {
                        "cpu_percent": 9.0,
                        "latency_ms": 6.5,
                        "memory_percent": 4.0,
                    },
                    "log_keywords": ["cpu", "timeout", "exhausted", "spike"],
                    "root_cause_type": "CPU Spike Detected",
                    "root_cause_service": "search-service",
                    "severity_distribution": {"CRITICAL": 1, "HIGH": 1, "MEDIUM": 1, "LOW": 0},
                    "num_affected": 3,
                },
                "resolution": "Kill runaway full-text search query and add query timeout limit of 5s in search-service config",
                "time_to_resolve": "3 minutes",
                "occurrence_count": 2,
            },
        ]
        self._save_kb()
        print(f"[PatternMemory] Seeded KB with {len(self.incidents)} default patterns")
