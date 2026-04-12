"""Observability metrics for the ComfyUI Comfy Cozy Agent.

Pure stdlib + threading. No external dependencies.
Thread-safe counters, histograms, and gauges with a global registry.
"""

import bisect
import math
import threading
from typing import Sequence

# ---------------------------------------------------------------------------
# Default histogram buckets
# ---------------------------------------------------------------------------

DEFAULT_BUCKETS: tuple[float, ...] = (
    0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0,
)


# ---------------------------------------------------------------------------
# Metric types
# ---------------------------------------------------------------------------


class Counter:
    """Thread-safe monotonic counter with label support."""

    def __init__(self, name: str, labels: Sequence[str] = ()) -> None:
        self.name = name
        self.labels = tuple(labels)
        self._values: dict[tuple[str, ...], int] = {}
        self._lock = threading.Lock()

    def inc(self, amount: int = 1, **label_values: str) -> None:
        """Increment the counter for the given label combination."""
        key = self._key(label_values)
        with self._lock:
            self._values[key] = self._values.get(key, 0) + amount

    def get(self) -> dict[tuple[str, ...], int]:
        """Return a snapshot of all label-combo -> count mappings."""
        with self._lock:
            return dict(self._values)

    def reset(self) -> None:
        """Clear all values. For testing."""
        with self._lock:
            self._values.clear()

    def _key(self, label_values: dict[str, str]) -> tuple[str, ...]:
        return tuple(label_values.get(lb, "") for lb in self.labels)


class Histogram:
    """Thread-safe histogram with configurable buckets."""

    def __init__(
        self,
        name: str,
        labels: Sequence[str] = (),
        buckets: Sequence[float] = DEFAULT_BUCKETS,
    ) -> None:
        self.name = name
        self.labels = tuple(labels)
        self.buckets = tuple(sorted(buckets))
        self._observations: dict[tuple[str, ...], list[float]] = {}
        self._lock = threading.Lock()

    def observe(self, value: float, **label_values: str) -> None:
        """Record an observation for the given label combination."""
        key = self._key(label_values)
        with self._lock:
            if key not in self._observations:
                self._observations[key] = []
            self._observations[key].append(value)

    def percentile(self, p: float, **label_values: str) -> float:
        """Compute the p-th percentile (0-100) for a label combination.

        Returns NaN if no observations exist.
        """
        key = self._key(label_values)
        with self._lock:
            obs = list(self._observations.get(key, []))
        if not obs:
            return float("nan")
        obs.sort()
        k = (p / 100.0) * (len(obs) - 1)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return obs[int(k)]
        return obs[f] * (c - k) + obs[c] * (k - f)

    def get(self) -> dict:
        """Return a snapshot: {label_key: {count, sum, buckets, p50, p99}}."""
        with self._lock:
            snapshot = {k: list(v) for k, v in self._observations.items()}
        result: dict = {}
        for key, obs in snapshot.items():
            obs_sorted = sorted(obs)
            bucket_counts: dict[str, int] = {}
            for b in self.buckets:
                bucket_counts[str(b)] = bisect.bisect_right(obs_sorted, b)
            bucket_counts["+Inf"] = len(obs_sorted)
            result[key] = {
                "count": len(obs),
                "sum": sum(obs),
                "buckets": bucket_counts,
            }
        return result

    def reset(self) -> None:
        """Clear all observations. For testing."""
        with self._lock:
            self._observations.clear()

    def _key(self, label_values: dict[str, str]) -> tuple[str, ...]:
        return tuple(label_values.get(lb, "") for lb in self.labels)


class Gauge:
    """Thread-safe gauge (can go up and down)."""

    def __init__(self, name: str, labels: Sequence[str] = ()) -> None:
        self.name = name
        self.labels = tuple(labels)
        self._values: dict[tuple[str, ...], float] = {}
        self._lock = threading.Lock()

    def set(self, value: float, **label_values: str) -> None:
        """Set the gauge to a specific value."""
        key = self._key(label_values)
        with self._lock:
            self._values[key] = value

    def inc(self, amount: float = 1.0, **label_values: str) -> None:
        """Increment the gauge."""
        key = self._key(label_values)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def dec(self, amount: float = 1.0, **label_values: str) -> None:
        """Decrement the gauge."""
        key = self._key(label_values)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) - amount

    def get(self) -> dict[tuple[str, ...], float]:
        """Return a snapshot of all label-combo -> value mappings."""
        with self._lock:
            return dict(self._values)

    def reset(self) -> None:
        """Clear all values. For testing."""
        with self._lock:
            self._values.clear()

    def _key(self, label_values: dict[str, str]) -> tuple[str, ...]:
        return tuple(label_values.get(lb, "") for lb in self.labels)


# ---------------------------------------------------------------------------
# Registry (singleton)
# ---------------------------------------------------------------------------


