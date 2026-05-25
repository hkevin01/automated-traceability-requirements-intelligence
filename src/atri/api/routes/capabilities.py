from fastapi import APIRouter

from atri.api.schemas import CapabilityCatalogResponse

router = APIRouter(prefix="/api/v1/capabilities", tags=["capabilities"])


@router.get("/catalog", response_model=CapabilityCatalogResponse)
def catalog() -> dict:
    return {
        "capabilities": [
            {
                "name": "AI-assisted requirement linking",
                "description": (
                    "Propose trace links between requirements, design, code, tests, "
                    "hazards, and interfaces."
                ),
            },
            {
                "name": "Automated change-impact analysis",
                "description": (
                    "Identify impacted artifacts when a requirement, design element, "
                    "or code module changes."
                ),
            },
            {
                "name": "Intelligent gap detection",
                "description": (
                    "Detect orphan requirements, missing tests, incomplete mitigations, "
                    "and weak verification coverage."
                ),
            },
            {
                "name": "Real-time traceability dashboards",
                "description": (
                    "Summarize coverage, orphan artifacts, high-risk modules, and "
                    "verification progress."
                ),
            },
        ]
    }