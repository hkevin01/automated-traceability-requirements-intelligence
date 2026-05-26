from fastapi import APIRouter, Depends
from pydantic import BaseModel

from atri.api.schemas import ImpactAnalysisResponse
from atri.core.services.graph_store import TraceGraphStore
from atri.core.services.graph_factory import make_graph_store
from atri.core.services.impact import ImpactAnalysisService
from atri.core.tenancy import TenantContext, resolve_tenant

router = APIRouter(prefix="/api/v1/impact", tags=["impact"])


class ImpactRequest(BaseModel):
    changed_ids: list[str]
    adjacency: dict[str, list[str]] | None = None
    depth: int = 2


@router.post("/analyze", response_model=ImpactAnalysisResponse)
def analyze_impact(
    payload: ImpactRequest,
    tenant: TenantContext = Depends(resolve_tenant),
) -> dict:
    """
    ID: ATRI-IMPACT-001
    Purpose: Analyze the downstream impact of changed artifacts for the current tenant.
    """
    svc = ImpactAnalysisService(make_graph_store(str(tenant.graph_store_path)))
    return svc.analyze(payload.changed_ids, payload.adjacency, payload.depth)
