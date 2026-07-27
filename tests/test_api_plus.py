from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_plus_success():
    resp = client.post("/api/plus", json={"a": 2.5, "b": 1.5})
    assert resp.status_code == 200
    data = resp.json()
    assert "result" in data
    assert abs(data["result"] - 4.0) < 1e-9


def test_plus_missing_field():
    resp = client.post("/api/plus", json={"a": 1.0})
    assert resp.status_code == 422


def test_plus_invalid_type():
    resp = client.post("/api/plus", json={"a": "x", "b": 2})
    assert resp.status_code == 422
