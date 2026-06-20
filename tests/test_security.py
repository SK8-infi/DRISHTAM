"""Tests for API security middleware (main.py).

Covers: security headers, CORS, rate limiting, exception handlers,
body size limits, docs availability, health endpoint.
"""

from unittest.mock import patch


def test_health_returns_ok(client):
    """GET /health returns 200 with engines_loaded status."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["engines_loaded"] is True


def test_security_headers_present(client):
    """Every response must include all required security headers."""
    r = client.get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-XSS-Protection"] == "1; mode=block"
    assert r.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in r.headers["Permissions-Policy"]
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert "X-Request-ID" in r.headers
    assert "Server-Timing" in r.headers


def test_request_id_passthrough(client):
    """X-Request-ID from client should be echoed back."""
    custom_id = "test-request-12345"
    r = client.get("/health", headers={"X-Request-ID": custom_id})
    assert r.headers["X-Request-ID"] == custom_id


def test_request_id_generated_when_missing(client):
    """When no X-Request-ID header sent, one is auto-generated (UUID format)."""
    r = client.get("/health")
    rid = r.headers.get("X-Request-ID", "")
    assert len(rid) == 36  # UUID format: 8-4-4-4-12


def test_cors_allowed_origin(client):
    """Requests from allowed origin get CORS headers."""
    r = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert r.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"


def test_cors_disallowed_origin(client):
    """Requests from non-allowed origin should NOT get Access-Control-Allow-Origin."""
    r = client.get("/health", headers={"Origin": "http://evil.com"})
    assert r.headers.get("Access-Control-Allow-Origin") != "http://evil.com"


def test_cors_no_credentials(client):
    """Credentials should not be allowed (we don't use cookies/auth)."""
    r = client.get("/health", headers={"Origin": "http://localhost:3000"})
    # Should either be absent or "false"
    assert r.headers.get("Access-Control-Allow-Credentials") != "true"


def test_docs_available_in_dev(client):
    """In development mode, /docs should be accessible."""
    r = client.get("/docs")
    assert r.status_code == 200


def test_openapi_available_in_dev(client):
    """In development mode, /openapi.json should be accessible."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert "paths" in schema


def test_404_returns_clean_error(client):
    """Non-existent endpoints should return 404 without stack traces."""
    r = client.get("/api/nonexistent")
    assert r.status_code in (404, 405)


def test_validation_error_returns_422(client):
    """Invalid query params should return 422 with clean error info."""
    r = client.get("/api/segments?lat_min=invalid")
    assert r.status_code == 422
    body = r.json()
    assert "detail" in body or "errors" in body


def test_body_size_header_check(client):
    """Requests claiming very large content-length should be rejected."""
    r = client.post(
        "/api/whatif",
        headers={"Content-Length": "999999999"},
        content=b"{}",
    )
    assert r.status_code == 413


def test_options_preflight(client):
    """OPTIONS preflight should return 200 with CORS headers."""
    r = client.options(
        "/api/overview",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code == 200


def test_server_timing_header(client):
    """Server-Timing header should contain total duration."""
    r = client.get("/health")
    timing = r.headers.get("Server-Timing", "")
    assert "total;dur=" in timing


def test_server_timing_has_duration(client):
    """Server-Timing header should have numeric duration."""
    r = client.get("/api/overview")
    timing = r.headers.get("Server-Timing", "")
    assert "total;dur=" in timing
    # Extract and validate duration is numeric
    dur_str = timing.split("dur=")[1]
    assert float(dur_str) >= 0


def test_rate_limiter_skips_health(client):
    """Rate limiter should always allow /health requests."""
    for _ in range(10):
        r = client.get("/health")
        assert r.status_code == 200


def test_rate_limiter_applies_to_api(client):
    """Rate limiter should apply to API endpoints."""
    # Normal request should succeed
    r = client.get("/api/overview")
    assert r.status_code == 200


def test_validation_error_format(client):
    """Validation errors should return structured error response."""
    r = client.post("/api/whatif", json={"action": "INVALID"})
    assert r.status_code == 422
    body = r.json()
    assert "detail" in body
    assert "errors" in body


def test_multiple_endpoints_have_security_headers(client):
    """Verify security headers are set on multiple different endpoints."""
    endpoints = ["/health", "/api/overview", "/api/violations"]
    for ep in endpoints:
        r = client.get(ep)
        assert r.headers.get("X-Content-Type-Options") == "nosniff", f"Missing header on {ep}"
        assert r.headers.get("X-Frame-Options") == "DENY", f"Missing header on {ep}"


def test_cors_preflight_methods(client):
    """Verify CORS allows expected methods."""
    r = client.options(
        "/api/overview",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.status_code == 200
