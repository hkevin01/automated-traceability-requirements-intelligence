"""
ID: ATRI-ING-SYSML-001
Purpose: Ingestion adapter for SysML v1 XMI and SysML v2 JSON exports.
Requirement: Parse SysML model elements (RequirementBlocks, Blocks, UseCases)
             into ATRI IngestionResult artifacts.
Rationale: Systems engineers use SysML for model-based systems engineering (MBSE);
           requirement and block elements must be traceable in ATRI.
Inputs: XMI file path (.xmi, .uml, .xml) or SysML v2 JSON.
Outputs: list[IngestionResult]
Failure modes: FileNotFoundError, ET.ParseError, json.JSONDecodeError
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from atri.ingestion.base import BaseIngestionAdapter, IngestionResult


# SysML XMI element types to ATRI artifact types
_XMI_TYPE_MAP: dict[str, str] = {
    "sysml:requirement": "requirement",
    "sysml:requirementblock": "requirement",
    "sysml:block": "design",
    "sysml:valueblock": "design",
    "sysml:usecase": "requirement",
    "sysml:activity": "design",
    "sysml:testcase": "test",
    "uml:class": "design",
    "uml:usecase": "requirement",
    "uml:activity": "design",
    "uml:component": "design",
    "uml:interface": "design",
    "uml:operation": "design",
}


class SysMLAdapter(BaseIngestionAdapter):
    """
    ID: ATRI-ING-SYSML-002
    Purpose: Adapter for SysML XMI and JSON exports.
    Preconditions: Source file must exist and be valid XML/JSON.
    Postconditions: Returns IngestionResult list for all requirement and block elements found.
    Side Effects: Reads file from disk.
    """

    def __init__(self) -> None:
        super().__init__("sysml")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def ingest(self, source: str | Path | bytes) -> list[IngestionResult]:
        """
        Purpose: Dispatch to XMI or JSON parser based on content type.
        Inputs: file path (.xmi, .uml, .xml, .json) or raw bytes.
        Outputs: list[IngestionResult]
        """
        if isinstance(source, bytes):
            content = source.decode("utf-8", errors="replace")
            # JSON detection heuristic
            stripped = content.lstrip()
            if stripped.startswith("{") or stripped.startswith("["):
                return self._parse_json(json.loads(content))
            return self._parse_xmi_string(content)

        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"SysML source not found: {path}")

        if path.suffix.lower() == ".json":
            return self._parse_json(json.loads(path.read_text(encoding="utf-8")))

        return self._parse_xmi_string(path.read_text(encoding="utf-8", errors="replace"))

    # ------------------------------------------------------------------
    # XMI parsing
    # ------------------------------------------------------------------

    def _parse_xmi_string(self, content: str) -> list[IngestionResult]:
        """Parse an XMI string (SysML v1 / UML 2 XMI format)."""
        # Strip namespace prefixes to simplify element matching
        clean = self._strip_ns(content)
        root = ET.fromstring(clean)
        return self._walk_xmi(root)

    def _walk_xmi(self, root: ET.Element, prefix: str = "") -> list[IngestionResult]:
        """Recursively walk XMI tree and collect typed elements."""
        results: list[IngestionResult] = []
        for element in root.iter():
            xmi_type = (
                element.get("xmi:type")
                or element.get("type")
                or element.tag
                or ""
            ).lower()

            artifact_type = _XMI_TYPE_MAP.get(xmi_type)
            if artifact_type is None:
                continue

            raw_id = element.get("xmi:id") or element.get("id") or element.get("href") or ""
            name = element.get("name") or element.get("humanName") or ""
            text = (
                element.findtext("ownedComment/body")
                or element.findtext("text")
                or element.get("text")
                or element.get("body")
                or ""
            ).strip()

            if not name and not text:
                continue

            artifact_id = self._sanitise_id(raw_id or name or f"SML-{len(results)+1}")

            results.append(
                IngestionResult(
                    artifact_id=f"SML-{artifact_id}",
                    source=self._source_name,
                    artifact_type=artifact_type,
                    title=name or artifact_id,
                    body=text or name,
                    version="v1",
                    metadata={"xmi_type": xmi_type, "xmi_id": raw_id},
                )
            )
        return results

    # ------------------------------------------------------------------
    # SysML v2 JSON parsing (Pilot Implementation JSON)
    # ------------------------------------------------------------------

    def _parse_json(self, payload: Any) -> list[IngestionResult]:
        """
        Parse a SysML v2 JSON export.
        Handles both a list of elements and a dict with "@graph" / "elements" keys.
        """
        elements: list[dict[str, Any]] = []
        if isinstance(payload, list):
            elements = payload
        elif isinstance(payload, dict):
            elements = payload.get("elements", payload.get("@graph", [payload]))

        results: list[IngestionResult] = []
        for idx, elem in enumerate(elements, start=1):
            raw_type = (
                elem.get("@type")
                or elem.get("qualifiedName", "").split("::")[-1]
                or ""
            ).lower()

            # Map SysML v2 types to ATRI types
            if "requirement" in raw_type:
                artifact_type = "requirement"
            elif "test" in raw_type:
                artifact_type = "test"
            elif "block" in raw_type or "part" in raw_type:
                artifact_type = "design"
            elif "usecase" in raw_type:
                artifact_type = "requirement"
            else:
                continue

            elem_id = elem.get("@id") or elem.get("identifier") or f"SML-{idx}"
            name = elem.get("name") or elem.get("qualifiedName") or str(elem_id)
            body = (
                elem.get("documentation")
                or elem.get("text")
                or elem.get("description")
                or name
            )

            results.append(
                IngestionResult(
                    artifact_id=f"SML-{self._sanitise_id(str(elem_id))}",
                    source=self._source_name,
                    artifact_type=artifact_type,
                    title=name,
                    body=str(body).strip(),
                    version="v1",
                    metadata={"sysml_type": raw_type, "element_id": str(elem_id)},
                )
            )
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_ns(xml_str: str) -> str:
        return re.sub(r'\s*xmlns(?::\w+)?="[^"]*"', "", xml_str)

    @staticmethod
    def _sanitise_id(raw: str) -> str:
        return re.sub(r"[^\w\-.]", "_", raw.strip())[:120]
