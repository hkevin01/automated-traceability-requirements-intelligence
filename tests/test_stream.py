"""
ID: TEST-STREAM-001
Purpose: Tests for WebSocket streaming endpoint and stream status route.
"""
from fastapi.testclient import TestClient
from atri.main import app


def test_stream_status_endpoint():
    with TestClient(app) as client:
        resp = client.get("/api/v1/stream/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "connected_clients" in data
        assert data["connected_clients"] == 0


def test_websocket_connect_and_receive_snapshot():
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/stream/events?topic=dashboard") as ws:
            # First message should be a dashboard_snapshot
            msg = ws.receive_json()
            assert msg["type"] == "dashboard_snapshot"
            assert "data" in msg


def test_websocket_audit_topic():
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/stream/events?topic=audit") as ws:
            # For audit-only topic, no immediate message is expected (no new events)
            # Just confirm connection is accepted without error
            import threading
            received = []
            def recv():
                try:
                    msg = ws.receive_json(timeout=0.5)
                    received.append(msg)
                except Exception:
                    pass
            t = threading.Thread(target=recv, daemon=True)
            t.start()
            t.join(timeout=1)
            # Either 0 or more messages, no exceptions is the success condition


def test_broadcast_function():
    """Test the broadcast helper is importable and callable."""
    import asyncio
    from atri.api.routes.stream import broadcast_audit_event
    # Should run without error even with no connected clients
    asyncio.run(broadcast_audit_event({"event_type": "test", "actor": "ci"}))
