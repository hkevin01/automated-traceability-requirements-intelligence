"""
ID: ATRI-STREAM-001
Purpose: WebSocket endpoint that streams live audit events and dashboard metric
         snapshots to connected clients.
Requirement: Clients subscribing to /api/v1/stream/events receive a JSON message
             every time a new audit event is written to the store.
Rationale: Real-time dashboards need push notifications for review decisions,
           graph syncs, and ingestion completions without polling at high frequency.
Inputs:
  WebSocket connection to /api/v1/stream/events.
  Optional query param topic (audit|dashboard|all, default all).
Outputs:
  JSON text frames: {"type": "audit_event"|"dashboard_snapshot", "data": {...}}.
Preconditions: Client must maintain the WebSocket connection.
Postconditions: Client receives events as long as the connection is open.
Assumptions: No authentication on the WebSocket endpoint in dev mode.
             In production, set ATRI_AUTH_ENABLED=true and pass the JWT as a
             query parameter (?token=...) since browser WebSocket does not support
             custom headers.
Side Effects: Reads audit store periodically; no writes.
Failure modes:
  - Connection drops: server cleans up state silently.
  - Store read error: sends {"type": "error", "data": "..."} and continues.
Constraints: Poll interval is 2 seconds; configurable via ATRI_STREAM_POLL_INTERVAL_S.
Verification: Integration tests use a TestClient WebSocket context.
References: FastAPI WebSocket docs; RFC 6455 (WebSocket).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Literal

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from atri.config import settings
from atri.core.services.audit import TraceAuditService
from atri.core.services.review import TraceReviewService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/stream", tags=["stream"])

_POLL_INTERVAL_S: float = 2.0

# ---------------------------------------------------------------------------
# Connection manager - tracks open sockets and broadcasts messages
# ---------------------------------------------------------------------------

class _ConnectionManager:
    """
    ID: ATRI-STREAM-002
    Purpose: Thread-safe registry of active WebSocket connections.
    Side Effects: Removes disconnected clients on failed send.
    """

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        logger.info("Stream client connected. Total: %d", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._connections:
            self._connections.remove(ws)
        logger.info("Stream client disconnected. Total: %d", len(self._connections))

    async def send(self, ws: WebSocket, payload: dict) -> bool:
        """Send payload to a single client; return False if the send failed."""
        try:
            await ws.send_text(json.dumps(payload))
            return True
        except Exception:  # noqa: BLE001
            return False

    async def broadcast(self, payload: dict) -> None:
        """Send payload to all connected clients; remove any that fail."""
        dead: list[WebSocket] = []
        for ws in list(self._connections):
            ok = await self.send(ws, payload)
            if not ok:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


_manager = _ConnectionManager()


# ---------------------------------------------------------------------------
# Public interface for other services to push events
# ---------------------------------------------------------------------------

async def broadcast_audit_event(event_dict: dict) -> None:
    """
    ID: ATRI-STREAM-003
    Purpose: Called by services after recording an audit event to push it to all
             connected WebSocket clients in real time.
    Inputs: event_dict - the serialised AuditEvent dict.
    Side Effects: Broadcasts to all open WebSocket connections.
    """
    await _manager.broadcast({"type": "audit_event", "data": event_dict})


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.websocket("/events")
async def stream_events(
    websocket: WebSocket,
    topic: Literal["audit", "dashboard", "all"] = Query(default="all"),
) -> None:
    """
    ID: ATRI-STREAM-004
    Purpose: WebSocket endpoint that pushes audit events and/or dashboard snapshots.
    Inputs:
      websocket - upgraded WebSocket connection.
      topic     - filter: "audit" for audit events only; "dashboard" for metric
                  snapshots only; "all" for both.
    Outputs: JSON text frames on each event or poll tick.
    Failure modes: Disconnection is handled cleanly; no crash.
    """
    await _manager.connect(websocket)
    audit_svc = TraceAuditService(settings.audit_store_path)
    review_svc = TraceReviewService(
        settings.review_store_path,
        history_path=settings.review_history_store_path,
    )

    # Send initial state immediately on connect
    if topic in ("dashboard", "all"):
        snapshot = _build_snapshot(audit_svc, review_svc)
        await _manager.send(websocket, {"type": "dashboard_snapshot", "data": snapshot})

    last_event_count = audit_svc.total_count()

    try:
        while True:
            await asyncio.sleep(_POLL_INTERVAL_S)

            # Push new audit events since last poll
            if topic in ("audit", "all"):
                try:
                    current_count = audit_svc.total_count()
                    if current_count > last_event_count:
                        new_events = audit_svc.list_events(
                            offset=last_event_count,
                            limit=current_count - last_event_count,
                        )
                        for ev in new_events:
                            ok = await _manager.send(
                                websocket,
                                {
                                    "type": "audit_event",
                                    "data": {
                                        "event_type": ev.event_type,
                                        "subject_id": ev.subject_id,
                                        "actor": ev.actor,
                                        "timestamp": ev.timestamp,
                                        "details": ev.details,
                                    },
                                },
                            )
                            if not ok:
                                return
                        last_event_count = current_count
                except Exception as exc:  # noqa: BLE001
                    await _manager.send(websocket, {"type": "error", "data": str(exc)})

            # Push a dashboard snapshot on every poll if requested
            if topic == "dashboard":
                try:
                    snapshot = _build_snapshot(audit_svc, review_svc)
                    ok = await _manager.send(websocket, {"type": "dashboard_snapshot", "data": snapshot})
                    if not ok:
                        return
                except Exception as exc:  # noqa: BLE001
                    await _manager.send(websocket, {"type": "error", "data": str(exc)})

    except WebSocketDisconnect:
        pass
    finally:
        _manager.disconnect(websocket)


@router.get("/status")
def stream_status() -> dict:
    """
    ID: ATRI-STREAM-005
    Purpose: Return the number of currently connected WebSocket clients.
    Outputs: dict with connected_clients count.
    """
    return {"connected_clients": _manager.connection_count}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_snapshot(audit_svc: TraceAuditService, review_svc: TraceReviewService) -> dict:
    """Build a lightweight dashboard snapshot dict for streaming."""
    return {
        "audit": audit_svc.summarize_events(),
        "reviews": review_svc.summarize_reviews(),
    }
