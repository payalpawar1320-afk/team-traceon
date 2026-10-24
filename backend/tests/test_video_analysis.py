import io
import os
import tempfile
import uuid
from pathlib import Path
import cv2
import numpy as np
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
    """Helper to register a case."""
    res = client.post(
        "/api/cases",
        json={
            "title": f"CCTV Forensic Investigation {uuid.uuid4().hex[:6]}",
            "investigator_name": "Traffic Inspector",
        },
    )
    assert res.status_code == 201
    return res.json()["id"]


def generate_synthetic_mp4(
    num_frames: int = 15,
    fps: int = 10,
    with_freeze: bool = False,
) -> bytes:
    """
    Generate an in-memory synthetic MP4 video using OpenCV.
    If with_freeze is True, frames 5..10 are identical (frozen CCTV).
    """
    temp_dir = tempfile.mkdtemp()
    temp_file = Path(temp_dir) / f"synth_{uuid.uuid4().hex}.mp4"

    # Use 'mp4v' fourcc
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(temp_file), fourcc, fps, (160, 120))

    frozen_frame = None

    for i in range(num_frames):
        if with_freeze and 5 <= i <= 9:
            if frozen_frame is None:
                frozen_frame = np.full((120, 160, 3), 128, dtype=np.uint8)
                cv2.putText(frozen_frame, "FREEZE", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            out.write(frozen_frame)
        else:
            frame = np.full((120, 160, 3), (i * 15) % 255, dtype=np.uint8)
            cv2.circle(frame, (20 + i * 8, 60), 15, (0, 255, 0), -1)
            cv2.putText(frame, f"F:{i}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            out.write(frame)

    out.release()

    with open(temp_file, "rb") as f:
        data = f.read()

    # Clean up temp files
    try:
        temp_file.unlink()
        os.rmdir(temp_dir)
    except Exception:
        pass

    return data


def test_analyze_video_continuous():
    """Verify video properties, frame extraction, and continuous sequence on normal video."""
    case_id = create_test_case()
    video_bytes = generate_synthetic_mp4(num_frames=12, fps=10, with_freeze=False)

    upload_res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("highway_cam_feed.mp4", io.BytesIO(video_bytes), "video/mp4")},
    )
    assert upload_res.status_code == 201
    ev_id = upload_res.json()["id"]

    analyze_res = client.post(f"/api/evidence/{ev_id}/analyze/video?target_sample_frames=8")
    assert analyze_res.status_code == 200
    data = analyze_res.json()

    assert data["evidence_id"] == ev_id
    assert data["analysis_type"] == "video_forensics"

    v_report = data["video_report"]
    assert v_report["status"] == "completed"
    assert v_report["width"] == 160
    assert v_report["height"] == 120
    assert v_report["fps"] == 10.0
    assert v_report["total_frames"] == 12
    assert v_report["sampled_frames_count"] > 0

    # Verify thumbnails are accessible
    first_frame = v_report["sampled_frames"][0]
    thumb_res = client.get(first_frame["thumbnail_url"])
    assert thumb_res.status_code == 200
    assert "image/jpeg" in thumb_res.headers.get("content-type", "")


def test_detect_frozen_cctv_frames():
    """Verify detection of repeated / frozen frames in CCTV footage."""
    case_id = create_test_case()
    frozen_video = generate_synthetic_mp4(num_frames=15, fps=10, with_freeze=True)

    upload_res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("frozen_atm_feed.mp4", io.BytesIO(frozen_video), "video/mp4")},
    )
    assert upload_res.status_code == 201
    ev_id = upload_res.json()["id"]

    analyze_res = client.post(f"/api/evidence/{ev_id}/analyze/video?target_sample_frames=15")
    assert analyze_res.status_code == 200
    data = analyze_res.json()

    v_report = data["video_report"]
    assert v_report["duplicate_frames_count"] >= 3
    assert v_report["is_frozen_detected"] is True
    assert "Review recommended" in data["status"]

    frozen_findings = [f for f in v_report["findings"] if "Frozen" in f["title"] or "Duplicate" in f["title"]]
    assert len(frozen_findings) >= 1


def test_reject_video_analysis_on_image():
    """Verify that requesting video analysis on an image file returns 400 Bad Request."""
    case_id = create_test_case()
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
        b"\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    upload_res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("photo.png", io.BytesIO(png_bytes), "image/png")},
    )
    assert upload_res.status_code == 201
    ev_id = upload_res.json()["id"]

    analyze_res = client.post(f"/api/evidence/{ev_id}/analyze/video")
    assert analyze_res.status_code == 400
    assert "not a video" in analyze_res.json()["detail"]
