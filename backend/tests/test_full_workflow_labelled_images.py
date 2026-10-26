import io
import json
import numpy as np
import pypdf
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def generate_labelled_real_image() -> bytes:
    """
    Generate an image simulating a real optical camera scene:
    Smooth photographic gradient, low-frequency natural transitions.
    """
    img = Image.new("RGB", (256, 256), color=(135, 206, 235))
    draw = ImageDraw.Draw(img)
    # Natural landscape horizon
    draw.rectangle([0, 160, 256, 256], fill=(34, 139, 34))
    draw.ellipse([40, 40, 90, 90], fill=(255, 223, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def generate_labelled_ai_synthetic_image() -> bytes:
    """
    Generate an image with synthetic high-frequency spectral patterns and checkerboard artifacts
    characteristic of deconvolution grids / synthetic generation.
    """
    arr = np.zeros((256, 256, 3), dtype=np.uint8)
    for y in range(256):
        for x in range(256):
            # High-frequency alternating pattern
            val = int(127 + 120 * np.sin(x * 0.8) * np.cos(y * 0.8))
            arr[y, x] = [val, (val * 2) % 255, (255 - val)]
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def test_full_workflow_labelled_real_and_ai_images():
    """
    Requirement 7:
    Upload a labelled real image and a labelled AI-generated image,
    execute analysis, inspect dashboard results, download both PDFs,
    and verify that the recorded predictions match the actual backend outputs.
    """
    # 1. Create Investigation Case
    case_res = client.post(
        "/api/cases",
        json={
            "title": "Full Workflow Dual Image Verification",
            "investigator_name": "Senior Examiner Miller",
            "status": "active",
            "description": "Validation of real and AI-generated image assessment pipeline.",
        },
    )
    assert case_res.status_code == 201
    case_data = case_res.json()
    case_id = case_data["id"]

    real_bytes = generate_labelled_real_image()
    ai_bytes = generate_labelled_ai_synthetic_image()

    # 2. Upload labelled real image
    up_real_res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("labelled_real_image.jpg", real_bytes, "image/jpeg")},
    )
    assert up_real_res.status_code == 201
    ev_real = up_real_res.json()
    real_id = ev_real["id"]
    assert ev_real["is_duplicate"] is False

    # 3. Upload labelled AI-generated image
    up_ai_res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("labelled_ai_generated_image.jpg", ai_bytes, "image/jpeg")},
    )
    assert up_ai_res.status_code == 201
    ev_ai = up_ai_res.json()
    ai_id = ev_ai["id"]
    assert ev_ai["is_duplicate"] is False

    # 4. Execute image forensic analysis on real image
    an_real_res = client.post(f"/api/evidence/{real_id}/analyze/image")
    assert an_real_res.status_code == 200
    real_analysis = an_real_res.json()
    assert real_analysis["ai_detection_report"] is not None
    real_ai_report = real_analysis["ai_detection_report"]
    assert real_ai_report["status"] == "completed"
    real_prediction = real_ai_report["prediction"]
    real_prob_real = real_ai_report["probability_real_pct"]
    real_prob_ai = real_ai_report["probability_ai_pct"]

    # 5. Execute image forensic analysis on AI synthetic image
    an_ai_res = client.post(f"/api/evidence/{ai_id}/analyze/image")
    assert an_ai_res.status_code == 200
    ai_analysis = an_ai_res.json()
    assert ai_analysis["ai_detection_report"] is not None
    synth_ai_report = ai_analysis["ai_detection_report"]
    assert synth_ai_report["status"] == "completed"
    ai_prediction = synth_ai_report["prediction"]
    ai_prob_real = synth_ai_report["probability_real_pct"]
    ai_prob_ai = synth_ai_report["probability_ai_pct"]

    # 6. Verify GET /api/evidence/{id}/analysis preserves AI reports
    hist_real = client.get(f"/api/evidence/{real_id}/analysis").json()
    assert len(hist_real) >= 1
    assert hist_real[0]["ai_detection_report"]["prediction"] == real_prediction

    hist_ai = client.get(f"/api/evidence/{ai_id}/analysis").json()
    assert len(hist_ai) >= 1
    assert hist_ai[0]["ai_detection_report"]["prediction"] == ai_prediction

    # 7. Inspect dashboard case details
    case_detail_res = client.get(f"/api/cases/{case_id}")
    assert case_detail_res.status_code == 200
    case_detail = case_detail_res.json()
    assert len(case_detail["evidence_items"]) == 2

    # 8. Generate and download PDF for Real Image
    rep_real_res = client.post(
        f"/api/cases/{case_id}/reports",
        json={"evidence_ids": [real_id], "include_audit_trail": True},
    )
    assert rep_real_res.status_code == 201
    report_real_id = rep_real_res.json()["id"]

    dl_real = client.get(f"/api/reports/{report_real_id}/download")
    assert dl_real.status_code == 200
    pdf_real_reader = pypdf.PdfReader(io.BytesIO(dl_real.content))
    pdf_real_text = "\n".join(p.extract_text() for p in pdf_real_reader.pages)
    pdf_real_norm = " ".join(pdf_real_text.split())

    # Verify real image PDF matches backend outputs exactly
    assert ev_real["evidence_number"] in pdf_real_text
    assert real_prediction in pdf_real_text
    assert f"{real_prob_real}%" in pdf_real_text or f"{real_prob_ai}%" in pdf_real_text
    assert "CIFAKE-EfficientNet-B0 (ONNX)" in pdf_real_text

    # 9. Generate and download PDF for AI Image
    rep_ai_res = client.post(
        f"/api/cases/{case_id}/reports",
        json={"evidence_ids": [ai_id], "include_audit_trail": True},
    )
    assert rep_ai_res.status_code == 201
    report_ai_id = rep_ai_res.json()["id"]

    dl_ai = client.get(f"/api/reports/{report_ai_id}/download")
    assert dl_ai.status_code == 200
    pdf_ai_reader = pypdf.PdfReader(io.BytesIO(dl_ai.content))
    pdf_ai_text = "\n".join(p.extract_text() for p in pdf_ai_reader.pages)
    pdf_ai_norm = " ".join(pdf_ai_text.split())

    # Verify AI image PDF matches backend outputs exactly
    assert ev_ai["evidence_number"] in pdf_ai_text
    assert ai_prediction in pdf_ai_text
    assert f"{ai_prob_real}%" in pdf_ai_text or f"{ai_prob_ai}%" in pdf_ai_text
    assert "CIFAKE-EfficientNet-B0 (ONNX)" in pdf_ai_text

    # 10. Verify audit IPs are redacted in both demonstration reports
    assert "[REDACTED: DEMO AUDIT]" in pdf_real_norm or "[SYNTHETIC-AUDIT-IP]" in pdf_real_norm
    assert "[REDACTED: DEMO AUDIT]" in pdf_ai_norm or "[SYNTHETIC-AUDIT-IP]" in pdf_ai_norm
    assert "127.0.0.1" not in pdf_real_text
    assert "127.0.0.1" not in pdf_ai_text
