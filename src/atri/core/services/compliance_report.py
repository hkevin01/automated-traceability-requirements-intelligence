"""
ID: ATRI-RPT-001
Purpose: Compliance report generator for audit trails and review records.
Requirement: Produce structured compliance snapshots in JSON and CSV formats
             suitable for DO-178C / IEC-62304 program review packages.
Rationale: Regulated programs need exportable evidence packages that combine
           audit event logs, review decisions, and coverage metrics into a
           single deliverable.
Inputs:
  audit_store_path   - Path to immutable JSONL audit event log.
  review_store_path  - Path to current reviews JSON file.
  review_history_path - Path to JSONL review history log.
Outputs: ComplianceReport dataclass with summary stats and CSV/JSON serialisers.
Preconditions: All path files may be absent (treated as empty).
Postconditions: Report is generated from current on-disk state; no side effects.
Assumptions: Files are valid JSONL / JSON; corrupt lines are skipped with a warning.
Side Effects: None - read-only operation.
Failure modes: IOError on unreadable files propagates to caller.
Constraints: Loads entire file into memory; suitable for < 100k events.
Verification: tests/test_compliance_report.py
References: DO-178C Section 11 software life cycle data; IEC-62304 Section 9.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Report model
# ---------------------------------------------------------------------------

@dataclass
class ComplianceReport:
    """
    ID: ATRI-RPT-002
    Purpose: Structured compliance snapshot combining audit and review evidence.
    Postconditions: All list fields are non-None (may be empty).
    """
    # Summary counts
    total_audit_events: int = 0
    total_reviews: int = 0
    accepted_reviews: int = 0
    rejected_reviews: int = 0
    pending_reviews: int = 0

    # Actor-level accountability
    actor_event_counts: dict[str, int] = field(default_factory=dict)
    reviewer_decision_counts: dict[str, dict[str, int]] = field(default_factory=dict)

    # Event-type breakdown
    event_type_counts: dict[str, int] = field(default_factory=dict)

    # Raw records (kept for CSV export)
    audit_events: list[dict] = field(default_factory=list)
    reviews: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """
        ID: ATRI-RPT-003
        Purpose: Return JSON-serialisable summary dict (excludes raw record lists).
        Outputs: dict with summary statistics only.
        """
        return {
            "total_audit_events": self.total_audit_events,
            "total_reviews": self.total_reviews,
            "accepted_reviews": self.accepted_reviews,
            "rejected_reviews": self.rejected_reviews,
            "pending_reviews": self.pending_reviews,
            "actor_event_counts": self.actor_event_counts,
            "reviewer_decision_counts": self.reviewer_decision_counts,
            "event_type_counts": self.event_type_counts,
        }

    def to_audit_csv(self) -> str:
        """
        ID: ATRI-RPT-004
        Purpose: Serialise audit_events list to CSV string.
        Outputs: UTF-8 CSV string with header row; empty string if no events.
        """
        if not self.audit_events:
            return ""
        buf = io.StringIO()
        fields = ["timestamp", "event_type", "subject_id", "actor", "details"]
        writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for ev in self.audit_events:
            row = dict(ev)
            row["details"] = json.dumps(ev.get("details", {}))
            writer.writerow(row)
        return buf.getvalue()

    def to_review_csv(self) -> str:
        """
        ID: ATRI-RPT-005
        Purpose: Serialise reviews list to CSV string.
        Outputs: UTF-8 CSV string with header row; empty string if no reviews.
        """
        if not self.reviews:
            return ""
        buf = io.StringIO()
        fields = ["source_id", "target_id", "decision", "reviewer", "comments", "timestamp"]
        writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(self.reviews)
        return buf.getvalue()


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class ComplianceReportService:
    """
    ID: ATRI-RPT-006
    Purpose: Build ComplianceReport from on-disk audit + review stores.
    Preconditions: Storage paths may point to non-existent files.
    Side Effects: None - read-only.
    """

    def __init__(
        self,
        audit_store_path: str | Path,
        review_store_path: str | Path,
        review_history_path: str | Path,
    ) -> None:
        self._audit_path = Path(audit_store_path)
        self._review_path = Path(review_store_path)
        self._history_path = Path(review_history_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self) -> ComplianceReport:
        """
        ID: ATRI-RPT-007
        Purpose: Load all stores and produce a ComplianceReport.
        Outputs: ComplianceReport with populated summary and raw record lists.
        Failure modes: Corrupt JSONL lines are skipped; missing files yield empty data.
        """
        report = ComplianceReport()
        report.audit_events = self._load_audit_events()
        report.reviews = self._load_reviews()

        # Aggregate audit stats
        report.total_audit_events = len(report.audit_events)
        for ev in report.audit_events:
            actor = ev.get("actor", "unknown")
            etype = ev.get("event_type", "unknown")
            report.actor_event_counts[actor] = report.actor_event_counts.get(actor, 0) + 1
            report.event_type_counts[etype] = report.event_type_counts.get(etype, 0) + 1

        # Aggregate review stats
        report.total_reviews = len(report.reviews)
        for rv in report.reviews:
            decision = rv.get("decision", "unknown")
            reviewer = rv.get("reviewer") or "unassigned"
            if decision == "accepted":
                report.accepted_reviews += 1
            elif decision == "rejected":
                report.rejected_reviews += 1
            else:
                report.pending_reviews += 1
            bucket = report.reviewer_decision_counts.setdefault(reviewer, {})
            bucket[decision] = bucket.get(decision, 0) + 1

        return report

    # ------------------------------------------------------------------
    # Internal loaders
    # ------------------------------------------------------------------

    def _load_audit_events(self) -> list[dict]:
        """
        ID: ATRI-RPT-008
        Purpose: Read JSONL audit log; skip corrupt lines.
        Outputs: list of event dicts ordered oldest-first.
        """
        if not self._audit_path.exists():
            return []
        events: list[dict] = []
        for line in self._audit_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("Skipping corrupt audit line: %s", line[:80])
        return events

    def _load_reviews(self) -> list[dict]:
        """
        ID: ATRI-RPT-009
        Purpose: Read current reviews JSON file.
        Outputs: list of review dicts; empty list if file absent or corrupt.
        """
        if not self._review_path.exists():
            return []
        try:
            raw = json.loads(self._review_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                return raw
            # Support both list and {"reviews": [...]} shapes
            return raw.get("reviews", [])
        except (json.JSONDecodeError, AttributeError):
            logger.warning("Could not parse reviews file: %s", self._review_path)
            return []
