import hashlib
import json
import logging
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.config import settings
from app.database import get_db
from app.models.case import Case
from app.models.evidence import Evidence
from app.models.integrity import IntegrityCheck
from app.models.audit import AuditEvent
from app.schemas.evidence import (
    EvidenceResponse,
    EvidenceDetailResponse,
    IntegrityCheckBrief,
    IntegrityVerifyResult,
    BatchVerifyItem,
    BatchVerifyResponse,
)
from app.utils.forensics import (
    ALLOWED_MIME_TYPES,
    EXTENSION_TO_MIME,
    inspect_magic_bytes,
    sanitize_filename,
    calculate_sha256,
    generate_storage_filename,
)

logger = logging.getLogger("evidenceguard.evidence")
router = APIRouter(tags=["Evidence & Integrity Verification"])


def generate_unique_evidence_number(db: Session) -> str:
    """Generate a clean, police-format evidence identifier: EVID-2026-XXXX."""
    year = datetime.now(timezone.utc).year
    for _ in range(20):
        candidate = f"EVID-{year}-{random.randint(1001, 9999)}"
        exists = db.query(Evidence.id).filter(Evidence.evidence_number == candidate).first()
        if not exists:
            return candidate
    return f"EVID-{year}-{int(datetime.now(timezone.utc).timestamp()) % 100000:05d}"


def get_client_ip(request: Request) -> Optional[str]:
    """Safely extract client IP from request headers or client host."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def get_latest_integrity_status(evidence_id: int, db: Session) -> str:
    """Retrieve the status of the most recent integrity check for an evidence file."""
    latest = (
        db.query(IntegrityCheck)
        .filter(IntegrityCheck.evidence_id == evidence_id)
        .order_by(IntegrityCheck.checked_at.desc())
        .first()
    )
    return latest.result if latest else "Not checked"


def check_duplicate_evidence(
    db: Session,
    sha256_hash: str,
    case_id: Optional[int] = None,
    exclude_evidence_id: Optional[int] = None,
) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Check whether another evidence record has an identical SHA-256 hash.
    Prioritizes matching within the same case, then across cases.
    Returns (is_duplicate, duplicate_warning, duplicate_of_evidence_number).
    """
    query = db.query(Evidence).filter(Evidence.sha256_hash == sha256_hash)
    if exclude_evidence_id is not None:
        query = query.filter(Evidence.id != exclude_evidence_id)

    if case_id is not None:
        same_case_dup = query.filter(Evidence.case_id == case_id).order_by(Evidence.uploaded_at.asc()).first()
        if same_case_dup:
            warning = (
                f"Duplicate file warning: Identical SHA-256 hash ({sha256_hash[:16]}...) "
                f"matches evidence {same_case_dup.evidence_number} ('{same_case_dup.original_filename}') in this case. "
                "The same file was uploaded twice. Both evidence records are retained in chain of custody."
            )
            return True, warning, same_case_dup.evidence_number
        return False, None, None

    any_dup = query.order_by(Evidence.uploaded_at.asc()).first()
    if any_dup:
        warning = (
            f"Duplicate file warning: Identical SHA-256 hash ({sha256_hash[:16]}...) "
            f"matches evidence {any_dup.evidence_number} ('{any_dup.original_filename}'). "
            "Both evidence records are retained in chain of custody."
        )
        return True, warning, any_dup.evidence_number

    return False, None, None


# --- Evidence Ingestion (Upload) ---


