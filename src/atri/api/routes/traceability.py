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
review_service = TraceReviewService(settings.review_store_path)
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
