"""
ID: ATRI-REV-001
Purpose: Review workflow service with full history, reviewer assignment, and pending state.
Requirement: Support the full review lifecycle: pending -> accepted/rejected with history trail.
Rationale: Regulated programs require evidence of review decisions and reviewer accountability.
Inputs: source_id, target_id, decision, reviewer, comments, assigned_reviewer.
Outputs: ReviewRecord persisted to JSON store; history persisted to JSONL audit trail.
Preconditions: Storage paths must be writable.
Postconditions: Every state change is appended to history; latest state stored in primary store.
Side Effects: Writes to two files (reviews.json and review_history.jsonl).
Failure modes: ValueError for invalid decisions; IOError propagates to caller.
Verification: Unit tests cover all state transitions and history replay.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

VALID_DECISIONS = frozenset({"accepted", "rejected", "pending"})


@dataclass(slots=True)
class ReviewRecord:
    """
    ID: ATRI-REV-002
    Purpose: Mutable review state for a single source->target trace link pair.
    Inputs: All string fields; assigned_reviewer may be empty.
    Postconditions: decision is always one of: accepted, rejected, pending.
    """
    source_id: str
    target_id: str
    decision: str
    reviewer: str
    comments: str = ""
    assigned_reviewer: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict."""
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "decision": self.decision,
            "reviewer": self.reviewer,
            "comments": self.comments,
            "assigned_reviewer": self.assigned_reviewer,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(slots=True)
