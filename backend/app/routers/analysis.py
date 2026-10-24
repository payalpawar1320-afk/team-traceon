import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.case import Case
from app.models.evidence import Evidence
from app.models.analysis import AnalysisResult
from app.models.audit import AuditEvent
from app.schemas.analysis import (
    ImageForensicAnalysisResponse,
    ImageMetadataReport,
    ELAReport,
    VideoForensicAnalysisResponse,
    VideoForensicReport,
    AudioForensicAnalysisResponse,
    AudioMetadataReport,
    AnalysisResultBrief,
)
from app.utils.image_analysis import (
    extract_image_metadata,
    perform_error_level_analysis,
)
from app.utils.video_analysis import analyze_video_file
from app.utils.audio_analysis import analyze_audio_file


logger = logging.getLogger("evidenceguard.analysis")
router = APIRouter(tags=["Forensic Analysis"])


def get_client_ip(request: Request) -> Optional[str]:
    """Safely extract client IP from request headers or client host."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.post("/evidence/{evidence_id}/analyze/image", response_model=ImageForensicAnalysisResponse)
def analyze_image_evidence(
    evidence_id: int,
    request: Request,
    quality: int = Query(92, ge=50, le=100, description="Reference JPEG quality for ELA"),
    scale: int = Query(15, ge=5, le=40, description="Error amplification brightness scale"),
    db: Session = Depends(get_db),
):
    """
    Perform forensic examination on image evidence (FR-05).
    Extracts camera EXIF, GPS coordinates, editing-software traces, timestamp conflicts,
    and calculates Error Level Analysis (ELA) compression difference heatmaps.
    """
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence item ID {evidence_id} not found.",
        )

    if evidence.detected_file_type != "image":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Evidence {evidence.evidence_number} is '{evidence.detected_file_type}', not an image. Image forensics is only applicable to image files.",
        )

    file_path = Path(evidence.storage_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence file was not found on secure storage.",
        )

    settings.ensure_storage_directories()

    # 1. Run EXIF metadata and consistency audit
    metadata_data = extract_image_metadata(str(file_path))

    # 2. Run Error Level Analysis (ELA)
    ela_data = perform_error_level_analysis(
        str(file_path),
        settings.DERIVED_OUTPUT_DIR,
        quality=quality,
        scale=scale,
    )

    # 3. Format ELA URL if generated
    if ela_data.get("ela_filename"):
        ela_data["ela_url"] = f"/api/analysis/derived/{ela_data['ela_filename']}"

    # 4. Assess overall forensic status verdict
    total_indicators = metadata_data.get("indicators_count", 0)
    if ela_data.get("indicator_detected"):
        total_indicators += 1

    all_findings = metadata_data.get("findings", []) + ela_data.get("findings", [])
    has_high = any(f.get("severity") == "high" for f in all_findings)
    has_medium = any(f.get("severity") == "medium" for f in all_findings)

    if has_high:
        verdict_status = "Review recommended: High-risk anomaly detected"
    elif has_medium or total_indicators > 0:
        verdict_status = "Review recommended: Potential manipulation indicator"
    else:
        verdict_status = "No indicator detected by this check"

    limitations_text = (
        "Forensic Limitations (spec.md §FR-05): "
        "Metadata can be missing, altered, or stripped during normal transmission (e.g. messaging apps). "
        "Error Level Analysis identifies compression variations; high-contrast edges and textures naturally "
        "yield differing error rates. An indicator alone does not establish intentional manipulation."
    )

    combined_payload = {
        "metadata_report": metadata_data,
        "ela_report": ela_data,
        "total_indicators": total_indicators,
        "status": verdict_status,
        "limitations": limitations_text,
    }

    # 5. Persist AnalysisResult in database
    analysis_record = AnalysisResult(
        case_id=evidence.case_id,
        evidence_id=evidence.id,
        analysis_type="image_forensics",
        status=verdict_status,
        findings_json=json.dumps(combined_payload),
        limitations=limitations_text,
    )
    db.add(analysis_record)

    # 6. Record Audit Event
    audit = AuditEvent(
        case_id=evidence.case_id,
        evidence_id=evidence.id,
        actor_id="system_forensic_engine",
        action="IMAGE_FORENSIC_ANALYSIS",
        result="success",
        details_json=json.dumps({
            "status": verdict_status,
            "total_indicators": total_indicators,
            "has_exif": metadata_data.get("has_exif", False),
            "ela_max_error": ela_data.get("max_error", 0),
        }),
        ip_address=get_client_ip(request),
    )
    db.add(audit)
    db.commit()
    db.refresh(analysis_record)

    logger.info(
        f"Completed image analysis for Evidence {evidence.evidence_number}. "
        f"Verdict: '{verdict_status}', Indicators: {total_indicators}"
    )

    return ImageForensicAnalysisResponse(
        analysis_id=analysis_record.id,
        evidence_id=evidence.id,
        case_id=evidence.case_id,
        analysis_type="image_forensics",
        status=verdict_status,
        metadata_report=ImageMetadataReport(**metadata_data),
        ela_report=ELAReport(**ela_data),
        total_indicators=total_indicators,
        limitations=limitations_text,
        created_at=analysis_record.created_at,
    )


@router.post("/evidence/{evidence_id}/analyze/video", response_model=VideoForensicAnalysisResponse)
def analyze_video_evidence(
    evidence_id: int,
    request: Request,
    target_sample_frames: int = Query(20, ge=5, le=60, description="Target number of frames to sample and inspect"),
    db: Session = Depends(get_db),
):
    """
    Perform forensic examination on video / CCTV footage (spec.md FR-06).
    Extracts video duration, resolution, frame rate, and codec.
    Samples frame sequence, identifies duplicate/frozen frames, and verifies temporal continuity.
    """
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence item ID {evidence_id} not found.",
        )

    if evidence.detected_file_type != "video":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Evidence {evidence.evidence_number} is '{evidence.detected_file_type}', not a video. Video forensics is only applicable to video files.",
        )

    file_path = Path(evidence.storage_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence video file was not found on secure storage.",
        )

    settings.ensure_storage_directories()

    # Run video analysis
    video_data = analyze_video_file(
        str(file_path),
        settings.DERIVED_OUTPUT_DIR,
        target_sample_frames=target_sample_frames,
    )

    if video_data.get("status") == "failed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to decode video stream or process frame sequence.",
        )

    dup_count = video_data.get("duplicate_frames_count", 0)
    is_frozen = video_data.get("is_frozen_detected", False)

    if is_frozen:
        verdict_status = "Review recommended: Consecutive duplicate/frozen frames detected"
        indicators_count = 1
    elif dup_count > 0:
        verdict_status = "Review recommended: Repeated frames detected across footage"
        indicators_count = 1
    else:
        verdict_status = "No indicator detected by this check"
        indicators_count = 0

    limitations_text = video_data.get("limitations", "")

    combined_payload = {
        "video_report": video_data,
        "total_indicators": indicators_count,
        "status": verdict_status,
        "limitations": limitations_text,
    }

    # Persist in database
    analysis_record = AnalysisResult(
        case_id=evidence.case_id,
        evidence_id=evidence.id,
        analysis_type="video_forensics",
        status=verdict_status,
        findings_json=json.dumps(combined_payload),
        limitations=limitations_text,
    )
    db.add(analysis_record)

    # Record Audit Event
    audit = AuditEvent(
        case_id=evidence.case_id,
        evidence_id=evidence.id,
        actor_id="system_forensic_engine",
        action="VIDEO_FORENSIC_ANALYSIS",
        result="success",
        details_json=json.dumps({
            "status": verdict_status,
            "duration_sec": video_data.get("duration_sec"),
            "duplicate_frames": dup_count,
            "fps": video_data.get("fps"),
        }),
        ip_address=get_client_ip(request),
    )
    db.add(audit)
    db.commit()
    db.refresh(analysis_record)

    logger.info(
        f"Completed video analysis for Evidence {evidence.evidence_number}. "
        f"Verdict: '{verdict_status}', Duplicates: {dup_count}"
    )

    return VideoForensicAnalysisResponse(
        analysis_id=analysis_record.id,
        evidence_id=evidence.id,
        case_id=evidence.case_id,
        analysis_type="video_forensics",
        status=verdict_status,
        video_report=VideoForensicReport(**video_data),
        total_indicators=indicators_count,
        limitations=limitations_text,
        created_at=analysis_record.created_at,
    )


@router.post("/evidence/{evidence_id}/analyze/audio", response_model=AudioForensicAnalysisResponse)
def analyze_audio_evidence(
    evidence_id: int,
    request: Request,
    target_waveform_points: int = Query(100, ge=20, le=500, description="Waveform peak points to sample"),
    db: Session = Depends(get_db),
):
    """
    Perform forensic examination on audio evidence (FR-07).
    Extracts audio stream metadata (sample rate, channels, bit depth, bitrate),
    ID3/encoder software traces, waveform peak envelope, digital zero silence drop count,
    and 0 dBFS signal clipping indicators.
    """
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence item ID {evidence_id} not found.",
        )

    if evidence.detected_file_type != "audio":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Evidence {evidence.evidence_number} is '{evidence.detected_file_type}', not audio. Audio forensics is only applicable to audio files.",
        )

    file_path = Path(evidence.storage_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence file was not found on secure storage.",
        )

    audio_data = analyze_audio_file(str(file_path), target_waveform_points=target_waveform_points)

    indicators_count = audio_data.get("indicators_count", 0)
    all_findings = audio_data.get("findings", [])
    has_high = any(f.get("severity") == "high" for f in all_findings)
    has_medium = any(f.get("severity") == "medium" for f in all_findings)

    if has_high:
        verdict_status = "Review recommended: High-risk anomaly detected"
    elif has_medium or indicators_count > 0:
        verdict_status = "Review recommended: Potential manipulation indicator"
    else:
        verdict_status = "No indicator detected by this check"

    limitations_text = audio_data.get("limitations") or (
        "Forensic Limitations (spec.md §FR-07): "
        "Standard acoustic inspection checks digital clipping, silence discontinuities, and encoder metadata. "
        "This system does not claim AI voice deepfake detection or speaker identification without specialized acoustic models."
    )

    combined_payload = {
        "audio_report": audio_data,
        "total_indicators": indicators_count,
        "status": verdict_status,
        "limitations": limitations_text,
    }

    analysis_record = AnalysisResult(
        case_id=evidence.case_id,
        evidence_id=evidence.id,
        analysis_type="audio_forensics",
        status=verdict_status,
        findings_json=json.dumps(combined_payload),
        limitations=limitations_text,
    )
    db.add(analysis_record)

    audit = AuditEvent(
        case_id=evidence.case_id,
        evidence_id=evidence.id,
        actor_id="system_forensic_engine",
        action="AUDIO_FORENSIC_ANALYSIS",
        result="success",
        details_json=json.dumps({
            "status": verdict_status,
            "duration_sec": audio_data.get("duration_sec"),
            "format": audio_data.get("format"),
            "clipped": audio_data.get("is_clipped"),
            "silence_drops": audio_data.get("silence_drop_count"),
        }),
        ip_address=get_client_ip(request),
    )
    db.add(audit)
    db.commit()
    db.refresh(analysis_record)

    logger.info(
        f"Completed audio analysis for Evidence {evidence.evidence_number}. "
        f"Verdict: '{verdict_status}', Indicators: {indicators_count}"
    )

    return AudioForensicAnalysisResponse(
        analysis_id=analysis_record.id,
        evidence_id=evidence.id,
        case_id=evidence.case_id,
        analysis_type="audio_forensics",
        status=verdict_status,
        audio_report=AudioMetadataReport(**audio_data),
        total_indicators=indicators_count,
        limitations=limitations_text,
        created_at=analysis_record.created_at,
    )


@router.get("/evidence/{evidence_id}/analysis")
def get_evidence_analyses(evidence_id: int, db: Session = Depends(get_db)):
    """Retrieve all historical forensic analysis results for a specific evidence item."""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence item ID {evidence_id} not found.",
        )

    records = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.evidence_id == evidence_id)
        .order_by(AnalysisResult.created_at.desc())
        .all()
    )

    results = []
    for rec in records:
        if not rec.findings_json:
            continue
        try:
            payload = json.loads(rec.findings_json)
            if rec.analysis_type == "image_forensics":
                results.append(
                    ImageForensicAnalysisResponse(
                        analysis_id=rec.id,
                        evidence_id=evidence.id,
                        case_id=evidence.case_id,
                        analysis_type=rec.analysis_type,
                        status=rec.status,
                        metadata_report=ImageMetadataReport(**payload.get("metadata_report", {})),
                        ela_report=ELAReport(**payload.get("ela_report", {})),
                        total_indicators=payload.get("total_indicators", 0),
                        limitations=rec.limitations or "",
                        created_at=rec.created_at,
                    )
                )
            elif rec.analysis_type == "video_forensics":
                results.append(
                    VideoForensicAnalysisResponse(
                        analysis_id=rec.id,
                        evidence_id=evidence.id,
                        case_id=evidence.case_id,
                        analysis_type=rec.analysis_type,
                        status=rec.status,
                        video_report=VideoForensicReport(**payload.get("video_report", {})),
                        total_indicators=payload.get("total_indicators", 0),
                        limitations=rec.limitations or "",
                        created_at=rec.created_at,
                    )
                )
            elif rec.analysis_type == "audio_forensics":
                results.append(
                    AudioForensicAnalysisResponse(
                        analysis_id=rec.id,
                        evidence_id=evidence.id,
                        case_id=evidence.case_id,
                        analysis_type=rec.analysis_type,
                        status=rec.status,
                        audio_report=AudioMetadataReport(**payload.get("audio_report", {})),
                        total_indicators=payload.get("total_indicators", 0),
                        limitations=rec.limitations or "",
                        created_at=rec.created_at,
                    )
                )
        except Exception as e:
            logger.error(f"Error parsing analysis record ID={rec.id}: {e}")

    return results



@router.get("/analysis/derived/{filename}")
def get_derived_asset(filename: str):
    """Safely stream derived forensic assets (such as ELA heatmaps) with path traversal safeguards."""
    # Strip dangerous path components
    safe_name = os.path.basename(filename)
    asset_path = Path(settings.DERIVED_OUTPUT_DIR) / safe_name

    if not asset_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Derived forensic asset '{safe_name}' not found.",
        )

    # Determine content type
    suffix = asset_path.suffix.lower()
    media_type = "image/jpeg" if suffix in [".jpg", ".jpeg"] else "image/png"

    return FileResponse(
        path=str(asset_path),
        media_type=media_type,
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get("/cases/{case_id}/analysis", response_model=List[AnalysisResultBrief])
def get_case_analyses(case_id: int, db: Session = Depends(get_db)):
    """Retrieve summary of all forensic analysis checks conducted across evidence in a case."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case ID {case_id} not found.",
        )

    records = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.case_id == case_id)
        .order_by(AnalysisResult.created_at.desc())
        .all()
    )

    return [
        AnalysisResultBrief(
            id=r.id,
            case_id=r.case_id,
            evidence_id=r.evidence_id,
            analysis_type=r.analysis_type,
            status=r.status,
            created_at=r.created_at,
            error_summary=r.error_summary,
        )
        for r in records
    ]
