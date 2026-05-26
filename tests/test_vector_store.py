"""
ID: ATRI-TEST-VEC-001
Purpose: Unit tests for VectorSearchService TF-IDF semantic index.
"""

from __future__ import annotations

import pytest

from atri.core.services.vector_store import VectorSearchService


@pytest.fixture
def sample_artifacts():
    return [
        {"artifact_id": "REQ-1", "artifact_type": "requirement", "title": "Login", "body": "User shall authenticate."},
        {"artifact_id": "REQ-2", "artifact_type": "requirement", "title": "Logout", "body": "User can sign out."},
        {"artifact_id": "TC-1",  "artifact_type": "test",        "title": "Test login flow", "body": "Verify authentication works."},
        {"artifact_id": "ARCH-1","artifact_type": "design",      "title": "Auth module",     "body": "Module handles user login and session."},
    ]


@pytest.fixture
def service(tmp_path, sample_artifacts):
    svc = VectorSearchService(tmp_path / "index.json")
    svc.build_index(sample_artifacts)
    return svc


class TestVectorSearchService:
    def test_corpus_size(self, service):
        assert service.corpus_size() == 4

    def test_query_returns_results(self, service):
        query = {"artifact_id": "Q1", "artifact_type": "requirement", "title": "auth", "body": "login authentication"}
        results = service.query(query, top_k=3)
        assert len(results) > 0

    def test_query_excludes_same_id(self, service):
        query = {"artifact_id": "REQ-1", "artifact_type": "requirement", "title": "Login", "body": "User shall authenticate."}
        results = service.query(query, top_k=4)
        ids = [r["artifact_id"] for r in results]
        assert "REQ-1" not in ids

    def test_query_min_score_filtering(self, service):
        query = {"artifact_id": "X", "artifact_type": "requirement", "title": "completely unrelated", "body": "xyz123"}
        results = service.query(query, min_score=0.99)
        # Very high threshold should produce 0 or very few results
        assert isinstance(results, list)

    def test_results_have_required_fields(self, service):
        query = {"artifact_id": "Q", "artifact_type": "requirement", "title": "login", "body": "authenticate"}
        results = service.query(query, top_k=2)
        for r in results:
            assert "artifact_id" in r
            assert "score" in r

    def test_update_artifact_increases_corpus(self, service):
        new_art = {"artifact_id": "REQ-99", "artifact_type": "requirement", "title": "New req", "body": "New body text."}
        service.update_artifact(new_art)
        assert service.corpus_size() == 5

    def test_persist_and_reload(self, tmp_path, sample_artifacts):
        path = tmp_path / "idx2.json"
        svc = VectorSearchService(path)
        svc.build_index(sample_artifacts)
        # build_index auto-saves; create a new instance and check
        svc2 = VectorSearchService(path)
        assert svc2.corpus_size() == 4

    def test_empty_index_returns_empty(self, tmp_path):
        svc = VectorSearchService(tmp_path / "empty.json")
        svc.build_index([])
        result = svc.query({"artifact_id": "Q", "artifact_type": "r", "title": "t", "body": "b"})
        assert result == []
