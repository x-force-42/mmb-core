"""Testes da rota /api/projects."""

import pytest
from fastapi.testclient import TestClient

import config
from logger import RunLogger


@pytest.fixture
def api(tmp_path, monkeypatch):
    db = tmp_path / "test_api.db"
    monkeypatch.setattr(config, "MMB_DB_PATH", db)
    from api.deps import get_logger
    get_logger.cache_clear()

    log = RunLogger(db)
    from api.app import app
    yield TestClient(app), log
    get_logger.cache_clear()


class TestListProjects:
    def test_empty(self, api):
        client, _ = api
        r = client.get("/api/projects")
        assert r.status_code == 200
        assert r.json() == {"items": []}

    def test_returns_sorted_by_slug(self, api):
        client, log = api
        log.ensure_project(slug="zeta", name="Z", path="/z")
        log.ensure_project(slug="alpha", name="A", path="/a", repo_url="https://x/a")
        r = client.get("/api/projects")
        assert r.status_code == 200
        items = r.json()["items"]
        assert [p["slug"] for p in items] == ["alpha", "zeta"]
        assert items[0]["repo_url"] == "https://x/a"
        assert items[1]["repo_url"] is None

    def test_expose_active_and_mode(self, api):
        client, log = api
        log.ensure_project(slug="x", name="X", path="/x")
        r = client.get("/api/projects")
        items = r.json()["items"]
        # ensure_project usa o default do schema → active=1, mode='pontual'
        assert items[0]["active"] == 1
        assert items[0]["mode"] == "pontual"

    def test_oculta_projetos_inativos(self, api, tmp_path):
        client, log = api
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        log.register_project(slug="vivo", path=str(repo))
        log.register_project(slug="morto", path=str(repo))
        log.deactivate_project("morto")
        items = client.get("/api/projects").json()["items"]
        slugs = [p["slug"] for p in items]
        assert "vivo" in slugs
        assert "morto" not in slugs
