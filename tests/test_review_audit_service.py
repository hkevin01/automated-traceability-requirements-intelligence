"""
ID: ATRI-TEST-RVAS-001
Purpose: Unit tests for TraceReviewService (history, assignment, reviewer summary)
         and TraceAuditService (JSONL append, actor summary, subject history, pagination).
"""

from __future__ import annotations

import json
import time

import pytest

from atri.core.services.audit import TraceAuditService
from atri.core.services.review import TraceReviewService


# ===========================================================================
# TraceAuditService tests
# ===========================================================================

@pytest.fixture
def audit(tmp_path):
    return TraceAuditService(tmp_path / "events.jsonl")


class TestTraceAuditService:
    def test_record_and_retrieve_event(self, audit):
        audit.record_event("link_created", "REQ-1->TC-1", actor="alice")
        events = audit.list_events()
        assert len(events) == 1
        assert events[0].event_type == "link_created"

    def test_multiple_events_appended(self, audit):
        for i in range(5):
            audit.record_event("ev", f"subj-{i}", actor="system")
        assert audit.total_count() == 5

    def test_filter_by_event_type(self, audit):
        audit.record_event("link_created", "A->B", actor="alice")
        audit.record_event("review_submitted", "A->B", actor="bob")
        only_links = audit.list_events(event_type="link_created")
        assert all(e.event_type == "link_created" for e in only_links)

    def test_filter_by_actor(self, audit):
        audit.record_event("ev", "s1", actor="alice")
        audit.record_event("ev", "s2", actor="bob")
        assert len(audit.list_events(actor="alice")) == 1

    def test_filter_by_subject_id(self, audit):
        audit.record_event("ev", "REQ-1->TC-1", actor="x")
        audit.record_event("ev", "REQ-2->TC-2", actor="x")
        assert len(audit.list_events(subject_id="REQ-1->TC-1")) == 1

    def test_pagination_limit_offset(self, audit):
        for i in range(10):
            audit.record_event("ev", f"s{i}", actor="a")
        page1 = audit.list_events(limit=3, offset=0)
        page2 = audit.list_events(limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 3
        ids1 = [e.subject_id for e in page1]
        ids2 = [e.subject_id for e in page2]
        assert not set(ids1) & set(ids2)

    def test_actor_summary(self, audit):
        audit.record_event("ev", "s1", actor="alice")
        audit.record_event("ev", "s2", actor="alice")
        audit.record_event("ev", "s3", actor="bob")
        summary = audit.actor_summary()
        counts = {entry["actor"]: entry["total"] for entry in summary}
        assert counts["alice"] == 2
        assert counts["bob"] == 1

    def test_subject_history(self, audit):
        audit.record_event("ev", "REQ-1->TC-1", actor="alice")
        audit.record_event("ev", "REQ-1->TC-1", actor="bob")
        audit.record_event("ev", "REQ-2->TC-2", actor="alice")
        hist = audit.subject_history("REQ-1->TC-1")
        assert len(hist) == 2

    def test_persist_across_instances(self, tmp_path):
        path = tmp_path / "ev.jsonl"
        svc1 = TraceAuditService(path)
        svc1.record_event("ev", "s1", actor="a")
        svc2 = TraceAuditService(path)
        assert svc2.total_count() == 1

    def test_no_in_memory_cache(self, tmp_path):
        # Write an event externally to the file; the service should read it
        path = tmp_path / "ev.jsonl"
        svc = TraceAuditService(path)
        with path.open("a") as f:
            f.write(json.dumps({
                "event_type": "external_ev",
                "subject_id": "s",
                "actor": "external",
                "timestamp": "2025-01-01T00:00:00",
                "details": {},
            }) + "\n")
        assert svc.total_count() == 1

    def test_summarize_events_returns_totals(self, audit):
        audit.record_event("link_created", "s1", actor="a")
        audit.record_event("review_submitted", "s2", actor="a")
        summary = audit.summarize_events()
        assert "total_events" in summary


# ===========================================================================
# TraceReviewService tests
# ===========================================================================

@pytest.fixture
def review(tmp_path):
    return TraceReviewService(
        storage_path=tmp_path / "reviews.json",
        history_path=tmp_path / "review_history.jsonl",
    )


class TestTraceReviewService:
    def test_record_review_accepted(self, review):
        record = review.record_review("REQ-1", "TC-1", decision="accepted", reviewer="alice")
        assert record.decision == "accepted"

    def test_record_review_rejected(self, review):
        record = review.record_review("REQ-1", "TC-1", decision="rejected", reviewer="alice")
        assert record.decision == "rejected"

    def test_record_review_pending(self, review):
        record = review.record_review("REQ-1", "TC-1", decision="pending", reviewer="")
        assert record.decision == "pending"

    def test_list_reviews_is_empty_initially(self, review):
        assert review.list_reviews() == []

    def test_list_reviews_after_record(self, review):
        review.record_review("A", "B", decision="accepted", reviewer="alice")
        assert len(review.list_reviews()) == 1

    def test_assign_reviewer_creates_pending_record(self, review):
        record = review.assign_reviewer("REQ-1", "TC-1", assigned_reviewer="bob", actor="alice")
        assert record.assigned_reviewer == "bob"
        assert record.decision == "pending"

    def test_assign_reviewer_updates_existing_record(self, review):
        review.record_review("REQ-1", "TC-1", decision="pending", reviewer="")
        record = review.assign_reviewer("REQ-1", "TC-1", assigned_reviewer="bob", actor="alice")
        assert record.assigned_reviewer == "bob"

    def test_list_history_returns_entries(self, review):
        review.record_review("A", "B", decision="accepted", reviewer="alice")
        hist = review.list_history()
        assert len(hist) >= 1

    def test_list_history_filter_by_source_id(self, review):
        review.record_review("A", "B", decision="accepted", reviewer="alice")
        review.record_review("C", "D", decision="accepted", reviewer="alice")
        hist = review.list_history(source_id="A")
        assert all(e.source_id == "A" for e in hist)

    def test_reviewer_summary(self, review):
        review.record_review("A", "B", decision="accepted", reviewer="alice")
        review.record_review("C", "D", decision="accepted", reviewer="alice")
        review.record_review("E", "F", decision="rejected", reviewer="bob")
        summary = review.reviewer_summary()
        by_reviewer = {e["reviewer"]: e for e in summary}
        assert by_reviewer["alice"]["total"] == 2
        assert by_reviewer["bob"]["total"] == 1

    def test_persist_across_instances(self, tmp_path):
        r1 = TraceReviewService(tmp_path / "r.json", tmp_path / "rh.jsonl")
        r1.record_review("A", "B", decision="accepted", reviewer="alice")
        r2 = TraceReviewService(tmp_path / "r.json", tmp_path / "rh.jsonl")
        assert len(r2.list_reviews()) == 1

    def test_to_dict_on_record(self, review):
        record = review.record_review("A", "B", decision="accepted", reviewer="alice")
        d = record.to_dict()
        assert d["source_id"] == "A"
        assert d["decision"] == "accepted"
