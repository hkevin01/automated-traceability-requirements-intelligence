"""
ID: ATRI-NOTIF-ROUTE-001
Purpose: Webhook notification management API routes.
Requirement: Allow operators to register, list, test, and remove webhook endpoints.
References: ATRI Epic 14.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from atri.core.services.notification import WebhookConfig, WebhookNotificationService

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

# In-process singleton shared across requests.
_service = WebhookNotificationService()


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------


class WebhookRegisterRequest(BaseModel):
    """
    ID: ATRI-NOTIF-ROUTE-002
    Purpose: Input body for registering a new webhook endpoint.
    """
    name: str
    url: str
    secret: str = ""
    event_filter: list[str] = []


class WebhookTestRequest(BaseModel):
    """Input body for test delivery."""
    name: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/webhooks", summary="List registered webhooks")
async def list_webhooks():
    """
    ID: ATRI-NOTIF-ROUTE-003
    Purpose: Return list of registered webhook endpoints (secret redacted).
    """
    return {"webhooks": _service.list_webhooks()}


@router.post("/webhooks", summary="Register a webhook endpoint", status_code=201)
async def register_webhook(body: WebhookRegisterRequest):
    """
    ID: ATRI-NOTIF-ROUTE-004
    Purpose: Add a new webhook endpoint to the in-process registry.
    Inputs: WebhookRegisterRequest with url, optional secret, optional event_filter.
    Failure modes: Duplicate name allowed (two entries with same name).
    """
    cfg = WebhookConfig(
        url=body.url,
        secret=body.secret,
        event_filter=body.event_filter,
        name=body.name,
    )
    _service.add_webhook(cfg)
    return {"registered": body.name}


@router.delete("/webhooks/{name}", summary="Remove a webhook by name")
async def remove_webhook(name: str):
    """
    ID: ATRI-NOTIF-ROUTE-005
    Purpose: Remove webhook endpoint by name.
    Failure modes: Returns 404 if name not found.
    """
    removed = _service.remove_webhook(name)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Webhook '{name}' not found")
    return {"removed": name}


@router.post("/webhooks/test", summary="Send a test ping to a webhook")
async def test_webhook(body: WebhookTestRequest):
    """
    ID: ATRI-NOTIF-ROUTE-006
    Purpose: Send a test ping to a named webhook and return the delivery result.
    Failure modes: Returns 404 if webhook name not found; delivery failures are returned (not raised).
    """
    result = _service.test_delivery(body.name)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Webhook '{body.name}' not found")
    return result.to_dict()
