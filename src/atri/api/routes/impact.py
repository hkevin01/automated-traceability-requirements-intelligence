from fastapi import APIRouter
from pydantic import BaseModel

from atri.core.services.impact import ImpactAnalysisService

router = APIRouter(prefix="/api/v1/impact", tags=["impact"])
service = ImpactAnalysisService()


class ImpactRequest(BaseModel):
    changed_ids: list[str]
    adjacency: dict[str, list[str]]
    depth: int = 2


@router.post("/analyze")
def analyze_impact(payload: ImpactRequest) -> dict:
    return service.analyze(payload.changed_ids, payload.adjacency, payload.depth)
