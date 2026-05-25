"""
ID: ATRI-ING-WORDPDF-001
Purpose: Ingestion adapter for Microsoft Word (.docx) and PDF documents.
Requirement: Extract paragraphs/sections from Word and PDF files as requirements.
Rationale: Many programs maintain requirements in Word or PDF format for external
           stakeholder distribution; ATRI must ingest these sources.
Inputs: file path (.docx or .pdf) or bytes.
Outputs: list[IngestionResult]
Failure modes: FileNotFoundError; python-docx and PyMuPDF errors propagate.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from atri.ingestion.base import BaseIngestionAdapter, IngestionResult


class WordPDFAdapter(BaseIngestionAdapter):
    """
    ID: ATRI-ING-WORDPDF-002
    Purpose: Parse Word/PDF documents into individual requirement IngestionResult records.
    Strategy:
      - Word: treat each non-empty paragraph as an artifact; use heading style for title.
      - PDF: treat each page's text blocks as artifacts grouped by page.
    Preconditions: python-docx and PyMuPDF must be installed (they are in pyproject.toml).
    Side Effects: Reads file from disk; may consume memory proportional to document size.
    """

    _HEADING_STYLES = ("heading 1", "heading 2", "heading 3", "title")
    _MIN_BODY_LENGTH = 20  # Skip very short paragraphs (likely artefacts)

    def __init__(self) -> None:
        super().__init__("word_pdf")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def ingest(self, source: str | Path | bytes, file_type: str = "auto") -> list[IngestionResult]:
        """
        Purpose: Auto-detect or use file_type hint to dispatch to Word or PDF parser.
        Inputs: source - file path or bytes; file_type - 'docx', 'pdf', or 'auto'.
        Outputs: list[IngestionResult]
        """
        if isinstance(source, bytes):
            return self._ingest_bytes(source, file_type)

        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Word/PDF source not found: {path}")

        suffix = path.suffix.lower()
        if suffix == ".docx" or file_type == "docx":
            return self._parse_docx_path(path)
        if suffix == ".pdf" or file_type == "pdf":
            return self._parse_pdf_path(path)

        raise ValueError(f"Unsupported file type: {suffix!r} - expected .docx or .pdf")

    # ------------------------------------------------------------------
    # Word (.docx)
    # ------------------------------------------------------------------

    def _parse_docx_path(self, path: Path) -> list[IngestionResult]:
        import docx  # noqa: PLC0415
        doc = docx.Document(str(path))
        return self._extract_docx_paragraphs(doc, source_label=path.name)

    def _ingest_bytes(self, data: bytes, file_type: str) -> list[IngestionResult]:
        # Detect by magic bytes
        if data[:4] == b"PK\x03\x04" or file_type == "docx":
            import io
            import docx  # noqa: PLC0415
            doc = docx.Document(io.BytesIO(data))
            return self._extract_docx_paragraphs(doc, source_label="uploaded.docx")
        # PDF magic bytes %PDF
        if data[:4] == b"%PDF" or file_type == "pdf":
            return self._parse_pdf_bytes(data)
        raise ValueError("Cannot determine file type from bytes; pass file_type='docx' or 'pdf'")

    def _extract_docx_paragraphs(self, doc: Any, source_label: str) -> list[IngestionResult]:
        """
        Extract paragraphs from a python-docx Document object.
        Headings become artifact titles; body paragraphs become requirement bodies.
        """
        results: list[IngestionResult] = []
        current_title = "Untitled Section"
        current_body_parts: list[str] = []
        section_counter = 0

        def flush_section() -> None:
            nonlocal section_counter
            body = " ".join(current_body_parts).strip()
            if len(body) >= self._MIN_BODY_LENGTH:
                section_counter += 1
                results.append(
                    IngestionResult(
                        artifact_id=f"WPDF-{self._slugify(source_label)}-{section_counter:04d}",
                        source=self._source_name,
                        artifact_type="requirement",
                        title=current_title,
                        body=body,
                        version="v1",
                        metadata={"source_file": source_label},
                    )
                )
            current_body_parts.clear()

        for para in doc.paragraphs:
            style_name = (para.style.name or "").lower() if para.style else ""
            text = para.text.strip()
            if not text:
                continue

            if any(style_name.startswith(h) for h in self._HEADING_STYLES):
                flush_section()
                current_title = text
            else:
                current_body_parts.append(text)

        flush_section()
        return results

    # ------------------------------------------------------------------
    # PDF
    # ------------------------------------------------------------------

    def _parse_pdf_path(self, path: Path) -> list[IngestionResult]:
        return self._parse_pdf_bytes(path.read_bytes(), source_label=path.name)

    def _parse_pdf_bytes(self, data: bytes, source_label: str = "uploaded.pdf") -> list[IngestionResult]:
        """
        Parse a PDF using PyMuPDF.
        Each page is treated as a separate artifact unless it contains only whitespace.
        """
        import fitz  # noqa: PLC0415 (PyMuPDF)
        results: list[IngestionResult] = []
        doc = fitz.Document(stream=data, filetype="pdf")

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text("text").strip()
            if len(text) < self._MIN_BODY_LENGTH:
                continue

            # Use first non-empty line as title, rest as body
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            title = lines[0][:200] if lines else f"Page {page_num + 1}"
            body = " ".join(lines[1:]) if len(lines) > 1 else text

            results.append(
                IngestionResult(
                    artifact_id=f"WPDF-{self._slugify(source_label)}-P{page_num + 1:04d}",
                    source=self._source_name,
                    artifact_type="requirement",
                    title=title,
                    body=body,
                    version="v1",
                    metadata={"source_file": source_label, "page": str(page_num + 1)},
                )
            )
        doc.close()
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _slugify(name: str) -> str:
        return re.sub(r"[^\w]", "_", Path(name).stem)[:40]
