import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from obbian_rag.api import create_app
from obbian_rag.config import Settings


def test_authenticated_api_and_limits(settings, pipeline):
    settings.requests_per_minute = 2
    headers = {"Authorization": f"Bearer {settings.api_key.get_secret_value()}"}
    with TestClient(create_app(settings, pipeline)) as client:
        assert client.get("/health/ready").status_code == 200
        assert client.post("/v1/answer", json={"question": "What is the fuel policy?"}).status_code == 401
        assert client.post("/v1/answer", headers=headers, json={"question": "x" * 2001}).status_code == 422
        assert (
            client.post("/v1/answer", headers=headers, json={"question": "fuel", "extra": "bad"}).status_code
            == 422
        )
        assert client.post("/v1/answer", headers=headers, content="x" * 9000).status_code == 413
        response = client.post(
            "/v1/answer", headers=headers, json={"question": "What is the cancellation policy?"}
        )
        assert response.status_code == 200 and response.json()["status"] == "answered"
        assert response.json()["citations"]
        client.post("/v1/answer", headers=headers, json={"question": "Track my booking"})
        limited = client.post("/v1/answer", headers=headers, json={"question": "What is the fuel policy?"})
        assert limited.status_code == 429 and limited.headers["retry-after"] == "60"
        assert client.get("/v1/metrics", headers=headers).json()["counts"]["answered"] == 1


def test_provider_error_is_sanitized(settings, pipeline, monkeypatch):
    def fail(*args):
        raise RuntimeError("secret-key-must-never-leak")

    monkeypatch.setattr(pipeline, "ask", fail)
    with TestClient(create_app(settings, pipeline)) as client:
        response = client.post(
            "/v1/answer",
            headers={"Authorization": f"Bearer {settings.api_key.get_secret_value()}"},
            json={"question": "fuel policy"},
        )
        assert response.status_code == 503 and "secret-key" not in response.text


def test_production_requires_secrets_and_live_provider():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", api_key="a" * 40, provider="offline")