@router.post("/cases/{case_id}/evidence", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    case_id: int,
    request: Request,
    file: UploadFile = File(..., description="Evidence file (Image, Video, or Audio)"),
    investigator_name: Optional[str] = Form(None, description="Investigator performing intake"),
    db: Session = Depends(get_db),
):
    """
    Ingest a new digital evidence file associated with an investigation case.
    Validates file extension, MIME type, and magic bytes header.
    Stores the file securely outside public directories without modifying original bytes.
    Computes and records the baseline SHA-256 cryptographic digest.
    """
    # 1. Verify case existence
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation case ID {case_id} not found.",
        )

    # 2. Validate filename and extension
    raw_filename = file.filename or "evidence"
    clean_filename = sanitize_filename(raw_filename)
    ext = Path(clean_filename).suffix.lower()

    if ext not in EXTENSION_TO_MIME:
        allowed = ", ".join(EXTENSION_TO_MIME.keys())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Supported formats: {allowed}",
        )

    # 3. Read first chunk for magic bytes validation
    header = await file.read(1024)
    if not header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes). Cannot register empty evidence.",
        )

    magic_result = inspect_magic_bytes(header)
    if not magic_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File signature (magic bytes) does not match valid media for extension '{ext}'. File may be corrupt or disguised.",
        )

    detected_type, canonical_mime = magic_result

    # 4. Ensure storage directory exists
    settings.ensure_storage_directories()
    storage_filename = generate_storage_filename(clean_filename)
    target_path = Path(settings.EVIDENCE_UPLOAD_DIR) / storage_filename

    # 5. Stream file to disk and calculate SHA-256 simultaneously
    sha256 = hashlib.sha256()
    sha256.update(header)
    total_size = len(header)

    try:
        with open(target_path, "wb") as f:
            f.write(header)
            while chunk := await file.read(65536):
                total_size += len(chunk)
                if total_size > settings.MAX_UPLOAD_SIZE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File size exceeds maximum upload limit of {settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB.",
                    )
                sha256.update(chunk)
                f.write(chunk)
    except HTTPException:
        # Clean up partial file on upload size violation
        if target_path.exists():
            target_path.unlink()
        raise
    except Exception as e:
        if target_path.exists():
            target_path.unlink()
        logger.error(f"Error saving uploaded evidence: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to preserve evidence file safely on internal storage.",
        )

    final_hash = sha256.hexdigest().lower()
    evidence_number = generate_unique_evidence_number(db)
    actor = investigator_name.strip() if investigator_name and investigator_name.strip() else case.investigator_name

    # 6. Create database record
    new_evidence = Evidence(
        case_id=case.id,
        evidence_number=evidence_number,
        original_filename=clean_filename,
        storage_filename=storage_filename,
        storage_path=str(target_path.resolve()),
        detected_file_type=detected_type,
        mime_type=canonical_mime,
        file_size=total_size,
        sha256_hash=final_hash,
        metadata_json=json.dumps({
            "original_name": raw_filename,
            "detected_mime": canonical_mime,
            "intake_header_bytes": len(header),
        }),
    )
    db.add(new_evidence)
    db.flush()

    # 7. Record baseline IntegrityCheck (Initial ingestion check)
    baseline_check = IntegrityCheck(
        evidence_id=new_evidence.id,
        recorded_hash=final_hash,
        recalculated_hash=final_hash,
        result="Match",
        notes="Baseline SHA-256 hash verified during secure intake.",
    )
    db.add(baseline_check)

    # 8. Record platform AuditEvent
    audit = AuditEvent(
        case_id=case.id,
        evidence_id=new_evidence.id,
        actor_id=actor,
        action="EVIDENCE_UPLOAD",
        result="success",
        details_json=json.dumps({
            "evidence_number": new_evidence.evidence_number,
            "original_filename": clean_filename,
            "file_size": total_size,
            "sha256_hash": final_hash,
            "file_type": detected_type,
        }),
        ip_address=get_client_ip(request),
    )
    db.add(audit)
    db.commit()
    db.refresh(new_evidence)

    logger.info(
        f"Ingested evidence ID={new_evidence.id} ({new_evidence.evidence_number}) "
        f"for Case ID={case.id}. SHA-256={final_hash[:16]}..."
    )

    is_dup, dup_warn, dup_of = check_duplicate_evidence(
        db, final_hash, case_id=case.id, exclude_evidence_id=new_evidence.id
    )
    if is_dup:
        logger.warning(
            f"Duplicate file uploaded: Evidence {new_evidence.evidence_number} has matching SHA-256 hash with {dup_of}"
        )

    return EvidenceResponse(
        id=new_evidence.id,
        case_id=new_evidence.case_id,
        evidence_number=new_evidence.evidence_number,
        original_filename=new_evidence.original_filename,
        storage_filename=new_evidence.storage_filename,
        detected_file_type=new_evidence.detected_file_type,
        mime_type=new_evidence.mime_type,
        file_size=new_evidence.file_size,
        sha256_hash=new_evidence.sha256_hash,
        uploaded_at=new_evidence.uploaded_at,
        metadata_json=new_evidence.metadata_json,
        latest_integrity_status="Match",
        is_duplicate=is_dup,
        duplicate_warning=dup_warn,
        duplicate_of_evidence_number=dup_of,
    )


