"""
Failure scenario definitions for synthetic data generation.
Each scenario defines: affected services, metric perturbations, log patterns, timing.
"""

import math
import random


class FailureScenario:
    """Base class for a failure scenario."""

    def __init__(self, scenario_id, name, description, root_cause_service,
                 affected_services, start_time, duration):
        self.scenario_id = scenario_id
        self.name = name
        self.description = description
        self.root_cause_service = root_cause_service
        self.affected_services = affected_services  # ordered by propagation
        self.start_time = start_time
        self.duration = duration

    def perturb_metric(self, service, metric_name, t, elapsed):
        """Return a multiplier/offset for the given metric at time t."""
        raise NotImplementedError

    def get_error_logs(self, service, elapsed):
        """Return list of error log messages for this service at this time."""
        raise NotImplementedError


class MemoryLeakScenario(FailureScenario):
    """
    Memory leak in Inventory Service → cascading GC pauses →
    timeout in Order Service → 5xx at API Gateway.
    """

    def __init__(self, start_time=100, duration=500):
        super().__init__(
            scenario_id="memory_leak",
            name="Memory Leak in Inventory Service",
            description=(
                "Inventory Service experiences a gradual memory leak causing GC overhead, "
                "leading to cascading timeouts in Order Service and 5xx errors at API Gateway."
            ),
            root_cause_service="inventory-service",
            affected_services=[
                ("inventory-service", 0),       # immediate
                ("inventory-db", 5),             # 5s delay — DB connections pile up
                ("order-service", 15),           # 15s delay — upstream timeouts
                ("notification-service", 20),    # 20s delay — order failures cascade
                ("api-gateway", 25),             # 25s delay — 5xx errors
            ],
            start_time=start_time,
            duration=duration,
        )

    def perturb_metric(self, service, metric_name, t, elapsed):
        if elapsed < 0:
            return 0.0
        progress = min(elapsed / self.duration, 1.0)

        if service == "inventory-service":
            if metric_name == "memory_percent":
                # Exponential ramp from ~45% to ~98%
                return 53.0 * (1 - math.exp(-3 * progress))
            elif metric_name == "cpu_percent":
                # GC overhead spikes
                if progress > 0.3:
                    return 40.0 * math.sin(elapsed * 0.5) ** 2 + 20.0 * progress
                return 5.0 * progress
            elif metric_name == "latency_ms":
                return 200.0 * progress ** 2
            elif metric_name == "error_rate":
                return 0.35 * max(0, progress - 0.4) / 0.6
        elif service == "order-service":
            prop_delay = 15
            if elapsed > prop_delay:
                local_progress = min((elapsed - prop_delay) / (self.duration - prop_delay), 1.0)
                if metric_name == "latency_ms":
                    return 500.0 * local_progress ** 1.5
                elif metric_name == "error_rate":
                    return 0.25 * local_progress
        elif service == "api-gateway":
            prop_delay = 25
            if elapsed > prop_delay:
                local_progress = min((elapsed - prop_delay) / (self.duration - prop_delay), 1.0)
                if metric_name == "error_rate":
                    return 0.34 * local_progress
                elif metric_name == "latency_ms":
                    return 300.0 * local_progress
        return 0.0

    def get_error_logs(self, service, elapsed):
        logs = []
        if elapsed < 0:
            return logs
        progress = min(elapsed / self.duration, 1.0)

        if service == "inventory-service":
            if progress > 0.2 and random.random() < 0.3:
                logs.append(("WARN", "High memory utilization detected: heap usage above 80%"))
            if progress > 0.4 and random.random() < 0.4:
                logs.append(("ERROR", "GC overhead limit exceeded — long pause detected"))
            if progress > 0.6 and random.random() < 0.5:
                logs.append(("ERROR", f"OutOfMemoryError: Java heap space — allocated {int(45 + 53 * progress)}%"))
            if progress > 0.8 and random.random() < 0.3:
                logs.append(("FATAL", "Service unresponsive — health check failed"))
        elif service == "order-service" and elapsed > 15:
            if random.random() < 0.3:
                logs.append(("WARN", "Upstream timeout: inventory-service — response exceeded 5000ms"))
            if progress > 0.5 and random.random() < 0.2:
                logs.append(("ERROR", "Failed to process order: inventory check timed out"))
        elif service == "api-gateway" and elapsed > 25:
            if random.random() < 0.25:
                logs.append(("ERROR", "502 Bad Gateway — upstream service unavailable"))
            if random.random() < 0.15:
                logs.append(("ERROR", "Circuit breaker OPEN for order-service"))
        return logs


