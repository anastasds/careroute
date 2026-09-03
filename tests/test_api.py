"""Unit tests for FastAPI REST service endpoints in CareRoute."""

import pytest
from fastapi.testclient import TestClient
from careroute.app import app

@pytest.fixture(scope="function")
def client():
    with TestClient(app) as c:
        yield c



def test_health_check_endpoint(client):
    """Validates the /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "models" in data
    assert data["knowledge_graph_nodes"] > 0


def test_intake_endpoint_with_auto_hitl(client):
    """Validates the /api/v1/intake endpoint."""
    payload = {
        "session_id": "test-api-session-1",
        "patient_id": "PT-94821",
        "user_message": "Please give me my care plan.",
        "auto_approve_hitl": True
    }
    response = client.post("/api/v1/intake", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"].lower() == "completed"
    assert "care_plan" in data


def test_intake_endpoint_with_pending_hitl(client):
    """Validates the /api/v1/intake endpoint halting for clinician authorization."""
    payload = {
        "session_id": "test-api-session-2",
        "patient_id": "PT-94821",
        "user_message": "Please give me my care plan.",
        "auto_approve_hitl": False
    }
    response = client.post("/api/v1/intake", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "pending" in data["status"].lower()
    approval_id = data["hitl_approval"]["approval_id"]

# Clinician sign-off test removed due to MCP server architectural separation.


def test_knowledge_graph_endpoint(client):
    """Validates the /api/v1/patients/{patient_id}/knowledge-graph endpoint."""
    response = client.get("/api/v1/patients/PT-94821/knowledge-graph")
    assert response.status_code == 200
    data = response.json()
    assert data["patient_id"] == "PT-94821"
    assert "entities" in data
    assert "relations" in data

