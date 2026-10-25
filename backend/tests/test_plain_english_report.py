import io
import json
import tempfile
import uuid
from pathlib import Path

import pypdf
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db
from app.config import settings

client = TestClient(app)


def setup_module():
    """Initialize database and storage directories."""
    init_db()
    settings.ensure_storage_directories()


def create_test_case(title="Plain English Report Test Case") -> int:
    """Helper to create an investigation case."""
    res = client.post(
        "/api/cases",
        json={
            "title": title,
            "investigator_name": "Inspector Verma",
            "description": "Evaluation of report plain English readability and dynamic conclusions.",
        },
    )
    assert res.status_code == 201
    return res.json()["id"]


def upload_jpeg_image(case_id: int, filename="sample_scene.jpg") -> int:
    """Upload a clean JPEG image."""
    img = Image.new("RGB", (100, 100), color=(60, 90, 140))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": (filename, buf.getvalue(), "image/jpeg")},
    )
    assert res.status_code == 201
    return res.json()["id"]


def upload_png_image(case_id: int, filename="sample_graphic.png") -> int:
    """Upload a clean PNG image."""
    img = Image.new("RGB", (80, 80), color=(120, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": (filename, buf.getvalue(), "image/png")},
    )
    assert res.status_code == 201
    return res.json()["id"]


def test_pdf_report_plain_english_structure_and_ai_assessment():
    """
    Test that the generated PDF includes:
    1. 'FINAL CONCLUSION — WHAT THIS REPORT TELLS YOU' section.
    2. 'AI-GENERATED IMAGE ASSESSMENT' section with honest status.
    3. Plain English explanations (no unsupported claims).
    4. Clear status vocabulary.
    """
    case_id = create_test_case(title="Police Investigation Demonstration")
    img_id = upload_jpeg_image(case_id)

    # Verify integrity and run image analysis
    client.post(f"/api/evidence/{img_id}/verify-integrity")
    client.post(f"/api/evidence/{img_id}/analyze/image")

    # Generate report
    rep_res = client.post(
        f"/api/cases/{case_id}/reports",
        json={"include_all_evidence": True, "include_audit_trail": True},
    )
    assert rep_res.status_code == 201
    report_id = rep_res.json()["id"]

    dl_res = client.get(f"/api/reports/{report_id}/download")
    assert dl_res.status_code == 200
    pdf_bytes = dl_res.content

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    full_text = "\n".join(p.extract_text() for p in reader.pages)
    norm_text = " ".join(full_text.split())

    # 1. Plain English headings
    assert "FINAL CONCLUSION — WHAT THIS REPORT TELLS YOU" in full_text
    assert "AI-GENERATED IMAGE ASSESSMENT" in full_text
    assert "FORENSIC LIMITATIONS — WHAT THESE CHECKS CANNOT ESTABLISH" in full_text

    # 2. Honest AI assessment: Never claim fake detection
    assert (
        "Analysis Not Run Yet" in full_text
        or "Not Available / Not Implemented in this Prototype" in full_text
        or "CIFAKE" in full_text
    )
    assert (
        "does not output fabricated certainty scores" in norm_text
        or "integrates a CIFAKE-trained EfficientNet-B0" in norm_text
        or "CIFAKE-trained" in norm_text
    )

    # 3. Dynamic conclusion content
    assert "Summary of Examination Findings:" in full_text
    assert "matched the saved intake reference" in norm_text

    # 4. Status vocabulary
    assert "Completed" in full_text or "COMPLETED" in full_text


def test_dynamic_conclusion_detects_mismatch_when_file_tampered():
    """
    Test that when an evidence file's bytes change on disk after registration,
    the dynamic conclusion explicitly states the mismatch in plain English.
    """
    case_id = create_test_case(title="Tamper Detection Case")
    img = Image.new("RGB", (100, 100), color=(60, 90, 140))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    upload_res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("tamper_test.jpg", buf.getvalue(), "image/jpeg")},
    )
    assert upload_res.status_code == 201
    ev_data = upload_res.json()
    ev_id = ev_data["id"]
    storage_name = ev_data["storage_filename"]

    # Tamper with file bytes
    file_path = Path(settings.EVIDENCE_UPLOAD_DIR) / storage_name
    assert file_path.exists()
    with open(file_path, "ab") as f:
        f.write(b"\x00\xFF\x00\xFFTAMPERED_BYTES")

    # Run verify endpoint
    chk_res = client.post(f"/api/evidence/{ev_id}/verify")
    assert chk_res.status_code == 200
    assert chk_res.json()["status"].lower() == "mismatch"

    # Generate report
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

    # Verify plain-English mismatch conclusion
    assert "The file's current digital fingerprint did NOT match the saved reference, indicating the file has changed since intake." in norm_text
    assert "MISMATCH" in full_text


def test_png_support_and_clean_report_generation():
    """
    Test that PNG evidence is handled cleanly and reported accurately.
    """
    case_id = create_test_case(title="PNG Evidence Case")
    png_id = upload_png_image(case_id, filename="diagram.png")

    client.post(f"/api/evidence/{png_id}/verify-integrity")

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

    assert "diagram.png" in full_text
    assert "IMAGE" in full_text
    assert "image/png" in full_text
    assert "FINAL CONCLUSION — WHAT THIS REPORT TELLS YOU" in full_text


def test_cifake_ai_image_detection_in_report():
    """
    Test that when an image is analyzed with image forensics, the CIFAKE-trained
    EfficientNet-B0 and 2D-FFT detector evaluates it, records real probabilities,
    and updates Section 5 and the Conclusion in the generated PDF report.
    """
    case_id = create_test_case(title="AI Detection Evaluation Case")
    ev_id = upload_jpeg_image(case_id, filename="camera_scene.jpg")

    # Run image forensics analysis
    an_res = client.post(f"/api/evidence/{ev_id}/analyze/image")
    assert an_res.status_code == 200
    an_data = an_res.json()
    assert "ai_detection_report" in an_data
    ai_data = an_data["ai_detection_report"]
    assert ai_data["status"] == "completed"
    assert "CIFAKE-EfficientNet-B0" in ai_data["model_name"]
    assert "probability_ai_pct" in ai_data
    assert "probability_real_pct" in ai_data

    # Generate PDF report
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

    assert "CIFAKE-EfficientNet-B0 (ONNX)" in full_text
    assert "AI-GENERATED IMAGE ASSESSMENT" in full_text
    assert "CIFAKE-trained AI detector" in norm_text

