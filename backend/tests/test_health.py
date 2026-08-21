from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    """Test GET /api/health returns 200 and expected payload."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "gameforge-api"


def test_root_endpoint():
    """Test root endpoint returns 200."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "health" in data
    assert data["health"] == "/api/health"
