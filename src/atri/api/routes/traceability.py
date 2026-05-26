from fastapi import APIRouter
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
from atri.config import settings
from atri.core.models.trace import Artifact
from atri.core.services.audit import TraceAuditService
from atri.core.services.graph_store import TraceGraphStore
from atri.core.services.linking import LinkSuggestionService
from atri.core.services.review import TraceReviewService

router = APIRouter(prefix="/api/v1/traceability", tags=["traceability"])
service = LinkSuggestionService()
review_service = TraceReviewService(
    settings.review_store_path,
    history_path=settings.review_history_store_path,
)
graph_store = TraceGraphStore(settings.graph_store_path)
audit_service = TraceAuditService(settings.audit_store_path)


class ArtifactIn(BaseModel):
    artifact_id: str
    artifact_type: str
    title: str
    body: str
    version: str = "v1"


class SuggestRequest(BaseModel):
    source: ArtifactIn
    candidates: list[ArtifactIn]


@router.post("/link-suggest", response_model=TraceabilitySuggestionsResponse)
def suggest_links(payload: SuggestRequest) -> dict:
    source = Artifact(**payload.source.model_dump())
    candidates = [Artifact(**candidate.model_dump()) for candidate in payload.candidates]
    suggestions = service.suggest_links(source, candidates)
    return {
        "suggestions": [
            {
                "source_id": item.source_id,
                "target_id": item.target_id,
                "link_type": item.link_type,
                "confidence": item.confidence,
                "rationale": item.rationale,
            }
            for item in suggestions
        ]
    }


@router.post("/review", response_model=ReviewDecisionResponse)
def review_trace_link(payload: ReviewDecisionRequest) -> dict:
    record = review_service.record_review(
        source_id=payload.source_id,
        target_id=payload.target_id,
        decision=payload.decision,
        reviewer=payload.reviewer,
        comments=payload.comments,
    )
    audit_service.record_event(
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
def list_reviews() -> list[dict]:
    return [
        {
            "source_id": record.source_id,
            "target_id": record.target_id,
            "decision": record.decision,
            "reviewer": record.reviewer,
            "comments": record.comments,
        }
        for record in review_service.list_reviews()
    ]


@router.get("/reviews/summary", response_model=ReviewSummaryResponse)
def review_summary() -> dict:
    return review_service.summarize_reviews()


@router.post("/graph", response_model=GraphSyncResponse)
def sync_graph(payload: GraphSyncRequest) -> dict:
    graph_store.replace_graph(
        artifacts=[item.model_dump() for item in payload.artifacts],
        links=[item.model_dump() for item in payload.links],
    )
    audit_service.record_event(
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
def list_audit_events() -> list[dict]:
    return [
        {
            "event_type": event.event_type,
            "subject_id": event.subject_id,
            "actor": event.actor,
            "timestamp": event.timestamp,
            "details": event.details,
        }
        for event in audit_service.list_events()
    ]


@router.get("/audit/summary")
def audit_summary() -> dict:
    return audit_service.summarize_events()


@router.get("/audit/actor-summary")
def audit_actor_summary() -> list[dict]:
    """
    ID: ATRI-TRACE-007
    Purpose: Return per-actor breakdown of audit events for reviewer drill-down.
    """
    return audit_service.actor_summary()


@router.get("/audit/subject/{subject_id}")
def audit_subject_history(subject_id: str) -> list[dict]:
    """
    ID: ATRI-TRACE-008
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
        for e in audit_service.subject_history(subject_id)
    ]


class ReviewAssignRequest(BaseModel):
    source_id: str
    target_id: str
    assigned_reviewer: str
    actor: str = "system"


@router.post("/review/assign", response_model=dict)
def assign_reviewer(payload: ReviewAssignRequest) -> dict:
    """
    ID: ATRI-TRACE-009
    Purpose: Assign a named reviewer to a trace link; creates a pending record if absent.
    """
    record = review_service.assign_reviewer(
        source_id=payload.source_id,
        target_id=payload.target_id,
        assigned_reviewer=payload.assigned_reviewer,
        actor=payload.actor,
    )
    audit_service.record_event(
        event_type="reviewer_assigned",
        subject_id=f"{record.source_id}->{record.target_id}",
        actor=payload.actor,
        details={"assigned_reviewer": payload.assigned_reviewer},
    )
    return record.to_dict()


@router.get("/reviews/history")
def review_history(
    source_id: str | None = None,
    target_id: str | None = None,
    reviewer: str | None = None,
) -> list[dict]:
    """
    ID: ATRI-TRACE-010
    Purpose: Return the reviewer history trail with optional filters.
    """
    entries = review_service.list_history(
        source_id=source_id,
        target_id=target_id,
        reviewer=reviewer,
    )
    return [e.to_dict() for e in entries]


@router.get("/reviews/reviewer-summary")
def reviewer_summary() -> list[dict]:
    """
    ID: ATRI-TRACE-011
    Purpose: Return per-reviewer review counts for dashboard drill-down.
    """
    return review_service.reviewer_summary()


class VectorIndexRequest(BaseModel):
    artifacts: list[ArtifactIn]


class VectorQueryRequest(BaseModel):
    source: ArtifactIn
    top_k: int = 10
    min_score: float = 0.1


@router.post("/vector/build")
def vector_build(payload: VectorIndexRequest) -> dict:
    """
    ID: ATRI-TRACE-012
    Purpose: Build the TF-IDF semantic index from the provided artifact list.
    """
    from atri.core.services.vector_store import VectorSearchService  # noqa: PLC0415
    from atri.config import settings as _settings  # noqa: PLC0415
    svc = VectorSearchService(_settings.vector_index_path)
    svc.build_index([a.model_dump() for a in payload.artifacts])
    return {"indexed": svc.corpus_size()}


@router.post("/vector/query")
def vector_query(payload: VectorQueryRequest) -> dict:
    """
    ID: ATRI-TRACE-013
    Purpose: Query the TF-IDF semantic index for candidates similar to source artifact.
    """
    from atri.core.services.vector_store import VectorSearchService  # noqa: PLC0415
    from atri.config import settings as _settings  # noqa: PLC0415
    svc = VectorSearchService(_settings.vector_index_path)
    results = svc.query(
        artifact=payload.source.model_dump(),
        top_k=payload.top_k,
        min_score=payload.min_score,
    )
    return {"results": results}


# ---------------------------------------------------------------------------
# LLM rationale enrichment
# ---------------------------------------------------------------------------

class LinkExplainRequest(BaseModel):
    source: ArtifactIn
    target: ArtifactIn
    context: str = ""


@router.post("/link-explain")
def link_explain(payload: LinkExplainRequest) -> dict:
    """
    ID: ATRI-TRACE-014
    Purpose: Generate an LLM-enriched rationale for a proposed trace link.
    Inputs: source and target ArtifactIn; optional context string.
    Outputs: RationaleResult dict with rationale text, model, is_fallback flag.
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