class MetricsRegistry:
    """Singleton registry for all metrics."""

    _instance: "MetricsRegistry | None" = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "MetricsRegistry":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._metrics: dict[str, Counter | Histogram | Gauge] = {}
                    inst._lock = threading.Lock()
                    cls._instance = inst
        return cls._instance

    def register(self, metric: Counter | Histogram | Gauge) -> None:
        """Register a metric by name."""
        with self._lock:
            self._metrics[metric.name] = metric

    def get_metric(self, name: str) -> Counter | Histogram | Gauge | None:
        """Retrieve a metric by name."""
        with self._lock:
            return self._metrics.get(name)

    def get_all(self) -> dict:
        """Return a JSON-serializable snapshot of all metrics."""
        with self._lock:
            metrics = dict(self._metrics)
        result: dict = {}
        for name, metric in metrics.items():
            data = metric.get()
            if isinstance(metric, Counter):
                # Convert tuple keys to string for JSON
                result[name] = {
                    "type": "counter",
                    "values": {
                        ",".join(k) if k else "__total__": v
                        for k, v in data.items()
                    },
                }
            elif isinstance(metric, Histogram):
                serialized: dict = {}
                for k, v in data.items():
                    key_str = ",".join(k) if k else "__total__"
                    serialized[key_str] = v
                result[name] = {"type": "histogram", "values": serialized}
            elif isinstance(metric, Gauge):
                result[name] = {
                    "type": "gauge",
                    "values": {
                        ",".join(k) if k else "__total__": v
                        for k, v in data.items()
                    },
                }
        return result

    def reset(self) -> None:
        """Reset all registered metrics. For testing."""
        with self._lock:
            for metric in self._metrics.values():
                metric.reset()


# ---------------------------------------------------------------------------
# Pre-registered metrics
# ---------------------------------------------------------------------------

_registry = MetricsRegistry()

tool_call_total = Counter("tool_call_total", labels=["tool_name", "status"])
tool_call_duration_seconds = Histogram(
    "tool_call_duration_seconds", labels=["tool_name"]
)
llm_call_total = Counter("llm_call_total", labels=["provider", "status"])
llm_call_duration_seconds = Histogram(
    "llm_call_duration_seconds", labels=["provider"]
)
circuit_breaker_transitions = Counter(
    "circuit_breaker_transitions", labels=["from_state", "to_state"]
)
session_active = Gauge("session_active", labels=[])
pipeline_runs_total = Counter("pipeline_runs_total", labels=["stage_reached"])

for _m in (
    tool_call_total,
    tool_call_duration_seconds,
    llm_call_total,
    llm_call_duration_seconds,
    circuit_breaker_transitions,
    session_active,
    pipeline_runs_total,
):
    _registry.register(_m)


# ---------------------------------------------------------------------------
# Export functions
# ---------------------------------------------------------------------------


def get_metrics() -> dict:
    """Return a JSON-serializable snapshot of all metrics."""
    return _registry.get_all()


def get_metrics_prometheus() -> str:
    """Return metrics in Prometheus text exposition format."""
    lines: list[str] = []
    all_data = _registry.get_all()

    for name, info in sorted(all_data.items()):
        mtype = info["type"]
        values = info["values"]

        if mtype == "counter":
            lines.append(f"# HELP {name} Counter metric")
            lines.append(f"# TYPE {name} counter")
            for label_key, count in sorted(values.items()):
                label_str = _format_prom_labels(name, label_key)
                lines.append(f"{name}{label_str} {count}")

        elif mtype == "histogram":
            lines.append(f"# HELP {name} Histogram metric")
            lines.append(f"# TYPE {name} histogram")
            for label_key, hdata in sorted(values.items()):
                base_labels = _format_prom_labels(name, label_key)
                for bucket_le, bucket_count in sorted(
                    hdata.get("buckets", {}).items(),
                    key=lambda x: (
                        float("inf") if x[0] == "+Inf" else float(x[0])
                    ),
                ):
                    le_label = _inject_le(base_labels, bucket_le)
                    lines.append(
                        f"{name}_bucket{le_label} {bucket_count}"
                    )
                lines.append(
                    f"{name}_count{base_labels} {hdata.get('count', 0)}"
                )
                lines.append(
                    f"{name}_sum{base_labels} {hdata.get('sum', 0)}"
                )

        elif mtype == "gauge":
            lines.append(f"# HELP {name} Gauge metric")
            lines.append(f"# TYPE {name} gauge")
            for label_key, val in sorted(values.items()):
                label_str = _format_prom_labels(name, label_key)
                lines.append(f"{name}{label_str} {val}")

    return "\n".join(lines) + "\n" if lines else ""


def _format_prom_labels(metric_name: str, label_key: str) -> str:
    """Format a label key string into Prometheus label format."""
    if label_key == "__total__":
        return ""
    # Find the metric to get label names
    metric = _registry.get_metric(metric_name)
    if metric is None or not metric.labels:
        return ""
    parts = label_key.split(",")
    pairs: list[str] = []
    for i, lname in enumerate(metric.labels):
        val = parts[i] if i < len(parts) else ""
        pairs.append(f'{lname}="{val}"')
    return "{" + ",".join(pairs) + "}"


def _inject_le(base_labels: str, le_value: str) -> str:
    """Inject le= into a label string for histogram buckets."""
    le_part = f'le="{le_value}"'
    if not base_labels:
        return "{" + le_part + "}"
    # Insert le before the closing brace
    return base_labels[:-1] + "," + le_part + "}"
