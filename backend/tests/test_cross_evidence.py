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
            "title": f"Cross-Evidence Test Case {uuid.uuid4().hex[:6]}",
            "investigator_name": "Forensic Officer Verma",
        },
    )
    assert res.status_code == 201
    return res.json()["id"]


def create_jpeg(datetime_str: str = "2026:03-10 14:00:00", software: str = None, make: str = "Sony", model: str = "ILCE-7M4", size=(100, 100)) -> bytes:
    """Create in-memory JPEG with specific EXIF properties."""
    img = Image.new("RGB", size, color=(120, 140, 160))
    exif = img.getexif()
    if make:
        exif[271] = make
    if model:
        exif[272] = model
    if software:
        exif[305] = software
    if datetime_str:
        exif[306] = datetime_str

    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def create_png_no_exif(size=(100, 100)) -> bytes:
    """Create in-memory PNG with no EXIF metadata."""
    img = Image.new("RGB", size, color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def upload_evidence(case_id: int, filename: str, data: bytes) -> int:
    """Helper to upload an evidence file to a case."""
    res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": (filename, data, "image/jpeg" if filename.endswith(".jpg") else "image/png")},
    )
    assert res.status_code == 201
    return res.json()["id"]


def test_cross_evidence_identical_cameras_and_aligned_timestamps():
    """Verify comparing 2 images from same camera with aligned timestamps returns consistent status."""
    case_id = create_test_case()

    img1 = create_jpeg(datetime_str="2026:03:10 14:00:00", make="Nikon", model="Z9")
    img2 = create_jpeg(datetime_str="2026:03:10 14:00:25", make="Nikon", model="Z9")  # 25s later

    ev1 = upload_evidence(case_id, "scene_photo_01.jpg", img1)
    ev2 = upload_evidence(case_id, "scene_photo_02.jpg", img2)

    res = client.post(
        f"/api/cases/{case_id}/compare-evidence",
        json={"evidence_ids": [ev1, ev2], "time_tolerance_seconds": 60},
    )
    assert res.status_code == 200
    data = res.json()

    assert data["case_id"] == case_id
    assert len(data["compared_evidence_ids"]) == 2
    assert len(data["evidence_summaries"]) == 2
    assert len(data["timeline"]) >= 2
    assert data["summary"]["overall_status"] == "consistent"

    # Verify field comparisons
    fields = {f["field_id"]: f for f in data["comparison_matrix"]}
    assert "capture_timestamp" in fields
    assert fields["capture_timestamp"]["status"] == "consistent"
    assert "25 seconds" in fields["capture_timestamp"]["delta_or_diff"]

    assert "device_hardware" in fields
    assert fields["device_hardware"]["status"] == "consistent"
    assert "Nikon Z9" in fields["device_hardware"]["delta_or_diff"]


def test_cross_evidence_divergent_timestamps_flagged():
    """Verify that divergent timestamps (> tolerance) are accurately flagged as inconsistent with explanations."""
    case_id = create_test_case()

    img1 = create_jpeg(datetime_str="2026:03:10 10:00:00")
    img2 = create_jpeg(datetime_str="2026:03:14 18:30:00")  # > 4 days later

    ev1 = upload_evidence(case_id, "cctv_frame.jpg", img1)
    ev2 = upload_evidence(case_id, "phone_snap.jpg", img2)

    res = client.post(
        f"/api/cases/{case_id}/compare-evidence",
        json={"evidence_ids": [ev1, ev2], "time_tolerance_seconds": 120},
    )
    assert res.status_code == 200
    data = res.json()

    fields = {f["field_id"]: f for f in data["comparison_matrix"]}
    assert fields["capture_timestamp"]["status"] == "inconsistent"
    assert "days apart" in fields["capture_timestamp"]["delta_or_diff"]
    assert len(fields["capture_timestamp"]["plausible_causes"]) > 0
    assert data["summary"]["inconsistent_count"] >= 1
    assert data["summary"]["overall_status"] == "inconsistencies_detected"


