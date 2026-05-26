from fastapi.testclient import TestClient

from atri.api.routes import impact as impact_route
from atri.core.services.audit import TraceAuditService
from atri.core.services.graph_store import TraceGraphStore
from atri.core.services.review import TraceReviewService
from atri.core.tenancy import TenantContext, resolve_tenant
from atri.main import app

client = TestClient(app)


def _tenant_ctx(tmp_path) -> TenantContext:
    """Return a TenantContext with all stores scoped to tmp_path."""
    return TenantContext(
        tenant_id="test",
        review_store_path=tmp_path / "reviews.json",
        review_history_store_path=tmp_path / "review_history.jsonl",
        graph_store_path=tmp_path / "trace_graph.json",
        audit_store_path=tmp_path / "audit_events.jsonl",
        ingestion_store_path=tmp_path / "ingested.jsonl",
        vector_index_path=tmp_path / "vector_index.json",
    )


def test_dashboard_summary_contract() -> None:
    response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == 200
    assert response.json() == {
        "trace_coverage": 0.78,
        "suspect_links": 14,
        "orphan_requirements": 7,
        "orphan_tests": 5,
        "high_risk_changes_7d": 3,
    }


def test_dashboard_view_renders_visual_summary(tmp_path, monkeypatch) -> None:
    review_store = tmp_path / "reviews.json"
    audit_store = tmp_path / "audit_events.jsonl"
    graph_store = tmp_path / "trace_graph.json"

    review_service = TraceReviewService(review_store)
    review_service.record_review(
        source_id="REQ-70",
        target_id="DES-70",
        decision="accepted",
        reviewer="analyst-g",
        comments="Visual dashboard seed.",
    )
    review_service.record_review(
        source_id="REQ-71",
        target_id="CODE-71",
        decision="rejected",
        reviewer="analyst-h",
        comments="Visual dashboard seed.",
    )

    audit_service = TraceAuditService(audit_store)
    audit_service.record_event(
        event_type="trace_review_decision",
        subject_id="REQ-70->DES-70",
        actor="analyst-g",
        details={"decision": "accepted"},
    )
    audit_service.record_event(
        event_type="graph_sync",
        subject_id="trace_graph",
        actor="system",
        details={"artifact_count": "3", "link_count": "2"},
    )

    graph = TraceGraphStore(graph_store)
    graph.replace_graph(
        artifacts=[
            {
                "artifact_id": "REQ-70",
                "artifact_type": "requirement",
                "title": "Visual requirement",
                "body": "Need a dashboard view.",
                "version": "v1",
            },
            {
                "artifact_id": "DES-70",
                "artifact_type": "design",
                "title": "Visual design",
                "body": "Render the dashboard.",
                "version": "v1",
            },
            {
                "artifact_id": "CODE-70",
                "artifact_type": "code",
                "title": "Visual code",
                "body": "Render charts.",
                "version": "v1",
            },
        ],
        links=[
            {
                "source_id": "REQ-70",
                "target_id": "DES-70",
                "link_type": "refines",
                "confidence": 0.91,
                "rationale": "Dashboard requirement maps to design.",
            },
            {
                "source_id": "DES-70",
                "target_id": "CODE-70",
                "link_type": "implements",
                "confidence": 0.9,
                "rationale": "Dashboard design maps to implementation.",
            },
        ],
    )

    monkeypatch.setitem(app.dependency_overrides, resolve_tenant, lambda: _tenant_ctx(tmp_path))

    response = client.get("/api/v1/dashboard/view")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Traceability Dashboard" in response.text
    assert "Accepted reviews: 1" in response.text
    assert "Audit events: 2" in response.text
    assert "Isolated artifacts: 0" in response.text


def test_capability_catalog_contract() -> None:
    response = client.get("/api/v1/capabilities/catalog")

    assert response.status_code == 200
    assert response.json() == {
        "capabilities": [
            {
                "name": "AI-assisted requirement linking",
                "description": (
                    "Propose trace links between requirements, design, code, tests, "
                    "hazards, and interfaces."
                ),
            },
            {
                "name": "Automated change-impact analysis",
                "description": (
                    "Identify impacted artifacts when a requirement, design element, "
                    "or code module changes."
                ),
            },
            {
                "name": "Intelligent gap detection",
                "description": (
                    "Detect orphan requirements, missing tests, incomplete mitigations, "
                    "and weak verification coverage."
                ),
            },
            {
                "name": "Real-time traceability dashboards",
                "description": (
                    "Summarize coverage, orphan artifacts, high-risk modules, and "
                    "verification progress."
                ),
            },
        ]
    }


