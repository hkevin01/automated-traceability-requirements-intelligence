"""
ID: ATRI-METRICS-001
Purpose: In-process Prometheus-compatible metrics registry for ATRI.
Requirement: Expose request counts, latencies, and domain counters via
             GET /metrics in Prometheus text exposition format.
Rationale: Observability is mandatory for SRE-style production operation.
           Using a lightweight in-process registry avoids a hard prometheus_client
           dependency; the output format is compatible with Prometheus scraping.
Inputs: Increments called from FastAPI middleware and service layer.
Outputs: Prometheus text format string via to_text_format().
Preconditions: None - registry is a module-level singleton.
Side Effects: Maintains in-memory counters; resets on process restart.
Failure modes: Thread-safe via threading.Lock; no file I/O.
Constraints: Counter only (no histograms/gauges) - sufficient for basic SRE dashboards.
Verification: tests/test_metrics.py
References: Prometheus data model - https://prometheus.io/docs/concepts/data_model/
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class MetricsRegistry:
    """
    ID: ATRI-METRICS-002
    Purpose: Thread-safe counter and summary registry in Prometheus text format.
    Side Effects: All operations acquire a lock; lock held briefly.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, float] = defaultdict(float)
        self._histograms: dict[str, list[float]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Counter
    # ------------------------------------------------------------------

    def increment(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """
        ID: ATRI-METRICS-003
        Purpose: Increment a named counter by value.
        Inputs: name - metric name; value - increment amount; labels - optional tag dict.
        Side Effects: Updates _counters dict under lock.
        """
        key = _label_key(name, labels)
        with self._lock:
            self._counters[key] += value

    def counter_value(self, name: str, labels: dict[str, str] | None = None) -> float:
        """Return current value of a named counter (0 if not yet set)."""
        key = _label_key(name, labels)
        with self._lock:
            return self._counters.get(key, 0.0)

    # ------------------------------------------------------------------
    # Histogram (stores raw observations for p50/p95/p99)
    # ------------------------------------------------------------------

    def observe(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """
        ID: ATRI-METRICS-004
        Purpose: Record a raw latency/size observation for histogram summary.
        Inputs: name - metric name; value - observed value (e.g. seconds).
        Side Effects: Appends to in-memory list; capped at 10000 observations.
        """
        key = _label_key(name, labels)
        with self._lock:
            obs = self._histograms[key]
            obs.append(value)
            if len(obs) > 10_000:
                del obs[:5_000]  # drop oldest half

    def summary(self, name: str, labels: dict[str, str] | None = None) -> dict:
        """Return {count, sum, p50, p95, p99} for an observation series."""
        key = _label_key(name, labels)
        with self._lock:
            obs = sorted(self._histograms.get(key, []))
        if not obs:
            return {"count": 0, "sum": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}
        n = len(obs)
        return {
            "count": n,
            "sum": round(sum(obs), 6),
            "p50": _percentile(obs, 50),
            "p95": _percentile(obs, 95),
            "p99": _percentile(obs, 99),
        }

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def to_text_format(self) -> str:
        """
        ID: ATRI-METRICS-005
        Purpose: Serialise all metrics to Prometheus text exposition format.
        Outputs: UTF-8 string ending with a newline; ready for HTTP response.
        References: https://prometheus.io/docs/instrumenting/exposition_formats/
        """
        lines: list[str] = []
        with self._lock:
            counters_copy = dict(self._counters)
            hist_copy = {k: list(v) for k, v in self._histograms.items()}

        for key, value in sorted(counters_copy.items()):
            name, labels_str = _parse_key(key)
            help_line = f"# HELP {name} ATRI counter"
            type_line = f"# TYPE {name} counter"
            metric_line = f"{name}{labels_str} {value}"
            lines += [help_line, type_line, metric_line, ""]

        for key, obs in sorted(hist_copy.items()):
            name, labels_str = _parse_key(key)
            obs_s = sorted(obs)
            n = len(obs_s)
            total = sum(obs_s)
            lines += [
                f"# HELP {name} ATRI histogram",
                f"# TYPE {name} summary",
                f'{name}_count{labels_str} {n}',
                f'{name}_sum{labels_str} {round(total, 6)}',
                f'{name}{{quantile="0.5"}}{labels_str[:-1] if labels_str.endswith("}") else ""} {_percentile(obs_s, 50)}',
                f'{name}{{quantile="0.95"}}{labels_str[:-1] if labels_str.endswith("}") else ""} {_percentile(obs_s, 95)}',
                f'{name}{{quantile="0.99"}}{labels_str[:-1] if labels_str.endswith("}") else ""} {_percentile(obs_s, 99)}',
                "",
            ]

        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        """Clear all metrics (for tests)."""
        with self._lock:
            self._counters.clear()
            self._histograms.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _label_key(name: str, labels: dict[str, str] | None) -> str:
    """Encode metric name + labels into a stable dict key."""
    if not labels:
        return name
    parts = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    return f"{name}{{{parts}}}"


def _parse_key(key: str) -> tuple[str, str]:
    """Split 'name{k="v"}' back into (name, '{k="v"}')."""
    if "{" in key:
        idx = key.index("{")
        return key[:idx], key[idx:]
    return key, ""


def _percentile(sorted_data: list[float], pct: int) -> float:
    """Return the pct-th percentile of pre-sorted data."""
    if not sorted_data:
        return 0.0
    idx = int(len(sorted_data) * pct / 100)
    idx = min(idx, len(sorted_data) - 1)
    return round(sorted_data[idx], 6)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

registry = MetricsRegistry()
