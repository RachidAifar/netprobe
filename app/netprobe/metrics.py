"""Prometheus metrics. Each app instance uses its own registry so tests stay isolated."""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

from .probes import ProbeResult

LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5)


class ProbeMetrics:
    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or CollectorRegistry()
        labels = ("target", "type")
        self.up = Gauge(
            "netprobe_target_up", "1 if the last probe succeeded, else 0.", labels, registry=self.registry
        )
        self.duration = Histogram(
            "netprobe_probe_duration_seconds",
            "Time taken by each probe.",
            labels,
            buckets=LATENCY_BUCKETS,
            registry=self.registry,
        )
        self.failures = Counter(
            "netprobe_probe_failures_total", "Failed probes.", labels, registry=self.registry
        )
        self.rounds = Counter("netprobe_rounds_total", "Completed probe rounds.", registry=self.registry)

    def record(self, result: ProbeResult) -> None:
        self.up.labels(result.target, result.type).set(1 if result.up else 0)
        self.duration.labels(result.target, result.type).observe(result.duration_seconds)
        if not result.up:
            self.failures.labels(result.target, result.type).inc()
