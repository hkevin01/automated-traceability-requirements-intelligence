from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary() -> dict:
    return {
        "trace_coverage": 0.78,
        "suspect_links": 14,
        "orphan_requirements": 7,
        "orphan_tests": 5,
        "high_risk_changes_7d": 3,
    }
