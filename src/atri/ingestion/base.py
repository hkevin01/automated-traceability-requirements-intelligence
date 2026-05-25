"""
ID: ATRI-ING-BASE-001
Purpose: Abstract base class for all ingestion adapters and shared IngestionResult model.
Requirement: Every adapter must normalise source data into a list of IngestionResult items.
Rationale: Uniform data contract allows the pipeline to treat all sources identically.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class IngestionResult:
    """
    ID: ATRI-ING-BASE-002
    Purpose: Canonical representation of a single ingested artifact.
    Inputs: All string fields; metadata is a free-form dict.
    Outputs: Hashable, JSON-serialisable record.
    Preconditions: artifact_id and source must be non-empty.
    Postconditions: content_hash is always a stable SHA-256 hex digest of title+body.
    Failure modes: ValueError raised if required fields are empty strings.
    """

    artifact_id: str
    source: str
    artifact_type: str
    title: str
    body: str
    version: str = "v1"
    metadata: dict[str, Any] = field(default_factory=dict)
    content_hash: str = field(default="", init=False)

    def __post_init__(self) -> None:
        # Validation
        if not self.artifact_id:
            raise ValueError("artifact_id must be non-empty")
        if not self.source:
            raise ValueError("source must be non-empty")
        # Stable content hash for deduplication and change detection
        raw = f"{self.title}\n{self.body}".encode("utf-8")
        self.content_hash = hashlib.sha256(raw).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict."""
        return {
            "artifact_id": self.artifact_id,
            "source": self.source,
            "artifact_type": self.artifact_type,
            "title": self.title,
            "body": self.body,
            "version": self.version,
            "metadata": self.metadata,
            "content_hash": self.content_hash,
        }


# ---------------------------------------------------------------------------
# Abstract base adapter
# ---------------------------------------------------------------------------

class BaseIngestionAdapter(ABC):
    """
    ID: ATRI-ING-BASE-003
    Purpose: Abstract base for all source-specific ingestion adapters.
    Requirement: Subclasses implement `ingest()` to return normalised IngestionResult items.
    Preconditions: source_name must identify the origin system.
    Side Effects: None at this level; subclasses may perform I/O.
    """

    def __init__(self, source_name: str) -> None:
        self._source_name = source_name

    @property
    def source_name(self) -> str:
        return self._source_name

    @abstractmethod
    def ingest(self, source: Any) -> list[IngestionResult]:
        """
        Ingest artifacts from `source` (path, URL, bytes, dict, etc.) and
        return a list of normalised IngestionResult objects.
        """

    # ------------------------------------------------------------------
    # Shared persistence helper
    # ------------------------------------------------------------------

    @staticmethod
    def persist(results: list[IngestionResult], store_path: str | Path) -> None:
        """
        ID: ATRI-ING-BASE-004
        Purpose: Append ingested results to a JSONL file for immutable provenance.
        Inputs: results - list of IngestionResult; store_path - target JSONL path.
        Side Effects: Creates parent directories; appends to file.
        Failure modes: IOError propagates to caller.
        """
        path = Path(store_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for item in results:
                fh.write(json.dumps(item.to_dict(), sort_keys=True) + "\n")
