"""
ID: ATRI-NEO4J-001
Purpose: Neo4j graph database adapter for ATRI trace graph persistence.
Requirement: Provide a Neo4j-backed implementation of the TraceGraphStore interface.
Rationale: Neo4j enables traversal-efficient impact analysis and supports
           Cypher queries for complex traceability chain interrogation.
           Falls back gracefully when neo4j driver is not installed or unreachable.
Inputs: Neo4j connection URI, username, password, database name.
Outputs: Artifacts and links stored as Neo4j nodes and relationships.
Preconditions: Neo4j server must be running; neo4j Python driver must be installed.
Failure modes: ConnectionError on startup (caught, logged); falls back to no-op.
Constraints: Driver is an optional dependency; import is deferred to runtime.
Verification: Integration tests require a running Neo4j instance (skipped in CI without one).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class Neo4jGraphStore:
    """
    ID: ATRI-NEO4J-002
    Purpose: Thin adapter over the neo4j Python driver for trace graph operations.
    Preconditions: neo4j package must be installed (optional dependency).
    Postconditions: Artifacts stored as (:Artifact) nodes; links as typed relationships.
    Side Effects: Writes to Neo4j database.
    """

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
    ) -> None:
        """
        Inputs:
          uri      - Bolt URI, e.g. "bolt://localhost:7687"
          user     - Neo4j username
          password - Neo4j password
          database - target database name (default "neo4j")
        """
        self._uri = uri
        self._user = user
        self._password = password
        self._database = database
        self._driver: Any = None
        self._available = False
        self._connect()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        """
        ID: ATRI-NEO4J-003
        Purpose: Establish driver connection; set _available flag.
        Failure modes: ImportError (driver not installed) or ServiceUnavailable
                       both set _available=False and log a warning.
        """
        try:
            from neo4j import GraphDatabase  # noqa: PLC0415
            self._driver = GraphDatabase.driver(
                self._uri,
                auth=(self._user, self._password),
            )
            # Verify connectivity
            self._driver.verify_connectivity()
            self._available = True
            logger.info("Neo4j connection established: %s", self._uri)
        except ImportError:
            logger.warning(
                "neo4j driver not installed - Neo4j store unavailable. "
                "Install with: pip install neo4j"
            )
        except Exception as exc:
            logger.warning("Neo4j connection failed (%s): %s", self._uri, exc)

    def close(self) -> None:
        """Close the driver connection."""
        if self._driver:
            self._driver.close()

    @property
    def available(self) -> bool:
        return self._available

    # ------------------------------------------------------------------
    # Schema init
    # ------------------------------------------------------------------

    def ensure_schema(self) -> None:
        """
        ID: ATRI-NEO4J-004
        Purpose: Create uniqueness constraint and index for artifact_id.
        Side Effects: Runs CREATE CONSTRAINT IF NOT EXISTS in Neo4j.
        """
        if not self._available:
            return
        with self._driver.session(database=self._database) as session:
            session.run(
                "CREATE CONSTRAINT artifact_id_unique IF NOT EXISTS "
                "FOR (a:Artifact) REQUIRE a.artifact_id IS UNIQUE"
            )

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def replace_graph(self, artifacts: list[dict], links: list[dict]) -> None:
        """
        ID: ATRI-NEO4J-005
        Purpose: Replace the entire trace graph in Neo4j with a new set of artifacts and links.
        Inputs:
          artifacts - list of dicts with at least 'artifact_id', 'artifact_type', 'title', 'body'.
          links     - list of dicts with 'source_id', 'target_id', 'link_type', 'confidence'.
        Side Effects: Deletes all :Artifact nodes and relationships; recreates from inputs.
        Failure modes: Logs and returns if not available.
        """
        if not self._available:
            return
        with self._driver.session(database=self._database) as session:
            # Clear existing graph
            session.run("MATCH (n:Artifact) DETACH DELETE n")

            # Create nodes
            for artifact in artifacts:
                session.run(
                    "MERGE (a:Artifact {artifact_id: $artifact_id}) "
                    "SET a += $props",
                    artifact_id=artifact["artifact_id"],
                    props={k: v for k, v in artifact.items()},
                )

            # Create relationships
            for link in links:
                import re as _re  # noqa: PLC0415
                link_type = _re.sub(r"\W", "_", link.get("link_type", "RELATED_TO")).upper()
                session.run(
                    f"MATCH (src:Artifact {{artifact_id: $src_id}}) "
                    f"MATCH (tgt:Artifact {{artifact_id: $tgt_id}}) "
                    f"MERGE (src)-[r:{link_type}]->(tgt) "
                    f"SET r += $props",
                    src_id=link["source_id"],
                    tgt_id=link["target_id"],
                    props={k: v for k, v in link.items()},
                )

    def adjacency_map(self) -> dict[str, list[str]]:
        """
        ID: ATRI-NEO4J-006
        Purpose: Return outgoing adjacency map {artifact_id: [neighbour_id, ...]}.
        Outputs: dict mapping each node to its direct downstream neighbours.
        Failure modes: Returns empty dict if not available.
        """
        if not self._available:
            return {}
        with self._driver.session(database=self._database) as session:
            result = session.run(
                "MATCH (a:Artifact)-[r]->(b:Artifact) "
                "RETURN a.artifact_id AS src, b.artifact_id AS tgt"
            )
            adj: dict[str, list[str]] = {}
            for record in result:
                src = record["src"]
                tgt = record["tgt"]
                adj.setdefault(src, []).append(tgt)
        return adj

    def stats(self) -> dict[str, int | float]:
        """
        ID: ATRI-NEO4J-007
        Purpose: Return graph statistics from Neo4j.
        Outputs: dict with artifact_count, link_count, etc.
        Failure modes: Returns zeros if not available.
        """
        if not self._available:
            return {
                "artifact_count": 0, "link_count": 0,
                "isolated_artifacts": 0, "root_artifacts": 0,
                "leaf_artifacts": 0, "average_degree": 0.0,
            }
        with self._driver.session(database=self._database) as session:
            r_artifacts = session.run("MATCH (a:Artifact) RETURN count(a) AS cnt")
            artifact_count = r_artifacts.single()["cnt"]

            r_links = session.run("MATCH ()-[r]->() RETURN count(r) AS cnt")
            link_count = r_links.single()["cnt"]

            r_isolated = session.run(
                "MATCH (a:Artifact) WHERE NOT (a)--() RETURN count(a) AS cnt"
            )
            isolated = r_isolated.single()["cnt"]

            r_roots = session.run(
                "MATCH (a:Artifact) WHERE NOT ()-[]->(a) AND (a)-[]->() RETURN count(a) AS cnt"
            )
            roots = r_roots.single()["cnt"]

            r_leaves = session.run(
                "MATCH (a:Artifact) WHERE NOT (a)-[]->() AND ()-[]->(a) RETURN count(a) AS cnt"
            )
            leaves = r_leaves.single()["cnt"]

        return {
            "artifact_count": artifact_count,
            "link_count": link_count,
            "isolated_artifacts": isolated,
            "root_artifacts": roots,
            "leaf_artifacts": leaves,
            "average_degree": round(link_count / artifact_count, 2) if artifact_count else 0.0,
        }

    def get_artifact(self, artifact_id: str) -> dict | None:
        """Fetch a single artifact by ID."""
        if not self._available:
            return None
        with self._driver.session(database=self._database) as session:
            result = session.run(
                "MATCH (a:Artifact {artifact_id: $aid}) RETURN properties(a) AS props",
                aid=artifact_id,
            )
            record = result.single()
            return dict(record["props"]) if record else None
        """
        ID: ATRI-NEO4J-008
        Purpose: Return all downstream artifacts within `depth` hops using Cypher.
        Inputs: artifact_id - starting node; depth - max traversal depth.
        Outputs: list of artifact dicts with distance annotation.
        """
        if not self._available:
            return []
        with self._driver.session(database=self._database) as session:
            result = session.run(
                f"MATCH p=(start:Artifact {{artifact_id: $aid}})-[*1..{depth}]->(end:Artifact) "
                "RETURN DISTINCT end.artifact_id AS artifact_id, "
                "min(length(p)) AS distance, end.artifact_type AS artifact_type, "
                "end.title AS title",
                aid=artifact_id,
            )
            return [
                {
                    "artifact_id": r["artifact_id"],
                    "distance": r["distance"],
                    "artifact_type": r["artifact_type"],
                    "title": r["title"],
                }
                for r in result
            ]


# Lazy import guard - import re only if needed
import re  # noqa: E402
