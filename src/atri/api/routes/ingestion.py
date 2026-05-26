"""
ID: ATRI-ING-ROUTE-001
Purpose: Ingestion API routes - accept artifact uploads from DOORS, Jama, Visure, Word/PDF, and SysML.
Requirement: Expose a unified upload endpoint that dispatches to the correct adapter by source type.
Rationale: A single HTTP endpoint simplifies integration for CI pipelines and external tools.
Inputs: Multipart file upload or JSON payload with source_type hint.
Outputs: IngestionResponse listing the ingested artifact IDs and count.
Preconditions: None.
Postconditions: Ingested artifacts are appended to the JSONL store and returned in the response.
Failure modes: HTTP 400 for unsupported source_type; HTTP 422 for malformed payloads.
Constraints: File size limited by uvicorn's body-size limit (default 1 MB); configurable.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from atri.ingestion.base import BaseIngestionAdapter, IngestionResult
from atri.ingestion.doors import DOORSAdapter
from atri.ingestion.jama import JamaAdapter
from atri.ingestion.sysml import SysMLAdapter
from atri.ingestion.visure import VisureAdapter
from atri.ingestion.word_pdf import WordPDFAdapter
from atri.core.tenancy import TenantContext, resolve_tenant

router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])

# Registry maps source_type string to adapter instance
_ADAPTERS: dict[str, BaseIngestionAdapter] = {
    "doors": DOORSAdapter(),
    "jama": JamaAdapter(),
    "visure": VisureAdapter(),
    "word": WordPDFAdapter(),
    "pdf": WordPDFAdapter(),
    "sysml": SysMLAdapter(),
}


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------

class IngestionItemResponse(BaseModel):
    """ID: ATRI-ING-ROUTE-002 - Single ingested artifact summary."""
    artifact_id: str
    artifact_type: str
    title: str
    content_hash: str


class IngestionResponse(BaseModel):
    """ID: ATRI-ING-ROUTE-003 - Full ingestion response."""
    source_type: str
    artifact_count: int = Field(ge=0)
    artifacts: list[IngestionItemResponse]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload/{source_type}", response_model=IngestionResponse)
async def upload_artifact(
    source_type: str,
    file: UploadFile = File(...),
    tenant: TenantContext = Depends(resolve_tenant),
) -> dict:
    """
    ID: ATRI-ING-ROUTE-004
    Purpose: Accept a file upload and ingest it using the adapter for source_type.
    Inputs:
      source_type - path param identifying the source (doors, jama, visure, word, pdf, sysml).
      file        - multipart file upload.
    Outputs: IngestionResponse with artifact list.
    Failure modes: HTTP 400 for unknown source_type; HTTP 422 for parse failure.
    """
    adapter = _ADAPTERS.get(source_type.lower())
    if adapter is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown source_type '{source_type}'. "
                f"Supported: {sorted(_ADAPTERS.keys())}"
            ),
        )

    raw_bytes = await file.read()
    try:
        results: list[IngestionResult] = adapter.ingest(raw_bytes)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to parse uploaded file: {exc}",
        ) from exc

    BaseIngestionAdapter.persist(results, str(tenant.ingestion_store_path))

    return {
        "source_type": source_type,
        "artifact_count": len(results),
        "artifacts": [
            {
                "artifact_id": r.artifact_id,
                "artifact_type": r.artifact_type,
                "title": r.title,
                "content_hash": r.content_hash,
            }
            for r in results
        ],
    }


@router.get("/sources")
def list_sources() -> dict:
    """
    ID: ATRI-ING-ROUTE-005
    Purpose: Return the list of supported ingestion source types.
    Outputs: dict with sources list.
    """
    return {"sources": sorted(_ADAPTERS.keys())}
