"""API-level tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

from .conftest import blurred_image, dark_image, encode, sharp_image


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


def test_health_reports_limits_and_fail_closed_policy(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["readiness_policy_validated"] is False
    assert body["limits"]["max_upload_bytes"] == 2_000_000
    assert "image/jpeg" in body["limits"]["supported_formats"]


def _post(client: TestClient, data: bytes, name: str = "sample.png", mime: str = "image/png"):
    return client.post("/api/analyze", files={"image": (name, data, mime)})


def test_analyze_passing_image(client: TestClient) -> None:
    response = _post(client, encode(sharp_image()))
    assert response.status_code == 200
    body = response.json()
    assert body["visual_status"] == "pass"
    assert body["readiness_status"] == "unverified"
    assert body["readiness_reason"] == "Readiness unverified — plant validation required."
    assert body["metrics"]["width"] == 320
    assert body["limitations"]


def test_analyze_dark_image_returns_actionable_reason(client: TestClient) -> None:
    body = _post(client, encode(dark_image())).json()
    assert body["visual_status"] == "fail"
    assert body["visual_reason"] == "Image too dark — improve lighting."


def test_analyze_blurred_image_fails(client: TestClient) -> None:
    body = _post(client, encode(blurred_image())).json()
    assert body["visual_status"] == "fail"
    assert "blurred" in body["visual_reason"].lower()


def test_declared_mime_type_is_not_trusted(client: TestClient) -> None:
    """A text file renamed to .png is rejected on its actual bytes."""

    response = _post(client, b"not an image at all", "fake.png", "image/png")
    assert response.status_code == 400
    assert response.json()["code"] == "unsupported_format"


def test_oversized_upload_rejected_with_413(client: TestClient) -> None:
    payload = b"\x89PNG\r\n\x1a\n" + b"0" * 3_000_000
    response = _post(client, payload)
    assert response.status_code == 413
    assert response.json()["code"] == "file_too_large"


def test_missing_file_is_rejected(client: TestClient) -> None:
    assert client.post("/api/analyze").status_code == 422


def test_cors_allows_configured_origin(client: TestClient) -> None:
    response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_blocks_unknown_origin(client: TestClient) -> None:
    response = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in response.headers
