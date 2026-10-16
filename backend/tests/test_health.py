def test_health_reports_version_and_timezone(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["timezone"] == "Asia/Kolkata"
    assert body["environment"] == "test"
    assert body["version"]


def test_database_health_is_ok_when_database_reachable(client):
    response = client.get("/api/v1/health/database")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_database_health_never_leaks_connection_string(client, monkeypatch):
    from app.api.v1 import health

    monkeypatch.setattr(health, "check_database", lambda: False)
    response = client.get("/api/v1/health/database")
    assert response.status_code == 200
    body = response.text
    assert "unreachable" in body
    assert "postgresql" not in body and "password" not in body.lower()


def test_cors_allows_configured_origin_only(client):
    allowed = client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    denied = client.options(
        "/api/v1/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in denied.headers


def test_oversized_request_is_rejected(client):
    response = client.post("/api/v1/health", headers={"content-length": str(50 * 1024 * 1024)})
    assert response.status_code == 413


def test_api_docs_available_outside_production(client):
    assert client.get("/api/docs").status_code == 200
    assert client.get("/api/openapi.json").status_code == 200


def test_api_docs_hidden_in_production(monkeypatch):
    from fastapi.testclient import TestClient

    from app.core import config
    from app.main import create_app

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "k" * 40)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    config.get_settings.cache_clear()
    try:
        with TestClient(create_app()) as production_client:
            assert production_client.get("/api/docs").status_code == 404
            assert production_client.get("/api/openapi.json").status_code == 404
            assert production_client.get("/api/v1/health").status_code == 200
    finally:
        config.get_settings.cache_clear()
