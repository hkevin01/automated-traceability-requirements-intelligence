from fastapi import FastAPI

from atri.api.routes.dashboard import router as dashboard_router
from atri.api.routes.gaps import router as gaps_router
from atri.api.routes.health import router as health_router
from atri.api.routes.impact import router as impact_router
from atri.api.routes.traceability import router as traceability_router
from atri.config import settings

app = FastAPI(title=settings.app_name)

app.include_router(health_router)
app.include_router(dashboard_router)
app.include_router(traceability_router)
app.include_router(impact_router)
app.include_router(gaps_router)
