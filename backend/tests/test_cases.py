import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db

client = TestClient(app)


def setup_module():
    """Ensure database tables are initialized before tests run."""
    init_db()


def test_create_case_auto_generated_number():
    """Verify case creation with auto-generated CASE-2026-XXXX identifier."""
    payload = {
        "title": f"Cyber Extortion Incident {uuid.uuid4().hex[:6]}",
        "description": "Reported unauthorized system access and ransom demand.",
        "investigator_name": "Inspector R. Sharma",
        "status": "active",
    }
    response = client.post("/api/cases", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["case_number"].startswith("CASE-")
    assert data["title"] == payload["title"]
    assert data["investigator_name"] == payload["investigator_name"]
    assert data["status"] == "active"
    assert data["evidence_count"] == 0


def test_create_case_custom_valid_number():
    """Verify case creation with a specified valid case number."""
    custom_number = f"CYBER-{uuid.uuid4().hex[:8].upper()}"
    payload = {
        "case_number": custom_number,
        "title": "Mobile Device Forensic Seizure",
        "investigator_name": "SI K. Kumar",
        "status": "active",
    }
    response = client.post("/api/cases", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["case_number"] == custom_number


def test_create_case_duplicate_number_rejected():
    """Verify that attempting to create a duplicate case number returns 409 Conflict."""
    dup_number = f"DUP-{uuid.uuid4().hex[:6].upper()}"
    payload = {
        "case_number": dup_number,
        "title": "Initial Case Registration",
        "investigator_name": "Inspector A. Verma",
    }
    resp1 = client.post("/api/cases", json=payload)
    assert resp1.status_code == 201

    # Attempt second registration with same case_number
    resp2 = client.post("/api/cases", json=payload)
    assert resp2.status_code == 409
    assert "already registered" in resp2.json()["detail"]


def test_create_case_invalid_title():
    """Verify validation error when title is too short."""
    payload = {
        "title": "A",  # Min length is 3
        "investigator_name": "Officer",
    }
    response = client.post("/api/cases", json=payload)
    assert response.status_code == 422


def test_list_and_search_cases():
    """Verify listing cases and searching by keyword."""
    tag = uuid.uuid4().hex[:8]
    client.post("/api/cases", json={
        "title": f"Phishing Campaign Analysis {tag}",
        "investigator_name": "Officer Test",
    })

    # Search for tag
    search_resp = client.get(f"/api/cases?search={tag}")
    assert search_resp.status_code == 200
    results = search_resp.json()
    assert len(results) >= 1
    assert tag in results[0]["title"]


def test_get_case_detail_by_id_and_number():
    """Verify retrieval of full case details by ID and by case number."""
    unique_no = f"FIND-{uuid.uuid4().hex[:6].upper()}"
    create_resp = client.post("/api/cases", json={
        "case_number": unique_no,
        "title": "CCTV Footage Tampering Investigation",
        "description": "Verifying frame continuity across highway camera feeds.",
        "investigator_name": "Cyber Cell Inspector",
    })
    created = create_resp.json()
    case_id = created["id"]

    # Retrieve by numeric ID
    id_resp = client.get(f"/api/cases/{case_id}")
    assert id_resp.status_code == 200
    assert id_resp.json()["case_number"] == unique_no
    assert "audit_events" in id_resp.json()
    assert len(id_resp.json()["audit_events"]) >= 1

    # Retrieve by case number string
    num_resp = client.get(f"/api/cases/{unique_no}")
    assert num_resp.status_code == 200
    assert num_resp.json()["id"] == case_id


def test_get_nonexistent_case_returns_404():
    """Verify that querying a nonexistent case returns 404."""
    response = client.get("/api/cases/NONEXISTENT-999999")
    assert response.status_code == 404


def test_update_case():
    """Verify updating case status and details."""
    create_resp = client.post("/api/cases", json={
        "title": "Case to be Updated",
        "status": "active",
    })
    case_id = create_resp.json()["id"]

    update_resp = client.patch(f"/api/cases/{case_id}", json={
        "title": "Updated Case Title",
        "status": "closed",
    })
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["title"] == "Updated Case Title"
    assert data["status"] == "closed"


def test_case_stats():
    """Verify /api/cases/stats returns integer metrics."""
    response = client.get("/api/cases/stats")
    assert response.status_code == 200
    stats = response.json()
    assert "total_cases" in stats
    assert "active_cases" in stats
    assert "closed_cases" in stats
    assert "archived_cases" in stats
    assert "total_evidence" in stats
    assert stats["total_cases"] >= 1