# --- List Evidence by Case ---


@router.get("/cases/{case_id}/evidence", response_model=List[EvidenceResponse])
def list_case_evidence(case_id: int, db: Session = Depends(get_db)):
    """Retrieve all evidence registered under a specific investigation case."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation case ID {case_id} not found.",
        )

    evidence_items = (
        db.query(Evidence)
        .filter(Evidence.case_id == case_id)
        .order_by(Evidence.uploaded_at.desc())
        .all()
    )

    hash_counts: dict = {}
    for item in evidence_items:
        hash_counts.setdefault(item.sha256_hash, []).append(item)

    results = []
    for item in evidence_items:
        latest_status = get_latest_integrity_status(item.id, db)
        items_with_hash = hash_counts.get(item.sha256_hash, [])
        is_dup = len(items_with_hash) > 1
        dup_warn = None
        dup_of = None
        if is_dup:
            other = next((o for o in items_with_hash if o.id != item.id), None)
            if other:
                dup_of = other.evidence_number
                dup_warn = (
                    f"Duplicate file warning: Identical SHA-256 hash ({item.sha256_hash[:16]}...) "
                    f"matches evidence {other.evidence_number} ('{other.original_filename}'). "
                    "File was uploaded twice. Both records are preserved in chain of custody."
                )

        results.append(
            EvidenceResponse(
                id=item.id,
                case_id=item.case_id,
                evidence_number=item.evidence_number,
                original_filename=item.original_filename,
                storage_filename=item.storage_filename,
                detected_file_type=item.detected_file_type,
                mime_type=item.mime_type,
                file_size=item.file_size,
                sha256_hash=item.sha256_hash,
                uploaded_at=item.uploaded_at,
                metadata_json=item.metadata_json,
                latest_integrity_status=latest_status,
                is_duplicate=is_dup,
                duplicate_warning=dup_warn,
                duplicate_of_evidence_number=dup_of,
            )
        )
    return results


# --- Global Evidence Directory ---


@router.get("/evidence", response_model=List[EvidenceResponse])
def list_all_evidence(
    search: Optional[str] = Query(None, description="Search by evidence number or filename"),
    detected_file_type: Optional[str] = Query(None, description="Filter by file type (image, video, audio)"),
    case_id: Optional[int] = Query(None, description="Filter by case ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Search and browse all digital evidence files across cases."""
    query = db.query(Evidence)

    if case_id is not None:
        query = query.filter(Evidence.case_id == case_id)

    if detected_file_type and detected_file_type.strip():
        query = query.filter(Evidence.detected_file_type == detected_file_type.strip().lower())

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Evidence.evidence_number.ilike(term),
                Evidence.original_filename.ilike(term),
                Evidence.sha256_hash.ilike(term),
            )
        )

    items = query.order_by(Evidence.uploaded_at.desc()).offset(offset).limit(limit).all()

    results = []
    for item in items:
        latest_status = get_latest_integrity_status(item.id, db)
        is_dup, dup_warn, dup_of = check_duplicate_evidence(
            db, item.sha256_hash, case_id=item.case_id, exclude_evidence_id=item.id
        )
        results.append(
            EvidenceResponse(
                id=item.id,
                case_id=item.case_id,
                evidence_number=item.evidence_number,
                original_filename=item.original_filename,
                storage_filename=item.storage_filename,
                detected_file_type=item.detected_file_type,
                mime_type=item.mime_type,
                file_size=item.file_size,
                sha256_hash=item.sha256_hash,
                uploaded_at=item.uploaded_at,
                metadata_json=item.metadata_json,
                latest_integrity_status=latest_status,
                is_duplicate=is_dup,
                duplicate_warning=dup_warn,
                duplicate_of_evidence_number=dup_of,
            )
        )
    return results


# --- Evidence Item Detail ---


