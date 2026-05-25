from fastapi import APIRouter
from pydantic import BaseModel

from atri.api.schemas import (
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    ReviewStatusResponse,
    ReviewSummaryResponse,
    TraceabilitySuggestionsResponse,
)
from atri.config import settings
from atri.core.models.trace import Artifact
from atri.core.services.linking import LinkSuggestionService
from atri.core.services.review import TraceReviewService

router = APIRouter(prefix="/api/v1/traceability", tags=["traceability"])
service = LinkSuggestionService()
review_service = TraceReviewService(settings.review_store_path)


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