class ReviewHistoryEntry:
    """
    ID: ATRI-REV-003
    Purpose: Immutable snapshot of a review state change.
    """
    source_id: str
    target_id: str
    decision: str
    reviewer: str
    comments: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "decision": self.decision,
            "reviewer": self.reviewer,
            "comments": self.comments,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class TraceReviewService:
    """
    ID: ATRI-REV-004
    Purpose: Manage review lifecycle for trace links.
    Side Effects: Writes to primary store (JSON) and history store (JSONL).
    """

    def __init__(
        self,
        storage_path: str | Path = "data/processed/reviews.json",
        history_path: str | Path = "data/processed/review_history.jsonl",
    ) -> None:
        self._storage_path = Path(storage_path)
        self._history_path = Path(history_path)
        self._reviews: dict[tuple[str, str], ReviewRecord] = {}
        self._load_reviews()

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def assign_reviewer(
        self,
        source_id: str,
        target_id: str,
        assigned_reviewer: str,
        actor: str = "system",
    ) -> ReviewRecord:
        """
        ID: ATRI-REV-005
        Purpose: Assign a reviewer to a trace link; create pending record if absent.
        Inputs: source_id, target_id - link key; assigned_reviewer - username of assigned reviewer.
        Outputs: Updated ReviewRecord.
        Side Effects: Creates or updates review record; appends to history.
        """
        key = (source_id, target_id)
        if key in self._reviews:
            record = self._reviews[key]
            record.assigned_reviewer = assigned_reviewer
            record.updated_at = datetime.now(UTC).isoformat()
        else:
            record = ReviewRecord(
                source_id=source_id,
                target_id=target_id,
                decision="pending",
                reviewer=actor,
                assigned_reviewer=assigned_reviewer,
            )
            self._reviews[key] = record

        self._append_history(
            ReviewHistoryEntry(
                source_id=source_id,
                target_id=target_id,
                decision="assigned",
                reviewer=actor,
                comments=f"Assigned to {assigned_reviewer}",
            )
        )
        self._save_reviews()
        return record

    def record_review(
        self,
        source_id: str,
        target_id: str,
        decision: str,
        reviewer: str,
        comments: str = "",
    ) -> ReviewRecord:
        """
        ID: ATRI-REV-006
        Purpose: Record a review decision (accepted/rejected/pending) for a trace link.
        Inputs: source_id, target_id - link key; decision - must be in VALID_DECISIONS.
        Outputs: ReviewRecord with updated state.
        Failure modes: ValueError if decision is invalid.
        Side Effects: Persists to primary store and appends to history.
        """
        normalised = decision.strip().lower()
        if normalised not in VALID_DECISIONS:
            raise ValueError(f"decision must be one of {sorted(VALID_DECISIONS)}")

        key = (source_id, target_id)
        existing = self._reviews.get(key)
        now = datetime.now(UTC).isoformat()

        record = ReviewRecord(
            source_id=source_id,
            target_id=target_id,
            decision=normalised,
            reviewer=reviewer,
            comments=comments,
            assigned_reviewer=existing.assigned_reviewer if existing else "",
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        self._reviews[key] = record
        self._append_history(
            ReviewHistoryEntry(
                source_id=source_id,
                target_id=target_id,
                decision=normalised,
                reviewer=reviewer,
                comments=comments,
            )
        )
        self._save_reviews()
        return record

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_reviews(self) -> list[ReviewRecord]:
        """Return all current review records."""
        return list(self._reviews.values())

    def get_review(self, source_id: str, target_id: str) -> ReviewRecord | None:
        """Return the current review state for a link pair, or None."""
        return self._reviews.get((source_id, target_id))

    def list_history(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        reviewer: str | None = None,
    ) -> list[ReviewHistoryEntry]:
        """
        ID: ATRI-REV-007
        Purpose: Return reviewer history entries with optional filters.
        Inputs: Optional filter by source_id, target_id, or reviewer username.
        Outputs: Filtered list of ReviewHistoryEntry objects.
        """
        entries = self._load_history()
        if source_id:
            entries = [e for e in entries if e.source_id == source_id]
        if target_id:
            entries = [e for e in entries if e.target_id == target_id]
        if reviewer:
            entries = [e for e in entries if e.reviewer == reviewer]
        return entries

    def reviewer_summary(self) -> list[dict]:
        """
        ID: ATRI-REV-008
        Purpose: Return a per-reviewer summary of review decisions for drill-down.
        Outputs: list of dicts {reviewer, total, accepted, rejected, pending}.
        """
        history = self._load_history()
        stats: dict[str, dict[str, int]] = {}
        for entry in history:
            if entry.decision not in {"accepted", "rejected", "pending"}:
                continue
            r = entry.reviewer
            if r not in stats:
                stats[r] = {"total": 0, "accepted": 0, "rejected": 0, "pending": 0}
            stats[r]["total"] += 1
            stats[r][entry.decision] += 1
        return [
            {"reviewer": r, **counts}
            for r, counts in sorted(stats.items())
        ]

    def summarize_reviews(self) -> dict:
        """Return aggregate review counts for the dashboard."""
        reviews = self.list_reviews()
        accepted = sum(1 for r in reviews if r.decision == "accepted")
        rejected = sum(1 for r in reviews if r.decision == "rejected")
        pending = sum(1 for r in reviews if r.decision == "pending")
        total = len(reviews)
        return {
            "total_reviews": total,
            "accepted_reviews": accepted,
            "rejected_reviews": rejected,
            "pending_reviews": pending,
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_reviews(self) -> None:
        """Load current review state from JSON store."""
        if not self._storage_path.exists():
            return
        try:
            payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
            for item in payload:
                record = ReviewRecord(
                    source_id=item["source_id"],
                    target_id=item["target_id"],
                    decision=item.get("decision", "pending"),
                    reviewer=item.get("reviewer", ""),
                    comments=item.get("comments", ""),
                    assigned_reviewer=item.get("assigned_reviewer", ""),
                    created_at=item.get("created_at", datetime.now(UTC).isoformat()),
                    updated_at=item.get("updated_at", datetime.now(UTC).isoformat()),
                )
                self._reviews[(record.source_id, record.target_id)] = record
        except (json.JSONDecodeError, KeyError):
            self._reviews = {}

    def _save_reviews(self) -> None:
        """Persist current review state to JSON store."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [record.to_dict() for record in self._reviews.values()]
        self._storage_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )

    def _append_history(self, entry: ReviewHistoryEntry) -> None:
        """Append a single history entry to the JSONL history file."""
        self._history_path.parent.mkdir(parents=True, exist_ok=True)
        with self._history_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")

    def _load_history(self) -> list[ReviewHistoryEntry]:
        """Load all history entries from the JSONL file."""
        if not self._history_path.exists():
            return []
        entries: list[ReviewHistoryEntry] = []
        for line in self._history_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                entries.append(ReviewHistoryEntry(**item))
            except (json.JSONDecodeError, TypeError, KeyError):
                continue
        return entries
