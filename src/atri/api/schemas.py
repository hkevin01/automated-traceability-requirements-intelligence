from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]


class DashboardSummaryResponse(BaseModel):
    trace_coverage: float = Field(ge=0.0, le=1.0)
    suspect_links: int = Field(ge=0)
    orphan_requirements: int = Field(ge=0)
    orphan_tests: int = Field(ge=0)
    high_risk_changes_7d: int = Field(ge=0)


class TraceabilitySuggestionResponse(BaseModel):
    source_id: str
    target_id: str
    link_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


class TraceabilitySuggestionsResponse(BaseModel):
    suggestions: list[TraceabilitySuggestionResponse]


class ReviewStatusResponse(BaseModel):
    source_id: str
    target_id: str
    decision: str
    reviewer: str
    comments: str = ""


class ReviewDecisionRequest(BaseModel):
    source_id: str
    target_id: str
    decision: str
    reviewer: str
    comments: str = ""


class ReviewDecisionResponse(BaseModel):
    review: ReviewStatusResponse


class ReviewSummaryResponse(BaseModel):
    total_reviews: int = Field(ge=0)
    accepted_reviews: int = Field(ge=0)
    rejected_reviews: int = Field(ge=0)
    pending_reviews: int = Field(ge=0)


class GraphArtifactRequest(BaseModel):
    artifact_id: str
    artifact_type: str
    title: str
    body: str
    version: str


class GraphLinkRequest(BaseModel):
    source_id: str
    target_id: str
    link_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


class GraphSyncRequest(BaseModel):
    artifacts: list[GraphArtifactRequest]
    links: list[GraphLinkRequest]


class GraphSyncResponse(BaseModel):
    artifact_count: int = Field(ge=0)
    link_count: int = Field(ge=0)


class AuditEventResponse(BaseModel):
    event_type: str
    subject_id: str
    actor: str
    timestamp: str
    details: dict[str, str]


class AuditSummaryResponse(BaseModel):
    total_events: int = Field(ge=0)


class ImpactFindingResponse(BaseModel):
    artifact_id: str
    score: float = Field(ge=0.0, le=1.0)
    distance: int = Field(ge=1)


class ImpactAnalysisResponse(BaseModel):
    changed: list[str]
    impacted: list[ImpactFindingResponse]


class GapFindingResponse(BaseModel):
    artifact_id: str
    finding_type: str
    severity: str
    rationale: str


class GapDetectionResponse(BaseModel):
    findings: list[GapFindingResponse]


class CapabilityResponse(BaseModel):
    name: str
    description: str


class CapabilityCatalogResponse(BaseModel):
    capabilities: list[CapabilityResponse]