@router.get("/evidence/{evidence_id}", response_model=EvidenceDetailResponse)
def get_evidence_detail(evidence_id: int, db: Session = Depends(get_db)):
    """Retrieve full details, integrity check history, and audit log for an evidence item."""
    item = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence item ID {evidence_id} not found.",
        )

    case = db.query(Case).filter(Case.id == item.case_id).first()
    checks = (
        db.query(IntegrityCheck)
        .filter(IntegrityCheck.evidence_id == item.id)
        .order_by(IntegrityCheck.checked_at.desc())
        .all()
    )
    latest_status = checks[0].result if checks else "Not checked"

    is_dup, dup_warn, dup_of = check_duplicate_evidence(
        db, item.sha256_hash, case_id=item.case_id, exclude_evidence_id=item.id
    )

    return EvidenceDetailResponse(
        id=item.id,
        case_id=item.case_id,
        case_number=case.case_number if case else "UNKNOWN",
        case_title=case.title if case else "Unknown Case",
        evidence_number=item.evidence_number,
        original_filename=item.original_filename,
        storage_filename=item.storage_filename,
        detected_file_type=item.detected_file_type,
        mime_type=item.mime_type,
        file_size=item.file_size,
        sha256_hash=item.sha256_hash,
        uploaded_at=item.uploaded_at,
        metadata_json=item.metadata_json,
        latest_integrity_status=latest_status,
        is_duplicate=is_dup,
        duplicate_warning=dup_warn,
        duplicate_of_evidence_number=dup_of,
        integrity_checks=checks,
    )


# --- Secure Evidence Download / View ---


@router.get("/evidence/{evidence_id}/download")
def download_evidence(evidence_id: int, db: Session = Depends(get_db)):
    """Securely stream original evidence file bytes for authorized forensic review."""
    item = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence item ID {evidence_id} not found.",
        )

    file_path = Path(item.storage_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence file was not found on secure storage.",
        )

    return FileResponse(
        path=str(file_path),
        filename=item.original_filename,
        media_type=item.mime_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'inline; filename="{item.original_filename}"',
        },
    )


# --- SHA-256 On-Demand Integrity Verification (FR-04) ---


@router.post("/evidence/{evidence_id}/verify", response_model=IntegrityVerifyResult)
def verify_evidence_integrity(
    evidence_id: int,
    request: Request,
    notes: Optional[str] = Query(None, description="Optional investigator check reason"),
    db: Session = Depends(get_db),
):
    """
    On-demand byte-level integrity verification.
    Recalculates SHA-256 hash strictly from binary disk bytes and compares with baseline hash.
    Records the verification in integrity_checks table and platform audit log.
    """
    item = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence item ID {evidence_id} not found.",
        )

    file_path = Path(item.storage_path)
    now = datetime.now(timezone.utc)

    if not file_path.exists():
        # Check failed: Missing file
        check = IntegrityCheck(
            evidence_id=item.id,
            recorded_hash=item.sha256_hash,
            recalculated_hash="",
            result="Check failed",
            notes="Integrity check failed: File missing from secure internal storage.",
            checked_at=now,
        )
        db.add(check)
        audit = AuditEvent(
            case_id=item.case_id,
            evidence_id=item.id,
            actor_id="system_investigator",
            action="HASH_VERIFY",
            result="failure",
            details_json=json.dumps({"status": "Check failed", "reason": "Missing file on disk"}),
            ip_address=get_client_ip(request),
        )
        db.add(audit)
        db.commit()

        return IntegrityVerifyResult(
            evidence_id=item.id,
            evidence_number=item.evidence_number,
            original_filename=item.original_filename,
            recorded_hash=item.sha256_hash,
            recalculated_hash="",
            status="Check failed",
            is_match=False,
            notes="Evidence file missing on internal storage. Verification could not be completed.",
            checked_at=now,
        )

    # Recalculate hash from stored file bytes
    recalculated = calculate_sha256(str(file_path))
    is_match = recalculated.lower() == item.sha256_hash.lower()
    status_label = "Match" if is_match else "Mismatch"

    check_notes = notes or (
        "SHA-256 hash recalculation verified byte equality with the baseline recorded at ingestion."
        if is_match
        else "CRITICAL ALERT: Recalculated SHA-256 hash differs from ingestion baseline. File bytes have been modified!"
    )

    check = IntegrityCheck(
        evidence_id=item.id,
        recorded_hash=item.sha256_hash,
        recalculated_hash=recalculated,
        result=status_label,
        notes=check_notes,
        checked_at=now,
    )
    db.add(check)

    audit = AuditEvent(
        case_id=item.case_id,
        evidence_id=item.id,
        actor_id="system_investigator",
        action="HASH_VERIFY",
        result="success" if is_match else "warning",
        details_json=json.dumps({
            "status": status_label,
            "recorded_hash": item.sha256_hash,
            "recalculated_hash": recalculated,
            "match": is_match,
        }),
        ip_address=get_client_ip(request),
    )
    db.add(audit)
    db.commit()

    logger.info(
        f"Integrity check for Evidence {item.evidence_number}: {status_label} "
        f"(Recalculated: {recalculated[:16]}...)"
    )

    return IntegrityVerifyResult(
        evidence_id=item.id,
        evidence_number=item.evidence_number,
        original_filename=item.original_filename,
        recorded_hash=item.sha256_hash,
        recalculated_hash=recalculated,
        status=status_label,
        is_match=is_match,
        notes=check_notes,
        checked_at=now,
    )


