import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models.case import Case
from app.models.evidence import Evidence
from app.models.audit import AuditEvent
from app.schemas.audit import AuditEventResponse, AuditLogListResponse

logger = logging.getLogger("evidenceguard.audit")
router = APIRouter(tags=["Chain of Custody & Audit"])


@router.get("/audit-log", response_model=AuditLogListResponse)
def get_audit_log(
    case_id: Optional[int] = Query(None, description="Filter events by case ID"),
    evidence_id: Optional[int] = Query(None, description="Filter events by evidence ID"),
    action: Optional[str] = Query(None, description="Filter by action name (e.g. EVIDENCE_UPLOAD, INTEGRITY_VERIFY)"),
    result: Optional[str] = Query(None, description="Filter by result: success, failure, warning"),
    search: Optional[str] = Query(None, description="Keyword search in action, actor, or details"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Retrieve filterable, chronological chain of custody audit log (spec.md §FR-02 & §6).
    Documents all case creations, evidence uploads, integrity checks, forensic analyses,
    and report generation events.
    
    Notice: Stored in a secure relational audit table within the local database.
    Does not make false claims of distributed ledger or blockchain immutability.
    """
    query = db.query(AuditEvent)

    if case_id is not None:
        query = query.filter(AuditEvent.case_id == case_id)
    if evidence_id is not None:
        query = query.filter(AuditEvent.evidence_id == evidence_id)
    if action and action.strip():
        query = query.filter(AuditEvent.action.ilike(f"%{action.strip()}%"))
    if result and result.strip():
        query = query.filter(AuditEvent.result == result.strip().lower())
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                AuditEvent.action.ilike(term),
                AuditEvent.actor_id.ilike(term),
                AuditEvent.details_json.ilike(term),
            )
        )

    total_count = query.count()
    events = query.order_by(AuditEvent.created_at.desc()).offset(offset).limit(limit).all()

    # Preload case numbers and evidence numbers for enriched display
    case_ids = {e.case_id for e in events if e.case_id}
    evidence_ids = {e.evidence_id for e in events if e.evidence_id}

    case_map = {}
    if case_ids:
        cases = db.query(Case.id, Case.case_number).filter(Case.id.in_(case_ids)).all()
        case_map = {c[0]: c[1] for c in cases}

    evidence_map = {}
    if evidence_ids:
        evs = db.query(Evidence.id, Evidence.evidence_number).filter(Evidence.id.in_(evidence_ids)).all()
        evidence_map = {ev[0]: ev[1] for ev in evs}

    results = []
    for evt in events:
        parsed_details = None
        if evt.details_json:
            try:
                parsed_details = json.loads(evt.details_json)
            except Exception:
                pass

        results.append(
            AuditEventResponse(
                id=evt.id,
                case_id=evt.case_id,
                case_number=case_map.get(evt.case_id),
                evidence_id=evt.evidence_id,
                evidence_number=evidence_map.get(evt.evidence_id),
                actor_id=evt.actor_id,
                action=evt.action,
                result=evt.result,
                details=parsed_details,
                details_raw=evt.details_json,
                ip_address=evt.ip_address,
                created_at=evt.created_at,
            )
        )

    return AuditLogListResponse(
        total_count=total_count,
        limit=limit,
        offset=offset,
        events=results,
    )
