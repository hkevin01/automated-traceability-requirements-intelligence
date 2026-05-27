"""
ID: ATRI-NOTIF-001
Purpose: Webhook notification service - delivers HTTP POST payloads on key events.
Requirement: Allow external systems (Jira, Slack, Teams, custom) to receive
             ATRI events without polling the API.
Rationale: Safety-critical programs often need integrations with ticketing and
           communication tools. A webhook pattern decouples ATRI from consumers.
Inputs:
  webhooks - list of WebhookConfig objects with URL, secret, and event filters.
  event_type - string identifying the ATRI event (e.g. "review.accepted").
  payload - dict of event data to include in the POST body.
Outputs: WebhookDeliveryResult per registered webhook.
Preconditions: httpx must be importable (it is in dev extras; use requests fallback).
Postconditions: Each registered, matching webhook receives a signed HTTP POST.
Assumptions: Webhook URLs are reachable from the ATRI host.
Side Effects: Makes outbound HTTP requests; records delivery results.
Failure modes: Connection error or non-2xx response -> DeliveryError result (no retry).
Constraints: Synchronous delivery; fire-and-forget suitable for low-volume events.
Verification: tests/test_notification.py (mocked HTTP)
References: ATRI Epic 14.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass
class WebhookConfig:
    """
    ID: ATRI-NOTIF-002
    Purpose: Configuration for a single outbound webhook endpoint.
    Inputs:
      url          - Full URL to POST to.
      secret       - HMAC-SHA256 secret for payload signing (empty = unsigned).
      event_filter - Whitelist of event_type strings; empty means all events.
      name         - Human-readable label for logging.
    """
    url: str
    secret: str = ""
    event_filter: list[str] = field(default_factory=list)
    name: str = "webhook"

    def matches(self, event_type: str) -> bool:
        """Return True if this webhook should fire for the given event_type."""
        return not self.event_filter or event_type in self.event_filter


@dataclass
class WebhookDeliveryResult:
    """
    ID: ATRI-NOTIF-003
    Purpose: Record of a single webhook delivery attempt.
    """
    webhook_name: str
    url: str
    event_type: str
    status_code: int | None
    success: bool
    error: str | None = None
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        """Return JSON-serialisable dict."""
        return {
            "webhook_name": self.webhook_name,
            "url": self.url,
            "event_type": self.event_type,
            "status_code": self.status_code,
            "success": self.success,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 1),
        }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class WebhookNotificationService:
    """
    ID: ATRI-NOTIF-004
    Purpose: Manages a list of WebhookConfig objects and delivers event payloads.
    Preconditions: webhooks list is provided at construction; may be empty.
    Side Effects: Outbound HTTP POST on each notify() call for matching webhooks.
    """

    def __init__(self, webhooks: list[WebhookConfig] | None = None) -> None:
        self._webhooks: list[WebhookConfig] = webhooks or []

    def add_webhook(self, config: WebhookConfig) -> None:
        """Register a new webhook endpoint."""
        self._webhooks.append(config)

    def remove_webhook(self, name: str) -> bool:
        """Remove webhook by name. Returns True if found and removed."""
        before = len(self._webhooks)
        self._webhooks = [w for w in self._webhooks if w.name != name]
        return len(self._webhooks) < before

    def list_webhooks(self) -> list[dict]:
        """Return webhook configs as dicts (secret redacted)."""
        return [
            {
                "name": w.name,
                "url": w.url,
                "event_filter": w.event_filter,
                "has_secret": bool(w.secret),
            }
            for w in self._webhooks
        ]

    def notify(self, event_type: str, payload: dict) -> list[WebhookDeliveryResult]:
        """
        ID: ATRI-NOTIF-005
        Purpose: Deliver payload to all matching webhooks.
        Inputs:
          event_type - string key e.g. "review.accepted", "gap.detected".
          payload    - dict of event data; will be JSON-serialised.
        Outputs: list of WebhookDeliveryResult (one per matching webhook).
        Failure modes: HTTP errors logged and returned as failed results; no exception raised.
        """
        results: list[WebhookDeliveryResult] = []
        matching = [w for w in self._webhooks if w.matches(event_type)]
        if not matching:
            return results

        body = json.dumps({"event_type": event_type, "payload": payload}, default=str)

        for webhook in matching:
            results.append(self._deliver(webhook, event_type, body))

        return results

    def test_delivery(self, webhook_name: str) -> WebhookDeliveryResult | None:
        """
        ID: ATRI-NOTIF-006
        Purpose: Send a test ping to a named webhook endpoint.
        Outputs: WebhookDeliveryResult or None if webhook not found.
        """
        match = next((w for w in self._webhooks if w.name == webhook_name), None)
        if match is None:
            return None
        body = json.dumps({"event_type": "test.ping", "payload": {"message": "ATRI webhook test"}})
        return self._deliver(match, "test.ping", body)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _deliver(self, webhook: WebhookConfig, event_type: str, body: str) -> WebhookDeliveryResult:
        """
        ID: ATRI-NOTIF-007
        Purpose: Execute single HTTP POST delivery with optional HMAC signature.
        Inputs:
          webhook    - WebhookConfig target.
          event_type - event identifier string.
          body       - pre-serialised JSON string.
        Outputs: WebhookDeliveryResult with HTTP status or error.
        Side Effects: Outbound HTTP POST.
        Failure modes: Any exception caught; result.success = False.
        """
        headers = {
            "Content-Type": "application/json",
            "X-ATRI-Event": event_type,
        }
        if webhook.secret:
            sig = hmac.new(
                webhook.secret.encode(),
                body.encode(),
                hashlib.sha256,
            ).hexdigest()
            headers["X-ATRI-Signature"] = f"sha256={sig}"

        start = time.monotonic()
        try:
            import httpx  # noqa: PLC0415
            resp = httpx.post(webhook.url, content=body, headers=headers, timeout=10.0)
            duration = (time.monotonic() - start) * 1000
            success = resp.is_success
            if not success:
                logger.warning("Webhook %s returned %d", webhook.name, resp.status_code)
            return WebhookDeliveryResult(
                webhook_name=webhook.name,
                url=webhook.url,
                event_type=event_type,
                status_code=resp.status_code,
                success=success,
                duration_ms=duration,
            )
        except Exception as exc:  # noqa: BLE001
            duration = (time.monotonic() - start) * 1000
            logger.warning("Webhook %s delivery failed: %s", webhook.name, exc)
            return WebhookDeliveryResult(
                webhook_name=webhook.name,
                url=webhook.url,
                event_type=event_type,
                status_code=None,
                success=False,
                error=str(exc),
                duration_ms=duration,
            )
