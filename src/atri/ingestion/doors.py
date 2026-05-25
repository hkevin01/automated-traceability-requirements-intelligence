"""
ID: ATRI-ING-DOORS-001
Purpose: Ingestion adapter for IBM DOORS / DOORS Next exports.
Requirement: Parse CSV and XML-based DOORS exports into IngestionResult items.
Rationale: DOORS is the predominant requirements management tool in aerospace/defence;
           CSV export is the most common interchange format.
Inputs: CSV file path (str or Path), optional XML file path.
Outputs: list[IngestionResult]
Failure modes: FileNotFoundError, csv.Error, xml.etree.ElementTree.ParseError
               all propagate to the caller.
"""

from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from atri.ingestion.base import BaseIngestionAdapter, IngestionResult


class DOORSAdapter(BaseIngestionAdapter):
    """
    ID: ATRI-ING-DOORS-002
    Purpose: Adapter for IBM DOORS CSV and XML exports.
    Preconditions: Source file must exist and be UTF-8 or Latin-1 encoded.
    Postconditions: Returns normalised IngestionResult list.
    Side Effects: Reads file from disk.
    """

    # Expected CSV column names (case-insensitive, flexible matching)
    _ID_COLS = ("id", "object id", "requirement id", "doors id")
    _TITLE_COLS = ("title", "name", "heading", "object heading")
    _BODY_COLS = ("body", "text", "description", "object text", "requirement text")
    _TYPE_COLS = ("type", "object type", "artifact type")
    _VER_COLS = ("version", "baseline", "revision")

    def __init__(self) -> None:
        super().__init__("doors")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def ingest(self, source: str | Path | bytes) -> list[IngestionResult]:
        """
        Purpose: Dispatch to CSV or XML parser based on file extension or content.
        Inputs: source - file path or raw bytes.
        Outputs: list[IngestionResult]
        """
        if isinstance(source, bytes):
            content = source.decode("utf-8", errors="replace")
            return self._parse_csv_content(content)

        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"DOORS source not found: {path}")

        suffix = path.suffix.lower()
        if suffix == ".xml":
            return self._parse_xml(path)
        return self._parse_csv(path)

    # ------------------------------------------------------------------
    # CSV parsing
    # ------------------------------------------------------------------

    def _parse_csv(self, path: Path) -> list[IngestionResult]:
        """Parse a DOORS CSV export file."""
        for encoding in ("utf-8-sig", "latin-1"):
            try:
                return self._parse_csv_content(path.read_text(encoding=encoding))
            except UnicodeDecodeError:
                continue
        return self._parse_csv_content(path.read_text(encoding="utf-8", errors="replace"))

    def _parse_csv_content(self, content: str) -> list[IngestionResult]:
        """Parse CSV content string into IngestionResult list."""
        results: list[IngestionResult] = []
        reader = csv.DictReader(content.splitlines())
        if reader.fieldnames is None:
            return results

        col_map = self._map_columns(list(reader.fieldnames))
        for row_num, row in enumerate(reader, start=2):
            artifact_id = self._get_col(row, col_map, "id") or f"DOORS-{row_num}"
            title = self._get_col(row, col_map, "title") or artifact_id
            body = self._get_col(row, col_map, "body") or ""
            artifact_type = self._normalise_type(
                self._get_col(row, col_map, "type") or "requirement"
            )
            version = self._get_col(row, col_map, "version") or "v1"
            metadata: dict[str, Any] = {
                k: v for k, v in row.items()
                if k not in (col_map.get("id"), col_map.get("title"),
                             col_map.get("body"), col_map.get("type"),
                             col_map.get("version"))
                and v
            }
            results.append(
                IngestionResult(
                    artifact_id=self._sanitise_id(artifact_id),
                    source=self._source_name,
                    artifact_type=artifact_type,
                    title=title.strip(),
                    body=body.strip(),
                    version=version,
                    metadata=metadata,
                )
            )
        return results

    # ------------------------------------------------------------------
    # XML parsing (DOORS ReqIF / native XML export)
    # ------------------------------------------------------------------

    def _parse_xml(self, path: Path) -> list[IngestionResult]:
        """
        Parse a DOORS XML export (ReqIF-compatible or native DOORS XML).
        Handles both <SPEC-OBJECT> elements (ReqIF) and <Requirement> elements
        (native DOORS XML export).
        """
        tree = ET.parse(str(path))
        root = tree.getroot()

        # Strip namespace prefixes for simpler XPath
        ns_stripped = self._strip_ns(ET.tostring(root, encoding="unicode"))
        clean_root = ET.fromstring(ns_stripped)

        results: list[IngestionResult] = []

        # ReqIF: SPEC-OBJECT elements
        for idx, obj in enumerate(clean_root.iter("SPEC-OBJECT"), start=1):
            artifact_id = obj.get("IDENTIFIER") or obj.get("id") or f"DOORS-{idx}"
            title = self._xml_text(obj, "LONG-NAME") or artifact_id
            body = self._xml_attr_value(obj, "ReqIF.Text") or self._xml_text(obj, "DESC") or ""
            results.append(
                IngestionResult(
                    artifact_id=self._sanitise_id(artifact_id),
                    source=self._source_name,
                    artifact_type="requirement",
                    title=title,
                    body=body,
                    version="v1",
                )
            )

        # Native DOORS XML: <Requirement> or <Object> elements
        if not results:
            for idx, obj in enumerate(clean_root.iter("Requirement"), start=1):
                artifact_id = obj.get("ID") or obj.get("id") or f"DOORS-{idx}"
                title = (obj.findtext("Title") or obj.findtext("Heading") or artifact_id).strip()
                body = (obj.findtext("Body") or obj.findtext("Text") or "").strip()
                results.append(
                    IngestionResult(
                        artifact_id=self._sanitise_id(artifact_id),
                        source=self._source_name,
                        artifact_type="requirement",
                        title=title,
                        body=body,
                        version="v1",
                    )
                )

        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _map_columns(self, fieldnames: list[str]) -> dict[str, str]:
        """Map logical column roles to actual CSV header names."""
        lower_map = {f.lower(): f for f in fieldnames}
        mapping: dict[str, str] = {}
        for role, candidates in [
            ("id", self._ID_COLS),
            ("title", self._TITLE_COLS),
            ("body", self._BODY_COLS),
            ("type", self._TYPE_COLS),
            ("version", self._VER_COLS),
        ]:
            for candidate in candidates:
                if candidate in lower_map:
                    mapping[role] = lower_map[candidate]
                    break
        return mapping

    @staticmethod
    def _get_col(row: dict[str, str], col_map: dict[str, str], role: str) -> str:
        key = col_map.get(role)
        return (row.get(key) or "").strip() if key else ""

    @staticmethod
    def _normalise_type(raw: str) -> str:
        mapping = {
            "functional requirement": "requirement",
            "system requirement": "requirement",
            "req": "requirement",
            "req.": "requirement",
            "design": "design",
            "test": "test",
            "hazard": "hazard",
            "risk": "risk",
        }
        return mapping.get(raw.strip().lower(), "requirement")

    @staticmethod
    def _sanitise_id(raw: str) -> str:
        return re.sub(r"[^\w\-.]", "_", raw.strip())[:120]

    @staticmethod
    def _strip_ns(xml_str: str) -> str:
        return re.sub(r'\s*xmlns(?::\w+)?="[^"]*"', "", xml_str)

    @staticmethod
    def _xml_text(element: ET.Element, tag: str) -> str:
        found = element.find(tag)
        return (found.text or "").strip() if found is not None else ""

    @staticmethod
    def _xml_attr_value(element: ET.Element, attr_name: str) -> str:
        """Search for ATTRIBUTE-VALUE-* children and return the value matching attr_name."""
        for child in element.iter():
            if child.get("ATTRIBUTE-DEFINITION-REF") == attr_name:
                text_node = child.find("THE-VALUE")
                if text_node is not None:
                    return (text_node.text or "").strip()
        return ""
