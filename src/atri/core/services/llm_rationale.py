"""
ID: ATRI-LLM-001
Purpose: LLM-enriched trace-link rationale generation.
Requirement: Given a source and target artifact, produce a human-readable rationale
             explaining why the link exists, citing specific shared concepts.
Rationale: Token-overlap heuristics explain *what* matched; an LLM explains *why*
           that match is significant in the context of the program's safety case.
Inputs:
  source      - dict with artifact_id, artifact_type, title, body.
  target      - dict with artifact_id, artifact_type, title, body.
  context     - optional extra context string (e.g. standard clause).
Outputs: RationaleResult dataclass with text, model, cached, token_count.
Preconditions: ATRI_LLM_RATIONALE_ENABLED=true and at least one AI provider key set.
Postconditions: Result is persisted to the JSON cache; repeated calls for the same
                pair return the cached value without making an API call.
Assumptions: Network access to OpenAI or Azure OpenAI endpoint.
Side Effects: Writes to llm_rationale_cache.json; makes external HTTPS call.
Failure modes:
  - API key missing or invalid: returns fallback heuristic rationale.
  - Rate limit: returns fallback with is_fallback=True.
  - Network error: returns fallback with is_fallback=True.
Constraints: Max ~2 000 tokens combined input to keep cost predictable.
Verification: Unit tests mock the HTTP call; integration tests require env keys.
References: OpenAI Chat Completions API; Azure OpenAI REST API.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

@dataclass
class RationaleResult:
    """
    ID: ATRI-LLM-002
    Purpose: Immutable result of a rationale generation call.
    Postconditions: is_fallback is True whenever no LLM call was made.
    """
    source_id: str
    target_id: str
    rationale: str
    model: str
    is_fallback: bool = False
    token_count: int = 0
    cached: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serialisable representation."""
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "rationale": self.rationale,
            "model": self.model,
            "is_fallback": self.is_fallback,
            "token_count": self.token_count,
            "cached": self.cached,
        }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class LLMRationaleService:
    """
    ID: ATRI-LLM-003
    Purpose: Generate and cache LLM rationale for trace link pairs.
    Side Effects: HTTP calls to OpenAI/Azure; disk writes to cache file.
    Failure modes: Graceful fallback to heuristic text on all provider errors.
    """

    _SYSTEM_PROMPT = (
        "You are a safety-critical systems traceability analyst. "
        "Given a source artifact (requirement, design, test, or code) and a "
        "target artifact, write a concise 2-3 sentence rationale explaining "
        "why a trace link between them is appropriate. Focus on the shared "
        "safety, functional, or verification intent. "
        "Do not repeat the artifact titles verbatim - synthesise the connection."
    )

    def __init__(self, cache_path: str | Path | None = None) -> None:
        from atri.config import settings  # noqa: PLC0415 - late import avoids circular

        self._settings = settings
        self._cache_path = Path(cache_path or settings.llm_rationale_cache_path)
        self._cache: dict[str, dict] = self._load_cache()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def explain(
        self,
        source: dict[str, Any],
        target: dict[str, Any],
        context: str = "",
    ) -> RationaleResult:
        """
        ID: ATRI-LLM-004
        Purpose: Return a rationale for the source->target trace link.
        Inputs:
          source  - artifact dict (artifact_id, artifact_type, title, body).
          target  - artifact dict (artifact_id, artifact_type, title, body).
          context - optional additional context string.
        Outputs: RationaleResult; cached result if already computed.
        Failure modes: Returns is_fallback=True result on any provider error.
        """
        cache_key = self._cache_key(source, target)
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            return RationaleResult(
                source_id=source.get("artifact_id", ""),
                target_id=target.get("artifact_id", ""),
                rationale=cached["rationale"],
                model=cached.get("model", "cache"),
                is_fallback=cached.get("is_fallback", False),
                token_count=cached.get("token_count", 0),
                cached=True,
            )

        if not self._settings.llm_rationale_enabled:
            return self._fallback(source, target)

        result = self._call_provider(source, target, context)
        self._cache[cache_key] = result.to_dict()
        self._save_cache()
        return result

    def cache_size(self) -> int:
        """Return number of cached rationale entries."""
        return len(self._cache)

    def clear_cache(self) -> None:
        """Wipe the in-memory and on-disk rationale cache."""
        self._cache = {}
        if self._cache_path.exists():
            self._cache_path.unlink()

    # ------------------------------------------------------------------
    # Internal - provider dispatch
    # ------------------------------------------------------------------

    def _call_provider(
        self,
        source: dict,
        target: dict,
        context: str,
    ) -> RationaleResult:
        """
        ID: ATRI-LLM-005
        Purpose: Dispatch to OpenAI or Azure OpenAI; fall back on any error.
        Error Handling: Catches all exceptions and returns is_fallback=True.
        """
        user_prompt = self._build_prompt(source, target, context)
        try:
            if self._settings.azure_openai_api_key and self._settings.azure_openai_endpoint:
                return self._call_azure(source, target, user_prompt)
            if self._settings.openai_api_key:
                return self._call_openai(source, target, user_prompt)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM rationale call failed: %s - falling back to heuristic.", exc)
        return self._fallback(source, target)

    def _call_openai(
        self,
        source: dict,
        target: dict,
        user_prompt: str,
    ) -> RationaleResult:
        """
        ID: ATRI-LLM-006
        Purpose: Call the OpenAI Chat Completions API.
        Preconditions: openai package installed; ATRI_OPENAI_API_KEY set.
        Failure modes: ImportError if openai not installed; propagates to caller.
        """
        import openai  # noqa: PLC0415

        client = openai.OpenAI(api_key=self._settings.openai_api_key)
        response = client.chat.completions.create(
            model=self._settings.openai_model,
            messages=[
                {"role": "system", "content": self._SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=256,
            temperature=0.2,
        )
        text = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else 0
        return RationaleResult(
            source_id=source.get("artifact_id", ""),
            target_id=target.get("artifact_id", ""),
            rationale=text.strip(),
            model=self._settings.openai_model,
            is_fallback=False,
            token_count=tokens,
        )

    def _call_azure(
        self,
        source: dict,
        target: dict,
        user_prompt: str,
    ) -> RationaleResult:
        """
        ID: ATRI-LLM-007
        Purpose: Call Azure OpenAI Chat Completions endpoint.
        Preconditions: openai package installed; Azure env vars set.
        Failure modes: ImportError if openai not installed; propagates to caller.
        """
        import openai  # noqa: PLC0415

        client = openai.AzureOpenAI(
            api_key=self._settings.azure_openai_api_key,
            azure_endpoint=self._settings.azure_openai_endpoint,
            api_version="2024-02-01",
        )
        response = client.chat.completions.create(
            model=self._settings.azure_openai_deployment,
            messages=[
                {"role": "system", "content": self._SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=256,
            temperature=0.2,
        )
        text = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else 0
        return RationaleResult(
            source_id=source.get("artifact_id", ""),
            target_id=target.get("artifact_id", ""),
            rationale=text.strip(),
            model=f"azure/{self._settings.azure_openai_deployment}",
            is_fallback=False,
            token_count=tokens,
        )

    # ------------------------------------------------------------------
    # Internal - helpers
    # ------------------------------------------------------------------

    def _build_prompt(self, source: dict, target: dict, context: str) -> str:
        lines = [
            f"Source artifact ({source.get('artifact_type', 'unknown')}):",
            f"  ID: {source.get('artifact_id', '')}",
            f"  Title: {source.get('title', '')}",
            f"  Body: {source.get('body', '')[:600]}",
            "",
            f"Target artifact ({target.get('artifact_type', 'unknown')}):",
            f"  ID: {target.get('artifact_id', '')}",
            f"  Title: {target.get('title', '')}",
            f"  Body: {target.get('body', '')[:600]}",
        ]
        if context:
            lines += ["", f"Additional context: {context[:300]}"]
        lines.append("\nProvide the trace link rationale:")
        return "\n".join(lines)

    @staticmethod
    def _fallback(source: dict, target: dict) -> RationaleResult:
        """Build a deterministic heuristic rationale when LLM is unavailable."""
        src_type = source.get("artifact_type", "artifact")
        tgt_type = target.get("artifact_type", "artifact")
        src_title = source.get("title", source.get("artifact_id", ""))
        tgt_title = target.get("title", target.get("artifact_id", ""))
        rationale = (
            f"The {src_type} '{src_title}' has a trace relationship to the "
            f"{tgt_type} '{tgt_title}' based on shared terminology and lifecycle "
            f"alignment. LLM enrichment is disabled or unavailable; this rationale "
            f"was generated by the heuristic fallback."
        )
        return RationaleResult(
            source_id=source.get("artifact_id", ""),
            target_id=target.get("artifact_id", ""),
            rationale=rationale,
            model="heuristic-fallback",
            is_fallback=True,
        )

    @staticmethod
    def _cache_key(source: dict, target: dict) -> str:
        """Deterministic cache key from the artifact bodies."""
        raw = (
            source.get("artifact_id", "")
            + "|"
            + target.get("artifact_id", "")
            + "|"
            + source.get("body", "")[:300]
            + "|"
            + target.get("body", "")[:300]
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def _load_cache(self) -> dict[str, dict]:
        if self._cache_path.exists():
            try:
                return json.loads(self._cache_path.read_text())
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_cache(self) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(json.dumps(self._cache, indent=2))
