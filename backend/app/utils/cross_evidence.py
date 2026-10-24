import json
import logging
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.evidence import Evidence
from app.models.analysis import AnalysisResult
from app.schemas.cross_evidence import (
    CrossEvidenceCompareRequest,
    CrossEvidenceItemSummary,
    TimelineEvent,
    FieldComparison,
    ComparisonSummary,
    CrossEvidenceComparisonResponse,
)
from app.utils.image_analysis import extract_image_metadata
from app.utils.audio_analysis import analyze_audio_file
from app.config import settings

logger = logging.getLogger("evidenceguard.cross_evidence")


def _parse_exif_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse EXIF datetime strings like '2026:03-15 14:30:22' or ISO formats to UTC datetime."""
    if not dt_str or not isinstance(dt_str, str):
        return None
    clean = dt_str.strip()
    
    # Standard EXIF: "YYYY:MM:DD HH:MM:SS"
    patterns = [
        r"%Y:%m:%d %H:%M:%S",
        r"%Y-%m-%d %H:%M:%S",
        r"%Y/%m/%d %H:%M:%S",
        r"%Y-%m-%dT%H:%M:%S",
        r"%Y-%m-%dT%H:%M:%SZ",
        r"%Y:%m:%d",
        r"%Y-%m-%d",
    ]
    for pattern in patterns:
        try:
            dt = datetime.strptime(clean[:19], pattern)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def _haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two GPS points in kilometers."""
    radius_earth_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(radius_earth_km * c, 3)


def extract_or_load_evidence_summary(
    evidence: Evidence,
    db: Session,
) -> CrossEvidenceItemSummary:
    """
    Extract or retrieve normalized forensic properties for a single evidence item.
    Reuses existing AnalysisResult if present; otherwise probes the storage file.
    """
    # Default initial properties
    summary = CrossEvidenceItemSummary(
        evidence_id=evidence.id,
        evidence_number=evidence.evidence_number,
        original_filename=evidence.original_filename,
        file_type=evidence.detected_file_type,
        mime_type=evidence.mime_type,
        file_size_bytes=evidence.file_size,
        sha256_hash=evidence.sha256_hash,
        uploaded_at=evidence.uploaded_at,
        capture_timestamp=None,
        capture_timestamp_raw=None,
        modification_timestamp=None,
        device_make=None,
        device_model=None,
        device_label=None,
        software_footprint=None,
        dimensions=None,
        duration_sec=None,
        gps_latitude=None,
        gps_longitude=None,
        has_gps=False,
        has_exif=False,
    )

    storage_path = Path(evidence.storage_path)
    if storage_path.exists():
        try:
            mtime = datetime.fromtimestamp(storage_path.stat().st_mtime, tz=timezone.utc)
            summary.modification_timestamp = mtime
        except Exception:
            pass

    # 1. Check if there are pre-existing analysis records in DB
    existing_analyses = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.evidence_id == evidence.id)
        .order_by(AnalysisResult.created_at.desc())
        .all()
    )

    found_in_analysis = False
    for rec in existing_analyses:
        if not rec.findings_json:
            continue
        try:
            data = json.loads(rec.findings_json)
            if rec.analysis_type == "image_forensics" and "metadata_report" in data:
                meta = data["metadata_report"]
                summary.has_exif = bool(meta.get("has_exif"))
                summary.device_make = meta.get("camera_make")
                summary.device_model = meta.get("camera_model")
                summary.software_footprint = meta.get("software")
                raw_cap = meta.get("capture_date")
                if raw_cap:
                    summary.capture_timestamp_raw = raw_cap
                    summary.capture_timestamp = _parse_exif_datetime(raw_cap)
                if meta.get("width") and meta.get("height"):
                    summary.dimensions = f"{meta['width']} x {meta['height']}"
                if meta.get("gps"):
                    gps = meta["gps"]
                    summary.gps_latitude = gps.get("latitude")
                    summary.gps_longitude = gps.get("longitude")
                    summary.has_gps = summary.gps_latitude is not None and summary.gps_longitude is not None
                found_in_analysis = True
                break

            elif rec.analysis_type == "video_forensics" and "video_report" in data:
                vid = data["video_report"]
                if vid.get("width") and vid.get("height"):
                    summary.dimensions = f"{vid['width']} x {vid['height']}"
                summary.duration_sec = vid.get("duration_sec")
                found_in_analysis = True
                break

            elif rec.analysis_type == "audio_forensics" and "audio_report" in data:
                aud = data["audio_report"]
                summary.duration_sec = aud.get("duration_sec")
                summary.software_footprint = aud.get("software_signature")
                found_in_analysis = True
                break
        except Exception as e:
            logger.debug(f"Could not parse analysis findings for evidence {evidence.id}: {e}")

    # 2. If not found in analysis and file exists, perform on-the-fly metadata probing
    if not found_in_analysis and storage_path.exists():
        try:
            if evidence.detected_file_type == "image":
                meta = extract_image_metadata(str(storage_path))
                summary.has_exif = bool(meta.get("has_exif"))
                summary.device_make = meta.get("camera_make")
                summary.device_model = meta.get("camera_model")
                summary.software_footprint = meta.get("software")
                raw_cap = meta.get("capture_date")
                if raw_cap:
                    summary.capture_timestamp_raw = raw_cap
                    summary.capture_timestamp = _parse_exif_datetime(raw_cap)
                if meta.get("width") and meta.get("height"):
                    summary.dimensions = f"{meta['width']} x {meta['height']}"
                if meta.get("gps"):
                    summary.gps_latitude = meta["gps"].get("latitude")
                    summary.gps_longitude = meta["gps"].get("longitude")
                    summary.has_gps = summary.gps_latitude is not None and summary.gps_longitude is not None

            elif evidence.detected_file_type == "audio":
                aud = analyze_audio_file(str(storage_path))
                summary.duration_sec = aud.get("duration_sec")
                summary.software_footprint = aud.get("software_signature")

            elif evidence.detected_file_type == "video":
                # Quick cv2 probe for dimensions and duration
                import cv2
                cap = cv2.VideoCapture(str(storage_path))
                if cap.isOpened():
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
                    total = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
                    if w > 0 and h > 0:
                        summary.dimensions = f"{w} x {h}"
                    if fps > 0 and total > 0:
                        summary.duration_sec = round(total / fps, 2)
                    cap.release()
        except Exception as e:
            logger.warning(f"On-the-fly metadata extraction error for evidence {evidence.id}: {e}")

    # Build device label
    if summary.device_make or summary.device_model:
        parts = [summary.device_make, summary.device_model]
        summary.device_label = " ".join([p for p in parts if p]).strip()
    else:
        summary.device_label = "Unknown / Stripped"

    return summary


