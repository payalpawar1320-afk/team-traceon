import json
import logging
from datetime import datetime, timezone
from typing import List, Optional
import random

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.database import get_db
from app.models.case import Case
from app.models.evidence import Evidence
from app.models.audit import AuditEvent
from app.schemas.case import (
    CaseCreate,
    CaseUpdate,
    CaseResponse,
    CaseDetailResponse,
    CaseStatsResponse,
)
from app.schemas.cross_evidence import (
    CrossEvidenceCompareRequest,
    CrossEvidenceComparisonResponse,
)
from app.utils.cross_evidence import compare_cross_evidence

logger = logging.getLogger("evidenceguard.cases")
router = APIRouter(prefix="/cases", tags=["Case Management"])


def generate_unique_case_number(db: Session) -> str:
    """Generate a clean, police-format case identifier: CASE-2026-XXXX."""
    year = datetime.now(timezone.utc).year
    for _ in range(20):
        candidate = f"CASE-{year}-{random.randint(1001, 9999)}"
        exists = db.query(Case.id).filter(Case.case_number == candidate).first()
        if not exists:
            return candidate
    # Fallback with timestamp microsecond
    return f"CASE-{year}-{int(datetime.now(timezone.utc).timestamp()) % 100000:05d}"


def get_client_ip(request: Request) -> Optional[str]:
    """Safely extract client IP from request headers or client tuple."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.get("/stats", response_model=CaseStatsResponse)
def get_case_statistics(db: Session = Depends(get_db)):
    """Retrieve real aggregate statistics for dashboard metrics."""
    total_cases = db.query(func.count(Case.id)).scalar() or 0
    active_cases = db.query(func.count(Case.id)).filter(Case.status == "active").scalar() or 0
    closed_cases = db.query(func.count(Case.id)).filter(Case.status == "closed").scalar() or 0
    archived_cases = db.query(func.count(Case.id)).filter(Case.status == "archived").scalar() or 0
    total_evidence = db.query(func.count(Evidence.id)).scalar() or 0

    return CaseStatsResponse(
        total_cases=total_cases,
        active_cases=active_cases,
        closed_cases=closed_cases,
        archived_cases=archived_cases,
        total_evidence=total_evidence,
    )


@router.get("", response_model=List[CaseResponse])
def list_cases(
    search: Optional[str] = Query(None, description="Search by case number or title"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by case status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieve searchable, filterable list of registered investigation cases."""
    query = db.query(Case)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(Case.case_number.ilike(term), Case.title.ilike(term)))

    if status_filter and status_filter.strip():
        query = query.filter(Case.status == status_filter.strip().lower())

    cases = query.order_by(Case.created_at.desc()).offset(offset).limit(limit).all()

    # Enrich with counts
    results = []
    for c in cases:
        ev_count = db.query(func.count(Evidence.id)).filter(Evidence.case_id == c.id).scalar() or 0
        resp = CaseResponse(
            id=c.id,
            case_number=c.case_number,
            title=c.title,
            description=c.description,
            investigator_name=c.investigator_name,
            status=c.status,
            created_at=c.created_at,
            updated_at=c.updated_at,
            evidence_count=ev_count,
            analysis_count=0,
        )
        results.append(resp)

    return results


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CaseCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Register a new investigation case with audit log record."""
    case_number = payload.case_number
    if not case_number:
        case_number = generate_unique_case_number(db)
    else:
        # Check uniqueness
        existing = db.query(Case).filter(Case.case_number == case_number).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Case number '{case_number}' is already registered in the platform.",
            )

    new_case = Case(
        case_number=case_number,
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else None,
        investigator_name=payload.investigator_name.strip(),
        status=payload.status,
    )

    db.add(new_case)
    db.flush()  # Get new_case.id before recording audit event

    # Record Audit Event
    audit_event = AuditEvent(
        case_id=new_case.id,
        actor_id=payload.investigator_name.strip() or "system_investigator",
        action="CASE_CREATE",
        result="success",
        details_json=json.dumps({
            "case_number": new_case.case_number,
            "title": new_case.title,
            "status": new_case.status,
        }),
        ip_address=get_client_ip(request),
    )
    db.add(audit_event)
    db.commit()
    db.refresh(new_case)

    logger.info(f"Registered investigation case ID={new_case.id} Number={new_case.case_number}")

    return CaseResponse(
        id=new_case.id,
        case_number=new_case.case_number,
        title=new_case.title,
        description=new_case.description,
        investigator_name=new_case.investigator_name,
        status=new_case.status,
        created_at=new_case.created_at,
        updated_at=new_case.updated_at,
        evidence_count=0,
        analysis_count=0,
    )


@router.get("/{case_identifier}", response_model=CaseDetailResponse)
def get_case_detail(case_identifier: str, db: Session = Depends(get_db)):
    """Retrieve full details of an investigation case by numeric ID or case number."""
    if case_identifier.isdigit():
        case = db.query(Case).filter(Case.id == int(case_identifier)).first()
    else:
        case = db.query(Case).filter(Case.case_number == case_identifier.strip().upper()).first()

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation case '{case_identifier}' was not found.",
        )

    ev_count = len(case.evidence_items)
    an_count = len(case.analysis_results)

    # Sort audit events newest first
    recent_audits = sorted(case.audit_events, key=lambda a: a.created_at, reverse=True)[:50]

    return CaseDetailResponse(
        id=case.id,
        case_number=case.case_number,
        title=case.title,
        description=case.description,
        investigator_name=case.investigator_name,
        status=case.status,
        created_at=case.created_at,
        updated_at=case.updated_at,
        evidence_count=ev_count,
        analysis_count=an_count,
        evidence_items=case.evidence_items,
        audit_events=recent_audits,
    )


@router.patch("/{case_id}", response_model=CaseResponse)
def update_case(
    case_id: int,
    payload: CaseUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Update case status, title, description, or assigned investigator."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation case ID {case_id} was not found.",
        )

    changes = {}
    if payload.title is not None and payload.title.strip() != case.title:
        changes["title"] = {"old": case.title, "new": payload.title.strip()}
        case.title = payload.title.strip()

    if payload.description is not None:
        new_desc = payload.description.strip() if payload.description else None
        if new_desc != case.description:
            changes["description"] = "updated"
            case.description = new_desc

    if payload.investigator_name is not None and payload.investigator_name.strip() != case.investigator_name:
        changes["investigator_name"] = {"old": case.investigator_name, "new": payload.investigator_name.strip()}
        case.investigator_name = payload.investigator_name.strip()

    if payload.status is not None and payload.status != case.status:
        changes["status"] = {"old": case.status, "new": payload.status}
        case.status = payload.status

    if changes:
        case.updated_at = datetime.now(timezone.utc)
        audit_event = AuditEvent(
            case_id=case.id,
            actor_id=case.investigator_name,
            action="CASE_UPDATE",
            result="success",
            details_json=json.dumps(changes),
            ip_address=get_client_ip(request),
        )
        db.add(audit_event)
        db.commit()
        db.refresh(case)

    ev_count = db.query(func.count(Evidence.id)).filter(Evidence.case_id == case.id).scalar() or 0

    return CaseResponse(
        id=case.id,
        case_number=case.case_number,
        title=case.title,
        description=case.description,
        investigator_name=case.investigator_name,
        status=case.status,
        created_at=case.created_at,
        updated_at=case.updated_at,
        evidence_count=ev_count,
        analysis_count=len(case.analysis_results),
    )


@router.post("/{case_id}/compare-evidence", response_model=CrossEvidenceComparisonResponse)
def compare_case_evidence(
    case_id: int,
    payload: CrossEvidenceCompareRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Perform forensic cross-evidence consistency comparison across 2+ evidence items (spec.md §FR-08).
    Examines capture timestamps, time zone deltas, hardware/device models,
    editing software footprints, and geographic proximity.
    """
    # 1. Verify case existence
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation case ID {case_id} was not found.",
        )

    # 2. Validate at least 2 distinct evidence items
    unique_ids = list(dict.fromkeys(payload.evidence_ids))
    if len(unique_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 distinct evidence items are required to execute cross-evidence comparison.",
        )

    # 3. Retrieve evidence items belonging to this specific case
    evidence_items = (
        db.query(Evidence)
        .filter(Evidence.case_id == case_id, Evidence.id.in_(unique_ids))
        .all()
    )

    found_ids = {e.id for e in evidence_items}
    missing_ids = [eid for eid in unique_ids if eid not in found_ids]
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Evidence ID(s) {missing_ids} do not belong to case '{case.case_number}' (ID: {case_id}) or do not exist.",
        )

    # 4. Execute forensic comparison
    result = compare_cross_evidence(case, evidence_items, db, payload)

    # 5. Log Chain of Custody Audit Event
    try:
        audit_entry = AuditEvent(
            case_id=case.id,
            actor_id=case.investigator_name,
            action="CROSS_EVIDENCE_COMPARISON",
            result="success",
            details_json=json.dumps({
                "compared_evidence_ids": unique_ids,
                "inconsistencies_count": result.summary.inconsistent_count,
                "consistent_count": result.summary.consistent_count,
                "overall_status": result.summary.overall_status,
            }),
            ip_address=get_client_ip(request),
        )
        db.add(audit_entry)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to record audit event for cross-evidence comparison: {e}")
        db.rollback()

    return result

