"""
ID: ATRI-TEST-RPT-001
Purpose: Unit and integration tests for ComplianceReportService and report routes.
"""
import json

import pytest
from fastapi.testclient import TestClient

from atri.core.services.compliance_report import ComplianceReportService
from atri.core.tenancy import TenantContext
from atri.main import app
from atri.core.tenancy import resolve_tenant


@pytest.fixture()
def tenant_dir(tmp_path):
    """Tenant dir with sample audit JSONL and reviews JSON."""
    audit = tmp_path / "audit_events.jsonl"
    audit.write_text(
        json.dumps({"event_type": "link_added", "subject_id": "REQ-1", "actor": "alice", "timestamp": "2024-01-01T00:00:00", "details": {}}) + "\n"
        + json.dumps({"event_type": "review_submitted", "subject_id": "REQ-2", "actor": "bob", "timestamp": "2024-01-02T00:00:00", "details": {}}) + "\n"
    )
    reviews = tmp_path / "reviews.json"
    reviews.write_text(json.dumps([
        {"source_id": "REQ-1", "target_id": "TC-1", "decision": "accepted", "reviewer": "alice", "comments": "", "timestamp": "2024-01-01"},
        {"source_id": "REQ-2", "target_id": "TC-2", "decision": "rejected", "reviewer": "bob", "comments": "", "timestamp": "2024-01-02"},
        {"source_id": "REQ-3", "target_id": "TC-3", "decision": "pending", "reviewer": None, "comments": "", "timestamp": "2024-01-03"},
    ]))
    history = tmp_path / "review_history.jsonl"
    history.write_text("")
    return tmp_path


def test_build_counts(tenant_dir):
    svc = ComplianceReportService(
        audit_store_path=tenant_dir / "audit_events.jsonl",
        review_store_path=tenant_dir / "reviews.json",
        review_history_path=tenant_dir / "review_history.jsonl",
    )
    report = svc.build()
    assert report.total_audit_events == 2
    assert report.total_reviews == 3
    assert report.accepted_reviews == 1
    assert report.rejected_reviews == 1
    assert report.pending_reviews == 1


def test_actor_counts(tenant_dir):
    svc = ComplianceReportService(
        audit_store_path=tenant_dir / "audit_events.jsonl",
        review_store_path=tenant_dir / "reviews.json",
        review_history_path=tenant_dir / "review_history.jsonl",
    )
    report = svc.build()
    assert report.actor_event_counts["alice"] == 1
    assert report.actor_event_counts["bob"] == 1


def test_event_type_counts(tenant_dir):
    svc = ComplianceReportService(
        audit_store_path=tenant_dir / "audit_events.jsonl",
        review_store_path=tenant_dir / "reviews.json",
        review_history_path=tenant_dir / "review_history.jsonl",
    )
    report = svc.build()
    assert report.event_type_counts["link_added"] == 1
    assert report.event_type_counts["review_submitted"] == 1


def test_audit_csv(tenant_dir):
    svc = ComplianceReportService(
        audit_store_path=tenant_dir / "audit_events.jsonl",
        review_store_path=tenant_dir / "reviews.json",
        review_history_path=tenant_dir / "review_history.jsonl",
    )
    report = svc.build()
    csv = report.to_audit_csv()
    assert "timestamp" in csv
    assert "link_added" in csv


def test_review_csv(tenant_dir):
    svc = ComplianceReportService(
        audit_store_path=tenant_dir / "audit_events.jsonl",
        review_store_path=tenant_dir / "reviews.json",
        review_history_path=tenant_dir / "review_history.jsonl",
    )
    report = svc.build()
    csv = report.to_review_csv()
    assert "source_id" in csv
    assert "accepted" in csv


def test_empty_files(tmp_path):
    svc = ComplianceReportService(
        audit_store_path=tmp_path / "nope.jsonl",
        review_store_path=tmp_path / "nope.json",
        review_history_path=tmp_path / "nope2.jsonl",
    )
    report = svc.build()
    assert report.total_audit_events == 0
    assert report.total_reviews == 0
    assert report.to_audit_csv() == ""
    assert report.to_review_csv() == ""


def make_tenant(tmp_path):
    return TenantContext(
        tenant_id="test",
        audit_store_path=tmp_path / "audit_events.jsonl",
        review_store_path=tmp_path / "reviews.json",
        review_history_store_path=tmp_path / "review_history.jsonl",
        graph_store_path=tmp_path / "graph.json",
        ingestion_store_path=tmp_path / "ingestion.json",
        vector_index_path=tmp_path / "vector.json",
    )


def test_route_compliance_json(tenant_dir):
    tc = make_tenant(tenant_dir)
    app.dependency_overrides[resolve_tenant] = lambda: tc
    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get("/api/v1/reports/compliance")
    app.dependency_overrides.clear()
    assert resp.status_code == 200
    data = resp.json()
    assert "total_audit_events" in data


def test_route_audit_csv(tenant_dir):
    tc = make_tenant(tenant_dir)
    app.dependency_overrides[resolve_tenant] = lambda: tc
    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get("/api/v1/reports/compliance/audit.csv")
    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]


def test_route_reviews_csv(tenant_dir):
    tc = make_tenant(tenant_dir)
    app.dependency_overrides[resolve_tenant] = lambda: tc
    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get("/api/v1/reports/compliance/reviews.csv")
    app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
