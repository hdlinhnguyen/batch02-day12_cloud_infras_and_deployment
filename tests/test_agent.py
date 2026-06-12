import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "uptime_seconds" in data
    assert "version" in data

def test_ready_check():
    # Since Redis is not running during local unit test, it will fall back to in-memory mode
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True

def test_ask_endpoint_unauthorized():
    # Request without X-API-Key header should return 401
    response = client.post(
        "/ask",
        json={"user_id": "test-user", "question": "What is the capital of France?"}
    )
    assert response.status_code == 401
    assert "detail" in response.json()

def test_ask_endpoint_forbidden():
    # Request with invalid X-API-Key header should return 403
    response = client.post(
        "/ask",
        headers={"X-API-Key": "invalid-key-1234"},
        json={"user_id": "test-user", "question": "What is the capital of France?"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid API key."

def test_ask_endpoint_success():
    # Request with correct API Key (default is "demo-key-change-in-production")
    response = client.post(
        "/ask",
        headers={"X-API-Key": "demo-key-change-in-production"},
        json={"user_id": "test-user", "question": "What is the capital of France?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["question"] == "What is the capital of France?"
    assert "answer" in data
    assert "served_by" in data
    assert "usage" in data
    assert data["usage"]["rate_limit_remaining"] == 9
    assert data["usage"]["monthly_cost_usd"] > 0
