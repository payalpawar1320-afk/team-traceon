from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.schemas.health import HealthResponse
from app import __version__

router = APIRouter(prefix="/api", tags=["System Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System Health & Diagnostic Check",
    description="Inspects database connectivity, application version, environment, and secure evidence storage paths.",
)
def get_health(db: Session = Depends(get_db)):
    # 1. Check Database
    db_connected = False
    try:
        db.execute(text("SELECT 1"))
        db_connected = True
    except Exception:
        db_connected = False

    # 2. Check Storage Directories
    storage_dirs = {
        "storage_base": settings.STORAGE_BASE_DIR,
        "evidence_upload": settings.EVIDENCE_UPLOAD_DIR,
        "derived_output": settings.DERIVED_OUTPUT_DIR,
        "reports": settings.REPORTS_DIR,
    }

    storage_details = {}
    all_storage_ok = True
    for key, path_str in storage_dirs.items():
        try:
            p = Path(path_str)
            p.mkdir(parents=True, exist_ok=True)
            # Test write permission safely with a temporary check file
            test_file = p / ".health_check_probe"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink(missing_ok=True)
            storage_details[key] = True
        except Exception:
            storage_details[key] = False
            all_storage_ok = False

    is_healthy = db_connected and all_storage_ok
    system_status = "healthy" if is_healthy else "degraded"

    payload = HealthResponse(
        status=system_status,
        app_name="EvidenceGuard AI",
        version=__version__,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc).isoformat(),
        database_connected=db_connected,
        storage_verified=all_storage_ok,
        storage_details=storage_details,
    )

    if not is_healthy:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=payload.model_dump(),
        )

    return payload
