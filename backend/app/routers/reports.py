import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.case import Case
from app.models.report import Report
from app.models.audit import AuditEvent
from app.schemas.report import ReportGenerateRequest, ReportResponse
from app.utils.pdf_report import create_case_forensic_pdf
from app.config import settings

logger = logging.getLogger("evidenceguard.reports")
router = APIRouter(tags=["Forensic Reports"])


def get_client_ip(request: Request) -> Optional[str]:
    """Safely extract client IP from request headers or client host."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.post("/cases/{case_id}/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def generate_case_report(
    case_id: int,
    payload: ReportGenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Generate an authoritative, structured forensic PDF examination report (spec.md §FR-10).
    Aggregates case information, registered evidence manifests, SHA-256 baseline verifications,
    executed forensic analysis findings, and chain-of-custody audit excerpts.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation case ID {case_id} was not found.",
        )

    try:
        report_number, file_path, file_size = create_case_forensic_pdf(case, db, payload)
    except Exception as e:
        logger.error(f"Failed to generate forensic PDF report for case {case_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report generation error: {str(e)}",
        )

    report_filename = os.path.basename(file_path)

    # Create database record
    new_report = Report(
        case_id=case.id,
        report_number=report_number,
        report_filename=report_filename,
        report_path=str(Path(file_path).resolve()),
        report_status="generated",
        generated_at=datetime.now(timezone.utc),
    )
    db.add(new_report)
    db.flush()

    # Log Chain of Custody Audit Event
    try:
        audit_event = AuditEvent(
            case_id=case.id,
            actor_id=case.investigator_name,
            action="REPORT_GENERATION",
            result="success",
            details_json=json.dumps({
                "report_number": report_number,
                "report_id": new_report.id,
                "file_size_bytes": file_size,
                "include_audit_trail": payload.include_audit_trail,
            }),
            ip_address=get_client_ip(request),
        )
        db.add(audit_event)
        db.commit()
        db.refresh(new_report)
    except Exception as e:
        logger.warning(f"Failed to log audit event for report generation: {e}")
        db.commit()

    return ReportResponse(
        id=new_report.id,
        case_id=new_report.case_id,
        report_number=new_report.report_number,
        report_filename=new_report.report_filename,
        report_status=new_report.report_status,
        generated_at=new_report.generated_at,
        file_size_bytes=file_size,
        download_url=f"/api/reports/{new_report.id}/download",
    )


@router.get("/cases/{case_id}/reports", response_model=List[ReportResponse])
def list_case_reports(case_id: int, db: Session = Depends(get_db)):
    """Retrieve list of all generated forensic PDF reports for a specific case."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation case ID {case_id} was not found.",
        )

    reports = (
        db.query(Report)
        .filter(Report.case_id == case_id)
        .order_by(Report.generated_at.desc())
        .all()
    )

    results = []
    for r in reports:
        sz = None
        try:
            if Path(r.report_path).exists():
                sz = os.path.getsize(r.report_path)
        except Exception:
            pass

        results.append(
            ReportResponse(
                id=r.id,
                case_id=r.case_id,
                report_number=r.report_number,
                report_filename=r.report_filename,
                report_status=r.report_status,
                generated_at=r.generated_at,
                file_size_bytes=sz,
                download_url=f"/api/reports/{r.id}/download",
            )
        )

    return results


@router.get("/reports/{report_id}", response_model=ReportResponse)
def get_report_metadata(report_id: int, db: Session = Depends(get_db)):
    """Retrieve metadata for a specific forensic report."""
    rep = db.query(Report).filter(Report.id == report_id).first()
    if not rep:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Forensic report ID {report_id} was not found.",
        )

    sz = None
    if Path(rep.report_path).exists():
        sz = os.path.getsize(rep.report_path)

    return ReportResponse(
        id=rep.id,
        case_id=rep.case_id,
        report_number=rep.report_number,
        report_filename=rep.report_filename,
        report_status=rep.report_status,
        generated_at=rep.generated_at,
        file_size_bytes=sz,
        download_url=f"/api/reports/{rep.id}/download",
    )


@router.get("/reports/{report_id}/download")
def download_forensic_report(
    report_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Stream and securely download the generated forensic PDF report (spec.md §FR-10).
    Enforces internal storage path isolation and logs chain-of-custody download activity.
    """
    rep = db.query(Report).filter(Report.id == report_id).first()
    if not rep:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Forensic report ID {report_id} was not found.",
        )

    settings.ensure_storage_directories()
    file_path = Path(rep.report_path)
    if not file_path.exists():
        # Check by filename in current settings.REPORTS_DIR
        alt_path = Path(settings.REPORTS_DIR) / rep.report_filename
        if alt_path.exists():
            file_path = alt_path
        else:
            # Ephemeral cloud container fallback: re-generate report dynamically on demand
            case = db.query(Case).filter(Case.id == rep.case_id).first()
            if case:
                try:
                    logger.info(f"Report file {rep.report_filename} not on disk (cloud restart). Auto-regenerating...")
                    _, new_path, _ = create_case_forensic_pdf(
                        case,
                        db,
                        ReportGenerateRequest(include_all_evidence=True, include_audit_trail=True),
                        report_number=rep.report_number,
                        output_filename=rep.report_filename,
                    )
                    file_path = Path(new_path)
                    rep.report_path = str(file_path.resolve())
                    db.commit()
                except Exception as gen_err:
                    logger.error(f"Failed to auto-regenerate missing report file: {gen_err}")

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Physical report file for {rep.report_number} was not found on internal storage.",
        )

    # Log download access audit event
    try:
        audit_event = AuditEvent(
            case_id=rep.case_id,
            actor_id="investigator",
            action="REPORT_DOWNLOAD",
            result="success",
            details_json=json.dumps({
                "report_id": rep.id,
                "report_number": rep.report_number,
            }),
            ip_address=get_client_ip(request),
        )
        db.add(audit_event)
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to record download audit event: {e}")

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=rep.report_filename,
        headers={
            "Content-Disposition": f'attachment; filename="{rep.report_filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
