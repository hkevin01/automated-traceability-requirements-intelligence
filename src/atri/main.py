from importlib.metadata import PackageNotFoundError, version

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atri.api.routes.capabilities import router as capabilities_router
from atri.api.routes.dashboard import router as dashboard_router
from atri.api.routes.gaps import router as gaps_router
from atri.api.routes.health import router as health_router
from atri.api.routes.impact import router as impact_router
from atri.api.routes.ingestion import router as ingestion_router
from atri.api.routes.traceability import router as traceability_router
from atri.config import settings

try:
    app_version = version("atri")
except PackageNotFoundError:
    app_version = "0.1.0"

app = FastAPI(
    title=settings.app_name,
    version=app_version,
    description=(
        "Automated Traceability and Requirements Intelligence (ATRI) - "
        "AI-assisted linking, impact analysis, gap detection, and audit for "
        "safety-critical programs."
    ),
)

# Allow cross-origin requests from the React frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(capabilities_router)
app.include_router(dashboard_router)
app.include_router(traceability_router)
app.include_router(impact_router)
app.include_router(gaps_router)
app.include_router(ingestion_router)
