from fastapi import APIRouter
from pydantic import BaseModel

from atri.core.services.gaps import GapDetectionService

router = APIRouter(prefix="/api/v1/gaps", tags=["gaps"])
service = GapDetectionService()


class ArtifactEntry(BaseModel):
    artifact_id: str
    artifact_type: str


class LinkEntry(BaseModel):
    source_id: str
    target_id: str


class GapRequest(BaseModel):
    artifacts: list[ArtifactEntry]
    links: list[LinkEntry]


@router.post("/detect")
def detect_gaps(payload: GapRequest) -> dict:
    return {
        "findings": service.detect(
            artifacts=[item.model_dump() for item in payload.artifacts],
            links=[item.model_dump() for item in payload.links],
        )
    }
