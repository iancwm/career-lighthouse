"""Integration tests asserting security headers survive middleware registration order."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from main import app
    return TestClient(app)


REQUIRED_HEADERS = [
    "X-Content-Type-Options",
    "X-Frame-Options",
    "Content-Security-Policy",
]

REPRESENTATIVE_ENDPOINTS = [
    "/health",
    "/api/docs",
]


@pytest.mark.parametrize("header", REQUIRED_HEADERS)
@pytest.mark.parametrize("path", REPRESENTATIVE_ENDPOINTS)
def test_security_header_present(client, header, path):
    response = client.get(path)
    assert header in response.headers, (
        f"Missing security header {header!r} on GET {path}"
    )


def test_x_content_type_options_value(client):
    response = client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_x_frame_options_value(client):
    response = client.get("/health")
    assert response.headers["X-Frame-Options"] == "DENY"


def test_csp_value(client):
    response = client.get("/health")
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
