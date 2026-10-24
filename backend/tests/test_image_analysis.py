import io
import os
import uuid
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db
from app.config import settings

client = TestClient(app)


def setup_module():
    """Ensure database and storage directories are initialized."""
    init_db()
    settings.ensure_storage_directories()


def create_test_case() -> int:
    """Helper to create a test case."""
    res = client.post(
        "/api/cases",
        json={
            "title": f"Image Forensic Case {uuid.uuid4().hex[:6]}",
            "investigator_name": "Cyber Inspector",
        },
    )
    assert res.status_code == 201
    return res.json()["id"]


def create_sample_jpeg_with_exif(software: str = None, make: str = None, model: str = None) -> bytes:
    """Helper to generate a valid in-memory JPEG with customized EXIF data."""
    img = Image.new("RGB", (120, 120), color=(100, 150, 200))
    exif = img.getexif()

    # Tag 305 = Software
    if software:
        exif[305] = software
    # Tag 271 = Make
    if make:
        exif[271] = make
    # Tag 272 = Model
    if model:
        exif[272] = model
    # Tag 306 = DateTime
    exif[306] = "2026:01:15 10:30:00"

    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def test_analyze_image_clean_jpeg():
    """Verify metadata extraction and ELA generation on a clean JPEG image."""
    case_id = create_test_case()
    jpeg_bytes = create_sample_jpeg_with_exif(make="Canon", model="EOS R5")

    # Ingest image
    upload_res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("scene_clean.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")},
    )
    assert upload_res.status_code == 201
    ev_id = upload_res.json()["id"]

    # Run image analysis
    analyze_res = client.post(f"/api/evidence/{ev_id}/analyze/image")
    assert analyze_res.status_code == 200
    data = analyze_res.json()

    assert data["evidence_id"] == ev_id
    assert data["case_id"] == case_id
    assert data["analysis_type"] == "image_forensics"

    # Verify metadata report
    meta = data["metadata_report"]
    assert meta["has_exif"] is True
    assert meta["camera_make"] == "Canon"
    assert meta["camera_model"] == "EOS R5"
    assert meta["width"] == 120
    assert meta["height"] == 120

    # Verify ELA report
    ela = data["ela_report"]
    assert ela["status"] == "completed"
    assert ela["ela_filename"] is not None
    assert ela["ela_url"] is not None
    assert "mean_error" in ela
    assert "variance" in ela

    # Verify derived ELA asset is downloadable
    asset_res = client.get(ela["ela_url"])
    assert asset_res.status_code == 200
    assert "image/jpeg" in asset_res.headers.get("content-type", "")


def test_detect_editing_software_signature():
    """Verify that EXIF software signature (e.g. Adobe Photoshop) triggers an indicator finding."""
    case_id = create_test_case()
    tampered_jpeg = create_sample_jpeg_with_exif(software="Adobe Photoshop 2024 (Windows)")

    upload_res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("edited_contract.jpg", io.BytesIO(tampered_jpeg), "image/jpeg")},
    )
    assert upload_res.status_code == 201
    ev_id = upload_res.json()["id"]

    analyze_res = client.post(f"/api/evidence/{ev_id}/analyze/image")
    assert analyze_res.status_code == 200
    data = analyze_res.json()

    assert data["total_indicators"] >= 1
    assert "Review recommended" in data["status"]

    meta_findings = data["metadata_report"]["findings"]
    software_findings = [f for f in meta_findings if "Software" in f["category"] or "Software" in f["title"]]
    assert len(software_findings) >= 1
    assert "Photoshop" in software_findings[0]["description"]


def test_reject_image_analysis_on_non_image():
    """Verify that requesting image analysis on an audio file returns 400 Bad Request."""
    case_id = create_test_case()
    # 44-byte WAV
    wav_bytes = (
        b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    )

    upload_res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("audio_wire.wav", io.BytesIO(wav_bytes), "audio/wav")},
    )
    assert upload_res.status_code == 201
    ev_id = upload_res.json()["id"]

    analyze_res = client.post(f"/api/evidence/{ev_id}/analyze/image")
    assert analyze_res.status_code == 400
    assert "not an image" in analyze_res.json()["detail"]


def test_get_evidence_analysis_history():
    """Verify retrieval of historical analysis results for an evidence file and case."""
    case_id = create_test_case()
    jpeg_bytes = create_sample_jpeg_with_exif(make="Sony", model="A7 IV")

    upload_res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("scene_history.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")},
    )
    ev_id = upload_res.json()["id"]

    # Run analysis
    client.post(f"/api/evidence/{ev_id}/analyze/image")

    # Get evidence analysis
    hist_res = client.get(f"/api/evidence/{ev_id}/analysis")
    assert hist_res.status_code == 200
    hist_data = hist_res.json()
    assert len(hist_data) >= 1
    assert hist_data[0]["evidence_id"] == ev_id

    # Get case-wide analysis summary
    case_analysis_res = client.get(f"/api/cases/{case_id}/analysis")
    assert case_analysis_res.status_code == 200
    case_data = case_analysis_res.json()
    assert len(case_data) >= 1
