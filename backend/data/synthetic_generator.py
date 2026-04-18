"""
Synthetic data generator for microservice telemetry.
Produces logs, metrics, and dependency graph data with injected failure scenarios.
"""

import json
import math
import os
import random
import time
import uuid
from datetime import datetime, timedelta

import numpy as np

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from data.scenarios import get_scenario, list_scenarios


# ── Log Templates ─────────────────────────────────────────────────

NORMAL_LOG_TEMPLATES = {
    "api-gateway": [
        "Received {method} request to {path} from {ip}",
        "Request processed successfully in {latency}ms",
        "Rate limiter: {count} requests in window",
        "Routing request to upstream service: {service}",
        "TLS handshake completed for client {ip}",
        "Health check passed — all upstreams healthy",
        "Load balancer selected backend: {service}:{port}",
    ],
    "auth-service": [
        "User {user_id} authenticated successfully",
        "Token generated for user {user_id} — expires in 3600s",
        "Token validation successful for session {session_id}",
        "Password hash verification completed in {latency}ms",
        "OAuth2 callback processed for provider {provider}",
        "Session refreshed for user {user_id}",
    ],
    "user-db": [
        "Query executed in {latency}ms: SELECT * FROM users WHERE id = {user_id}",
        "Connection pool status: {active}/{max} active connections",
        "Index scan on users.email completed in {latency}ms",
        "Transaction committed: update user profile {user_id}",
        "Slow query detected: {latency}ms — {query}",
    ],
    "order-service": [
        "Order {order_id} created by user {user_id}",
        "Order {order_id} — inventory check initiated",
        "Order {order_id} — payment processing started",
        "Order {order_id} completed successfully — total: ${amount}",
        "Order queue depth: {count} pending orders",
        "Notification dispatched for order {order_id}",
    ],
    "inventory-service": [
        "Inventory check for SKU {sku}: {quantity} available",
        "Stock reserved: {quantity} units of SKU {sku}",
        "Inventory sync completed — {count} items updated",
        "Warehouse {warehouse} stock level: {quantity} units",
        "Reorder alert: SKU {sku} below threshold ({quantity} remaining)",
    ],
    "inventory-db": [
        "Query executed in {latency}ms: SELECT stock FROM inventory WHERE sku = {sku}",
        "Batch update: {count} inventory records modified",
        "Connection pool: {active}/{max} connections active",
        "Table lock acquired for inventory update",
    ],
    "payment-service": [
        "Payment {payment_id} initiated — amount: ${amount}",
        "Payment {payment_id} authorized by gateway",
        "Payment {payment_id} captured successfully",
        "Refund processed for payment {payment_id}: ${amount}",
        "Payment retry scheduled: attempt {attempt}/3",
    ],
    "payment-gateway": [
        "Transaction {txn_id} received — processing",
        "Transaction {txn_id} approved — auth code: {auth_code}",
        "Settlement batch {batch_id} processed: {count} transactions",
        "Fraud check passed for transaction {txn_id}",
    ],
    "notification-service": [
        "Email sent to {email}: order confirmation {order_id}",
        "SMS dispatched to {phone}: delivery update",
        "Push notification sent to device {device_id}",
        "Notification queue depth: {count} pending",
    ],
    "search-service": [
        "Search query '{query}' returned {count} results in {latency}ms",
        "Index refreshed: {count} documents updated",
        "Cache hit for query '{query}' — returning cached results",
        "Full-text search completed in {latency}ms",
        "Search suggestions generated for prefix '{prefix}'",
    ],
    "cache-redis": [
        "Cache GET {key}: {result}",
        "Cache SET {key}: TTL={ttl}s",
        "Cache eviction: {count} keys removed (maxmemory policy)",
        "Memory usage: {memory_mb}MB / {max_mb}MB",
        "Connected clients: {count}",
    ],
}


