import io
import json
import tempfile
import uuid
from pathlib import Path
import wave

import cv2
import numpy as np
import pypdf
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db
from app.config import settings

client = TestClient(app)


def setup_module():
    """Initialize test database and storage directories."""
    init_db()
    settings.ensure_storage_directories()


def create_test_case(title="Forensic PDF Test Case", case_number=None) -> int:
    """Helper to register an investigation case."""
    payload = {
        "title": title,
        "investigator_name": "Inspector Raman",
        "description": "Multi-modal forensic evaluation of CCTV, photo, and voice memo.",
    }
    if case_number:
        payload["case_number"] = case_number
    res = client.post("/api/cases", json=payload)
    assert res.status_code == 201
    return res.json()["id"]


def upload_sample_image(case_id: int) -> int:
    """Helper to upload a sample JPEG image."""
    img = Image.new("RGB", (120, 120), color=(40, 80, 160))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("cctv_still_photo.jpg", buf.getvalue(), "image/jpeg")},
    )
    assert res.status_code == 201
    return res.json()["id"]


def upload_sample_video(case_id: int) -> int:
    """Helper to upload an OpenCV-generated synthetic MP4 video."""
    temp_dir = tempfile.mkdtemp()
    temp_file = Path(temp_dir) / f"synth_{uuid.uuid4().hex[:8]}.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(temp_file), fourcc, 10, (160, 120))

    for i in range(25):
        frame = np.full((120, 160, 3), (i * 10) % 255, dtype=np.uint8)
        cv2.putText(frame, f"F:{i}", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        out.write(frame)
    out.release()

    with open(temp_file, "rb") as f:
        vid_bytes = f.read()

    res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("store_entrance_cam.mp4", vid_bytes, "video/mp4")},
    )
    assert res.status_code == 201
    return res.json()["id"]


