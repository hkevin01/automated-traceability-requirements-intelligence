"""
ID: ATRI-GFACT-001
Purpose: Graph store factory - selects Neo4j or local JSON backend based on config.
Requirement: When ATRI_GRAPH_BACKEND_URI is set, return a Neo4jGraphStore;
             otherwise return a TraceGraphStore scoped to the given file path.
Rationale: Allows the same route handlers to work in both local dev (JSON) and
           production (Neo4j) without code changes in the routes themselves.
Inputs: storage_path - file path for local store; settings.graph_backend_uri etc.
Outputs: TraceGraphStore or Neo4jGraphStore instance.
Preconditions: config.settings must be importable.
Postconditions: Returned store is ready for replace_graph / adjacency_map / stats.
Assumptions: Neo4jGraphStore falls back gracefully when driver not installed.
Failure modes: Neo4j connection error is caught inside Neo4jGraphStore._connect().
Side Effects: May open a Neo4j connection on first call per process.
Constraints: Neo4j singleton is shared across requests for efficiency.
Verification: tests/test_graph_factory.py
References: ATRI architecture doc, Epic 10.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Union

from atri.config import settings
from atri.core.services.graph_store import TraceGraphStore
from atri.core.services.neo4j_store import Neo4jGraphStore

# ---------------------------------------------------------------------------
# Neo4j singleton - one connection pool per process
# ---------------------------------------------------------------------------
_neo4j_lock = threading.Lock()
_neo4j_instance: Neo4jGraphStore | None = None


def _get_or_create_neo4j() -> Neo4jGraphStore:
    """
    ID: ATRI-GFACT-002
    Purpose: Return a cached Neo4jGraphStore singleton; create on first call.
    Postconditions: _neo4j_instance is set and returned.
    Side Effects: Opens Neo4j connection on first call.
    """
    global _neo4j_instance  # noqa: PLW0603
    with _neo4j_lock:
        if _neo4j_instance is None:
            _neo4j_instance = Neo4jGraphStore(
                uri=settings.graph_backend_uri,
                user=settings.graph_backend_user,
                password=settings.graph_backend_password,
                database=settings.graph_backend_name,
            )
            _neo4j_instance.ensure_schema()
    return _neo4j_instance


def reset_neo4j_singleton() -> None:
    """
    ID: ATRI-GFACT-003
    Purpose: Close and discard the cached Neo4j singleton (for tests).
    Side Effects: Closes driver connection; sets _neo4j_instance to None.
    """
    global _neo4j_instance  # noqa: PLW0603
    with _neo4j_lock:
        if _neo4j_instance is not None:
            _neo4j_instance.close()
            _neo4j_instance = None


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------

GraphStore = Union[TraceGraphStore, Neo4jGraphStore]


def make_graph_store(storage_path: str | Path) -> GraphStore:
    """
    ID: ATRI-GFACT-004
    Purpose: Return the appropriate graph store based on configuration.
    Inputs:
      storage_path - Path to JSON file used by TraceGraphStore (ignored for Neo4j).
    Outputs: GraphStore - either TraceGraphStore or Neo4jGraphStore.
    Preconditions: settings.graph_backend_uri is set when Neo4j is desired.
    Postconditions: Returned store implements replace_graph, adjacency_map, stats.
    Failure modes: Neo4j unavailable - store returned with available=False (no-op writes).
    """
    if settings.graph_backend_uri:
        return _get_or_create_neo4j()
    return TraceGraphStore(storage_path)