def _fill_template(template):
    """Fill placeholders in a log template with random realistic values."""
    replacements = {
        "{method}": random.choice(["GET", "POST", "PUT", "DELETE"]),
        "{path}": random.choice(["/api/orders", "/api/users", "/api/search", "/api/auth", "/api/inventory"]),
        "{ip}": f"{random.randint(10,192)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
        "{latency}": str(random.randint(1, 500)),
        "{count}": str(random.randint(1, 1000)),
        "{service}": random.choice(config.SERVICES),
        "{port}": str(random.choice([8080, 8081, 8082, 3000, 5432])),
        "{user_id}": f"usr-{uuid.uuid4().hex[:8]}",
        "{session_id}": f"sess-{uuid.uuid4().hex[:12]}",
        "{provider}": random.choice(["google", "github", "okta"]),
        "{order_id}": f"ord-{uuid.uuid4().hex[:8]}",
        "{amount}": f"{random.uniform(10, 500):.2f}",
        "{sku}": f"SKU-{random.randint(1000, 9999)}",
        "{quantity}": str(random.randint(0, 500)),
        "{warehouse}": random.choice(["US-EAST-1", "US-WEST-2", "EU-WEST-1"]),
        "{payment_id}": f"pay-{uuid.uuid4().hex[:8]}",
        "{attempt}": str(random.randint(1, 3)),
        "{txn_id}": f"txn-{uuid.uuid4().hex[:10]}",
        "{auth_code}": f"{random.randint(100000, 999999)}",
        "{batch_id}": f"batch-{random.randint(1, 100)}",
        "{email}": f"user{random.randint(1,999)}@example.com",
        "{phone}": f"+1{random.randint(2000000000, 9999999999)}",
        "{device_id}": f"dev-{uuid.uuid4().hex[:8]}",
        "{query}": random.choice(["laptop", "headphones", "keyboard", "monitor", "mouse"]),
        "{prefix}": random.choice(["lap", "hea", "key", "mon"]),
        "{key}": f"cache:{random.choice(['user', 'product', 'session'])}:{random.randint(1,10000)}",
        "{result}": random.choice(["HIT", "MISS"]),
        "{ttl}": str(random.choice([300, 600, 1800, 3600])),
        "{memory_mb}": str(random.randint(100, 900)),
        "{max_mb}": "1024",
        "{active}": str(random.randint(1, 50)),
        "{max}": "50",
    }
    result = template
    for k, v in replacements.items():
        result = result.replace(k, v)
    return result


# ── Baseline Metric Generators ────────────────────────────────────

def _baseline_metrics(service, t):
    """Generate normal baseline metrics for a service at time t."""
    # Slight sinusoidal daily pattern + random noise
    phase = (t % 86400) / 86400 * 2 * math.pi
    load_factor = 0.5 + 0.3 * math.sin(phase) + random.gauss(0, 0.05)
    load_factor = max(0.1, min(1.0, load_factor))

    base = {
        "api-gateway":          {"cpu": 25, "mem": 40, "lat": 50,  "err": 0.001, "conn": 20},
        "auth-service":         {"cpu": 15, "mem": 35, "lat": 30,  "err": 0.002, "conn": 10},
        "user-db":              {"cpu": 20, "mem": 50, "lat": 15,  "err": 0.001, "conn": 15},
        "order-service":        {"cpu": 30, "mem": 45, "lat": 80,  "err": 0.003, "conn": 25},
        "inventory-service":    {"cpu": 20, "mem": 45, "lat": 40,  "err": 0.002, "conn": 12},
        "inventory-db":         {"cpu": 15, "mem": 55, "lat": 10,  "err": 0.001, "conn": 10},
        "payment-service":      {"cpu": 18, "mem": 38, "lat": 100, "err": 0.005, "conn": 8},
        "payment-gateway":      {"cpu": 10, "mem": 30, "lat": 120, "err": 0.003, "conn": 5},
        "notification-service": {"cpu": 12, "mem": 30, "lat": 25,  "err": 0.001, "conn": 6},
        "search-service":       {"cpu": 35, "mem": 50, "lat": 60,  "err": 0.002, "conn": 18},
        "cache-redis":          {"cpu": 10, "mem": 60, "lat": 2,   "err": 0.0005,"conn": 30},
    }

    b = base.get(service, {"cpu": 20, "mem": 40, "lat": 50, "err": 0.002, "conn": 10})

    return {
        "cpu_percent":    max(0, min(100, b["cpu"] * load_factor + random.gauss(0, 2))),
        "memory_percent": max(0, min(100, b["mem"] + random.gauss(0, 1.5))),
        "latency_ms":     max(1, b["lat"] * load_factor + random.gauss(0, b["lat"] * 0.1)),
        "error_rate":     max(0, min(1,   b["err"] + random.gauss(0, b["err"] * 0.3))),
        "connections":    max(0, b["conn"] * load_factor + random.gauss(0, 2)),
    }


# ── Main Generator ────────────────────────────────────────────────

