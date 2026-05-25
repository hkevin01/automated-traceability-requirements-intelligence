import json
from pathlib import Path

import networkx as nx


class TraceGraphStore:
    def __init__(self, storage_path: str | Path = "data/processed/trace_graph.json") -> None:
        self._storage_path = Path(storage_path)
        self._graph = nx.DiGraph()
        self._load()

    def replace_graph(self, artifacts: list[dict], links: list[dict]) -> None:
        self._graph.clear()
        for artifact in artifacts:
            self._graph.add_node(artifact["artifact_id"], **artifact)
        for link in links:
            self._graph.add_edge(link["source_id"], link["target_id"], **link)
        self._save()

    def adjacency_map(self) -> dict[str, list[str]]:
        return {
            node: sorted(self._graph.successors(node))
            for node in self._graph.nodes
        }

    def stats(self) -> dict[str, int | float]:
        artifact_count = self._graph.number_of_nodes()
        link_count = self._graph.number_of_edges()
        isolated_artifacts = sum(
            1
            for node in self._graph.nodes
            if self._graph.in_degree(node) == 0 and self._graph.out_degree(node) == 0
        )
        root_artifacts = sum(
            1
            for node in self._graph.nodes
            if self._graph.in_degree(node) == 0 and self._graph.out_degree(node) > 0
        )
        leaf_artifacts = sum(
            1
            for node in self._graph.nodes
            if self._graph.in_degree(node) > 0 and self._graph.out_degree(node) == 0
        )
        average_degree = round(link_count / artifact_count, 2) if artifact_count else 0.0
        return {
            "artifact_count": artifact_count,
            "link_count": link_count,
            "isolated_artifacts": isolated_artifacts,
            "root_artifacts": root_artifacts,
            "leaf_artifacts": leaf_artifacts,
            "average_degree": average_degree,
        }

    def _load(self) -> None:
        if not self._storage_path.exists():
            return

        payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
        for artifact in payload.get("artifacts", []):
            self._graph.add_node(artifact["artifact_id"], **artifact)
        for link in payload.get("links", []):
            self._graph.add_edge(link["source_id"], link["target_id"], **link)

    def _save(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "artifacts": [
                {"artifact_id": node_id, **data}
                for node_id, data in self._graph.nodes(data=True)
            ],
            "links": [
                {"source_id": source_id, "target_id": target_id, **data}
                for source_id, target_id, data in self._graph.edges(data=True)
            ],
        }
        serialized = json.dumps(payload, indent=2, sort_keys=True)
        self._storage_path.write_text(serialized, encoding="utf-8")