from fastapi import APIRouter
from pydantic import BaseModel

from atri.api.schemas import ImpactAnalysisResponse
from atri.core.services.impact import ImpactAnalysisService

router = APIRouter(prefix="/api/v1/impact", tags=["impact"])
service = ImpactAnalysisService()


class ImpactRequest(BaseModel):
    changed_ids: list[str]
    adjacency: dict[str, list[str]]
    depth: int = 2


@router.post("/analyze", response_model=ImpactAnalysisResponse)
def analyze_impact(payload: ImpactRequest) -> dict:
    return service.analyze(payload.changed_ids, payload.adjacency, payload.depth)
