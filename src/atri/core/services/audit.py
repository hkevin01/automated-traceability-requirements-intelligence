import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass(slots=True)
class AuditEvent:
    event_type: str
    subject_id: str
    actor: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    details: dict[str, str] = field(default_factory=dict)


class TraceAuditService:
    def __init__(self, storage_path: str | Path = "data/processed/audit_events.json") -> None:
        self._storage_path = Path(storage_path)
        self._events: list[AuditEvent] = []
        self._load_events()

    def record_event(
        self,
        event_type: str,
        subject_id: str,
        actor: str,
        details: dict[str, str] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_type=event_type,
            subject_id=subject_id,
            actor=actor,
            details=details or {},
        )
        self._events.append(event)
        self._save_events()
        return event

    def list_events(self) -> list[AuditEvent]:
        return list(self._events)

    def summarize_events(self) -> dict[str, int]:
        summary: dict[str, int] = {}
        for event in self._events:
            summary[event.event_type] = summary.get(event.event_type, 0) + 1
        summary["total_events"] = len(self._events)
        return summary

    def _load_events(self) -> None:
        if not self._storage_path.exists():
            return

        payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
        self._events = [AuditEvent(**item) for item in payload]

    def _save_events(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "event_type": event.event_type,
                "subject_id": event.subject_id,
                "actor": event.actor,
                "timestamp": event.timestamp,
                "details": event.details,
            }
            for event in self._events
        ]
        serialized = json.dumps(payload, indent=2, sort_keys=True)
        self._storage_path.write_text(serialized, encoding="utf-8")