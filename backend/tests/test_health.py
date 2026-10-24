from fastapi.testclient import TestClient
from sqlalchemy import inspect
from app.main import app
from app.database import engine, init_db


client = TestClient(app)


def test_health_endpoint():
    """Verify that GET /api/health returns 200 and expected diagnostic values."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "EvidenceGuard AI"
    assert data["database_connected"] is True
    assert data["storage_verified"] is True
    assert "storage_base" in data["storage_details"]
    assert "evidence_upload" in data["storage_details"]
    assert "derived_output" in data["storage_details"]
    assert "reports" in data["storage_details"]


def test_security_headers():
    """Verify that security headers are injected into HTTP responses."""
    response = client.get("/api/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert "strict-origin-when-cross-origin" in response.headers.get("Referrer-Policy", "")


def test_database_tables_exist():
    """Verify that the database schema is initialized with all core forensic entities."""
    init_db()
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    expected_tables = {
        "cases",
        "evidence",
        "analysis_results",
        "integrity_checks",
        "audit_events",
        "reports",
    }
    assert expected_tables.issubset(table_names), f"Missing tables: {expected_tables - table_names}"
