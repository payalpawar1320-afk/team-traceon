from app.routers.health import router as health_router
from app.routers.cases import router as cases_router
from app.routers.evidence import router as evidence_router
from app.routers.analysis import router as analysis_router
from app.routers.reports import router as reports_router
from app.routers.audit import router as audit_router

__all__ = [
    "health_router",
    "cases_router",
    "evidence_router",
    "analysis_router",
    "reports_router",
    "audit_router",
]



