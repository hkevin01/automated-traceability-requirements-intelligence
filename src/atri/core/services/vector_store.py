"""
ID: ATRI-VEC-001
Purpose: Semantic vector retrieval service using TF-IDF cosine similarity.
Requirement: Provide semantic linking suggestions beyond simple token-overlap heuristics.
Rationale: TF-IDF cosine similarity improves recall over word-overlap for
           requirements that share domain terminology but differ in exact wording.
           This approach requires only numpy - no external ML service or GPU needed.
Inputs: Artifact list (id, title, body strings).
Outputs: Ranked candidate list with cosine similarity scores.
Assumptions: numpy is available; corpus is small-to-medium sized (< 50k documents).
Failure modes: Empty corpus returns empty results; division-by-zero protected.
Constraints: O(N*M) at query time where N=corpus size, M=vocabulary size.
Verification: Unit tests compare cosine similarity output to known ground truth.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Tokenisation
# ---------------------------------------------------------------------------

def _tokenise(text: str) -> list[str]:
    """
    ID: ATRI-VEC-002
    Purpose: Lowercase + split on non-alphanumeric, strip stopwords.
    Inputs: text - raw requirement text.
    Outputs: list of lowercase tokens.
    """
    _STOP = frozenset({
        "the", "a", "an", "and", "or", "of", "in", "to", "is", "are", "be",
        "with", "that", "this", "it", "by", "for", "on", "as", "at", "from",
        "its", "shall", "should", "must", "will", "may", "can", "not", "no",
        "have", "has", "been", "was", "were", "which", "where", "when", "all",
    })
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if t not in _STOP and len(t) > 1]


# ---------------------------------------------------------------------------
# TF-IDF helpers (pure Python + numpy)
# ---------------------------------------------------------------------------

def _tf(tokens: list[str]) -> dict[str, float]:
    """Compute term frequency for a token list."""
    if not tokens:
        return {}
    counts = Counter(tokens)
    total = len(tokens)
    return {term: count / total for term, count in counts.items()}


def _build_idf(corpus_tokens: list[list[str]]) -> dict[str, float]:
    """
    ID: ATRI-VEC-003
    Purpose: Compute inverse document frequency for the corpus.
    Inputs: corpus_tokens - list of token lists (one per document).
    Outputs: dict mapping term to IDF weight.
    """
    n_docs = len(corpus_tokens)
    if n_docs == 0:
        return {}
    df: dict[str, int] = {}
    for tokens in corpus_tokens:
        for term in set(tokens):
            df[term] = df.get(term, 0) + 1
    return {
        term: math.log((n_docs + 1) / (count + 1)) + 1.0
        for term, count in df.items()
    }


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    """Compute TF-IDF vector as sparse dict."""
    tf = _tf(tokens)
    return {term: tf_val * idf.get(term, 1.0) for term, tf_val in tf.items()}


def _cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """
    ID: ATRI-VEC-004
    Purpose: Compute cosine similarity between two sparse TF-IDF vectors.
    Inputs: vec_a, vec_b - sparse float dicts.
    Outputs: float in [0, 1].
    Preconditions: Both dicts must be non-empty for non-zero result.
    Failure modes: Returns 0.0 on zero-magnitude vectors (safe division).
    """
    common_terms = set(vec_a) & set(vec_b)
    if not common_terms:
        return 0.0
    dot = sum(vec_a[t] * vec_b[t] for t in common_terms)
    mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
    mag_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return min(1.0, dot / (mag_a * mag_b))


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------

class VectorSearchService:
    """
    ID: ATRI-VEC-005
    Purpose: Build and query a TF-IDF index over ingested artifacts for semantic linking.
    Requirement: Return semantically similar artifact candidates for a query artifact.
    Inputs: Artifact dicts with at minimum 'artifact_id', 'title', 'body' keys.
    Outputs: Ranked list of (artifact_id, score) tuples.
    Preconditions: `build_index` must be called before `query`.
    Postconditions: Index can be persisted to and reloaded from disk (JSON).
    Side Effects: Reads/writes index file on disk when store_path is set.
    Failure modes: Query against empty index returns empty list.
    """

    def __init__(self, store_path: str | Path | None = None) -> None:
        """
        Inputs: store_path - optional JSON file path for index persistence.
        """
        self._store_path = Path(store_path) if store_path else None
        self._idf: dict[str, float] = {}
        self._vectors: dict[str, dict[str, float]] = {}  # artifact_id -> tfidf vec
        self._metadata: dict[str, dict[str, Any]] = {}   # artifact_id -> artifact data

        if self._store_path and self._store_path.exists():
            self._load()

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def build_index(self, artifacts: list[dict[str, Any]]) -> None:
        """
        ID: ATRI-VEC-006
        Purpose: Build TF-IDF index from a list of artifact dicts.
        Inputs: artifacts - list of dicts with 'artifact_id', 'title', 'body'.
        Side Effects: Overwrites in-memory index; persists to disk if store_path set.
        """
        corpus_tokens: list[list[str]] = []
        indexed: list[tuple[str, list[str], dict[str, Any]]] = []

        for artifact in artifacts:
            aid = artifact.get("artifact_id", "")
            text = f"{artifact.get('title', '')} {artifact.get('body', '')}"
            tokens = _tokenise(text)
            corpus_tokens.append(tokens)
            indexed.append((aid, tokens, artifact))

        self._idf = _build_idf(corpus_tokens)
        self._vectors = {}
        self._metadata = {}

        for aid, tokens, artifact in indexed:
            self._vectors[aid] = _tfidf_vector(tokens, self._idf)
            self._metadata[aid] = artifact

        if self._store_path:
            self._save()

    def update_artifact(self, artifact: dict[str, Any]) -> None:
        """
        ID: ATRI-VEC-007
        Purpose: Add or update a single artifact's vector in the index.
        Note: Does not rebuild IDF - uses existing IDF table. Call build_index to refresh IDF.
        """
        aid = artifact.get("artifact_id", "")
        text = f"{artifact.get('title', '')} {artifact.get('body', '')}"
        tokens = _tokenise(text)
        self._vectors[aid] = _tfidf_vector(tokens, self._idf)
        self._metadata[aid] = artifact

    def query(
        self,
        artifact: dict[str, Any],
        top_k: int = 10,
        min_score: float = 0.1,
        exclude_same_type: bool = False,
    ) -> list[dict[str, Any]]:
        """
        ID: ATRI-VEC-008
        Purpose: Return top-k semantically similar artifacts for the given artifact.
        Inputs:
          artifact   - query artifact dict with 'artifact_id', 'title', 'body'.
          top_k      - maximum number of results to return (default 10).
          min_score  - minimum cosine similarity threshold (default 0.1).
          exclude_same_type - if True, skip artifacts of the same type.
        Outputs: list of dicts with 'artifact_id', 'score', 'artifact_type', 'title'.
        Preconditions: build_index must have been called.
        Postconditions: Results sorted by score descending; query artifact excluded.
        Failure modes: Returns empty list if index is empty.
        """
        if not self._vectors:
            return []

        query_id = artifact.get("artifact_id", "")
        text = f"{artifact.get('title', '')} {artifact.get('body', '')}"
        query_tokens = _tokenise(text)
        query_vec = _tfidf_vector(query_tokens, self._idf)

        if not query_vec:
            return []

        scores: list[tuple[str, float]] = []
        for aid, vec in self._vectors.items():
            if aid == query_id:
                continue
            if exclude_same_type:
                meta = self._metadata.get(aid, {})
                if meta.get("artifact_type") == artifact.get("artifact_type"):
                    continue
            score = _cosine_similarity(query_vec, vec)
            if score >= min_score:
                scores.append((aid, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        results = []
        for aid, score in scores[:top_k]:
            meta = self._metadata.get(aid, {})
            results.append({
                "artifact_id": aid,
                "score": round(score, 4),
                "artifact_type": meta.get("artifact_type", ""),
                "title": meta.get("title", ""),
                "rationale": "TF-IDF cosine semantic similarity",
            })
        return results

    def corpus_size(self) -> int:
        """Return the number of artifacts currently indexed."""
        return len(self._vectors)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self) -> None:
        """Persist the index to a JSON file."""
        assert self._store_path is not None
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "idf": self._idf,
            "vectors": self._vectors,
            "metadata": self._metadata,
        }
        self._store_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load(self) -> None:
        """Load the index from a JSON file."""
        assert self._store_path is not None
        try:
            payload = json.loads(self._store_path.read_text(encoding="utf-8"))
            self._idf = payload.get("idf", {})
            self._vectors = payload.get("vectors", {})
            self._metadata = payload.get("metadata", {})
        except (json.JSONDecodeError, KeyError):
            # Corrupted index - start fresh
            self._idf = {}
            self._vectors = {}
            self._metadata = {}