def test_traceability_suggestions_contract() -> None:
    response = client.post(
        "/api/v1/traceability/link-suggest",
        json={
            "source": {
                "artifact_id": "REQ-1",
                "artifact_type": "requirement",
                "title": "Login requirement",
                "body": "The system shall authenticate users before access.",
                "version": "v1",
            },
            "candidates": [
                {
                    "artifact_id": "DES-1",
                    "artifact_type": "design",
                    "title": "Authentication flow",
                    "body": "Users authenticate before the system grants access.",
                    "version": "v1",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "suggestions": [
            {
                "source_id": "REQ-1",
                "target_id": "DES-1",
                "link_type": "related_to",
                "confidence": 0.3,
                "rationale": "Token overlap heuristic baseline",
            }
        ]
    }


def test_traceability_review_workflow_contract(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(app.dependency_overrides, resolve_tenant, lambda: _tenant_ctx(tmp_path))

    accepted_response = client.post(
        "/api/v1/traceability/review",
        json={
            "source_id": "REQ-1",
            "target_id": "DES-1",
            "decision": "accepted",
            "reviewer": "analyst-a",
            "comments": "Confirmed by design review evidence.",
        },
    )

    assert accepted_response.status_code == 200
    assert accepted_response.json() == {
        "review": {
            "source_id": "REQ-1",
            "target_id": "DES-1",
            "decision": "accepted",
            "reviewer": "analyst-a",
            "comments": "Confirmed by design review evidence.",
        }
    }

    rejected_response = client.post(
        "/api/v1/traceability/review",
        json={
            "source_id": "REQ-2",
            "target_id": "CODE-2",
            "decision": "rejected",
            "reviewer": "analyst-b",
            "comments": "No direct implementation evidence.",
        },
    )

    assert rejected_response.status_code == 200
    assert rejected_response.json() == {
        "review": {
            "source_id": "REQ-2",
            "target_id": "CODE-2",
            "decision": "rejected",
            "reviewer": "analyst-b",
            "comments": "No direct implementation evidence.",
        }
    }

    summary_response = client.get("/api/v1/traceability/reviews/summary")

    assert summary_response.status_code == 200
    assert summary_response.json() == {
        "total_reviews": 2,
        "accepted_reviews": 1,
        "rejected_reviews": 1,
        "pending_reviews": 0,
    }

    list_response = client.get("/api/v1/traceability/reviews")

    assert list_response.status_code == 200
    assert list_response.json() == [
        {
            "source_id": "REQ-1",
            "target_id": "DES-1",
            "decision": "accepted",
            "reviewer": "analyst-a",
            "comments": "Confirmed by design review evidence.",
        },
        {
            "source_id": "REQ-2",
            "target_id": "CODE-2",
            "decision": "rejected",
            "reviewer": "analyst-b",
            "comments": "No direct implementation evidence.",
        },
    ]


def test_audit_events_record_review_actions(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(app.dependency_overrides, resolve_tenant, lambda: _tenant_ctx(tmp_path))

    response = client.post(
        "/api/v1/traceability/review",
        json={
            "source_id": "REQ-40",
            "target_id": "DES-40",
            "decision": "accepted",
            "reviewer": "analyst-e",
            "comments": "Audit this action.",
        },
    )

    assert response.status_code == 200

    audit_events_response = client.get("/api/v1/traceability/audit/events")

    assert audit_events_response.status_code == 200
    assert audit_events_response.json()[0]["event_type"] == "trace_review_decision"
    assert audit_events_response.json()[0]["subject_id"] == "REQ-40->DES-40"
    assert audit_events_response.json()[0]["actor"] == "analyst-e"
    assert audit_events_response.json()[0]["details"] == {"decision": "accepted"}

    summary_response = client.get("/api/v1/traceability/audit/summary")

    assert summary_response.status_code == 200
    assert summary_response.json() == {
        "trace_review_decision": 1,
        "total_events": 1,
    }


def test_trace_review_service_persists_reviews(tmp_path) -> None:
    store_path = tmp_path / "reviews.json"
    service = TraceReviewService(store_path)

    service.record_review(
        source_id="REQ-9",
        target_id="DES-9",
        decision="accepted",
        reviewer="analyst-c",
        comments="Persist this decision.",
    )

    reloaded_service = TraceReviewService(store_path)
    reviews = reloaded_service.list_reviews()

    assert len(reviews) == 1
    assert reviews[0].source_id == "REQ-9"
    assert reviews[0].target_id == "DES-9"
    assert reviews[0].decision == "accepted"
    assert reviews[0].reviewer == "analyst-c"
    assert reviews[0].comments == "Persist this decision."


def test_trace_graph_store_persists_and_drives_impact(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(app.dependency_overrides, resolve_tenant, lambda: _tenant_ctx(tmp_path))

    sync_response = client.post(
        "/api/v1/traceability/graph",
        json={
            "artifacts": [
                {
                    "artifact_id": "REQ-10",
                    "artifact_type": "requirement",
                    "title": "Access requirement",
                    "body": "The system shall restrict access.",
                    "version": "v1",
                },
                {
                    "artifact_id": "DES-10",
                    "artifact_type": "design",
                    "title": "Access control design",
                    "body": "Access is controlled by a validation service.",
                    "version": "v1",
                },
                {
                    "artifact_id": "CODE-10",
                    "artifact_type": "code",
                    "title": "Access control module",
                    "body": "Implements the validation service.",
                    "version": "v1",
                },
            ],
            "links": [
                {
                    "source_id": "REQ-10",
                    "target_id": "DES-10",
                    "link_type": "refines",
                    "confidence": 0.95,
                    "rationale": "Requirement maps to design intent.",
                },
                {
                    "source_id": "DES-10",
                    "target_id": "CODE-10",
                    "link_type": "implements",
                    "confidence": 0.94,
                    "rationale": "Design maps to implementation.",
                },
            ],
        },
    )

    assert sync_response.status_code == 200
    assert sync_response.json() == {"artifact_count": 3, "link_count": 2}

    audit_summary_response = client.get("/api/v1/traceability/audit/summary")

    assert audit_summary_response.status_code == 200
    assert audit_summary_response.json() == {
        "graph_sync": 1,
        "total_events": 1,
    }

    impact_response = client.post(
        "/api/v1/impact/analyze",
        json={"changed_ids": ["REQ-10"], "depth": 2},
    )

    assert impact_response.status_code == 200
    assert impact_response.json() == {
        "changed": ["REQ-10"],
        "impacted": [
            {"artifact_id": "DES-10", "score": 0.75, "distance": 1},
            {"artifact_id": "CODE-10", "score": 0.5, "distance": 2},
        ],
    }


def test_trace_graph_store_reload(tmp_path) -> None:
    store_path = tmp_path / "trace_graph.json"
    graph_store = TraceGraphStore(store_path)

    graph_store.replace_graph(
        artifacts=[
            {
                "artifact_id": "REQ-20",
                "artifact_type": "requirement",
                "title": "Telemetry requirement",
                "body": "The system shall capture telemetry.",
                "version": "v1",
            }
        ],
        links=[
            {
                "source_id": "REQ-20",
                "target_id": "DES-20",
                "link_type": "refines",
                "confidence": 0.9,
                "rationale": "Direct trace to design.",
            }
        ],
    )

    reloaded_store = TraceGraphStore(store_path)

    assert reloaded_store.adjacency_map() == {"REQ-20": ["DES-20"], "DES-20": []}


def test_trace_audit_service_persists_events(tmp_path) -> None:
    store_path = tmp_path / "audit_events.json"
    audit_service = TraceAuditService(store_path)

    audit_service.record_event(
        event_type="trace_review_decision",
        subject_id="REQ-50->DES-50",
        actor="analyst-f",
        details={"decision": "rejected"},
    )

    reloaded_service = TraceAuditService(store_path)

    assert reloaded_service.summarize_events() == {
        "trace_review_decision": 1,
        "total_events": 1,
    }


def test_impact_analysis_contract() -> None:
    response = client.post(
        "/api/v1/impact/analyze",
        json={
            "changed_ids": ["REQ-1"],
            "adjacency": {
                "REQ-1": ["DES-1"],
                "DES-1": ["CODE-1"],
            },
            "depth": 2,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "changed": ["REQ-1"],
        "impacted": [
            {"artifact_id": "DES-1", "score": 0.75, "distance": 1},
            {"artifact_id": "CODE-1", "score": 0.5, "distance": 2},
        ],
    }


def test_gap_detection_contract() -> None:
    response = client.post(
        "/api/v1/gaps/detect",
        json={
            "artifacts": [
                {"artifact_id": "REQ-1", "artifact_type": "requirement"},
                {"artifact_id": "TEST-1", "artifact_type": "test"},
            ],
            "links": [],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "findings": [
            {
                "artifact_id": "REQ-1",
                "finding_type": "orphan_requirement",
                "severity": "high",
                "rationale": "Requirement has no downstream links",
            },
            {
                "artifact_id": "TEST-1",
                "finding_type": "orphan_test",
                "severity": "medium",
                "rationale": "Test has no upstream trace link",
            },
        ]
    }

# ---------------------------------------------------------------------------
# Dashboard drilldown endpoints
# ---------------------------------------------------------------------------

def test_drilldown_reviews_empty(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(app.dependency_overrides, resolve_tenant, lambda: _tenant_ctx(tmp_path))
    resp = client.get("/api/v1/dashboard/drilldown/reviews")
    assert resp.status_code == 200
    assert resp.json() == []


def test_drilldown_reviews_with_data(tmp_path, monkeypatch) -> None:
    # Write data using the same paths that _tenant_ctx will resolve
    review_service = TraceReviewService(
        tmp_path / "reviews.json",
        tmp_path / "review_history.jsonl",
    )
    review_service.record_review("A", "B", decision="accepted", reviewer="alice")
    review_service.record_review("C", "D", decision="accepted", reviewer="alice")
    monkeypatch.setitem(app.dependency_overrides, resolve_tenant, lambda: _tenant_ctx(tmp_path))
    resp = client.get("/api/v1/dashboard/drilldown/reviews")
    assert resp.status_code == 200
    data = resp.json()
    assert any(entry["reviewer"] == "alice" and entry["total"] == 2 for entry in data)


def test_drilldown_audit_empty(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(app.dependency_overrides, resolve_tenant, lambda: _tenant_ctx(tmp_path))
    resp = client.get("/api/v1/dashboard/drilldown/audit")
    assert resp.status_code == 200
    assert resp.json() == []


def test_drilldown_audit_with_data(tmp_path, monkeypatch) -> None:
    audit_service = TraceAuditService(tmp_path / "audit_events.jsonl")
    audit_service.record_event("link_created", "REQ-1->TC-1", actor="bob")
    audit_service.record_event("link_created", "REQ-2->TC-2", actor="bob")
    monkeypatch.setitem(app.dependency_overrides, resolve_tenant, lambda: _tenant_ctx(tmp_path))
    resp = client.get("/api/v1/dashboard/drilldown/audit")
    assert resp.status_code == 200
    data = resp.json()
    assert any(entry["actor"] == "bob" and entry["total"] == 2 for entry in data)


def test_drilldown_audit_subject(tmp_path, monkeypatch) -> None:
    audit_service = TraceAuditService(tmp_path / "audit_events.jsonl")
    audit_service.record_event("ev", "REQ-X->TC-X", actor="carol")
    audit_service.record_event("ev", "REQ-Y->TC-Y", actor="carol")
    monkeypatch.setitem(app.dependency_overrides, resolve_tenant, lambda: _tenant_ctx(tmp_path))
    resp = client.get("/api/v1/dashboard/drilldown/audit/subject/REQ-X->TC-X")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["actor"] == "carol"
    assert data[0]["subject_id"] == "REQ-X->TC-X"


def test_drilldown_graph(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(app.dependency_overrides, resolve_tenant, lambda: _tenant_ctx(tmp_path))
    resp = client.get("/api/v1/dashboard/drilldown/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert "stats" in data
    assert "adjacency_map" in data


# ---------------------------------------------------------------------------
# Ingestion route
# ---------------------------------------------------------------------------

def test_ingestion_sources_list() -> None:
    resp = client.get("/api/v1/ingestion/sources")
    assert resp.status_code == 200
    assert "sources" in resp.json()
    assert "doors" in resp.json()["sources"]


def test_ingestion_upload_unknown_source() -> None:
    from io import BytesIO
    resp = client.post(
        "/api/v1/ingestion/upload/nonexistent",
        files={"file": ("test.csv", BytesIO(b"id,title\n1,X"), "text/csv")},
    )
    assert resp.status_code == 400


def test_ingestion_upload_doors_csv(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(app.dependency_overrides, resolve_tenant, lambda: _tenant_ctx(tmp_path))
    csv_content = b"id,title,body\nREQ-1,Login,Users must authenticate."
    from io import BytesIO
    resp = client.post(
        "/api/v1/ingestion/upload/doors",
        files={"file": ("reqs.csv", BytesIO(csv_content), "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["artifact_count"] == 1
    assert data["artifacts"][0]["artifact_id"] == "REQ-1"
