"""
ID: ATRI-OBS-ROUTE-001
Purpose: Prometheus metrics endpoint and structured logging middleware.
Requirement: Expose GET /metrics in Prometheus text format; log all requests as JSON.
References: ATRI Epic 15.
"""

from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

from atri.core.services.metrics import registry

router = APIRouter(tags=["observability"])

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Metrics endpoint
# ---------------------------------------------------------------------------


@router.get("/metrics", summary="Prometheus metrics", include_in_schema=False)
async def get_metrics():
    """
    ID: ATRI-OBS-ROUTE-002
    Purpose: Return all registered metrics in Prometheus text exposition format.
    Outputs: text/plain with Prometheus-compatible metric lines.
    """
    return PlainTextResponse(content=registry.to_text_format(), media_type="text/plain; version=0.0.4")


# ---------------------------------------------------------------------------
# Structured logging + metrics middleware
# ---------------------------------------------------------------------------


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    ID: ATRI-OBS-MIDDLEWARE-001
    Purpose: Emit structured JSON log per request; increment Prometheus counters.
    Side Effects:
      - Logs one JSON line per request via stdlib logging.
      - Increments atri_requests_total counter.
      - Records atri_request_duration_seconds observation.
    Failure modes: Middleware exception propagates to FastAPI error handler.
    """

    async def dispatch(self, request: Request, call_next):
        """
        ID: ATRI-OBS-MIDDLEWARE-002
        Purpose: Wrap each request with timing, logging, and metric recording.
        Inputs: request - Starlette Request; call_next - next middleware/handler.
        Outputs: Response from downstream handler.
        """
        start = time.monotonic()
        tenant_id = request.headers.get("X-Tenant-ID", "default")

        response = await call_next(request)

        duration = time.monotonic() - start
        method = request.method
        path = request.url.path
        status = response.status_code

        # Structured JSON log
        log_record = {
            "method": method,
            "path": path,
            "status_code": status,
            "duration_ms": round(duration * 1000, 1),
            "tenant_id": tenant_id,
        }
        logger.info(json.dumps(log_record))

        # Metrics
        registry.increment(
            "atri_requests_total",
            labels={"method": method, "path": path, "status": str(status)},
        )
        registry.observe(
            "atri_request_duration_seconds",
            duration,
            labels={"path": path},
        )

        return response
