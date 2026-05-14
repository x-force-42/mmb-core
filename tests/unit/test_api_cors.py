"""CORS preflight pro cockpit (localhost:5173)."""

import pytest
from fastapi.testclient import TestClient

import config


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "test_api.db"
    monkeypatch.setattr(config, "MMB_DB_PATH", db)
    from api.deps import get_logger
    get_logger.cache_clear()
    from api.app import app
    yield TestClient(app)
    get_logger.cache_clear()


def test_cors_preflight_allows_cockpit_origin(client):
    r = client.options(
        "/api/runs",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_blocks_unknown_origin(client):
    r = client.options(
        "/api/runs",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    # Sem ACAO header pra origem não-permitida (Starlette ainda devolve 200
    # mas sem o header de allow-origin).
    assert r.headers.get("access-control-allow-origin") != "http://evil.example.com"
