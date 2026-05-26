"""
ID: TEST-LLM-001
Purpose: Unit tests for LLMRationaleService - fallback, cache, to_dict, prompt.
"""
from __future__ import annotations
import json
from pathlib import Path
from atri.core.services.llm_rationale import LLMRationaleService, RationaleResult


def _make_artifact(artifact_id: str, title: str = "Title", body: str = "Body") -> dict:
    return {"artifact_id": artifact_id, "artifact_type": "requirement", "title": title, "body": body}


def test_fallback_returned_when_llm_disabled(tmp_path):
    svc = LLMRationaleService(cache_path=tmp_path / "cache.json")
    result = svc.explain(_make_artifact("A", title="Alpha"), _make_artifact("B", title="Beta"))
    assert result.is_fallback is True
    assert "Alpha" in result.rationale or "Beta" in result.rationale
    assert result.model == "heuristic-fallback"


def test_fallback_result_not_cached(tmp_path):
    svc = LLMRationaleService(cache_path=tmp_path / "cache.json")
    svc.explain(_make_artifact("A"), _make_artifact("B"))
    # Fallback results are NOT persisted to avoid polluting cache with low-quality data
    # (cache is only written for real LLM responses)
    # Calling again should re-run fallback, not hit cache
    result2 = svc.explain(_make_artifact("A"), _make_artifact("B"))
    assert result2.cached is False


def test_to_dict_contains_all_fields(tmp_path):
    svc = LLMRationaleService(cache_path=tmp_path / "cache.json")
    result = svc.explain(_make_artifact("X"), _make_artifact("Y"))
    d = result.to_dict()
    for key in ("source_id", "target_id", "rationale", "model", "is_fallback", "token_count", "cached"):
        assert key in d


def test_cache_size_zero_initially(tmp_path):
    svc = LLMRationaleService(cache_path=tmp_path / "cache.json")
    assert svc.cache_size() == 0


def test_clear_cache(tmp_path):
    cache_file = tmp_path / "cache.json"
    # Manually seed the cache
    cache_file.write_text(json.dumps({"somekey": {"rationale": "hi", "model": "x", "is_fallback": False, "token_count": 0, "source_id": "s", "target_id": "t"}}))
    svc = LLMRationaleService(cache_path=cache_file)
    assert svc.cache_size() == 1
    svc.clear_cache()
    assert svc.cache_size() == 0
    assert not cache_file.exists()


def test_cache_hit(tmp_path):
    cache_file = tmp_path / "cache.json"
    from atri.core.services.llm_rationale import LLMRationaleService
    svc = LLMRationaleService(cache_path=cache_file)
    # Build the cache key exactly as the service would
    src = _make_artifact("S1", body="hello world")
    tgt = _make_artifact("T1", body="world hello")
    import hashlib
    raw = src["artifact_id"] + "|" + tgt["artifact_id"] + "|" + src["body"][:300] + "|" + tgt["body"][:300]
    key = hashlib.sha256(raw.encode()).hexdigest()
    # Pre-populate cache
    svc._cache[key] = {
        "source_id": "S1",
        "target_id": "T1",
        "rationale": "Cached rationale text",
        "model": "gpt-4o-mini",
        "is_fallback": False,
        "token_count": 42,
    }
    result = svc.explain(src, tgt)
    assert result.cached is True
    assert result.rationale == "Cached rationale text"
    assert result.token_count == 42


def test_result_dataclass_defaults():
    r = RationaleResult(source_id="a", target_id="b", rationale="text", model="m")
    assert r.is_fallback is False
    assert r.token_count == 0
    assert r.cached is False
