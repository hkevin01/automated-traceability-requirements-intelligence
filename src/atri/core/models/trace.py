from dataclasses import dataclass
from typing import Literal

ArtifactType = Literal["requirement", "design", "code", "test", "hazard", "risk"]


@dataclass(slots=True)
class Artifact:
    artifact_id: str
    artifact_type: ArtifactType
    title: str
    body: str
    version: str


@dataclass(slots=True)
class TraceLink:
    source_id: str
    target_id: str
    link_type: str
    confidence: float
    rationale: str
