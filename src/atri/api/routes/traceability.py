"""
ID: ATRI-TRACE-ROUTES-001
Purpose: Traceability API endpoints - link suggestion, review lifecycle,
         graph sync, audit trail, vector index, and LLM rationale.
Requirement: All data-store operations are scoped to the resolved tenant so that
             multi-tenant deployments maintain strict data isolation.
Rationale: Each handler instantiates its services from TenantContext paths rather
           than from module-level singletons, allowing the same code to serve any
           tenant without restart.
Inputs:
  X-Tenant-ID header (optional; resolved by resolve_tenant dependency).
Side Effects:
  Reads and writes review, audit, graph, and vector stores in tenant-scoped paths.
Failure modes:
  - Invalid tenant_id: HTTP 400 from resolve_tenant.
  - Malformed request body: HTTP 422.
References: ATRI architecture doc; FastAPI dependency injection.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from atri.api.schemas import (
    AuditEventResponse,
    GraphSyncRequest,
    GraphSyncResponse,
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    ReviewStatusResponse,
    ReviewSummaryResponse,
    TraceabilitySuggestionsResponse,
)
from atri.core.models.trace import Artifact
from atri.core.services.audit import TraceAuditService
from atri.core.services.graph_store import TraceGraphStore
from atri.core.services.linking import LinkSuggestionService
from atri.core.services.review import TraceReviewService
from atri.core.tenancy import TenantContext, resolve_tenant

router = APIRouter(prefix="/api/v1/traceability", tags=["traceability"])

# LinkSuggestionService is stateless - one instance is fine
_link_service = LinkSuggestionService()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ArtifactIn(BaseModel):
    artifact_id: str
    artifact_type: str
    title: str
    body: str
    version: str = "v1"


class SuggestRequest(BaseModel):
    source: ArtifactIn
    candidates: list[ArtifactIn]


class ReviewAssignRequest(BaseModel):
    source_id: str
    target_id: str
    assigned_reviewer: str
    actor: str = "system"


class VectorIndexRequest(BaseModel):
    artifacts: list[ArtifactIn]


class VectorQueryRequest(BaseModel):
    source: ArtifactIn
    top_k: int = 10
    min_score: float = 0.1


class LinkExplainRequest(BaseModel):
    source: ArtifactIn
    target: ArtifactIn
    context: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/link-suggest", response_model=TraceabilitySuggestionsResponse)
def suggest_links(payload: SuggestRequest) -> dict:
    """
    ID: ATRI-TRACE-001
    Purpose: Suggest trace links between a source artifact and a list of candidates.
    """
    source = Artifact(**payload.source.model_dump())
    candidates = [Artifact(**c.model_dump()) for c in payload.candidates]
    suggestions = _link_service.suggest_links(source, candidates)
    return {
        "suggestions": [
            {
                "source_id": s.source_id,
                "target_id": s.target_id,
                "link_type": s.link_type,
                "confidence": s.confidence,
                "rationale": s.rationale,
            }
            for s in suggestions
        ]
    }


@router.post("/review", response_model=ReviewDecisionResponse)
def review_trace_link(
    payload: ReviewDecisionRequest,
    tenant: TenantContext = Depends(resolve_tenant),
) -> dict:
    """
    ID: ATRI-TRACE-002
    Purpose: Record a reviewer decision (accept/reject/pending) for a trace link.
    """
    review_svc = TraceReviewService(
        str(tenant.review_store_path),
        history_path=str(tenant.review_history_store_path),
    )
    audit_svc = TraceAuditService(str(tenant.audit_store_path))

    record = review_svc.record_review(
        source_id=payload.source_id,
        target_id=payload.target_id,
        decision=payload.decision,
        reviewer=payload.reviewer,
        comments=payload.comments,
    )
    audit_svc.record_event(
        event_type="trace_review_decision",
        subject_id=f"{record.source_id}->{record.target_id}",
        actor=record.reviewer,
        details={"decision": record.decision},
    )
    return {
        "review": ReviewStatusResponse(
            source_id=record.source_id,
            target_id=record.target_id,
            decision=record.decision,
            reviewer=record.reviewer,
            comments=record.comments,
        )
    }


@router.get("/reviews", response_model=list[ReviewStatusResponse])
def list_reviews(tenant: TenantContext = Depends(resolve_tenant)) -> list[dict]:
    """
    ID: ATRI-TRACE-003
    Purpose: Return all review records for the current tenant.
    """
    review_svc = TraceReviewService(
        str(tenant.review_store_path),
        history_path=str(tenant.review_history_store_path),
    )
    return [
        {
            "source_id": r.source_id,
            "target_id": r.target_id,
            "decision": r.decision,
            "reviewer": r.reviewer,
            "comments": r.comments,
        }
        for r in review_svc.list_reviews()
    ]


@router.get("/reviews/summary", response_model=ReviewSummaryResponse)
def review_summary(tenant: TenantContext = Depends(resolve_tenant)) -> dict:
    """
    ID: ATRI-TRACE-004
    Purpose: Return aggregated review counts for the current tenant.
    """
    review_svc = TraceReviewService(
        str(tenant.review_store_path),
        history_path=str(tenant.review_history_store_path),
    )
    return review_svc.summarize_reviews()


@router.post("/graph", response_model=GraphSyncResponse)
def sync_graph(
    payload: GraphSyncRequest,
    tenant: TenantContext = Depends(resolve_tenant),
) -> dict:
    """
    ID: ATRI-TRACE-005
    Purpose: Replace the trace graph for the current tenant.
    """
    gs = TraceGraphStore(str(tenant.graph_store_path))
    audit_svc = TraceAuditService(str(tenant.audit_store_path))

    gs.replace_graph(
        artifacts=[item.model_dump() for item in payload.artifacts],
        links=[item.model_dump() for item in payload.links],
    )
    audit_svc.record_event(
        event_type="graph_sync",
        subject_id="trace_graph",
        actor="system",
        details={
            "artifact_count": str(len(payload.artifacts)),
            "link_count": str(len(payload.links)),
        },
    )
    return {
        "artifact_count": len(payload.artifacts),
        "link_count": len(payload.links),
    }


@router.get("/audit/events", response_model=list[AuditEventResponse])
def list_audit_events(tenant: TenantContext = Depends(resolve_tenant)) -> list[dict]:
    """
    ID: ATRI-TRACE-006
    Purpose: Return all audit events for the current tenant.
    """
    audit_svc = TraceAuditService(str(tenant.audit_store_path))
    return [
        {
            "event_type": e.event_type,
            "subject_id": e.subject_id,
            "actor": e.actor,
            "timestamp": e.timestamp,
            "details": e.details,
        }
        for e in audit_svc.list_events()
    ]


@router.get("/audit/summary")
def audit_summary(tenant: TenantContext = Depends(resolve_tenant)) -> dict:
    """
    ID: ATRI-TRACE-007
    Purpose: Return aggregated audit event summary for the current tenant.
    """
    return TraceAuditService(str(tenant.audit_store_path)).summarize_events()


@router.get("/audit/actor-summary")
def audit_actor_summary(tenant: TenantContext = Depends(resolve_tenant)) -> list[dict]:
    """
    ID: ATRI-TRACE-008
    Purpose: Return per-actor breakdown of audit events for reviewer drill-down.
    """
    return TraceAuditService(str(tenant.audit_store_path)).actor_summary()


@router.get("/audit/subject/{subject_id}")
def audit_subject_history(
    subject_id: str,
    tenant: TenantContext = Depends(resolve_tenant),
) -> list[dict]:
    """
    ID: ATRI-TRACE-009
    Purpose: Return all audit events for a specific artifact or link subject_id.
    """
    return [
        {
            "event_type": e.event_type,
            "subject_id": e.subject_id,
            "actor": e.actor,
            "timestamp": e.timestamp,
            "details": e.details,
        }
        for e in TraceAuditService(str(tenant.audit_store_path)).subject_history(subject_id)
    ]


@router.post("/review/assign", response_model=dict)
def assign_reviewer(
    payload: ReviewAssignRequest,
    tenant: TenantContext = Depends(resolve_tenant),
) -> dict:
    """
    ID: ATRI-TRACE-010
    Purpose: Assign a named reviewer to a trace link for the current tenant.
    """
    review_svc = TraceReviewService(
        str(tenant.review_store_path),
        history_path=str(tenant.review_history_store_path),
    )
    audit_svc = TraceAuditService(str(tenant.audit_store_path))

    record = review_svc.assign_reviewer(
        source_id=payload.source_id,
        target_id=payload.target_id,
        assigned_reviewer=payload.assigned_reviewer,
        actor=payload.actor,
    )
    audit_svc.record_event(
        event_type="reviewer_assigned",
        subject_id=f"{record.source_id}->{record.target_id}",
        actor=payload.actor,
        details={"assigned_reviewer": payload.assigned_reviewer},
    )
    return record.to_dict()


@router.get("/reviews/history")
def review_history(
    tenant: TenantContext = Depends(resolve_tenant),
    source_id: str | None = None,
    target_id: str | None = None,
    reviewer: str | None = None,
) -> list[dict]:
    """
    ID: ATRI-TRACE-011
    Purpose: Return the reviewer history trail with optional filters.
    """
    review_svc = TraceReviewService(
        str(tenant.review_store_path),
        history_path=str(tenant.review_history_store_path),
    )
    return [
        e.to_dict()
        for e in review_svc.list_history(
            source_id=source_id,
            target_id=target_id,
            reviewer=reviewer,
        )
    ]


@router.get("/reviews/reviewer-summary")
def reviewer_summary(tenant: TenantContext = Depends(resolve_tenant)) -> list[dict]:
    """
    ID: ATRI-TRACE-012
    Purpose: Return per-reviewer review counts for dashboard drill-down.
    """
    review_svc = TraceReviewService(
        str(tenant.review_store_path),
        history_path=str(tenant.review_history_store_path),
    )
    return review_svc.reviewer_summary()


@router.post("/vector/build")
def vector_build(
    payload: VectorIndexRequest,
    tenant: TenantContext = Depends(resolve_tenant),
) -> dict:
    """
    ID: ATRI-TRACE-013
    Purpose: Build the TF-IDF semantic index for the current tenant.
    """
    from atri.core.services.vector_store import VectorSearchService  # noqa: PLC0415

    svc = VectorSearchService(str(tenant.vector_index_path))
    svc.build_index([a.model_dump() for a in payload.artifacts])
    return {"indexed": svc.corpus_size()}


@router.post("/vector/query")
def vector_query(
    payload: VectorQueryRequest,
    tenant: TenantContext = Depends(resolve_tenant),
) -> dict:
    """
    ID: ATRI-TRACE-014
    Purpose: Query the TF-IDF semantic index for the current tenant.
    """
    from atri.core.services.vector_store import VectorSearchService  # noqa: PLC0415

    svc = VectorSearchService(str(tenant.vector_index_path))
    return {
        "results": svc.query(
            artifact=payload.source.model_dump(),
            top_k=payload.top_k,
            min_score=payload.min_score,
        )
    }


@router.post("/link-explain")
def link_explain(payload: LinkExplainRequest) -> dict:
    """
    ID: ATRI-TRACE-015
    Purpose: Generate an LLM-enriched rationale for a proposed trace link.
    Note: LLM rationale cache is shared across tenants (keyed by artifact body
          hash, not tenant_id) to maximise cache hit rate for identical artifacts.
    Failure modes: Always returns a result (heuristic fallback if LLM unavailable).
    """
    from atri.core.services.llm_rationale import LLMRationaleService  # noqa: PLC0415

    svc = LLMRationaleService()
    result = svc.explain(
        source=payload.source.model_dump(),
        target=payload.target.model_dump(),
        context=payload.context,
    )
    return result.to_dict()
