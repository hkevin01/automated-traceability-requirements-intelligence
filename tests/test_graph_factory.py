"""
ID: ATRI-TEST-GFACT-001
Purpose: Unit tests for graph_factory.py - local vs Neo4j store selection.
Verification: Covers local fallback, Neo4j selection, singleton caching, reset.
"""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import pytest

import atri.core.services.graph_factory as factory_module
from atri.core.services.graph_factory import make_graph_store, reset_neo4j_singleton
from atri.core.services.graph_store import TraceGraphStore


@pytest.fixture(autouse=True)
def reset_singleton():
    """Ensure Neo4j singleton is cleared before and after each test."""
    reset_neo4j_singleton()
    yield
    reset_neo4j_singleton()


# ---------------------------------------------------------------------------
# Local (file-based) store
# ---------------------------------------------------------------------------

def test_make_graph_store_returns_local_when_no_uri(tmp_path):
    """
    ID: ATRI-TEST-GFACT-002
    Purpose: make_graph_store returns TraceGraphStore when graph_backend_uri is empty.
    """
    with patch.object(factory_module.settings, "graph_backend_uri", ""):
        store = make_graph_store(str(tmp_path / "graph.json"))
    assert isinstance(store, TraceGraphStore)


def test_local_store_uses_given_path(tmp_path):
    """
    ID: ATRI-TEST-GFACT-003
    Purpose: Returned TraceGraphStore uses the storage_path argument.
    """
    path = tmp_path / "custom.json"
    with patch.object(factory_module.settings, "graph_backend_uri", ""):
        store = make_graph_store(str(path))
    assert isinstance(store, TraceGraphStore)
    # Replace graph and verify persistence at the given path
    store.replace_graph(
        [{"artifact_id": "A", "artifact_type": "req", "title": "T", "body": "B"}],
        [],
    )
    assert path.exists()


# ---------------------------------------------------------------------------
# Neo4j store (mocked - no live Neo4j needed)
# ---------------------------------------------------------------------------

def test_make_graph_store_returns_neo4j_when_uri_set(tmp_path):
    """
    ID: ATRI-TEST-GFACT-004
    Purpose: make_graph_store returns Neo4jGraphStore when graph_backend_uri is configured.
    """
    mock_store = MagicMock()
    mock_store.available = True

    with patch.object(factory_module.settings, "graph_backend_uri", "bolt://localhost:7687"), \
         patch("atri.core.services.graph_factory.Neo4jGraphStore", return_value=mock_store):
        store = make_graph_store(str(tmp_path / "ignored.json"))

    assert store is mock_store


def test_neo4j_singleton_cached(tmp_path):
    """
    ID: ATRI-TEST-GFACT-005
    Purpose: Two calls to make_graph_store return the same Neo4jGraphStore instance.
    """
    mock_store = MagicMock()
    mock_store.available = True

    with patch.object(factory_module.settings, "graph_backend_uri", "bolt://localhost:7687"), \
         patch("atri.core.services.graph_factory.Neo4jGraphStore", return_value=mock_store) as cls:
        s1 = make_graph_store(str(tmp_path / "a.json"))
        s2 = make_graph_store(str(tmp_path / "b.json"))

    # Constructor should only be called once (singleton)
    assert cls.call_count == 1
    assert s1 is s2


def test_reset_neo4j_singleton_clears_instance(tmp_path):
    """
    ID: ATRI-TEST-GFACT-006
    Purpose: reset_neo4j_singleton closes and discards the cached instance.
    """
    mock1 = MagicMock()
    mock1.available = True
    mock2 = MagicMock()
    mock2.available = True

    with patch.object(factory_module.settings, "graph_backend_uri", "bolt://localhost:7687"):
        with patch("atri.core.services.graph_factory.Neo4jGraphStore", return_value=mock1):
            s1 = make_graph_store(str(tmp_path / "a.json"))
        reset_neo4j_singleton()
        with patch("atri.core.services.graph_factory.Neo4jGraphStore", return_value=mock2):
            s2 = make_graph_store(str(tmp_path / "b.json"))

    mock1.close.assert_called_once()
    assert s1 is not s2
    assert s1 is mock1
    assert s2 is mock2


def test_neo4j_unavailable_store_returned_gracefully(tmp_path):
    """
    ID: ATRI-TEST-GFACT-007
    Purpose: Neo4jGraphStore with available=False is still returned (no exception).
    Rationale: Routes should degrade gracefully when Neo4j is unreachable.
    """
    mock_store = MagicMock()
    mock_store.available = False

    with patch.object(factory_module.settings, "graph_backend_uri", "bolt://localhost:7687"), \
         patch("atri.core.services.graph_factory.Neo4jGraphStore", return_value=mock_store):
        store = make_graph_store(str(tmp_path / "x.json"))

    assert store is mock_store
