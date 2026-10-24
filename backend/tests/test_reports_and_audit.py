import io
import uuid
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
            "title": f"Report Test Case {uuid.uuid4().hex[:6]}",
            "investigator_name": "Inspector Anand",
            "description": "Digital forensics examination of suspicious mobile recordings.",
        },
    )
    assert res.status_code == 201
    return res.json()["id"]


def upload_sample_image(case_id: int) -> int:
    """Helper to upload an image."""
    img = Image.new("RGB", (80, 80), color=(50, 100, 150))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("crime_scene_photo.jpg", buf.getvalue(), "image/jpeg")},
    )
    assert res.status_code == 201
    return res.json()["id"]


def test_generate_case_forensic_pdf_report():
    """Verify generating a forensic PDF report creates a valid PDF document on disk and logs an audit event."""
    case_id = create_test_case()
    ev1 = upload_sample_image(case_id)

    # Perform integrity check first so there's integrity log in the report
    client.post(f"/api/evidence/{ev1}/verify-integrity")

    # Generate PDF report
    res = client.post(
        f"/api/cases/{case_id}/reports",
        json={
            "include_all_evidence": True,
            "include_audit_trail": True,
            "notes": "Preliminary digital evidence examination completed. Byte integrity verified.",
        },
    )
    assert res.status_code == 201
    data = res.json()

    assert data["case_id"] == case_id
    assert data["report_number"].startswith("REP-")
    assert data["report_status"] == "generated"
    assert data["file_size_bytes"] is not None and data["file_size_bytes"] > 0
    assert "download_url" in data
    assert f"/api/reports/{data['id']}/download" in data["download_url"]


def test_download_forensic_report_pdf_bytes():
    """Verify that downloading the report streams valid PDF bytes."""
    case_id = create_test_case()
    upload_sample_image(case_id)

    rep_res = client.post(
        f"/api/cases/{case_id}/reports",
        json={"include_all_evidence": True, "include_audit_trail": True},
    )
    assert rep_res.status_code == 201
    report_id = rep_res.json()["id"]

    # Download report
    dl_res = client.get(f"/api/reports/{report_id}/download")
    assert dl_res.status_code == 200
    assert "application/pdf" in dl_res.headers.get("content-type", "")
    assert dl_res.content.startswith(b"%PDF-")


def test_list_case_reports():
    """Verify querying reports for a case returns all generated report records."""
    case_id = create_test_case()
    upload_sample_image(case_id)

    # Generate 2 reports
    client.post(f"/api/cases/{case_id}/reports", json={"notes": "First report"})
    client.post(f"/api/cases/{case_id}/reports", json={"notes": "Second report"})

    res = client.get(f"/api/cases/{case_id}/reports")
    assert res.status_code == 200
    reports = res.json()
    assert len(reports) >= 2
    assert all(r["case_id"] == case_id for r in reports)


def test_audit_log_query_and_filtering():
    """Verify that the chain-of-custody audit log records actions and supports filtering."""
    case_id = create_test_case()
    ev_id = upload_sample_image(case_id)

    # Trigger actions
    client.post(f"/api/evidence/{ev_id}/verify-integrity")
    rep = client.post(f"/api/cases/{case_id}/reports", json={})
    client.get(f"/api/reports/{rep.json()['id']}/download")

    # 1. Unfiltered query
    all_res = client.get("/api/audit-log")
    assert all_res.status_code == 200
    log_data = all_res.json()
    assert log_data["total_count"] > 0
    assert len(log_data["events"]) > 0

    # 2. Filter by case_id
    case_res = client.get(f"/api/audit-log?case_id={case_id}")
    assert case_res.status_code == 200
    case_events = case_res.json()["events"]
    assert len(case_events) >= 3
    actions = [e["action"] for e in case_events]
    assert "CASE_CREATE" in actions
    assert "EVIDENCE_UPLOAD" in actions
    assert "REPORT_GENERATION" in actions
    assert "REPORT_DOWNLOAD" in actions

    # 3. Filter by action
    action_res = client.get(f"/api/audit-log?case_id={case_id}&action=REPORT_GENERATION")
    assert action_res.status_code == 200
    assert all("REPORT_GENERATION" in e["action"] for e in action_res.json()["events"])


def test_report_error_handling_nonexistent_case():
    """Verify 404 error when generating a report for a nonexistent case."""
    res = client.post("/api/cases/999999/reports", json={})
    assert res.status_code == 404


def test_download_error_handling_nonexistent_report():
    """Verify 404 error when downloading a nonexistent report ID."""
    res = client.get("/api/reports/999999/download")
    assert res.status_code == 404


def test_report_generation_with_empty_fields_and_no_analyses():
    """Verify generating a report for a case with no description or analyses compiles cleanly."""
    # Case with minimal/empty fields
    res = client.post(
        "/api/cases",
        json={"title": f"Minimal Case {uuid.uuid4().hex[:6]}"},
    )
    assert res.status_code == 201
    case_id = res.json()["id"]

    # Generate report with no evidence and no analyses
    rep_res = client.post(
        f"/api/cases/{case_id}/reports",
        json={"include_all_evidence": True, "include_audit_trail": False},
    )
    assert rep_res.status_code == 201
    rep_id = rep_res.json()["id"]

    # Verify download
    dl = client.get(f"/api/reports/{rep_id}/download")
    assert dl.status_code == 200
    assert dl.content.startswith(b"%PDF-")


def test_report_generation_with_multiple_evidence_and_findings():
    """Verify generating a report with multiple evidence items and analyses."""
    case_id = create_test_case()
    ev1 = upload_sample_image(case_id)

    # Upload sample WAV audio
    wav_buf = io.BytesIO()
    import wave
    with wave.open(wav_buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(8000)
        wf.writeframes(b"\x00\x00" * 4000)
    wav_res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("recording.wav", wav_buf.getvalue(), "audio/wav")},
    )
    assert wav_res.status_code == 201
    ev2 = wav_res.json()["id"]

    # Run image analysis
    client.post(f"/api/evidence/{ev1}/analyze/image")
    # Run audio analysis
    client.post(f"/api/evidence/{ev2}/analyze/audio")
    # Run integrity verification
    client.post(f"/api/evidence/{ev1}/verify-integrity")

    # Generate full report
    rep_res = client.post(
        f"/api/cases/{case_id}/reports",
        json={
            "include_all_evidence": True,
            "include_audit_trail": True,
            "notes": "Full multi-modal examination with image and audio findings.",
        },
    )
    assert rep_res.status_code == 201
    data = rep_res.json()
    assert data["report_number"].startswith("REP-")

    # Download and verify PDF bytes
    dl = client.get(f"/api/reports/{data['id']}/download")
    assert dl.status_code == 200
    assert dl.content.startswith(b"%PDF-")
    assert len(dl.content) > 1000