class DBConnectionExhaustionScenario(FailureScenario):
    """
    DB connection pool exhaustion in User DB → Auth Service failures →
    all authenticated endpoints fail.
    """

    def __init__(self, start_time=100, duration=500):
        super().__init__(
            scenario_id="db_connection_exhaustion",
            name="DB Connection Pool Exhaustion",
            description=(
                "User DB connection pool becomes exhausted causing Auth Service to fail, "
                "breaking all authenticated API endpoints."
            ),
            root_cause_service="user-db",
            affected_services=[
                ("user-db", 0),
                ("auth-service", 8),
                ("api-gateway", 18),
            ],
            start_time=start_time,
            duration=duration,
        )

    def perturb_metric(self, service, metric_name, t, elapsed):
        if elapsed < 0:
            return 0.0
        progress = min(elapsed / self.duration, 1.0)

        if service == "user-db":
            if metric_name == "connections":
                # Step function — pool fills up
                return 95.0 * min(1.0, progress * 3)
            elif metric_name == "latency_ms":
                return 1000.0 * progress ** 2
            elif metric_name == "cpu_percent":
                return 30.0 * progress
        elif service == "auth-service" and elapsed > 8:
            local_p = min((elapsed - 8) / (self.duration - 8), 1.0)
            if metric_name == "error_rate":
                return 0.8 * local_p
            elif metric_name == "latency_ms":
                return 3000.0 * local_p
        elif service == "api-gateway" and elapsed > 18:
            local_p = min((elapsed - 18) / (self.duration - 18), 1.0)
            if metric_name == "error_rate":
                return 0.5 * local_p
        return 0.0

    def get_error_logs(self, service, elapsed):
        logs = []
        if elapsed < 0:
            return logs
        progress = min(elapsed / self.duration, 1.0)

        if service == "user-db":
            if progress > 0.2 and random.random() < 0.3:
                logs.append(("WARN", "Connection pool utilization above 85%"))
            if progress > 0.5 and random.random() < 0.4:
                logs.append(("ERROR", "Connection pool exhausted — no available connections"))
            if progress > 0.7 and random.random() < 0.3:
                logs.append(("ERROR", "Connection timeout after 30000ms — all slots occupied"))
        elif service == "auth-service" and elapsed > 8:
            if random.random() < 0.3:
                logs.append(("ERROR", "Failed to authenticate user: database connection timeout"))
            if random.random() < 0.2:
                logs.append(("ERROR", "Auth token validation failed — DB unreachable"))
        elif service == "api-gateway" and elapsed > 18:
            if random.random() < 0.25:
                logs.append(("ERROR", "401 Unauthorized — auth-service unavailable"))
        return logs


class NetworkPartitionScenario(FailureScenario):
    """
    Network partition between Payment Service and Payment Gateway →
    payment timeouts → order failures.
    """

    def __init__(self, start_time=100, duration=500):
        super().__init__(
            scenario_id="network_partition",
            name="Network Partition — Payment Gateway",
            description=(
                "Network partition isolates Payment Service from Payment Gateway, "
                "causing payment timeouts and order processing failures."
            ),
            root_cause_service="payment-gateway",
            affected_services=[
                ("payment-gateway", 0),
                ("payment-service", 3),
                ("order-service", 12),
                ("api-gateway", 20),
            ],
            start_time=start_time,
            duration=duration,
        )

    def perturb_metric(self, service, metric_name, t, elapsed):
        if elapsed < 0:
            return 0.0
        progress = min(elapsed / self.duration, 1.0)

        if service == "payment-gateway":
            if metric_name == "error_rate":
                return 0.95 if progress > 0.1 else 0.0  # nearly total failure
            elif metric_name == "latency_ms":
                return 10000.0 if progress > 0.1 else 0.0  # timeout
        elif service == "payment-service" and elapsed > 3:
            local_p = min((elapsed - 3) / (self.duration - 3), 1.0)
            if metric_name == "error_rate":
                return 0.7 * local_p
            elif metric_name == "latency_ms":
                return 8000.0 * local_p
        elif service == "order-service" and elapsed > 12:
            local_p = min((elapsed - 12) / (self.duration - 12), 1.0)
            if metric_name == "error_rate":
                return 0.3 * local_p
        return 0.0

    def get_error_logs(self, service, elapsed):
        logs = []
        if elapsed < 0:
            return logs
        progress = min(elapsed / self.duration, 1.0)

        if service == "payment-gateway" and progress > 0.1:
            if random.random() < 0.4:
                logs.append(("ERROR", "Connection refused — network unreachable"))
            if random.random() < 0.3:
                logs.append(("FATAL", "Health check failed — no route to host"))
        elif service == "payment-service" and elapsed > 3:
            if random.random() < 0.35:
                logs.append(("ERROR", "Payment processing failed: gateway timeout after 10000ms"))
            if random.random() < 0.2:
                logs.append(("WARN", "Retry attempt 3/3 for payment-gateway — all failed"))
        elif service == "order-service" and elapsed > 12:
            if random.random() < 0.25:
                logs.append(("ERROR", "Order completion failed: payment service returned error"))
        return logs


