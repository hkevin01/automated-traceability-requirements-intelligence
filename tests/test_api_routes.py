from fastapi.testclient import TestClient

from atri.main import app

client = TestClient(app)


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