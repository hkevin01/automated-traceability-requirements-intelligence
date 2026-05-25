from atri.core.models.trace import Artifact, TraceLink


class LinkSuggestionService:
    def suggest_links(self, source: Artifact, candidates: list[Artifact]) -> list[TraceLink]:
        links: list[TraceLink] = []
        for candidate in candidates:
            shared = len(set(source.body.lower().split()) & set(candidate.body.lower().split()))
            confidence = min(0.99, shared / 20.0)
            if confidence >= 0.2:
                links.append(
                    TraceLink(
                        source_id=source.artifact_id,
                        target_id=candidate.artifact_id,
                        link_type="related_to",
                        confidence=round(confidence, 2),
                        rationale="Token overlap heuristic baseline",
                    )
                )
        return sorted(links, key=lambda x: x.confidence, reverse=True)