# --- Integrity Verification History ---


@router.get("/evidence/{evidence_id}/integrity-checks", response_model=List[IntegrityCheckBrief])
def get_integrity_history(evidence_id: int, db: Session = Depends(get_db)):
    """Retrieve full chronological history of SHA-256 integrity verifications for an evidence item."""
    item = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence item ID {evidence_id} not found.",
        )

    checks = (
        db.query(IntegrityCheck)
        .filter(IntegrityCheck.evidence_id == evidence_id)
        .order_by(IntegrityCheck.checked_at.desc())
        .all()
    )
    return checks


# --- Batch Verification for Case ---


@router.post("/cases/{case_id}/verify-all", response_model=BatchVerifyResponse)
def verify_all_case_evidence(
    case_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Perform a complete forensic integrity audit across all evidence items registered in a case.
    Recalculates every file's SHA-256 and logs individual integrity checks and audit events.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation case ID {case_id} not found.",
        )

    evidence_items = db.query(Evidence).filter(Evidence.case_id == case_id).all()
    results = []
    match_count = 0
    mismatch_count = 0
    failed_count = 0
    now = datetime.now(timezone.utc)

    for item in evidence_items:
        file_path = Path(item.storage_path)
        if not file_path.exists():
            status_label = "Check failed"
            recalculated = ""
            is_match = False
            failed_count += 1
        else:
            recalculated = calculate_sha256(str(file_path))
            is_match = recalculated.lower() == item.sha256_hash.lower()
            if is_match:
                status_label = "Match"
                match_count += 1
            else:
                status_label = "Mismatch"
                mismatch_count += 1

        # Record check
        check = IntegrityCheck(
            evidence_id=item.id,
            recorded_hash=item.sha256_hash,
            recalculated_hash=recalculated,
            result=status_label,
            notes=f"Batch audit scan: {status_label}",
            checked_at=now,
        )
        db.add(check)

        results.append(
            BatchVerifyItem(
                evidence_id=item.id,
                evidence_number=item.evidence_number,
                original_filename=item.original_filename,
                recorded_hash=item.sha256_hash,
                recalculated_hash=recalculated,
                status=status_label,
                is_match=is_match,
            )
        )

    # Record overall audit event
    audit = AuditEvent(
        case_id=case.id,
        actor_id="system_investigator",
        action="CASE_BATCH_INTEGRITY_AUDIT",
        result="success" if mismatch_count == 0 and failed_count == 0 else "warning",
        details_json=json.dumps({
            "total_checked": len(evidence_items),
            "matches": match_count,
            "mismatches": mismatch_count,
            "failed": failed_count,
        }),
        ip_address=get_client_ip(request),
    )
    db.add(audit)
    db.commit()

    return BatchVerifyResponse(
        case_id=case.id,
        case_number=case.case_number,
        total_checked=len(evidence_items),
        match_count=match_count,
        mismatch_count=mismatch_count,
        failed_count=failed_count,
        results=results,
    )