class CPUSpikeScenario(FailureScenario):
    """
    CPU spike in Search Service → cache misses → latency explosion.
    """

    def __init__(self, start_time=100, duration=500):
        super().__init__(
            scenario_id="cpu_spike",
            name="CPU Spike in Search Service",
            description=(
                "Runaway query causes CPU spike in Search Service, leading to cache invalidation "
                "and a latency explosion across search-dependent paths."
            ),
            root_cause_service="search-service",
            affected_services=[
                ("search-service", 0),
                ("cache-redis", 5),
                ("api-gateway", 15),
            ],
            start_time=start_time,
            duration=duration,
        )

    def perturb_metric(self, service, metric_name, t, elapsed):
        if elapsed < 0:
            return 0.0
        progress = min(elapsed / self.duration, 1.0)

        if service == "search-service":
            if metric_name == "cpu_percent":
                # Sudden spike then sustained
                return 70.0 * (1 - math.exp(-5 * progress))
            elif metric_name == "latency_ms":
                return 2000.0 * progress ** 1.5
            elif metric_name == "memory_percent":
                return 20.0 * progress
        elif service == "cache-redis" and elapsed > 5:
            local_p = min((elapsed - 5) / (self.duration - 5), 1.0)
            if metric_name == "memory_percent":
                return 30.0 * local_p  # cache churn
            elif metric_name == "cpu_percent":
                return 25.0 * local_p
        elif service == "api-gateway" and elapsed > 15:
            local_p = min((elapsed - 15) / (self.duration - 15), 1.0)
            if metric_name == "latency_ms":
                return 500.0 * local_p
        return 0.0

    def get_error_logs(self, service, elapsed):
        logs = []
        if elapsed < 0:
            return logs
        progress = min(elapsed / self.duration, 1.0)

        if service == "search-service":
            if progress > 0.1 and random.random() < 0.3:
                logs.append(("WARN", "CPU utilization critical: above 90%"))
            if progress > 0.3 and random.random() < 0.25:
                logs.append(("ERROR", "Query execution timeout — killing long-running query"))
            if progress > 0.5 and random.random() < 0.2:
                logs.append(("ERROR", "Thread pool exhausted — rejecting new requests"))
        elif service == "cache-redis" and elapsed > 5:
            if random.random() < 0.2:
                logs.append(("WARN", "Cache eviction rate elevated — memory pressure"))
            if random.random() < 0.15:
                logs.append(("WARN", "Cache miss ratio above 60%"))
        return logs


# ── Registry ──────────────────────────────────────────────────────

SCENARIO_REGISTRY = {
    "memory_leak": MemoryLeakScenario,
    "db_connection_exhaustion": DBConnectionExhaustionScenario,
    "network_partition": NetworkPartitionScenario,
    "cpu_spike": CPUSpikeScenario,
}


def get_scenario(scenario_id, **kwargs):
    """Instantiate a failure scenario by ID."""
    if scenario_id not in SCENARIO_REGISTRY:
        raise ValueError(f"Unknown scenario: {scenario_id}")
    return SCENARIO_REGISTRY[scenario_id](**kwargs)


def list_scenarios():
    """Return summary info for all available scenarios."""
    results = []
    for sid, cls in SCENARIO_REGISTRY.items():
        instance = cls()
        results.append({
            "id": instance.scenario_id,
            "name": instance.name,
            "description": instance.description,
            "root_cause": instance.root_cause_service,
            "affected_services": [s for s, _ in instance.affected_services],
        })
    return results