def upload_sample_audio(case_id: int) -> int:
    """Helper to upload a sample WAV audio recording."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(8000)
        # 1 second of silence
        wf.writeframes(b"\x00\x00" * 8000)

    res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("witness_voice_memo.wav", buf.getvalue(), "audio/wav")},
    )
    assert res.status_code == 201
    return res.json()["id"]


def test_full_traceon_report_branding_and_quality():
    """
    Test complete report generation with synthetic demonstration evidence.
    Verifies:
    1. TRACEON product branding, tagline, title, subtitle.
    2. 'EvidenceGuard AI' is never displayed.
    3. Problem statement numbers are never printed.
    4. Executive first page with mandatory integrity notice.
    5. Deduplication of verification entries and video analysis findings.
    6. Truthful methodology and 20 sampled frames video wording.
    7. Consistent 'Demonstration Report — Not a Certified Forensic Report' status.
    """
    case_id = create_test_case(title="National Hackathon Demonstration Case")
    img_id = upload_sample_image(case_id)
    vid_id = upload_sample_video(case_id)
    aud_id = upload_sample_audio(case_id)

    # Trigger verify-integrity multiple times on image to test duplicate record prevention
    client.post(f"/api/evidence/{img_id}/verify")
    client.post(f"/api/evidence/{img_id}/verify")
    client.post(f"/api/evidence/{img_id}/verify")

    # Run image analysis
    client.post(f"/api/evidence/{img_id}/analyze/image")

    # Run video analysis TWICE to verify finding deduplication in report
    client.post(f"/api/evidence/{vid_id}/analyze/video?target_sample_frames=20")
    client.post(f"/api/evidence/{vid_id}/analyze/video?target_sample_frames=20")

    # Run audio analysis
    client.post(f"/api/evidence/{aud_id}/analyze/audio")

    # Generate full report
    rep_res = client.post(
        f"/api/cases/{case_id}/reports",
        json={
            "include_all_evidence": True,
            "include_audit_trail": True,
            "notes": "Comprehensive multi-modal forensic demonstration examination.",
        },
    )
    assert rep_res.status_code == 201
    data = rep_res.json()
    report_id = data["id"]

    # Download PDF
    dl_res = client.get(f"/api/reports/{report_id}/download")
    assert dl_res.status_code == 200
    pdf_bytes = dl_res.content
    assert pdf_bytes.startswith(b"%PDF-")

    # Parse with PyPDF
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    num_pages = len(reader.pages)
    assert num_pages >= 2, "Report should have at least 2 pages (Executive page 1 + Technical dossier)"

    all_page_texts = [reader.pages[i].extract_text() for i in range(num_pages)]
    full_text = "\n".join(all_page_texts)

    # 1. Product Branding Verification
    assert "TRACEON" in full_text
    assert "Every Trace. Every Truth." in full_text
    assert "Digital Evidence Integrity and Forensic Analysis" in full_text
    assert "Digital Evidence Examination Report" in full_text
    assert "Demonstration Report — Not a Certified Forensic Report." in full_text

    # 2. Strict Prohibition: Never display EvidenceGuard AI
    assert "EvidenceGuard AI" not in full_text
    assert "EvidenceGuard" not in full_text

    # 3. Strict Prohibition: Never display problem statement numbers
    assert "Problem Statement 112" not in full_text
    assert "Problem 112" not in full_text
    assert "PS-112" not in full_text
    assert "PS 112" not in full_text

    # 4. Status Consistency: No contradictory status labels
    assert "FINAL WORKING COPY" not in full_text
    assert "VERIFIED WORKING DOCUMENT" not in full_text
    assert "LAW ENFORCEMENT PROTOTYPE" not in full_text

    # 5. First Page Executive Summary & Prominent Limitation
    page1_text = all_page_texts[0]
    assert "1. INVESTIGATION CASE SUMMARY" in page1_text
    assert "2. DIGITAL EVIDENCE & INTEGRITY STATUS OVERVIEW" in page1_text
    assert "MANDATORY INTEGRITY VERIFICATION NOTICE & LIMITATIONS" in page1_text
    assert "does NOT prove the file was genuine when recorded" in page1_text
    assert "MATCH" in page1_text

    # 6. Deduplication Check on Page 1 Evidence Overview:
    # Even though verify was run 4 times on img_id, each item ID appears once in section 2
    # Check that item IDs appear exactly once in the overview
    assert page1_text.count("cctv_still_photo.jpg") == 1
    assert page1_text.count("store_entrance_cam.mp4") == 1
    assert page1_text.count("witness_voice_memo.wav") == 1

    # 7. Truthful Video Reporting Wording
    norm_text = " ".join(full_text.split())
    assert "20 sampled frames" in norm_text
    assert "No indicator was detected by this check in the examined samples. This result does not establish that the complete video is authentic or free from manipulation." in norm_text
    assert "Decodable" in norm_text or "decodability only, not footage authenticity" in norm_text

    # 8. Methodology Agreement
    # Since image, video, and audio analyses all ran, all should be COMPLETED
    assert "File Signature Validation" in norm_text
    assert "SHA-256 Digital Fingerprint" in norm_text
    assert "Video Continuity Check" in norm_text
    assert "Error Level Analysis (ELA)" in norm_text

    # 9. Deduplicated Findings:
    # Video forensics ran twice, but there should be only ONE finding for video_forensics
    video_findings_matches = [line for line in full_text.split("\n") if "Video Forensics" in line]
    assert len(video_findings_matches) == 1, "Video forensics finding should be deduplicated to latest run"


def test_truthful_methodology_when_checks_not_run():
    """
    Test that when an evidence item has NOT been analyzed with certain modules,
    the methodology table truthfully marks them as NOT APPLICABLE or NOT CHECKED,
    rather than claiming 'Completed'.
    """
    case_id = create_test_case(title="Image-Only Investigation")
    upload_sample_image(case_id)
    # Do NOT run any analysis modules!

    rep_res = client.post(
        f"/api/cases/{case_id}/reports",
        json={"include_all_evidence": True, "include_audit_trail": False},
    )
    assert rep_res.status_code == 201
    rep_id = rep_res.json()["id"]

    dl = client.get(f"/api/reports/{rep_id}/download")
    assert dl.status_code == 200

    reader = pypdf.PdfReader(io.BytesIO(dl.content))
    full_text = "\n".join(p.extract_text() for p in reader.pages)
    norm_text = " ".join(full_text.split())

    # File signature was checked at upload
    assert "File Signature Validation" in norm_text
    # Video and audio checks should be NOT APPLICABLE since there is only an image
    assert "NOT APPLICABLE" in norm_text
    # Findings should state that no formal modules were executed
    assert "No formal laboratory analysis modules" in norm_text


def test_case_number_sanitization_for_problem_statements():
    """
    Test that if a case reference is created with 'Problem Statement 112' or 'PS-112',
    the PDF generator sanitizes it and never prints the problem statement number.
    """
    unique_ref = f"CASE-{uuid.uuid4().hex[:4]}-PS112"
    case_id = create_test_case(
        title="Sanitization Verification Case",
        case_number=unique_ref,
    )
    upload_sample_image(case_id)

    rep_res = client.post(
        f"/api/cases/{case_id}/reports",
        json={"notes": "Examining Problem Statement 112 evidence artifacts."},
    )
    assert rep_res.status_code == 201
    rep_id = rep_res.json()["id"]

    dl = client.get(f"/api/reports/{rep_id}/download")
    assert dl.status_code == 200

    reader = pypdf.PdfReader(io.BytesIO(dl.content))
    full_text = "\n".join(p.extract_text() for p in reader.pages)

    assert "Problem Statement 112" not in full_text
    assert "Problem Statement" not in full_text
    assert "EvidenceGuard" not in full_text
