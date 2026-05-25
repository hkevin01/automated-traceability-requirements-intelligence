from dataclasses import dataclass


@dataclass(slots=True)
class ReviewRecord:
    source_id: str
    target_id: str
    decision: str
    reviewer: str
    comments: str = ""


class TraceReviewService:
    def __init__(self) -> None:
        self._reviews: dict[tuple[str, str], ReviewRecord] = {}

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