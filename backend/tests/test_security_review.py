import io
import uuid
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
            "title": f"Security Review Case {uuid.uuid4().hex[:6]}",
            "investigator_name": "Security Auditor",
        },
    )
    assert res.status_code == 201
    return res.json()["id"]


def test_security_headers_present_on_all_responses():
    """Verify that mandatory security headers are attached to API responses (spec.md §6)."""
    res = client.get("/api/health")
    assert res.status_code == 200
    headers = res.headers
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("x-xss-protection") == "1; mode=block"
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert "camera=()" in headers.get("permissions-policy", "")


def test_reject_dangerous_executable_upload():
    """Verify that executable, script, or system files are strictly rejected."""
    case_id = create_test_case()
    dangerous_payload = b"MZ\x90\x00\x03\x00\x00\x00"  # PE header

    for bad_name in ["payload.exe", "backdoor.sh", "script.py", "cmd.bat", "exploit.php"]:
        res = client.post(
            f"/api/cases/{case_id}/evidence",
            files={"file": (bad_name, dangerous_payload, "application/octet-stream")},
        )
        assert res.status_code == 400
        assert "Unsupported file format" in res.json()["detail"]


def test_reject_disguised_file_signature_spoofing():
    """Verify that renaming a text or binary file to .jpg/.png without valid magic bytes is rejected."""
    case_id = create_test_case()
    fake_data = b"This is plain text disguised as an image."

    res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("fake_image.jpg", fake_data, "image/jpeg")},
    )
    assert res.status_code == 400
    assert "magic bytes" in res.json()["detail"].lower()


def test_reject_empty_file_ingestion():
    """Verify that 0-byte empty files cannot be ingested into the repository."""
    case_id = create_test_case()
    res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("zero.png", b"", "image/png")},
    )
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()


def test_path_traversal_derived_assets():
    """Verify that path traversal in derived forensic assets is safely sanitized."""
    # Attempt directory traversal attacks
    traversal_payloads = [
        "../../../../windows/win.ini",
        "..%2F..%2F..%2Fetc%2Fpasswd",
        "..\\..\\..\\boot.ini",
        "....//....//config.py",
    ]
    for payload in traversal_payloads:
        res = client.get(f"/api/analysis/derived/{payload}")
        # Must return 404 Not Found, never 200 or 500 leaking files
        assert res.status_code == 404


def test_path_traversal_filename_sanitization_on_upload():
    """Verify that uploading a file with traversal characters in the filename is safely sanitized."""
    case_id = create_test_case()
    png_magic = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

    res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("../../../../etc/passwd.png", png_magic, "image/png")},
    )
    assert res.status_code == 201
    item = res.json()
    # Stored filename must not contain slashes
    assert "/" not in item["original_filename"]
    assert "\\" not in item["original_filename"]
    assert "passwd.png" in item["original_filename"]


def test_public_static_storage_not_accessible():
    """Verify that internal evidence storage directories are not mounted publicly (spec.md §6)."""
    # Attempting to fetch directly from /storage or /storage/evidence must return 404
    res = client.get("/storage/evidence/")
    assert res.status_code == 404

    res2 = client.get("/storage/reports/")
    assert res2.status_code == 404


def test_sanitized_error_handling_no_stack_traces_leaked():
    """Verify that unhandled errors and not-founds do not leak Python stack traces or filesystem paths."""
    res = client.get("/api/cases/invalid-case-id")
    assert res.status_code in [404, 422]  # Clean JSON error
    data = res.json()
    assert "Traceback" not in str(data)
    assert 'File "' not in str(data)
