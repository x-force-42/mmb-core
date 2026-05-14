"""Testes da rota /api/runs (lista, detalhe, PATCH)."""

import pytest
from fastapi.testclient import TestClient

import config
from logger import GaragemEntry, MeeseeksEntry, RunLogger


@pytest.fixture
def api(tmp_path, monkeypatch):
    """Banco temporário + cliente. Limpa cache do logger singleton."""
    db = tmp_path / "test_api.db"
    monkeypatch.setattr(config, "MMB_DB_PATH", db)
    from api.deps import get_logger
    get_logger.cache_clear()

    log = RunLogger(db)
    from api.app import app
    client = TestClient(app)
    yield client, log
    get_logger.cache_clear()


def _seed_run(log, *, slug="jogo", task="fix bug", phase="success", elapsed=42.0,
              garagem_cost=0.02, meeseeks_cost=0.08):
    pid = log.ensure_project(slug=slug, name=slug, path=f"/tmp/{slug}")
    rid = log.start_run(project_id=pid, task_raw=task)
    log.record_garagem(rid, GaragemEntry(model="m", elapsed_s=1.0,
                                          outcome="success", cost_usd=garagem_cost,
                                          briefing_json='{"escopo_claro": true}'))
    log.record_meeseeks(rid, MeeseeksEntry(model="m", elapsed_s=10.0,
                                            outcome="success", cost_usd=meeseeks_cost,
                                            commits=["abc123"]))
    log.finish_run(rid, terminal_phase=phase, total_elapsed_s=elapsed)
    return pid, rid


class TestListRuns:
    def test_empty_returns_valid_structure(self, api):
        client, _ = api
        r = client.get("/api/runs")
        assert r.status_code == 200
        body = r.json()
        assert body == {"items": [], "total": 0, "limit": 50, "offset": 0}

    def test_lists_seeded_runs(self, api):
        client, log = api
        _seed_run(log)
        r = client.get("/api/runs")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["project_slug"] == "jogo"
        assert body["items"][0]["terminal_phase"] == "success"

    def test_filter_by_phase(self, api):
        client, log = api
        _seed_run(log, task="ok", phase="success")
        _seed_run(log, task="pushback", phase="garagem_pushback")
        r = client.get("/api/runs", params={"phase": "garagem_pushback"})
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["terminal_phase"] == "garagem_pushback"

    def test_filter_by_project(self, api):
        client, log = api
        _seed_run(log, slug="alpha", task="a")
        _seed_run(log, slug="beta", task="b")
        r = client.get("/api/runs", params={"project": "alpha"})
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["project_slug"] == "alpha"

    def test_pagination(self, api):
        client, log = api
        for i in range(3):
            _seed_run(log, task=f"task {i}")
        r = client.get("/api/runs", params={"limit": 2, "offset": 1})
        body = r.json()
        assert body["total"] == 3
        assert len(body["items"]) == 2
        assert body["limit"] == 2 and body["offset"] == 1

    def test_invalid_phase_returns_422(self, api):
        client, _ = api
        r = client.get("/api/runs", params={"phase": "nonsense"})
        assert r.status_code == 422

    def test_limit_above_200_returns_422(self, api):
        client, _ = api
        r = client.get("/api/runs", params={"limit": 201})
        assert r.status_code == 422


class TestGetRun:
    def test_returns_detail_with_parsed_briefing(self, api):
        client, log = api
        _, rid = _seed_run(log)
        r = client.get(f"/api/runs/{rid}")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == rid
        assert body["project_slug"] == "jogo"
        assert body["garagem_briefing_json"] == {"escopo_claro": True}
        assert body["meeseeks_commits_json"] == ["abc123"]

    def test_404_for_unknown_id(self, api):
        client, _ = api
        r = client.get("/api/runs/nonexistent")
        assert r.status_code == 404
        assert r.json() == {"detail": "run não encontrado"}


class TestPatchRun:
    def test_persists_three_fields(self, api):
        client, log = api
        _, rid = _seed_run(log)
        r = client.patch(f"/api/runs/{rid}", json={
            "merged_to_main": 1,
            "assertiveness_score": 4,
            "review_note": "ficou bom",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["merged_to_main"] == 1
        assert body["assertiveness_score"] == 4
        assert body["review_note"] == "ficou bom"

    def test_ignores_extra_fields(self, api):
        client, log = api
        _, rid = _seed_run(log)
        r = client.patch(f"/api/runs/{rid}", json={
            "merged_to_main": 0,
            "assertiveness_score": 3,
            "review_note": "ok",
            "task_raw": "TENTATIVA DE EDITAR",  # deve ser ignorado
        })
        assert r.status_code == 200
        body = r.json()
        assert body["task_raw"] == "fix bug"  # original preservado

    def test_422_for_invalid_assertiveness(self, api):
        client, log = api
        _, rid = _seed_run(log)
        r = client.patch(f"/api/runs/{rid}", json={"assertiveness_score": 6})
        assert r.status_code == 422

    def test_422_for_invalid_merged_to_main(self, api):
        client, log = api
        _, rid = _seed_run(log)
        r = client.patch(f"/api/runs/{rid}", json={"merged_to_main": 7})
        assert r.status_code == 422

    def test_404_for_unknown_id(self, api):
        client, _ = api
        r = client.patch("/api/runs/nonexistent", json={"merged_to_main": 1})
        assert r.status_code == 404
