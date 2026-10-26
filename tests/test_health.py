from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_liveness() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_queries_postgresql() -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ready"}
