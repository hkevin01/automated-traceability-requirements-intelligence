from collections import deque


class ImpactAnalysisService:
    def analyze(
        self,
        changed_ids: list[str],
        adjacency: dict[str, list[str]],
        depth: int = 2,
    ) -> dict:
        visited: set[str] = set(changed_ids)
        queue = deque([(cid, 0) for cid in changed_ids])
        impacted: list[dict] = []

        while queue:
            node, level = queue.popleft()
            if level >= depth:
                continue
            for neighbor in adjacency.get(node, []):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                score = round(max(0.1, 1.0 - (0.25 * (level + 1))), 2)
                impacted.append({"artifact_id": neighbor, "score": score, "distance": level + 1})
                queue.append((neighbor, level + 1))

        return {"changed": changed_ids, "impacted": impacted}
