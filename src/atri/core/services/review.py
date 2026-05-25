import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ReviewRecord:
    source_id: str
    target_id: str
    decision: str
    reviewer: str
    comments: str = ""


class TraceReviewService:
    def __init__(self, storage_path: str | Path = "data/processed/reviews.json") -> None:
        self._storage_path = Path(storage_path)
        self._reviews: dict[tuple[str, str], ReviewRecord] = {}
        self._load_reviews()

    def record_review(
        self,
        source_id: str,
        target_id: str,
        decision: str,
        reviewer: str,
        comments: str = "",
    ) -> ReviewRecord:
        normalized_decision = decision.strip().lower()
        if normalized_decision not in {"accepted", "rejected"}:
            raise ValueError("decision must be accepted or rejected")

        record = ReviewRecord(
            source_id=source_id,
            target_id=target_id,
            decision=normalized_decision,
            reviewer=reviewer,
            comments=comments,
        )
        self._reviews[(source_id, target_id)] = record
        self._save_reviews()
        return record

    def list_reviews(self) -> list[ReviewRecord]:
        return list(self._reviews.values())

    def summarize_reviews(self) -> dict:
        reviews = self.list_reviews()
        accepted = sum(1 for review in reviews if review.decision == "accepted")
        rejected = sum(1 for review in reviews if review.decision == "rejected")
        total = len(reviews)
        return {
            "total_reviews": total,
            "accepted_reviews": accepted,
            "rejected_reviews": rejected,
            "pending_reviews": 0,
        }

    def _load_reviews(self) -> None:
        if not self._storage_path.exists():
            return

        payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
        for item in payload:
            record = ReviewRecord(
                source_id=item["source_id"],
                target_id=item["target_id"],
                decision=item["decision"],
                reviewer=item["reviewer"],
                comments=item.get("comments", ""),
            )
            self._reviews[(record.source_id, record.target_id)] = record

    def _save_reviews(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "source_id": record.source_id,
                "target_id": record.target_id,
                "decision": record.decision,
                "reviewer": record.reviewer,
                "comments": record.comments,
            }
            for record in self._reviews.values()
        ]
        serialized = json.dumps(payload, indent=2, sort_keys=True)
        self._storage_path.write_text(serialized, encoding="utf-8")