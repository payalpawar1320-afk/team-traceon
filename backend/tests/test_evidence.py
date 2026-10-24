import io
import os
import uuid
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db
from app.config import settings

client = TestClient(app)

# Minimal valid file byte headers for testing
# Valid 1x1 PNG
VALID_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

# Minimal valid JPEG
VALID_JPEG_BYTES = (
    b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xFF\xDB\x00C\x00\x08\x06\x06\x07\x06\x05\x08"
    b"\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \"#\x1c"
    b"\x1c(7),01444\x1f'9=82<.342\xFF\xC0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xFF\xC4\x00\x1f\x00\x00\x01\x05"
    b"\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xFF\xDA\x00\x08"
    b"\x01\x01\x00\x00?\x00\xbf\x00\xFF\xD9"
)

# Minimal valid WAV (44-byte standard header)
VALID_WAV_BYTES = (
    b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
)


def setup_module():
    """Ensure database and storage directories are initialized."""
    init_db()
    settings.ensure_storage_directories()


def create_test_case() -> int:
    """Helper to register a unique case for testing."""
    res = client.post(
        "/api/cases",
        json={
            "title": f"Forensic Evidence Test Case {uuid.uuid4().hex[:6]}",
            "investigator_name": "Forensic Inspector",
        },
    )
    assert res.status_code == 201
    return res.json()["id"]


def test_upload_valid_png_evidence():
    """Verify successful upload, hash calculation, and baseline integrity check of a valid PNG."""
    case_id = create_test_case()
    file_content = io.BytesIO(VALID_PNG_BYTES)

    response = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("crime_scene_photo.png", file_content, "image/png")},
        data={"investigator_name": "SI Forensic"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["case_id"] == case_id
    assert data["evidence_number"].startswith("EVID-")
    assert data["original_filename"] == "crime_scene_photo.png"
    assert data["detected_file_type"] == "image"
    assert data["mime_type"] == "image/png"
    assert data["file_size"] == len(VALID_PNG_BYTES)
    assert len(data["sha256_hash"]) == 64
    assert data["latest_integrity_status"] == "Match"


def test_upload_valid_jpeg_and_wav():
    """Verify upload support for JPEG images and WAV audio."""
    case_id = create_test_case()

    # JPEG
    res_jpg = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("suspect_vehicle.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")},
    )
    assert res_jpg.status_code == 201
    assert res_jpg.json()["detected_file_type"] == "image"

    # WAV
    res_wav = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("emergency_call.wav", io.BytesIO(VALID_WAV_BYTES), "audio/wav")},
    )
    assert res_wav.status_code == 201
    assert res_wav.json()["detected_file_type"] == "audio"


def test_reject_unsupported_extension():
    """Verify rejection of non-whitelisted file extensions (e.g. .exe, .sh, .py)."""
    case_id = create_test_case()
    res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("malware_payload.exe", io.BytesIO(b"MZ\x90\x00"), "application/x-msdownload")},
    )
    assert res.status_code == 400
    assert "Unsupported file format" in res.json()["detail"]


def test_reject_disguised_file_with_invalid_magic_bytes():
    """Verify that an arbitrary text file renamed to .png is rejected due to invalid file signature."""
    case_id = create_test_case()
    fake_png = io.BytesIO(b"This is purely plain text pretending to be a PNG image.")
    res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("disguised_script.png", fake_png, "image/png")},
    )
    assert res.status_code == 400
    assert "magic bytes" in res.json()["detail"]


def test_reject_empty_file():
    """Verify that 0-byte uploaded files are rejected."""
    case_id = create_test_case()
    res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("empty.png", io.BytesIO(b""), "image/png")},
    )
    assert res.status_code == 400
    assert "empty" in res.json()["detail"]


def test_path_traversal_sanitization():
    """Verify that path traversal characters in filename are safely stripped."""
    case_id = create_test_case()
    res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("../../../../etc/passwd.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )
    assert res.status_code == 201
    assert ".." not in res.json()["original_filename"]
    assert "/" not in res.json()["original_filename"]
    assert "\\" not in res.json()["original_filename"]


def test_on_demand_integrity_verification_match():
    """Verify FR-04: on-demand recalculation returns Match when file bytes are untouched."""
    case_id = create_test_case()
    upload_res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("integrity_test.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )
    assert upload_res.status_code == 201
    ev_id = upload_res.json()["id"]
    recorded_hash = upload_res.json()["sha256_hash"]

    # Trigger verify endpoint
    verify_res = client.post(f"/api/evidence/{ev_id}/verify")
    assert verify_res.status_code == 200
    verify_data = verify_res.json()
    assert verify_data["evidence_id"] == ev_id
    assert verify_data["status"] == "Match"
    assert verify_data["is_match"] is True
    assert verify_data["recorded_hash"] == recorded_hash
    assert verify_data["recalculated_hash"] == recorded_hash


def test_on_demand_integrity_verification_mismatch_detected():
    """Verify FR-04: deliberately altering file bytes on disk triggers Mismatch status."""
    case_id = create_test_case()
    upload_res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("tamper_test.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )
    assert upload_res.status_code == 201
    ev_data = upload_res.json()
    ev_id = ev_data["id"]
    storage_name = ev_data["storage_filename"]

    # Tamper with the file on disk by appending or modifying a byte
    file_path = Path(settings.EVIDENCE_UPLOAD_DIR) / storage_name
    assert file_path.exists()
    with open(file_path, "ab") as f:
        f.write(b"\x00TAMPERED_BYTE_INJECTION")

    # Re-verify hash
    verify_res = client.post(f"/api/evidence/{ev_id}/verify")
    assert verify_res.status_code == 200
    verify_data = verify_res.json()
    assert verify_data["status"] == "Mismatch"
    assert verify_data["is_match"] is False
    assert verify_data["recalculated_hash"] != verify_data["recorded_hash"]
    assert "differ" in verify_data["notes"] or "modified" in verify_data["notes"]


def test_batch_verify_all_case_evidence():
    """Verify batch integrity verification across all evidence in a case."""
    case_id = create_test_case()

    # Upload two items
    client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("batch1.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )
    client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("batch2.jpg", io.BytesIO(VALID_JPEG_BYTES), "image/jpeg")},
    )

    batch_res = client.post(f"/api/cases/{case_id}/verify-all")
    assert batch_res.status_code == 200
    batch_data = batch_res.json()
    assert batch_data["case_id"] == case_id
    assert batch_data["total_checked"] >= 2
    assert batch_data["match_count"] >= 2
    assert batch_data["mismatch_count"] == 0
    assert batch_data["failed_count"] == 0


def test_download_evidence_file():
    """Verify secure download endpoint delivers the exact preserved bytes."""
    case_id = create_test_case()
    upload_res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("original_download.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )
    ev_id = upload_res.json()["id"]

    download_res = client.get(f"/api/evidence/{ev_id}/download")
    assert download_res.status_code == 200
    assert download_res.content == VALID_PNG_BYTES
    assert "nosniff" in download_res.headers.get("X-Content-Type-Options", "")
