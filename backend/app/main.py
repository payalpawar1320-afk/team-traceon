from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging

from app.config import settings
from app.database import init_db
from app.routers.health import router as health_router
from app.routers.cases import router as cases_router
from app.routers.evidence import router as evidence_router
from app.routers.analysis import router as analysis_router
from app.routers.reports import router as reports_router
from app.routers.audit import router as audit_router
from app import __version__

# Configure logging without sensitive evidence details
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("evidenceguard")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and shutdown routines."""
    logger.info("Initializing EvidenceGuard AI database schema and secure storage...")
    init_db()
    logger.info("EvidenceGuard AI startup complete.")
    yield
    logger.info("EvidenceGuard AI shutting down.")


app = FastAPI(
    title="EvidenceGuard AI — Digital Evidence Platform",
    description=(
        "Digital Evidence Authenticity and Integrity Verification Platform prototype. "
        "Cyber Hackathon Bihar Police 2026 (PS-5)."
    ),
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Custom Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# CORS Middleware (Restricted to configured origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(health_router)
app.include_router(cases_router, prefix="/api")
app.include_router(evidence_router, prefix="/api")
app.include_router(analysis_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(audit_router, prefix="/api")




# Global Exception Handler (Prevents leakage of sensitive filesystem details or traces)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error processing request {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred while processing the forensic request.",
            "path": request.url.path,
        },
    )
