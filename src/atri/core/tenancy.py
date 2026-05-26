"""
ID: ATRI-TENANT-001
Purpose: Multi-tenant graph and store isolation.
Requirement: When ATRI_MULTI_TENANT_ENABLED=true, all data stores are scoped to a
             tenant_id resolved from the X-Tenant-ID request header.
Rationale: Enterprise programs run multiple projects (tenants) on shared infrastructure.
           Isolation must be enforced at the storage layer; one tenant cannot read or
           write another tenant's artifacts, reviews, or audit events.
Inputs:
  X-Tenant-ID request header (optional; defaults to settings.default_tenant_id).
Outputs:
  TenantContext dataclass with per-tenant resolved file paths.
Preconditions: ATRI_MULTI_TENANT_ENABLED=true and ATRI_TENANT_DATA_ROOT set.
Postconditions: Every resolved path is under tenant_data_root/{tenant_id}/.
Assumptions: tenant_id is alphanumeric + hyphen/underscore (validated; reject others).
Side Effects: Creates tenant data directory on first access.
Failure modes:
  - Invalid tenant_id characters: raises HTTP 400.
  - tenant_id missing and multi-tenant enabled: falls back to default_tenant_id.
Constraints: tenant_id max length 64 characters.
Verification: Unit tests check path isolation and invalid-id rejection.
References: None.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from fastapi import Header, HTTPException, status

from atri.config import settings

# Only alphanumeric, hyphens, and underscores allowed in tenant IDs
_TENANT_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


@dataclass(frozen=True)
class TenantContext:
    """
    ID: ATRI-TENANT-002
    Purpose: Fully resolved per-tenant data store paths.
    Postconditions: All paths exist under tenant_data_root/{tenant_id}/.
    """
    tenant_id: str
    review_store_path: Path
    review_history_store_path: Path
    graph_store_path: Path
    audit_store_path: Path
    ingestion_store_path: Path
    vector_index_path: Path


def resolve_tenant(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
) -> TenantContext:
    """
    ID: ATRI-TENANT-003
    Purpose: FastAPI dependency that resolves per-tenant store paths from the
             X-Tenant-ID header.
    Inputs:
      x_tenant_id - value of X-Tenant-ID header; None if not provided.
    Outputs: TenantContext with all store paths scoped to the tenant.
    Failure modes:
      - Invalid tenant_id format: raises HTTP 400.
    Side Effects: Creates the tenant data directory if it does not exist.
    """
    if not settings.multi_tenant_enabled:
        # Single-tenant mode: return paths from global settings
        return TenantContext(
            tenant_id=settings.default_tenant_id,
            review_store_path=Path(settings.review_store_path),
            review_history_store_path=Path(settings.review_history_store_path),
            graph_store_path=Path(settings.graph_store_path),
            audit_store_path=Path(settings.audit_store_path),
            ingestion_store_path=Path(settings.ingestion_store_path),
            vector_index_path=Path(settings.vector_index_path),
        )

    tenant_id = (x_tenant_id or settings.default_tenant_id).strip()

    if not _TENANT_ID_RE.match(tenant_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid X-Tenant-ID '{tenant_id}'. "
                "Must be 1-64 alphanumeric characters, hyphens, or underscores."
            ),
        )

    root = Path(settings.tenant_data_root) / tenant_id
    root.mkdir(parents=True, exist_ok=True)

    return TenantContext(
        tenant_id=tenant_id,
        review_store_path=root / "reviews.json",
        review_history_store_path=root / "review_history.jsonl",
        graph_store_path=root / "trace_graph.json",
        audit_store_path=root / "audit_events.jsonl",
        ingestion_store_path=root / "ingested_artifacts.jsonl",
        vector_index_path=root / "vector_index.json",
    )
