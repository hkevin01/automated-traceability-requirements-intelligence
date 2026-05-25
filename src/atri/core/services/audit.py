"""
ID: ATRI-AUD-001
Purpose: Immutable JSONL-backed audit event service with reviewer history drill-downs.
Requirement: Persist audit events to an append-only JSONL log; never mutate historical records.
Rationale: Immutability ensures regulatory audit trail integrity for DO-178C / IEC-62304 programs.
Inputs: event_type, subject_id, actor, details dict.
Outputs: AuditEvent persisted as a single JSON line in the JSONL store.
Preconditions: storage_path parent directory must exist or be creatable.
Postconditions: Each event is timestamped, serialised, and appended atomically.
Side Effects: Appends to JSONL file; reads are sequential scan.
Failure modes: IOError propagates to caller; corrupted lines are skipped on read.
Constraints: Read performance degrades for > 1M events; use offset pagination for large logs.
Verification: Tests verify append-only behaviour, filtering, and summary accuracy.
References: IEC-62304 software lifecycle audit trail requirements.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class AuditEvent:
    """
    ID: ATRI-AUD-002
    Purpose: Immutable representation of a single audit event.
    Inputs: event_type, subject_id, actor (all required); details optional.
    Postconditions: timestamp is always set to UTC ISO-8601.
    """
    event_type: str
    subject_id: str
    actor: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    details: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict."""
        return {
            "event_type": self.event_type,
            "subject_id": self.subject_id,
            "actor": self.actor,
            "timestamp": self.timestamp,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class TraceAuditService:
    """
    ID: ATRI-AUD-003
    Purpose: Append-only audit event log backed by JSONL file storage.
    Design: Events are never deleted or overwritten; reads reconstruct from JSONL.
    Side Effects: Appends to JSONL file on each record_event() call.
    """

    def __init__(self, storage_path: str | Path = "data/processed/audit_events.jsonl") -> None:
        self._storage_path = Path(storage_path)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record_event(
        self,
        event_type: str,
        subject_id: str,
        actor: str,
        details: dict[str, str] | None = None,
    ) -> AuditEvent:
        """
        ID: ATRI-AUD-004
        Purpose: Append a new audit event to the immutable JSONL store.
        Inputs: event_type, subject_id, actor - required strings; details - optional dict.
        Outputs: The created AuditEvent.
        Side Effects: Creates parent directories; appends one line to JSONL file.
        Failure modes: IOError propagates to caller.
        """
        event = AuditEvent(
            event_type=event_type,
            subject_id=subject_id,
            actor=actor,
            details=details or {},
        )
        self._append(event)
        return event

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def list_events(
        self,
        event_type: str | None = None,
        actor: str | None = None,
        subject_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """
        ID: ATRI-AUD-005
        Purpose: Return audit events with optional filters and pagination.
        Inputs:
          event_type - optional filter; actor - optional filter;
          subject_id - optional filter; limit - max rows; offset - skip N rows.
        Outputs: Filtered, paginated list of AuditEvent objects.
        Preconditions: None.
        Postconditions: Empty list returned if store does not exist or is empty.
        """
        events = self._read_all()
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if actor:
            events = [e for e in events if e.actor == actor]
        if subject_id:
            events = [e for e in events if e.subject_id == subject_id]
        events = events[offset:]
        if limit is not None:
            events = events[:limit]
        return events

    def summarize_events(self) -> dict[str, int]:
        """
        ID: ATRI-AUD-006
        Purpose: Return a count of events grouped by event_type plus a total.
        Outputs: dict {event_type: count, ..., total_events: N}.
        """
        summary: dict[str, int] = {}
        for event in self._read_all():
            summary[event.event_type] = summary.get(event.event_type, 0) + 1
        summary["total_events"] = sum(
            v for k, v in summary.items() if k != "total_events"
        )
        return summary

    def actor_summary(self) -> list[dict]:
        """
        ID: ATRI-AUD-007
        Purpose: Return per-actor event counts for the audit drill-down dashboard.
        Outputs: list of dicts {actor, total, ...event_type_counts}.
        """
        by_actor: dict[str, dict[str, int]] = {}
        for event in self._read_all():
            if event.actor not in by_actor:
                by_actor[event.actor] = {"total": 0}
            by_actor[event.actor]["total"] += 1
            by_actor[event.actor][event.event_type] = (
                by_actor[event.actor].get(event.event_type, 0) + 1
            )
        return [{"actor": actor, **counts} for actor, counts in sorted(by_actor.items())]

    def subject_history(self, subject_id: str) -> list[AuditEvent]:
        """
        ID: ATRI-AUD-008
        Purpose: Return all audit events for a specific subject (artifact or link).
        Inputs: subject_id - the artifact or link identifier to drill down on.
        Outputs: Chronological list of AuditEvent for that subject.
        """
        return [e for e in self._read_all() if e.subject_id == subject_id]

    def total_count(self) -> int:
        """Return total number of audit events in the store."""
        return sum(1 for _ in self._iter_lines())

    # ------------------------------------------------------------------
    # Internal I/O
    # ------------------------------------------------------------------

    def _append(self, event: AuditEvent) -> None:
        """Append one event as a JSON line to the JSONL file."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self._storage_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")

    def _read_all(self) -> list[AuditEvent]:
        """Read all events from the JSONL file; skip corrupted lines."""
        events: list[AuditEvent] = []
        for line in self._iter_lines():
            try:
                item = json.loads(line)
                events.append(AuditEvent(**item))
            except (json.JSONDecodeError, TypeError, KeyError):
                continue
        return events

    def _iter_lines(self):
        """Yield non-empty lines from the JSONL file."""
        if not self._storage_path.exists():
            return
        with self._storage_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield line
