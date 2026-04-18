"""
Confidence & Impact Scoring — No black boxes.

Confidence Score:
    Combines signal agreement, causal confirmation, evidence depth,
    and pattern match strength into a single 0-1 confidence score.

Impact Score:
    Blast radius (affected services), severity, user-facing impact,
    and downstream propagation combined into a 0-100 impact score.

Zero external APIs — pure arithmetic.
"""

import numpy as np
import networkx as nx

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


class ConfidenceImpactScorer:
    """
    Adds multi-dimensional confidence and impact scores to analysis results.
    Every finding gets a confidence percentage and impact assessment so
    decision-makers know exactly how certain we are and how severe the problem is.
    """

    def __init__(self):
        # Confidence weights
        self.w_signal = 0.30      # signal agreement weight
        self.w_causal = 0.25      # causal confirmation weight
        self.w_evidence = 0.25    # evidence depth weight
        self.w_pattern = 0.20     # pattern match weight

    def compute_confidence(self, analysis_result, causal_result=None,
                           pattern_result=None):
        """
        Compute multi-factor confidence score.

        Args:
            analysis_result: output from RootCauseEngine.analyze()
            causal_result: output from CausalInferenceEngine.analyze_causality()
            pattern_result: output from FailurePatternMemory.match_pattern()

        Returns:
            dict with overall confidence, label, and factor breakdown
        """
        root_cause = analysis_result.get("root_cause")
        if not root_cause:
            return {
                "overall": 0.0,
                "label": "N/A",
                "factors": {},
                "explanation": "No anomaly detected — confidence not applicable.",
            }

        # Factor 1: Signal Agreement
        signal_agreement = self._compute_signal_agreement(root_cause)

        # Factor 2: Causal Confirmation
        causal_confirmation = self._compute_causal_confirmation(
            root_cause, causal_result
        )

        # Factor 3: Evidence Depth
        evidence_depth = self._compute_evidence_depth(analysis_result)

        # Factor 4: Pattern Match Strength
        pattern_match = self._compute_pattern_match(pattern_result)

        # Weighted combination
        overall = (
            self.w_signal * signal_agreement
            + self.w_causal * causal_confirmation
            + self.w_evidence * evidence_depth
            + self.w_pattern * pattern_match
        )
        overall = min(1.0, max(0.0, overall))

        # Label
        if overall >= 0.85:
            label = "VERY HIGH"
        elif overall >= 0.70:
            label = "HIGH"
        elif overall >= 0.50:
            label = "MODERATE"
        elif overall >= 0.30:
            label = "LOW"
        else:
            label = "VERY LOW"

        # Explanation
        explanation = self._generate_confidence_explanation(
            label, signal_agreement, causal_confirmation,
            evidence_depth, pattern_match
        )

        return {
            "overall": round(overall, 3),
            "label": label,
            "factors": {
                "signal_agreement": round(signal_agreement, 3),
                "causal_confirmation": round(causal_confirmation, 3),
                "evidence_depth": round(evidence_depth, 3),
                "pattern_match": round(pattern_match, 3),
            },
            "explanation": explanation,
        }

    def compute_impact(self, analysis_result, graph_analyzer=None):
        """
        Compute impact assessment.

        Args:
            analysis_result: output from RootCauseEngine.analyze()
            graph_analyzer: GraphAnalyzer instance

        Returns:
            dict with impact score, label, blast radius, and details
        """
        ranked = analysis_result.get("ranked_services", [])
        root_cause = analysis_result.get("root_cause")
        num_anomalous = analysis_result.get("num_anomalous", 0)
        total_services = len(config.SERVICES)

        if not root_cause or num_anomalous == 0:
            return {
                "score": 0,
                "label": "NONE",
                "blast_radius": 0.0,
                "affected_services": 0,
                "total_services": total_services,
                "user_facing": False,
                "estimated_severity": "No impact detected.",
                "downstream_count": 0,
            }

        # 1. Blast radius: fraction of services affected
        blast_radius = num_anomalous / total_services

        # 2. Severity: max fused score
        max_severity = max(s.get("fused_score", 0) for s in ranked) if ranked else 0

        # 3. User-facing impact: does the failure reach api-gateway?
        user_facing = any(
            s.get("service") == "api-gateway" and s.get("is_anomaly", False)
            for s in ranked
        )

        # 4. Downstream count: services downstream of root cause
        downstream_count = 0
        if graph_analyzer and hasattr(graph_analyzer, 'G'):
            rc_service = root_cause.get("service", "")
            try:
                descendants = nx.descendants(graph_analyzer.G, rc_service)
                downstream_count = len(descendants)
            except (nx.NetworkXError, nx.NodeNotFound):
                pass

        # 5. Weighted average severity of affected services
        affected_severities = [s.get("fused_score", 0) for s in ranked if s.get("is_anomaly")]
        avg_severity = np.mean(affected_severities) if affected_severities else 0

        # Combined impact score (0-100)
        impact_score = (
            30 * blast_radius
            + 25 * max_severity
            + 20 * (1.0 if user_facing else 0.0)
            + 15 * min(downstream_count / max(total_services - 1, 1), 1.0)
            + 10 * avg_severity
        )
        impact_score = min(100, max(0, impact_score))

        # Label
        if impact_score >= 75:
            label = "CRITICAL"
        elif impact_score >= 50:
            label = "HIGH"
        elif impact_score >= 25:
            label = "MEDIUM"
        else:
            label = "LOW"

        # Severity description
        if impact_score >= 75:
            severity_desc = "Critical system failure with user-visible impact across multiple services."
        elif impact_score >= 50:
            severity_desc = "Significant degradation affecting core service functionality."
        elif impact_score >= 25:
            severity_desc = "Moderate service degradation with limited user impact."
        else:
            severity_desc = "Minor issue with minimal service impact."

        return {
            "score": round(impact_score, 1),
            "label": label,
            "blast_radius": round(blast_radius, 3),
            "affected_services": num_anomalous,
            "total_services": total_services,
            "user_facing": user_facing,
            "estimated_severity": severity_desc,
            "downstream_count": downstream_count,
            "max_severity_score": round(max_severity, 3),
            "avg_severity_score": round(avg_severity, 3),
        }

    def compute_all(self, analysis_result, causal_result=None,
                    pattern_result=None, graph_analyzer=None):
        """
        Compute both confidence and impact in one call.

        Returns:
            dict with 'confidence' and 'impact' sub-dicts
        """
        confidence = self.compute_confidence(
            analysis_result, causal_result, pattern_result
        )
        impact = self.compute_impact(analysis_result, graph_analyzer)

        return {
            "confidence": confidence,
            "impact": impact,
        }

    # ── Private Helpers ──────────────────────────────────────────

    def _compute_signal_agreement(self, root_cause):
        """
        How well do the three signal types (log, metric, graph) agree?

        If all three have high scores → strong agreement.
        If only one is high → weak agreement (could be noise).
        """
        log = root_cause.get("log_score", 0)
        metric = root_cause.get("metric_score", 0)
        graph = root_cause.get("graph_score", 0)

        scores = [log, metric, graph]
        active_signals = sum(1 for s in scores if s > 0.1)

        if active_signals == 0:
            return 0.0

        # Use the max signal as the base — if any signal is strong, confidence is high
        max_score = max(scores)
        mean_score = np.mean([s for s in scores if s > 0.1]) if active_signals > 0 else 0

        # Blend max and mean: reward strong signals, don't punish missing ones
        agreement = 0.6 * max_score + 0.4 * mean_score

        # Bonus for having multiple signals agree
        if active_signals >= 3:
            agreement = min(1.0, agreement * 1.4)
        elif active_signals >= 2:
            agreement = min(1.0, agreement * 1.2)

        return min(1.0, agreement)

    def _compute_causal_confirmation(self, root_cause, causal_result):
        """
        Did causal inference confirm the identified root cause?
        """
        if not causal_result:
            return 0.5  # neutral if not run

        causality_type = causal_result.get("causality_type", "uncertain")
        causal_root = causal_result.get("root_cause")
        engine_root = root_cause.get("service")

        # Base score from causality type
        type_scores = {
            "confirmed": 0.95,
            "probable": 0.85,
            "uncertain": 0.6,
            "single_service": 0.75,
        }
        base = type_scores.get(causality_type, 0.6)

        # Bonus if causal root matches engine root
        if causal_root and engine_root and causal_root == engine_root:
            base = min(1.0, base + 0.15)

        # Bonus for strong causal edges
        causal_edges = causal_result.get("causal_edges", [])
        if causal_edges:
            avg_strength = np.mean([e.get("strength", 0) for e in causal_edges])
            base = min(1.0, base + 0.1 * avg_strength)

        return base

    def _compute_evidence_depth(self, analysis_result):
        """
        How much evidence supports the conclusion?
        More evidence items = higher score (with diminishing returns).
        """
        explanation = analysis_result.get("explanation", {})
        chain = explanation.get("chain", {})

        if not chain:
            return 0.0

        # Count root cause evidence
        rc_evidence = chain.get("root_cause", {}).get("evidence", [])
        num_rc_evidence = len(rc_evidence)

        # Count impact evidence
        impacts = chain.get("impacts", [])
        num_impacts = len(impacts)
        total_impact_evidence = sum(len(imp.get("evidence", [])) for imp in impacts)

        # Total evidence items
        total = num_rc_evidence + total_impact_evidence

        # Diminishing returns: log scale
        # 1 evidence = 0.3, 3 evidence = 0.6, 6+ evidence = 0.85+
        if total == 0:
            return 0.1
        score = min(1.0, 0.3 + 0.2 * np.log1p(total))

        # Bonus for diverse evidence types
        evidence_types = set()
        for ev in rc_evidence:
            evidence_types.add(ev.get("type", ""))
        diversity_bonus = min(0.15, len(evidence_types) * 0.05)

        return min(1.0, score + diversity_bonus)

    def _compute_pattern_match(self, pattern_result):
        """
        Did the knowledge base find a similar past incident?
        """
        if not pattern_result:
            return 0.5  # neutral if not run

        matches = pattern_result.get("matches", [])
        if not matches:
            return 0.3  # no match = slightly less confident

        best = matches[0]
        similarity = best.get("similarity", 0)

        # Scale: 0.7+ similarity = strong match
        return min(1.0, similarity)

    def _generate_confidence_explanation(self, label, signal, causal,
                                         evidence, pattern):
        """Generate human-readable confidence explanation."""
        factors = []

        if signal >= 0.7:
            factors.append("all three signal types (logs, metrics, graph) strongly agree")
        elif signal >= 0.4:
            factors.append("moderate agreement across signal types")
        else:
            factors.append("signals show limited agreement")

        if causal >= 0.7:
            factors.append("causal analysis confirms the root cause")
        elif causal >= 0.5:
            factors.append("causal analysis partially supports the finding")

        if evidence >= 0.7:
            factors.append("supported by extensive evidence")
        elif evidence >= 0.4:
            factors.append("moderate evidence available")

        if pattern >= 0.7:
            factors.append("matches a known failure pattern with high similarity")
        elif pattern >= 0.5:
            factors.append("partially matches previous incidents")

        return f"{label} confidence — " + "; ".join(factors) + "."
