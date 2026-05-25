"""
ID: ATRI-ING-JAMA-001
Purpose: Ingestion adapter for Jama Connect REST API and CSV exports.
Requirement: Ingest requirements from Jama via REST API (JSON) or exported CSV.
Rationale: Jama is widely adopted in medical device and automotive IEC/ISO programs.
Inputs: dict (API response payload) or file path to Jama CSV export.
Outputs: list[IngestionResult]
Failure modes: KeyError on missing fields (caught, defaults applied);
               FileNotFoundError for missing CSV files.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from atri.ingestion.base import BaseIngestionAdapter, IngestionResult


class JamaAdapter(BaseIngestionAdapter):
    """
    ID: ATRI-ING-JAMA-002
    Purpose: Adapter for Jama Connect data (REST API JSON or CSV export).
    Preconditions: Source is either a dict/list (API payload), a Path (CSV), or bytes.
    Postconditions: Returns normalised IngestionResult list; never raises on empty data.
    Side Effects: Reads file from disk when source is a Path.
    """

    # Jama item-type name to ATRI artifact_type mapping
    _TYPE_MAP: dict[str, str] = {
        "text": "requirement",
        "functional requirement": "requirement",
        "system requirement": "requirement",
        "component requirement": "requirement",
        "feature": "requirement",
        "use case": "requirement",
        "test case": "test",
        "test plan": "test",
        "test run": "test",
        "defect": "risk",
        "risk": "risk",
        "hazard": "hazard",
        "design": "design",
    }

    def __init__(self) -> None:
        super().__init__("jama")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def ingest(self, source: Any) -> list[IngestionResult]:
        """
        Purpose: Dispatch to JSON or CSV parser based on input type.
        Inputs: dict/list (API payload), Path (CSV), bytes (raw CSV), str (JSON string or path).
        Outputs: list[IngestionResult]
        """
        if isinstance(source, (dict, list)):
            return self._parse_api_payload(source)

        if isinstance(source, bytes):
            try:
                parsed = json.loads(source.decode("utf-8"))
                return self._parse_api_payload(parsed)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return self._parse_csv_content(source.decode("utf-8", errors="replace"))

        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Jama source not found: {path}")

        if path.suffix.lower() == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            return self._parse_api_payload(payload)

        return self._parse_csv(path)

    # ------------------------------------------------------------------
    # API JSON parsing (Jama REST /items response)
    # ------------------------------------------------------------------

    def _parse_api_payload(self, payload: Any) -> list[IngestionResult]:
        """
        Parse Jama REST API response.
        Expected format:
          {"data": [{"id": 123, "fields": {"name": "...", "description": "..."},
                     "itemType": "...", "documentKey": "REQ-1"}, ...]}
        Also handles a plain list of item dicts.
        """
        items: list[dict[str, Any]] = []
        if isinstance(payload, dict):
            items = payload.get("data", [payload])
        elif isinstance(payload, list):
            items = payload

        results: list[IngestionResult] = []
        for idx, item in enumerate(items, start=1):
            fields = item.get("fields", {})
            jama_id = item.get("documentKey") or item.get("id") or f"JAMA-{idx}"
            title = fields.get("name") or fields.get("title") or str(jama_id)
            body = (
                fields.get("description")
                or fields.get("text")
                or fields.get("longDescription")
                or ""
            )
            raw_type = (
                item.get("itemType")
                or item.get("itemtype")
                or fields.get("type")
                or "requirement"
            )
            artifact_type = self._TYPE_MAP.get(str(raw_type).lower(), "requirement")
            version = fields.get("version") or item.get("version") or "v1"
            metadata = {
                "jama_id": str(item.get("id", "")),
                "project": str(item.get("project", "")),
                "document_key": str(jama_id),
            }
            results.append(
                IngestionResult(
                    artifact_id=f"JAMA-{jama_id}",
                    source=self._source_name,
                    artifact_type=artifact_type,
                    title=str(title).strip(),
                    body=str(body).strip(),
                    version=str(version),
                    metadata=metadata,
                )
            )
        return results

    # ------------------------------------------------------------------
    # CSV parsing
    # ------------------------------------------------------------------

    def _parse_csv(self, path: Path) -> list[IngestionResult]:
        for encoding in ("utf-8-sig", "latin-1"):
            try:
                return self._parse_csv_content(path.read_text(encoding=encoding))
            except UnicodeDecodeError:
                continue
        return self._parse_csv_content(path.read_text(encoding="utf-8", errors="replace"))

    def _parse_csv_content(self, content: str) -> list[IngestionResult]:
        results: list[IngestionResult] = []
        reader = csv.DictReader(content.splitlines())
        if reader.fieldnames is None:
            return results

        lower_headers = {h.lower(): h for h in reader.fieldnames}

        def col(row: dict, *candidates: str) -> str:
            for c in candidates:
                key = lower_headers.get(c.lower())
                if key and row.get(key):
                    return row[key].strip()
            return ""

        for idx, row in enumerate(reader, start=2):
            jama_id = col(row, "id", "document key", "key") or f"JAMA-{idx}"
            title = col(row, "name", "title", "summary") or jama_id
            body = col(row, "description", "text", "long description") or ""
            raw_type = col(row, "item type", "type", "category") or "requirement"
            artifact_type = self._TYPE_MAP.get(raw_type.lower(), "requirement")
            version = col(row, "version", "baseline") or "v1"
            results.append(
                IngestionResult(
                    artifact_id=f"JAMA-{jama_id}",
                    source=self._source_name,
                    artifact_type=artifact_type,
                    title=title,
                    body=body,
                    version=version,
                )
            )
        return results
