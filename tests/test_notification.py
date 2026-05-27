"""
ID: ATRI-TEST-NOTIF-001
Purpose: Tests for WebhookNotificationService and notification API routes.
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from atri.core.services.notification import (
    WebhookConfig,
    WebhookDeliveryResult,
    WebhookNotificationService,
)
from atri.main import app


# ---------------------------------------------------------------------------
# Unit tests for the service
# ---------------------------------------------------------------------------


def test_add_and_list():
    svc = WebhookNotificationService()
    svc.add_webhook(WebhookConfig(url="http://example.com/hook", name="test"))
    hooks = svc.list_webhooks()
    assert len(hooks) == 1
    assert hooks[0]["name"] == "test"
    assert hooks[0]["has_secret"] is False


def test_remove_existing():
    svc = WebhookNotificationService()
    svc.add_webhook(WebhookConfig(url="http://example.com/hook", name="x"))
    assert svc.remove_webhook("x") is True
    assert svc.list_webhooks() == []


def test_remove_missing():
    svc = WebhookNotificationService()
    assert svc.remove_webhook("nope") is False


def test_event_filter_matching():
    cfg = WebhookConfig(url="http://x.com", name="f", event_filter=["review.accepted"])
    assert cfg.matches("review.accepted") is True
    assert cfg.matches("gap.detected") is False


def test_notify_no_matching_webhooks():
    svc = WebhookNotificationService()
    results = svc.notify("some.event", {"key": "value"})
    assert results == []


def test_notify_delivers_post():
    svc = WebhookNotificationService()
    svc.add_webhook(WebhookConfig(url="http://example.com/hook", name="w"))

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_success = True

    with patch("atri.core.services.notification._httpx") as mock_httpx:
        mock_httpx.post.return_value = mock_resp
        results = svc.notify("review.accepted", {"id": "REQ-1"})

    assert len(results) == 1
    assert results[0].success is True
    assert results[0].status_code == 200


def test_notify_handles_connection_error():
    svc = WebhookNotificationService()
    svc.add_webhook(WebhookConfig(url="http://dead.host/hook", name="err"))

    with patch("atri.core.services.notification._httpx") as mock_httpx:
        mock_httpx.post.side_effect = ConnectionError("timeout")
        results = svc.notify("test.event", {})

    assert len(results) == 1
    assert results[0].success is False
    assert results[0].error is not None


def test_hmac_header_sent():
    svc = WebhookNotificationService()
    svc.add_webhook(WebhookConfig(url="http://example.com/hook", name="signed", secret="mysecret"))

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_success = True

    captured_headers = {}

    def capture_post(url, content, headers, timeout):
        captured_headers.update(headers)
        return mock_resp

    with patch("atri.core.services.notification._httpx") as mock_httpx:
        mock_httpx.post.side_effect = capture_post
        svc.notify("review.accepted", {})

    assert "X-ATRI-Signature" in captured_headers
    assert captured_headers["X-ATRI-Signature"].startswith("sha256=")


# ---------------------------------------------------------------------------
# Route integration tests
# ---------------------------------------------------------------------------

client = TestClient(app, raise_server_exceptions=True)


def test_route_list_webhooks():
    resp = client.get("/api/v1/notifications/webhooks")
    assert resp.status_code == 200
    assert "webhooks" in resp.json()


def test_route_register_and_delete():
    resp = client.post("/api/v1/notifications/webhooks", json={
        "name": "my-hook",
        "url": "http://example.com/hook",
    })
    assert resp.status_code == 201
    assert resp.json()["registered"] == "my-hook"

    resp2 = client.delete("/api/v1/notifications/webhooks/my-hook")
    assert resp2.status_code == 200


def test_route_delete_missing_returns_404():
    resp = client.delete("/api/v1/notifications/webhooks/ghost-hook")
    assert resp.status_code == 404


def test_route_test_missing_webhook_returns_404():
    resp = client.post("/api/v1/notifications/webhooks/test", json={"name": "no-such-hook"})
    assert resp.status_code == 404
