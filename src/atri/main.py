from importlib.metadata import PackageNotFoundError, version

from fastapi import FastAPI

from atri.api.routes.dashboard import router as dashboard_router
from atri.api.routes.gaps import router as gaps_router
from atri.api.routes.health import router as health_router
from atri.api.routes.impact import router as impact_router
from atri.api.routes.traceability import router as traceability_router
from atri.config import settings

try:
    app_version = version("atri")
except PackageNotFoundError:
    app_version = "0.1.0"

app = FastAPI(
    title=settings.app_name,
    version=app_version,
    description="Automated traceability and requirements intelligence API.",
)

app.include_router(health_router)
app.include_router(dashboard_router)
app.include_router(traceability_router)
app.include_router(impact_router)
app.include_router(gaps_router)
