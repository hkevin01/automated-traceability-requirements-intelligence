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