"""
ID: ATRI-TEST-METRICS-001
Purpose: Tests for MetricsRegistry and /metrics endpoint.
"""
import pytest
from fastapi.testclient import TestClient

from atri.core.services.metrics import MetricsRegistry, _label_key, _percentile, registry
from atri.main import app


@pytest.fixture(autouse=True)
def clean_registry():
    """Reset shared registry before each test."""
    registry.reset()
    yield
    registry.reset()


def test_increment_and_read():
    r = MetricsRegistry()
    r.increment("test_counter", labels={"method": "GET"})
    r.increment("test_counter", labels={"method": "GET"})
    assert r.counter_value("test_counter", labels={"method": "GET"}) == 2.0


def test_increment_different_labels():
    r = MetricsRegistry()
    r.increment("req", labels={"path": "/a"})
    r.increment("req", labels={"path": "/b"})
    assert r.counter_value("req", labels={"path": "/a"}) == 1.0
    assert r.counter_value("req", labels={"path": "/b"}) == 1.0


def test_observe_summary():
    r = MetricsRegistry()
    for v in [0.1, 0.2, 0.3, 0.4, 0.5]:
        r.observe("duration", v)
    s = r.summary("duration")
    assert s["count"] == 5
    assert s["p50"] > 0


def test_percentile_empty():
    assert _percentile([], 50) == 0.0


def test_to_text_format_contains_counter():
    r = MetricsRegistry()
    r.increment("atri_requests_total", labels={"method": "GET", "path": "/health", "status": "200"})
    text = r.to_text_format()
    assert "atri_requests_total" in text
    assert "# TYPE" in text


def test_reset():
    r = MetricsRegistry()
    r.increment("x")
    r.reset()
    assert r.counter_value("x") == 0.0


def test_metrics_endpoint():
    client = TestClient(app)
    # Make a real request so the middleware can increment something
    client.get("/api/v1/health")
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "atri_requests_total" in resp.text


def test_metrics_endpoint_content_type():
    client = TestClient(app)
    resp = client.get("/metrics")
    assert "text/plain" in resp.headers["content-type"]
