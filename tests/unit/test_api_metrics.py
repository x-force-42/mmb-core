"""Testes da rota /api/metrics/overview."""

import pytest
from fastapi.testclient import TestClient

import config
from logger import GaragemEntry, MeeseeksEntry, RunLogger


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


class TestOverview:
    def test_empty_payload_shape(self, api):
        client, _ = api
        r = client.get("/api/metrics/overview")
        assert r.status_code == 200
        body = r.json()
        assert body["window_days"] == 30
        assert body["runs_total"] == 0
        assert body["custo_total_usd"] == 0.0
        assert body["taxa_pushback"] == 0.0
        assert body["custo_por_dia"] == []
        assert body["runs_por_dia"] == []
        assert body["phase_breakdown"] == {}

    def test_aggregates_costs_and_phases(self, api):
        client, log = api
        pid = log.ensure_project(slug="jogo", name="jogo", path="/tmp")
        r1 = log.start_run(project_id=pid, task_raw="ok")
        r2 = log.start_run(project_id=pid, task_raw="pushback")
        log.record_garagem(r1, GaragemEntry(model="m", elapsed_s=1, outcome="success", cost_usd=0.05))
        log.record_meeseeks(r1, MeeseeksEntry(model="m", elapsed_s=10, outcome="success", cost_usd=0.10))
        log.finish_run(r1, terminal_phase="success", total_elapsed_s=11.0)
        log.record_garagem(r2, GaragemEntry(model="m", elapsed_s=1, outcome="pushback", cost_usd=0.02))
        log.finish_run(r2, terminal_phase="garagem_pushback", total_elapsed_s=2.0)

        r = client.get("/api/metrics/overview", params={"days": 7})
        body = r.json()
        assert body["window_days"] == 7
        assert body["runs_total"] == 2
        assert body["custo_total_usd"] == pytest.approx(0.17, abs=1e-6)
        assert body["taxa_pushback"] == 0.5
        assert body["phase_breakdown"] == {"success": 1, "garagem_pushback": 1}

    def test_invalid_days_returns_422(self, api):
        client, _ = api
        r = client.get("/api/metrics/overview", params={"days": 0})
        assert r.status_code == 422
        r = client.get("/api/metrics/overview", params={"days": 9999})
        assert r.status_code == 422