def test_cross_evidence_editing_software_detected():
    """Verify that asymmetric editing software signatures are highlighted."""
    case_id = create_test_case()

    clean_img = create_jpeg(software=None)
    edited_img = create_jpeg(software="Adobe Photoshop 2026 (Windows)")

    ev1 = upload_evidence(case_id, "camera_raw_snap.jpg", clean_img)
    ev2 = upload_evidence(case_id, "submitted_evidence.jpg", edited_img)

    res = client.post(
        f"/api/cases/{case_id}/compare-evidence",
        json={"evidence_ids": [ev1, ev2]},
    )
    assert res.status_code == 200
    data = res.json()

    fields = {f["field_id"]: f for f in data["comparison_matrix"]}
    assert fields["software_footprint"]["status"] == "inconsistent"
    assert "Adobe Photoshop" in str(fields["software_footprint"]["values_by_evidence"])
    assert data["summary"]["inconsistent_count"] >= 1


def test_cross_evidence_missing_metadata_handled_gracefully():
    """Verify comparison does not crash when comparing files without EXIF metadata (e.g. PNGs)."""
    case_id = create_test_case()

    png1 = create_png_no_exif(size=(80, 80))
    png2 = create_png_no_exif(size=(160, 160))

    ev1 = upload_evidence(case_id, "whatsapp_img_1.png", png1)
    ev2 = upload_evidence(case_id, "whatsapp_img_2.png", png2)

    res = client.post(
        f"/api/cases/{case_id}/compare-evidence",
        json={"evidence_ids": [ev1, ev2]},
    )
    assert res.status_code == 200
    data = res.json()

    fields = {f["field_id"]: f for f in data["comparison_matrix"]}
    assert fields["capture_timestamp"]["status"] == "missing_data"
    assert fields["device_hardware"]["status"] == "missing_data"
    assert "Forensic Cross-Evidence Limitations" in data["limitations"]


def test_cross_evidence_validation_rejects_single_or_duplicate_ids():
    """Verify validation requires at least 2 distinct evidence items."""
    case_id = create_test_case()
    img = create_jpeg()
    ev = upload_evidence(case_id, "lone_evidence.jpg", img)

    # Less than 2 items in list
    res1 = client.post(
        f"/api/cases/{case_id}/compare-evidence",
        json={"evidence_ids": [ev]},
    )
    assert res1.status_code == 422 or res1.status_code == 400

    # 2 duplicate IDs
    res2 = client.post(
        f"/api/cases/{case_id}/compare-evidence",
        json={"evidence_ids": [ev, ev]},
    )
    assert res2.status_code == 400
    assert "At least 2 distinct" in res2.json()["detail"]


def test_cross_evidence_rejects_foreign_case_evidence():
    """Verify an error is raised if an evidence item belongs to a different case."""
    case_a = create_test_case()
    case_b = create_test_case()

    ev_a = upload_evidence(case_a, "case_a_file.jpg", create_jpeg())
    ev_b = upload_evidence(case_b, "case_b_file.jpg", create_jpeg())

    res = client.post(
        f"/api/cases/{case_a}/compare-evidence",
        json={"evidence_ids": [ev_a, ev_b]},
    )
    assert res.status_code == 400
    assert "do not belong to case" in res.json()["detail"]


def test_cross_evidence_audit_logged():
    """Verify that running cross-evidence comparison logs a chain-of-custody audit event."""
    case_id = create_test_case()
    ev1 = upload_evidence(case_id, "img_a.jpg", create_jpeg())
    ev2 = upload_evidence(case_id, "img_b.jpg", create_jpeg())

    res = client.post(
        f"/api/cases/{case_id}/compare-evidence",
        json={"evidence_ids": [ev1, ev2]},
    )
    assert res.status_code == 200

    # Retrieve case details with audit events
    case_detail = client.get(f"/api/cases/{case_id}").json()
    audit_actions = [a["action"] for a in case_detail["audit_events"]]
    assert "CROSS_EVIDENCE_COMPARISON" in audit_actions