def compare_cross_evidence(
    case: Case,
    evidence_items: List[Evidence],
    db: Session,
    request: CrossEvidenceCompareRequest,
) -> CrossEvidenceComparisonResponse:
    """
    Perform deep cross-evidence forensic examination across 2+ evidence files (FR-08).
    Evaluates:
      1. Capture Timestamps & Chronological Order
      2. Hardware / Camera Make & Model
      3. Post-Processing & Editing Software Footprints
      4. Geographic Proximity (GPS distance vs. time delta)
      5. Resolution / Aspect Ratio Feasibility
      6. Audio/Video Duration Comparison
    """
    summaries: List[CrossEvidenceItemSummary] = []
    for item in evidence_items:
        s = extract_or_load_evidence_summary(item, db)
        summaries.append(s)

    field_comparisons: List[FieldComparison] = []
    timeline_events: List[TimelineEvent] = []

    # -------------------------------------------------------------
    # Build Chronological Timeline Events
    # -------------------------------------------------------------
    for s in summaries:
        # Capture timestamp event
        if s.capture_timestamp:
            timeline_events.append(
                TimelineEvent(
                    timestamp=s.capture_timestamp,
                    timestamp_str=s.capture_timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    event_type="Capture / Creation",
                    evidence_id=s.evidence_id,
                    evidence_number=s.evidence_number,
                    filename=s.original_filename,
                    description=f"Device timestamp recorded in file EXIF/metadata ({s.device_label})",
                    is_estimated=False,
                )
            )

        # Upload / Ingestion event
        upload_utc = s.uploaded_at
        if upload_utc.tzinfo is None:
            upload_utc = upload_utc.replace(tzinfo=timezone.utc)
        timeline_events.append(
            TimelineEvent(
                timestamp=upload_utc,
                timestamp_str=upload_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
                event_type="Evidence Ingestion",
                evidence_id=s.evidence_id,
                evidence_number=s.evidence_number,
                filename=s.original_filename,
                description="Secure intake and SHA-256 baseline calculation into TRACEON repository",
                is_estimated=False,
            )
        )

    # Sort timeline chronologically
    timeline_events.sort(key=lambda ev: ev.timestamp)

    # -------------------------------------------------------------
    # 1. Capture Timestamps & Temporal Alignment
    # -------------------------------------------------------------
    timestamp_vals = {s.evidence_number: s.capture_timestamp_raw or "Not present" for s in summaries}
    valid_capture_times = [s for s in summaries if s.capture_timestamp is not None]

    if len(valid_capture_times) == 0:
        field_comparisons.append(
            FieldComparison(
                field_id="capture_timestamp",
                field_label="Capture Timestamp Alignment",
                status="missing_data",
                values_by_evidence=timestamp_vals,
                delta_or_diff="No capture timestamps found in compared items",
                finding_title="Capture Metadata Unavailable in Selected Evidence",
                explanation="None of the selected evidence items retain embedded EXIF or container capture timestamps.",
                plausible_causes=[
                    "File sent via instant messaging or social media (e.g. WhatsApp, Telegram, Signal) which strips EXIF metadata for privacy.",
                    "Recording hardware/firmware does not write embedded datetime tags.",
                    "Evidence was exported or re-encoded without preserving container metadata tags.",
                ],
            )
        )
    elif len(valid_capture_times) < len(summaries):
        missing_count = len(summaries) - len(valid_capture_times)
        field_comparisons.append(
            FieldComparison(
                field_id="capture_timestamp",
                field_label="Capture Timestamp Alignment",
                status="missing_data",
                values_by_evidence=timestamp_vals,
                delta_or_diff=f"{len(valid_capture_times)} present, {missing_count} missing",
                finding_title="Partial Capture Timestamps Available",
                explanation=f"{len(valid_capture_times)} evidence item(s) contain capture timestamps, while {missing_count} item(s) have stripped or missing metadata.",
                plausible_causes=[
                    "Mixed sources: Some files were direct camera pulls while others were acquired via third-party messaging apps.",
                    "Manual redaction of metadata prior to police submission.",
                ],
            )
        )
    else:
        # All items have capture timestamps!
        dates = [s.capture_timestamp for s in valid_capture_times if s.capture_timestamp is not None]
        min_date = min(dates)
        max_date = max(dates)
        delta_sec = abs((max_date - min_date).total_seconds())

        delta_str = f"{int(delta_sec)} seconds apart"
        if delta_sec >= 86400:
            delta_str = f"{delta_sec / 86400:.1f} days apart"
        elif delta_sec >= 3600:
            delta_str = f"{delta_sec / 3600:.1f} hours apart"
        elif delta_sec >= 60:
            delta_str = f"{delta_sec / 60:.1f} minutes apart"

        if delta_sec <= request.time_tolerance_seconds:
            field_comparisons.append(
                FieldComparison(
                    field_id="capture_timestamp",
                    field_label="Capture Timestamp Alignment",
                    status="consistent",
                    values_by_evidence=timestamp_vals,
                    delta_or_diff=f"Delta: {delta_str} (within {request.time_tolerance_seconds}s tolerance)",
                    finding_title="Temporally Consistent Capture Times",
                    explanation=f"Recorded timestamps across all evidence items are closely aligned (delta: {delta_str}), supporting near-simultaneous recording or contiguous incident coverage.",
                    plausible_causes=[
                        "Synchronized multi-angle recording of the same scene.",
                        "Sequential burst captures from the same event.",
                    ],
                )
            )
        else:
            field_comparisons.append(
                FieldComparison(
                    field_id="capture_timestamp",
                    field_label="Capture Timestamp Alignment",
                    status="inconsistent",
                    values_by_evidence=timestamp_vals,
                    delta_or_diff=f"Delta: {delta_str} (exceeds {request.time_tolerance_seconds}s tolerance)",
                    finding_title="Significant Timestamp Divergence Detected",
                    explanation=f"A temporal divergence of {delta_str} was detected between evidence items. Investigator review is recommended to reconcile the timeline.",
                    plausible_causes=[
                        "Device internal clocks were not synchronized to network time (NTP), resulting in clock drift.",
                        "Timezone configuration discrepancy between recording devices (e.g., UTC vs local IST offset).",
                        "Files represent genuinely distinct events or different stages of the incident.",
                        "Manual alteration or synthetic modification of embedded timestamps.",
                    ],
                )
            )

    # -------------------------------------------------------------
    # 2. Camera / Recording Device Alignment
    # -------------------------------------------------------------
    device_vals = {s.evidence_number: s.device_label or "Unknown / Stripped" for s in summaries}
    known_devices = [s.device_label for s in summaries if s.device_label and s.device_label != "Unknown / Stripped"]

    if len(known_devices) == 0:
        field_comparisons.append(
            FieldComparison(
                field_id="device_hardware",
                field_label="Hardware / Device Consistency",
                status="missing_data",
                values_by_evidence=device_vals,
                delta_or_diff="No hardware make/model tags found",
                finding_title="Device Signatures Missing",
                explanation="None of the compared files contain identifiable camera make or model hardware tags.",
                plausible_causes=[
                    "Metadata stripped during sharing or transfer.",
                    "Audio/CCTV hardware does not embed device make/model in the file format.",
                ],
            )
        )
    elif len(set(known_devices)) == 1 and len(known_devices) == len(summaries):
        field_comparisons.append(
            FieldComparison(
                field_id="device_hardware",
                field_label="Hardware / Device Consistency",
                status="consistent",
                values_by_evidence=device_vals,
                delta_or_diff=f"Identical device model: {known_devices[0]}",
                finding_title="Identical Camera / Device Source",
                explanation=f"All compared evidence files identify the same device model: '{known_devices[0]}'.",
                plausible_causes=[
                    "Files originated from the same physical camera or smartphone.",
                    "Standard department-issued device hardware.",
                ],
            )
        )
    else:
        unique_devices = list(set(device_vals.values()))
        field_comparisons.append(
            FieldComparison(
                field_id="device_hardware",
                field_label="Hardware / Device Consistency",
                status="inconsistent" if len(known_devices) > 1 else "missing_data",
                values_by_evidence=device_vals,
                delta_or_diff=f"Distinct sources: {', '.join(unique_devices)}",
                finding_title="Different Hardware Sources Detected",
                explanation=f"Evidence items originated from distinct hardware devices: {', '.join(unique_devices)}.",
                plausible_causes=[
                    "Different eyewitnesses or officers recorded from different phones or body-worn cameras.",
                    "CCTV camera vs handheld mobile footage comparison.",
                    "Evidence from unrelated sources submitted together.",
                ],
            )
        )

    # -------------------------------------------------------------
    # 3. Post-Processing & Software Footprints
    # -------------------------------------------------------------
    software_vals = {s.evidence_number: s.software_footprint or "Clean / None detected" for s in summaries}
    flagged_software = [s for s in summaries if s.software_footprint is not None]

    if len(flagged_software) == 0:
        field_comparisons.append(
            FieldComparison(
                field_id="software_footprint",
                field_label="Editing Software Footprint",
                status="consistent",
                values_by_evidence=software_vals,
                delta_or_diff="No post-processing editing software detected",
                finding_title="No Editing Software Indicators",
                explanation="No editing, manipulation, or re-encoding software signatures (Photoshop, Audacity, Canva, GIMP, etc.) were found in any compared items.",
                plausible_causes=[
                    "Original unedited camera/audio recordings.",
                ],
            )
        )
    elif len(flagged_software) == len(summaries):
        field_comparisons.append(
            FieldComparison(
                field_id="software_footprint",
                field_label="Editing Software Footprint",
                status="inconsistent",
                values_by_evidence=software_vals,
                delta_or_diff="All compared items contain software footprints",
                finding_title="Editing Software Signatures Present Across All Items",
                explanation="All compared files contain signatures of editing or export software. Detailed single-file forensic review is advised.",
                plausible_causes=[
                    "All files were processed through an export pipeline, transcoder, or photo management tool.",
                    "Evidence underwent intentional modification before submission.",
                ],
            )
        )
    else:
        flagged_nums = [s.evidence_number for s in flagged_software]
        field_comparisons.append(
            FieldComparison(
                field_id="software_footprint",
                field_label="Editing Software Footprint",
                status="inconsistent",
                values_by_evidence=software_vals,
                delta_or_diff=f"Software detected in {len(flagged_software)} of {len(summaries)} items",
                finding_title="Asymmetric Editing Software Footprint",
                explanation=f"Evidence item(s) {', '.join(flagged_nums)} contain editing/processing software signatures, while the remaining files do not.",
                plausible_causes=[
                    "Selected evidence files were modified, cropped, or filtered in editing software.",
                    "Transcoding utility was applied selectively to some evidence items for viewing convenience.",
                ],
            )
        )

    # -------------------------------------------------------------
    # 4. Geolocation / Proximity Analysis
    # -------------------------------------------------------------
    gps_vals = {}
    for s in summaries:
        if s.has_gps and s.gps_latitude is not None and s.gps_longitude is not None:
            gps_vals[s.evidence_number] = f"{s.gps_latitude:.5f}, {s.gps_longitude:.5f}"
        else:
            gps_vals[s.evidence_number] = "No GPS Data"

    gps_items = [s for s in summaries if s.has_gps and s.gps_latitude is not None and s.gps_longitude is not None]

    if len(gps_items) == 0:
        field_comparisons.append(
            FieldComparison(
                field_id="gps_proximity",
                field_label="Geolocation Proximity",
                status="missing_data",
                values_by_evidence=gps_vals,
                delta_or_diff="No GPS coordinates present in compared files",
                finding_title="Geolocation Metadata Absent",
                explanation="None of the compared files contain embedded GPS coordinates.",
                plausible_causes=[
                    "Camera location services were disabled during capture.",
                    "EXIF location tags were stripped during file transfer.",
                ],
            )
        )
    elif len(gps_items) == 1:
        field_comparisons.append(
            FieldComparison(
                field_id="gps_proximity",
                field_label="Geolocation Proximity",
                status="missing_data",
                values_by_evidence=gps_vals,
                delta_or_diff="GPS present in only 1 item; cross-comparison not possible",
                finding_title="Single Evidence Location Available",
                explanation=f"Evidence {gps_items[0].evidence_number} contains GPS coordinates, but other items lack GPS for comparative proximity analysis.",
                plausible_causes=[
                    "Different recording devices with varying GPS sensor availability.",
                ],
            )
        )
    else:
        # 2 or more have GPS! Compare pairs
        max_dist_km = 0.0
        for i in range(len(gps_items)):
            for j in range(i + 1, len(gps_items)):
                item1 = gps_items[i]
                item2 = gps_items[j]
                dist = _haversine_distance_km(
                    item1.gps_latitude, item1.gps_longitude,
                    item2.gps_latitude, item2.gps_longitude,
                )
                if dist > max_dist_km:
                    max_dist_km = dist

        dist_str = f"{max_dist_km:.2f} km" if max_dist_km >= 1.0 else f"{int(max_dist_km * 1000)} meters"

        if max_dist_km < 0.2:  # within 200m
            field_comparisons.append(
                FieldComparison(
                    field_id="gps_proximity",
                    field_label="Geolocation Proximity",
                    status="consistent",
                    values_by_evidence=gps_vals,
                    delta_or_diff=f"Separation distance: {dist_str}",
                    finding_title="Consistent Geographic Proximity",
                    explanation=f"Evidence items were captured within {dist_str} of each other, confirming they share the same physical location or immediate crime scene.",
                    plausible_causes=[
                        "Recordings made at the same scene or intersection.",
                    ],
                )
            )
        else:
            field_comparisons.append(
                FieldComparison(
                    field_id="gps_proximity",
                    field_label="Geolocation Proximity",
                    status="inconsistent",
                    values_by_evidence=gps_vals,
                    delta_or_diff=f"Separation distance: {dist_str}",
                    finding_title="Geographic Separation Detected",
                    explanation=f"Compared files exhibit a geographic separation of {dist_str}. Verify whether the elapsed time supports travel between these locations.",
                    plausible_causes=[
                        "Recordings captured at different stages of an incident across different locations.",
                        "One or more GPS coordinates were injected or altered.",
                        "GPS sensor lock was lost, defaulting to last known cell-tower triangulation point.",
                    ],
                )
            )

    # -------------------------------------------------------------
    # 5. Media Resolution & Dimensions
    # -------------------------------------------------------------
    dim_vals = {s.evidence_number: s.dimensions or "Unknown" for s in summaries}
    valid_dims = [s.dimensions for s in summaries if s.dimensions]

    if len(valid_dims) >= 2:
        if len(set(valid_dims)) == 1:
            field_comparisons.append(
                FieldComparison(
                    field_id="dimensions_resolution",
                    field_label="Media Resolution & Dimensions",
                    status="consistent",
                    values_by_evidence=dim_vals,
                    delta_or_diff=f"Matching resolution: {valid_dims[0]}",
                    finding_title="Uniform Media Dimensions",
                    explanation=f"All compared items with dimensional data share the exact resolution ({valid_dims[0]}).",
                    plausible_causes=[
                        "Recordings made on identical sensor settings or camera presets.",
                    ],
                )
            )
        else:
            field_comparisons.append(
                FieldComparison(
                    field_id="dimensions_resolution",
                    field_label="Media Resolution & Dimensions",
                    status="inconsistent",
                    values_by_evidence=dim_vals,
                    delta_or_diff=f"Different dimensions: {', '.join(set(valid_dims))}",
                    finding_title="Differing Media Resolutions",
                    explanation=f"Compared media items exhibit differing pixel dimensions ({', '.join(set(valid_dims))}).",
                    plausible_causes=[
                        "Different camera sensors or aspect ratio selections (e.g. 16:9 vs 4:3).",
                        "One item may have been cropped, scaled down, or compressed.",
                    ],
                )
            )

    # -------------------------------------------------------------
    # 6. Audio / Video Durations (if applicable)
    # -------------------------------------------------------------
    dur_items = [s for s in summaries if s.duration_sec is not None and s.duration_sec > 0]
    if len(dur_items) >= 2:
        dur_vals = {s.evidence_number: f"{s.duration_sec:.2f}s" for s in summaries}
        durs = [s.duration_sec for s in dur_items if s.duration_sec is not None]
        dur_delta = abs(max(durs) - min(durs))
        if dur_delta <= 2.0:
            field_comparisons.append(
                FieldComparison(
                    field_id="media_duration",
                    field_label="Audio / Video Duration Alignment",
                    status="consistent",
                    values_by_evidence=dur_vals,
                    delta_or_diff=f"Delta: {dur_delta:.2f} seconds",
                    finding_title="Consistent Media Durations",
                    explanation=f"Compared time-based media files have virtually identical durations (delta: {dur_delta:.2f}s).",
                    plausible_causes=[
                        "Simultaneously terminated recordings or dual-stream audio/video capture.",
                    ],
                )
            )
        else:
            field_comparisons.append(
                FieldComparison(
                    field_id="media_duration",
                    field_label="Audio / Video Duration Alignment",
                    status="inconsistent",
                    values_by_evidence=dur_vals,
                    delta_or_diff=f"Delta: {dur_delta:.2f} seconds",
                    finding_title="Duration Discrepancy",
                    explanation=f"Compared media files differ in duration by {dur_delta:.2f} seconds.",
                    plausible_causes=[
                        "One recording started earlier or continued longer than the other.",
                        "Portions of footage or audio were trimmed or omitted.",
                    ],
                )
            )

    # -------------------------------------------------------------
    # Summarize Overall Consistency
    # -------------------------------------------------------------
    consistent_cnt = sum(1 for f in field_comparisons if f.status == "consistent")
    inconsistent_cnt = sum(1 for f in field_comparisons if f.status == "inconsistent")
    missing_cnt = sum(1 for f in field_comparisons if f.status == "missing_data")

    if inconsistent_cnt > 0:
        overall_status = "inconsistencies_detected"
        highest_sev = "medium" if inconsistent_cnt >= 2 else "low"
    elif consistent_cnt > 0:
        overall_status = "consistent"
        highest_sev = "info"
    else:
        overall_status = "insufficient_data"
        highest_sev = "info"

    summary_obj = ComparisonSummary(
        total_fields_evaluated=len(field_comparisons),
        consistent_count=consistent_cnt,
        inconsistent_count=inconsistent_cnt,
        missing_data_count=missing_cnt,
        overall_status=overall_status,
        highest_severity=highest_sev,
    )

    limitations_text = (
        "Forensic Cross-Evidence Limitations (spec.md §FR-08): "
        "A detected inconsistency or timestamp divergence does NOT automatically prove evidence fabrication, tampering, or perjury. "
        "Camera internal clocks frequently drift without NTP network synchronization; devices operate in different time zones; "
        "and consumer messaging platforms (WhatsApp, Signal, Telegram) routinely strip EXIF metadata and recompress media. "
        "These comparative findings must be evaluated by human investigators alongside corroborating witness testimony and chain of custody."
    )

    return CrossEvidenceComparisonResponse(
        case_id=case.id,
        case_number=case.case_number,
        compared_evidence_ids=[s.evidence_id for s in summaries],
        evidence_summaries=summaries,
        timeline=timeline_events,
        comparison_matrix=field_comparisons,
        summary=summary_obj,
        limitations=limitations_text,
        compared_at=datetime.now(timezone.utc),
    )
