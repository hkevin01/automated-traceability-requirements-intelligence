from fastapi import APIRouter
from pydantic import BaseModel

from atri.api.schemas import TraceabilitySuggestionsResponse
from atri.core.models.trace import Artifact
from atri.core.services.linking import LinkSuggestionService

router = APIRouter(prefix="/api/v1/traceability", tags=["traceability"])
service = LinkSuggestionService()


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
