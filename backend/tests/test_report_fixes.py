import io
import json
import pypdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.database import get_db, Base, engine

client = TestClient(app)


def create_case(title="Test Verification Case"):
    res = client.post(
        "/api/cases",
        json={"title": title, "investigator_name": "Examiner Fox", "status": "active"},
    )
    assert res.status_code == 201
    return res.json()["id"]


def make_test_jpeg(width=64, height=64, color=(120, 150, 180)):
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=color)
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def test_duplicate_file_upload_warning_preserves_both_records():
    """
    Test requirement 3: Confirm whether the same file was uploaded twice,
    do not automatically delete evidence, and display a duplicate-file warning.
    """
    case_id = create_case("Duplicate Upload Test Case")
    jpeg_bytes = make_test_jpeg(80, 80, (200, 100, 50))

    # 1. First upload
    res1 = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("photo_evidence.jpg", jpeg_bytes, "image/jpeg")},
    )
    assert res1.status_code == 201
    ev1 = res1.json()
    assert ev1["is_duplicate"] is False
    assert ev1["duplicate_warning"] is None

    # 2. Second upload with identical bytes and filename
    res2 = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("photo_evidence.jpg", jpeg_bytes, "image/jpeg")},
    )
    assert res2.status_code == 201
    ev2 = res2.json()

    # Confirm both records exist (neither was deleted)
    assert ev1["id"] != ev2["id"]
    assert ev1["evidence_number"] != ev2["evidence_number"]
    assert ev1["sha256_hash"] == ev2["sha256_hash"]

    # Confirm duplicate warning is populated
    assert ev2["is_duplicate"] is True
    assert ev2["duplicate_warning"] is not None
    assert ev1["evidence_number"] in ev2["duplicate_warning"]

    # Verify case evidence list returns both and flags duplicate
    list_res = client.get(f"/api/cases/{case_id}/evidence")
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) == 2
    dup_items = [i for i in items if i["is_duplicate"]]
    assert len(dup_items) >= 1

    # Verify case details returns both
    case_res = client.get(f"/api/cases/{case_id}")
    assert case_res.status_code == 200
    case_detail = case_res.json()
    assert len(case_detail["evidence_items"]) == 2


def test_pdf_report_duplicate_warning_and_ip_redaction():
    """
    Test requirements 3 & 5:
    - Display duplicate warning in PDF when hashes match.
    - Redact IP addresses in demonstration report audit trail.
    """
    case_id = create_case("Duplicate and Redaction Test Case")
    jpeg_bytes = make_test_jpeg(64, 64, (50, 120, 200))

    # Upload exact same file twice
    res1 = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("crime_scene.jpg", jpeg_bytes, "image/jpeg")},
    )
    res2 = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("crime_scene.jpg", jpeg_bytes, "image/jpeg")},
    )
    assert res1.status_code == 201 and res2.status_code == 201

    # Generate PDF with audit trail
    rep_res = client.post(
        f"/api/cases/{case_id}/reports",
        json={"include_all_evidence": True, "include_audit_trail": True},
    )
    assert rep_res.status_code == 201
    report_id = rep_res.json()["id"]

    dl_res = client.get(f"/api/reports/{report_id}/download")
    assert dl_res.status_code == 200
    reader = pypdf.PdfReader(io.BytesIO(dl_res.content))
    full_text = "\n".join(p.extract_text() for p in reader.pages)
    norm_text = " ".join(full_text.split())

    # 1. Duplicate warning present in PDF
    assert "DUPLICATE EVIDENCE UPLOAD WARNING" in full_text or "DUPLICATE FILE" in full_text
    assert "uploaded multiple times" in norm_text

    # 2. IP addresses redacted in demonstration report
    assert "[REDACTED: DEMO AUDIT]" in norm_text or "[SYNTHETIC-AUDIT-IP]" in norm_text
    # Real IP or raw loopback should not appear in audit table
    assert "127.0.0.1" not in full_text


def test_pdf_report_ai_assessment_truthful_when_not_run():
    """
    Test requirements 1, 2 & 4:
    - If analysis has not run, show 'Not run' and do not invent prediction or score.
    - If metadata analysis is 'Not run', do not claim EXIF or physical-device provenance was evaluated.
    """
    case_id = create_case("Unanalyzed Image Case")
    jpeg_bytes = make_test_jpeg(64, 64, (80, 80, 80))
    upload_res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("raw_snap.jpg", jpeg_bytes, "image/jpeg")},
    )
    assert upload_res.status_code == 201

    # Generate PDF WITHOUT running image analysis
    rep_res = client.post(
        f"/api/cases/{case_id}/reports",
        json={"include_all_evidence": True, "include_audit_trail": False},
    )
    assert rep_res.status_code == 201
    report_id = rep_res.json()["id"]

    dl_res = client.get(f"/api/reports/{report_id}/download")
    assert dl_res.status_code == 200
    reader = pypdf.PdfReader(io.BytesIO(dl_res.content))
    full_text = "\n".join(p.extract_text() for p in reader.pages)
    norm_text = " ".join(full_text.split())

    # Section 5 must show Not run
    assert "AI-GENERATED IMAGE ASSESSMENT" in full_text
    assert "Not run" in full_text

    # Must NOT claim EXIF or physical-device provenance was evaluated
    assert "Metadata analysis has not been executed; physical-device provenance was not evaluated" in norm_text
    assert "Evaluated via EXIF header" not in full_text


def test_analysis_history_preserves_ai_detection_report():
    """
    Test requirement 1: Verify complete path from execution to history retrieval.
    """
    case_id = create_case("AI Path Verification Case")
    jpeg_bytes = make_test_jpeg(128, 128, (100, 150, 200))
    upload_res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("street_photo.jpg", jpeg_bytes, "image/jpeg")},
    )
    assert upload_res.status_code == 201
    ev_id = upload_res.json()["id"]

    # Execute image analysis
    an_res = client.post(f"/api/evidence/{ev_id}/analyze/image")
    assert an_res.status_code == 200
    an_data = an_res.json()
    assert "ai_detection_report" in an_data
    assert an_data["ai_detection_report"] is not None
    assert an_data["ai_detection_report"]["status"] == "completed"

    # Now retrieve analysis history via GET /api/evidence/{id}/analysis
    hist_res = client.get(f"/api/evidence/{ev_id}/analysis")
    assert hist_res.status_code == 200
    hist_data = hist_res.json()
    assert len(hist_data) >= 1
    item = hist_data[0]
    assert "ai_detection_report" in item
    assert item["ai_detection_report"] is not None
    assert item["ai_detection_report"]["status"] == "completed"
    assert "prediction" in item["ai_detection_report"]