def generate_dataset(scenario_id=None, duration=None, seed=42):
    """
    Generate a complete synthetic dataset.

    Returns dict with keys: 'logs', 'metrics', 'graph', 'scenario_info'
    """
    random.seed(seed)
    np.random.seed(seed)

    duration = duration or config.SYNTHETIC_DURATION_SECONDS
    scenario = get_scenario(scenario_id) if scenario_id else None

    # Use current time so logs show realistic "just happened" timestamps
    base_time = datetime.now() - timedelta(seconds=duration or config.SYNTHETIC_DURATION_SECONDS)

    # ── Build dependency graph ────────────────────────────────────
    graph = {
        "nodes": [{"id": s, "type": _service_type(s)} for s in config.SERVICES],
        "edges": [],
    }
    for src, targets in config.DEPENDENCIES.items():
        for tgt in targets:
            graph["edges"].append({"source": src, "target": tgt})

    # ── Generate time-series metrics ──────────────────────────────
    metrics = {service: [] for service in config.SERVICES}
    for t in range(duration):
        timestamp = (base_time + timedelta(seconds=t)).isoformat()
        for service in config.SERVICES:
            m = _baseline_metrics(service, t)

            # Apply failure perturbation
            if scenario:
                elapsed = t - scenario.start_time
                for metric_name in m:
                    delta = scenario.perturb_metric(service, metric_name, t, elapsed)
                    m[metric_name] = max(0, min(
                        100 if "percent" in metric_name or metric_name == "error_rate" else 99999,
                        m[metric_name] + delta
                    ))

            m["timestamp"] = timestamp
            m["service"] = service
            metrics[service].append(m)

    # ── Generate logs ─────────────────────────────────────────────
    logs = []
    for t in range(duration):
        timestamp = (base_time + timedelta(seconds=t)).isoformat()
        for service in config.SERVICES:
            # Normal logs (variable frequency)
            num_normal = random.randint(0, 3)
            templates = NORMAL_LOG_TEMPLATES.get(service, [])
            for _ in range(num_normal):
                if templates:
                    msg = _fill_template(random.choice(templates))
                    logs.append({
                        "timestamp": timestamp,
                        "service": service,
                        "level": random.choices(["INFO", "DEBUG", "WARN"], weights=[0.7, 0.2, 0.1])[0],
                        "message": msg,
                        "trace_id": f"trace-{uuid.uuid4().hex[:12]}",
                    })

            # Scenario error logs
            if scenario:
                elapsed = t - scenario.start_time
                error_logs = scenario.get_error_logs(service, elapsed)
                for level, msg in error_logs:
                    logs.append({
                        "timestamp": timestamp,
                        "service": service,
                        "level": level,
                        "message": msg,
                        "trace_id": f"trace-{uuid.uuid4().hex[:12]}",
                    })

    # Sort logs by time
    logs.sort(key=lambda x: x["timestamp"])

    # ── Scenario metadata ─────────────────────────────────────────
    scenario_info = None
    if scenario:
        scenario_info = {
            "id": scenario.scenario_id,
            "name": scenario.name,
            "description": scenario.description,
            "root_cause_service": scenario.root_cause_service,
            "affected_services": [s for s, _ in scenario.affected_services],
            "start_time": scenario.start_time,
            "duration": scenario.duration,
        }

    return {
        "logs": logs,
        "metrics": metrics,
        "graph": graph,
        "scenario_info": scenario_info,
        "duration_seconds": duration,
        "num_services": len(config.SERVICES),
    }


def _service_type(service):
    """Classify service type for graph visualization."""
    if "db" in service or "redis" in service:
        return "datastore"
    if "gateway" in service:
        return "gateway"
    return "service"


def save_dataset(dataset, output_dir=None):
    """Save generated dataset to JSON files."""
    output_dir = output_dir or config.DATA_DIR
    os.makedirs(output_dir, exist_ok=True)

    with open(os.path.join(output_dir, "logs.json"), "w") as f:
        json.dump(dataset["logs"], f, indent=2)

    with open(os.path.join(output_dir, "metrics.json"), "w") as f:
        json.dump(dataset["metrics"], f, indent=2)

    with open(os.path.join(output_dir, "graph.json"), "w") as f:
        json.dump(dataset["graph"], f, indent=2)

    if dataset["scenario_info"]:
        with open(os.path.join(output_dir, "scenario_info.json"), "w") as f:
            json.dump(dataset["scenario_info"], f, indent=2)

    print(f"Dataset saved to {output_dir}")
    print(f"  Logs: {len(dataset['logs'])} entries")
    total_metrics = sum(len(v) for v in dataset["metrics"].values())
    print(f"  Metrics: {total_metrics} data points ({dataset['num_services']} services)")
    print(f"  Graph: {len(dataset['graph']['nodes'])} nodes, {len(dataset['graph']['edges'])} edges")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate synthetic microservice data")
    parser.add_argument("--scenario", type=str, default="memory_leak",
                        choices=["memory_leak", "db_connection_exhaustion", "network_partition", "cpu_spike"],
                        help="Failure scenario to inject")
    parser.add_argument("--duration", type=int, default=600, help="Duration in seconds")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    ds = generate_dataset(scenario_id=args.scenario, duration=args.duration, seed=args.seed)
    save_dataset(ds)
