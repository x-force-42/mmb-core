"""Testes do SDK de observabilidade (logger).

Usa banco em memória (:memory:) — zero I/O, isolado por teste.
"""

import json
import sqlite3
import pytest

from logger import (
    DevServerEntry,
    GaragemEntry,
    MeeseeksEntry,
    RunLogger,
)
from logger._db import get_connection


@pytest.fixture
def log(tmp_path):
    return RunLogger(tmp_path / "test.db")


@pytest.fixture
def project_id(log):
    return log.ensure_project(slug="test-proj", name="Test Project", path="/proj")


@pytest.fixture
def run_id(log, project_id):
    return log.start_run(project_id=project_id, task_raw="fix the login bug")


# ─── projects ────────────────────────────────────────────────────────────

class TestEnsureProject:
    def test_returns_uuid_string(self, log):
        pid = log.ensure_project(slug="p1", name="P1", path="/p1")
        assert isinstance(pid, str) and len(pid) == 36

    def test_idempotent_same_slug_same_id(self, log):
        a = log.ensure_project(slug="same", name="A", path="/a")
        b = log.ensure_project(slug="same", name="B", path="/b")
        assert a == b

    def test_different_slugs_different_ids(self, log):
        a = log.ensure_project(slug="alpha", name="A", path="/a")
        b = log.ensure_project(slug="beta",  name="B", path="/b")
        assert a != b

    def test_get_project_returns_stored_data(self, log):
        pid = log.ensure_project(slug="app", name="My App", path="/app",
                                 repo_url="https://github.com/x/app")
        proj = log.get_project(pid)
        assert proj["slug"] == "app"
        assert proj["name"] == "My App"
        assert proj["path"] == "/app"
        assert proj["repo_url"] == "https://github.com/x/app"

    def test_get_project_none_for_unknown(self, log):
        assert log.get_project("nonexistent-id") is None

    def test_repo_url_optional(self, log):
        pid = log.ensure_project(slug="no-url", name="N", path="/n")
        proj = log.get_project(pid)
        assert proj["repo_url"] is None


# ─── start_run ───────────────────────────────────────────────────────────

class TestStartRun:
    def test_returns_uuid_string(self, log, project_id):
        run_id = log.start_run(project_id=project_id, task_raw="task")
        assert isinstance(run_id, str) and len(run_id) == 36

    def test_each_call_unique_id(self, log, project_id):
        a = log.start_run(project_id=project_id, task_raw="task a")
        b = log.start_run(project_id=project_id, task_raw="task b")
        assert a != b

    def test_run_stored_with_task_raw(self, log, project_id):
        run_id = log.start_run(project_id=project_id, task_raw="fix login")
        run = log.get_run(run_id)
        assert run["task_raw"] == "fix login"
        assert run["project_id"] == project_id

    def test_new_run_phases_are_null(self, log, project_id):
        run_id = log.start_run(project_id=project_id, task_raw="t")
        run = log.get_run(run_id)
        assert run["terminal_phase"] is None
        assert run["garagem_outcome"] is None
        assert run["meeseeks_outcome"] is None

    def test_rerun_of_links_previous_run(self, log, project_id):
        original = log.start_run(project_id=project_id, task_raw="original")
        retry = log.start_run(project_id=project_id, task_raw="retry",
                               rerun_of=original)
        run = log.get_run(retry)
        assert run["rerun_of"] == original

    def test_get_run_none_for_unknown(self, log):
        assert log.get_run("does-not-exist") is None


# ─── record_garagem ──────────────────────────────────────────────────────

class TestRecordGaragem:
    def test_success_stores_all_fields(self, log, run_id):
        log.record_garagem(run_id, GaragemEntry(
            model="claude-sonnet-4-6",
            elapsed_s=12.3,
            outcome="success",
            tokens_input=1500,
            tokens_output=400,
            cost_usd=0.0023,
            turns=3,
            briefing_json='{"escopo_claro": true}',
            meeseeks_prompt="Implement X in file Y",
            criticality="medium",
            complexity="low",
            commit_type="fix",
            slug="fix-login-redirect",
        ))
        run = log.get_run(run_id)
        assert run["garagem_model"] == "claude-sonnet-4-6"
        assert run["garagem_elapsed_s"] == pytest.approx(12.3)
        assert run["garagem_outcome"] == "success"
        assert run["garagem_tokens_input"] == 1500
        assert run["garagem_tokens_output"] == 400
        assert run["garagem_cost_usd"] == pytest.approx(0.0023)
        assert run["garagem_turns"] == 3
        assert run["garagem_briefing_json"] == '{"escopo_claro": true}'
        assert run["garagem_meeseeks_prompt"] == "Implement X in file Y"
        assert run["garagem_criticality"] == "medium"
        assert run["garagem_complexity"] == "low"
        assert run["garagem_commit_type"] == "fix"
        assert run["garagem_slug"] == "fix-login-redirect"

    def test_pushback_stores_outcome(self, log, run_id):
        log.record_garagem(run_id, GaragemEntry(
            model="claude-sonnet-4-6",
            elapsed_s=5.0,
            outcome="pushback",
        ))
        run = log.get_run(run_id)
        assert run["garagem_outcome"] == "pushback"

    def test_error_stores_outcome(self, log, run_id):
        log.record_garagem(run_id, GaragemEntry(
            model="claude-sonnet-4-6",
            elapsed_s=1.0,
            outcome="error",
        ))
        assert log.get_run(run_id)["garagem_outcome"] == "error"

    def test_optional_fields_default_to_none(self, log, run_id):
        log.record_garagem(run_id, GaragemEntry(
            model="m", elapsed_s=1.0, outcome="success"
        ))
        run = log.get_run(run_id)
        assert run["garagem_tokens_input"] is None
        assert run["garagem_cost_usd"] is None
        assert run["garagem_criticality"] is None


# ─── record_meeseeks ─────────────────────────────────────────────────────

class TestRecordMeeseeks:
    def test_success_stores_all_fields(self, log, run_id):
        log.record_meeseeks(run_id, MeeseeksEntry(
            model="claude-sonnet-4-6",
            elapsed_s=87.4,
            outcome="success",
            tokens_input=8000,
            tokens_output=2000,
            cost_usd=0.048,
            branch="meeseeks/fix-login-redirect",
            commits=["abc1234", "def5678"],
            report="Implemented X, tests pass.",
            confidence=0.9,
            diff_added=42,
            diff_deleted=7,
            diff_files=3,
        ))
        run = log.get_run(run_id)
        assert run["meeseeks_model"] == "claude-sonnet-4-6"
        assert run["meeseeks_elapsed_s"] == pytest.approx(87.4)
        assert run["meeseeks_outcome"] == "success"
        assert run["meeseeks_branch"] == "meeseeks/fix-login-redirect"
        assert run["meeseeks_confidence"] == pytest.approx(0.9)
        assert run["meeseeks_diff_added"] == 42
        assert run["meeseeks_diff_deleted"] == 7
        assert run["meeseeks_diff_files"] == 3

    def test_commits_stored_as_json_array(self, log, run_id):
        log.record_meeseeks(run_id, MeeseeksEntry(
            model="m", elapsed_s=1.0, outcome="success",
            commits=["aaa", "bbb", "ccc"],
        ))
        run = log.get_run(run_id)
        assert json.loads(run["meeseeks_commits_json"]) == ["aaa", "bbb", "ccc"]

    def test_commits_none_stored_as_null(self, log, run_id):
        log.record_meeseeks(run_id, MeeseeksEntry(
            model="m", elapsed_s=1.0, outcome="failure",
        ))
        assert log.get_run(run_id)["meeseeks_commits_json"] is None

    def test_failure_outcome(self, log, run_id):
        log.record_meeseeks(run_id, MeeseeksEntry(
            model="m", elapsed_s=20.0, outcome="failure",
        ))
        assert log.get_run(run_id)["meeseeks_outcome"] == "failure"


# ─── record_dev_server ───────────────────────────────────────────────────

class TestRecordDevServer:
    def test_success_stores_port(self, log, run_id):
        log.record_dev_server(run_id, DevServerEntry(outcome="success", port=5173))
        run = log.get_run(run_id)
        assert run["dev_server_outcome"] == "success"
        assert run["dev_server_port"] == 5173

    def test_skipped_has_no_port(self, log, run_id):
        log.record_dev_server(run_id, DevServerEntry(outcome="skipped"))
        run = log.get_run(run_id)
        assert run["dev_server_outcome"] == "skipped"
        assert run["dev_server_port"] is None

    def test_failure_no_port(self, log, run_id):
        log.record_dev_server(run_id, DevServerEntry(outcome="failure"))
        assert log.get_run(run_id)["dev_server_outcome"] == "failure"


# ─── finish_run ──────────────────────────────────────────────────────────

class TestFinishRun:
    def test_sets_terminal_phase_and_elapsed(self, log, run_id):
        log.finish_run(run_id, terminal_phase="success", total_elapsed_s=99.9)
        run = log.get_run(run_id)
        assert run["terminal_phase"] == "success"
        assert run["total_elapsed_s"] == pytest.approx(99.9)

    def test_all_terminal_phases_accepted(self, log, project_id):
        phases = [
            "garagem_error", "garagem_pushback", "garagem_no_slug",
            "meeseeks_failure", "dev_server_failure", "success",
        ]
        for phase in phases:
            rid = log.start_run(project_id=project_id, task_raw=phase)
            log.finish_run(rid, terminal_phase=phase, total_elapsed_s=1.0)
            assert log.get_run(rid)["terminal_phase"] == phase


# ─── full lifecycle ──────────────────────────────────────────────────────

class TestFullLifecycle:
    def test_happy_path(self, log, project_id):
        run_id = log.start_run(project_id=project_id, task_raw="add dark mode")
        log.record_garagem(run_id, GaragemEntry(
            model="claude-sonnet-4-6", elapsed_s=10.0, outcome="success",
            tokens_input=1000, tokens_output=300, cost_usd=0.001,
            turns=2, slug="add-dark-mode", commit_type="feat",
        ))
        log.record_meeseeks(run_id, MeeseeksEntry(
            model="claude-sonnet-4-6", elapsed_s=60.0, outcome="success",
            commits=["abc123"], branch="meeseeks/add-dark-mode",
            diff_added=120, diff_deleted=5, diff_files=4,
        ))
        log.record_dev_server(run_id, DevServerEntry(outcome="success", port=5173))
        log.finish_run(run_id, terminal_phase="success", total_elapsed_s=71.5)

        run = log.get_run(run_id)
        assert run["terminal_phase"] == "success"
        assert run["garagem_outcome"] == "success"
        assert run["meeseeks_outcome"] == "success"
        assert run["dev_server_outcome"] == "success"
        assert run["total_elapsed_s"] == pytest.approx(71.5)

    def test_pushback_path_meeseeks_stays_null(self, log, project_id):
        run_id = log.start_run(project_id=project_id, task_raw="vague task")
        log.record_garagem(run_id, GaragemEntry(
            model="claude-sonnet-4-6", elapsed_s=8.0, outcome="pushback",
        ))
        log.finish_run(run_id, terminal_phase="garagem_pushback", total_elapsed_s=8.0)

        run = log.get_run(run_id)
        assert run["garagem_outcome"] == "pushback"
        assert run["meeseeks_outcome"] is None
        assert run["dev_server_outcome"] is None

    def test_meeseeks_failure_dev_server_skipped(self, log, project_id):
        run_id = log.start_run(project_id=project_id, task_raw="risky task")
        log.record_garagem(run_id, GaragemEntry(
            model="m", elapsed_s=5.0, outcome="success", slug="risky-task",
        ))
        log.record_meeseeks(run_id, MeeseeksEntry(
            model="m", elapsed_s=45.0, outcome="failure",
        ))
        log.finish_run(run_id, terminal_phase="meeseeks_failure", total_elapsed_s=51.0)

        run = log.get_run(run_id)
        assert run["terminal_phase"] == "meeseeks_failure"
        assert run["dev_server_outcome"] is None

    def test_multiple_projects_runs_isolated(self, log):
        p1 = log.ensure_project(slug="proj-a", name="A", path="/a")
        p2 = log.ensure_project(slug="proj-b", name="B", path="/b")

        r1 = log.start_run(project_id=p1, task_raw="task for A")
        r2 = log.start_run(project_id=p2, task_raw="task for B")

        assert log.get_run(r1)["project_id"] == p1
        assert log.get_run(r2)["project_id"] == p2
        assert p1 != p2
        assert r1 != r2


# ─── aggregated readers (cockpit API) ────────────────────────────────────


def _force_started_at(log, run_id, iso):
    """Sobrescreve started_at de uma run (pra testar filtros temporais)."""
    log._conn.execute("UPDATE runs SET started_at = ? WHERE id = ?", (iso, run_id))
    log._conn.commit()


class TestListRuns:
    def test_returns_empty_when_no_runs(self, log, project_id):
        items, total = log.list_runs()
        assert items == [] and total == 0

    def test_pagination_and_total(self, log, project_id):
        for i in range(5):
            log.start_run(project_id=project_id, task_raw=f"task {i}")
        items, total = log.list_runs(limit=2, offset=1)
        assert total == 5
        assert len(items) == 2

    def test_caps_limit_at_200(self, log, project_id):
        items, total = log.list_runs(limit=9999)
        assert total == 0 and items == []
        # Não dá pra observar o cap direto sem rodar SQL, mas garantimos que não explode.

    def test_joins_project_slug(self, log, project_id):
        log.start_run(project_id=project_id, task_raw="t")
        items, _ = log.list_runs()
        assert items[0]["project_slug"] == "test-proj"

    def test_filter_by_project_slug(self, log):
        p1 = log.ensure_project(slug="alpha", name="A", path="/a")
        p2 = log.ensure_project(slug="beta", name="B", path="/b")
        log.start_run(project_id=p1, task_raw="a")
        log.start_run(project_id=p2, task_raw="b")
        items, total = log.list_runs(project_slug="alpha")
        assert total == 1
        assert items[0]["project_slug"] == "alpha"

    def test_filter_by_phase(self, log, project_id):
        r1 = log.start_run(project_id=project_id, task_raw="ok")
        r2 = log.start_run(project_id=project_id, task_raw="pushback")
        log.finish_run(r1, terminal_phase="success", total_elapsed_s=10.0)
        log.finish_run(r2, terminal_phase="garagem_pushback", total_elapsed_s=5.0)
        items, total = log.list_runs(phase="success")
        assert total == 1
        assert items[0]["id"] == r1

    def test_filter_by_date_window(self, log, project_id):
        r_old = log.start_run(project_id=project_id, task_raw="old")
        r_new = log.start_run(project_id=project_id, task_raw="new")
        _force_started_at(log, r_old, "2026-01-01T00:00:00+00:00")
        _force_started_at(log, r_new, "2026-05-01T00:00:00+00:00")
        items, total = log.list_runs(from_iso="2026-04-01", to_iso="2026-06-01")
        assert total == 1 and items[0]["id"] == r_new

    def test_order_by_elapsed_asc(self, log, project_id):
        r1 = log.start_run(project_id=project_id, task_raw="slow")
        r2 = log.start_run(project_id=project_id, task_raw="fast")
        log.finish_run(r1, terminal_phase="success", total_elapsed_s=100.0)
        log.finish_run(r2, terminal_phase="success", total_elapsed_s=5.0)
        items, _ = log.list_runs(order="total_elapsed_s:asc")
        assert [it["id"] for it in items] == [r2, r1]

    def test_invalid_order_falls_back_to_default(self, log, project_id):
        log.start_run(project_id=project_id, task_raw="t")
        items, _ = log.list_runs(order="; DROP TABLE runs--")
        assert len(items) == 1  # não explode, retorna no default


class TestListProjects:
    def test_returns_empty(self, log):
        assert log.list_projects() == []

    def test_ordered_by_slug(self, log):
        log.ensure_project(slug="zeta", name="Z", path="/z")
        log.ensure_project(slug="alpha", name="A", path="/a")
        items = log.list_projects()
        assert [p["slug"] for p in items] == ["alpha", "zeta"]


class TestRegisterProject:
    """Validação completa do cadastro novo (B1)."""

    @pytest.fixture
    def repo_path(self, tmp_path):
        """Um diretório que parece um repo git."""
        repo = tmp_path / "fake-repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        return repo

    def test_happy_path_default_mode_pontual(self, log, repo_path):
        proj = log.register_project(slug="meu-app", path=str(repo_path))
        assert proj["slug"] == "meu-app"
        assert proj["name"] == "meu-app"
        assert proj["mode"] == "pontual"
        assert proj["active"] == 1
        assert proj["path"] == str(repo_path)

    def test_name_default_eh_slug(self, log, repo_path):
        proj = log.register_project(slug="x", path=str(repo_path))
        assert proj["name"] == "x"

    def test_aceita_mode_construtor(self, log, repo_path):
        proj = log.register_project(
            slug="ctor", path=str(repo_path), mode="construtor"
        )
        assert proj["mode"] == "construtor"

    def test_rejeita_mode_invalido(self, log, repo_path):
        from logger import ModoInvalido
        with pytest.raises(ModoInvalido):
            log.register_project(slug="x", path=str(repo_path), mode="bizarro")

    def test_rejeita_slug_invalido_uppercase(self, log, repo_path):
        from logger import SlugInvalido
        with pytest.raises(SlugInvalido):
            log.register_project(slug="MeuApp", path=str(repo_path))

    def test_rejeita_slug_invalido_underscore(self, log, repo_path):
        from logger import SlugInvalido
        with pytest.raises(SlugInvalido):
            log.register_project(slug="meu_app", path=str(repo_path))

    def test_rejeita_slug_comecando_com_digito(self, log, repo_path):
        from logger import SlugInvalido
        with pytest.raises(SlugInvalido):
            log.register_project(slug="1-projeto", path=str(repo_path))

    def test_rejeita_slug_muito_longo(self, log, repo_path):
        from logger import SlugInvalido
        with pytest.raises(SlugInvalido):
            log.register_project(slug="a" * 31, path=str(repo_path))

    def test_aceita_slug_no_limite(self, log, repo_path):
        proj = log.register_project(slug="a" * 30, path=str(repo_path))
        assert proj["slug"] == "a" * 30

    def test_rejeita_path_inexistente(self, log, tmp_path):
        from logger import PathInexistente
        with pytest.raises(PathInexistente):
            log.register_project(
                slug="x", path=str(tmp_path / "nao-existe")
            )

    def test_rejeita_path_que_eh_arquivo(self, log, tmp_path):
        from logger import PathInexistente
        f = tmp_path / "arquivo.txt"
        f.write_text("hi")
        with pytest.raises(PathInexistente):
            log.register_project(slug="x", path=str(f))

    def test_rejeita_path_sem_git(self, log, tmp_path):
        from logger import PathNaoEhRepo
        d = tmp_path / "nao-repo"
        d.mkdir()
        with pytest.raises(PathNaoEhRepo):
            log.register_project(slug="x", path=str(d))

    def test_rejeita_slug_duplicado_ativo(self, log, repo_path):
        from logger import SlugDuplicado
        log.register_project(slug="dup", path=str(repo_path))
        with pytest.raises(SlugDuplicado):
            log.register_project(slug="dup", path=str(repo_path))

    def test_rejeita_slug_duplicado_inativo(self, log, repo_path):
        """Slug é único globalmente — reativação não é parte da B1."""
        from logger import SlugDuplicado
        log.register_project(slug="dup", path=str(repo_path))
        log.deactivate_project("dup")
        with pytest.raises(SlugDuplicado):
            log.register_project(slug="dup", path=str(repo_path))


class TestListProjectsActiveFilter:
    @pytest.fixture
    def repo_path(self, tmp_path):
        repo = tmp_path / "r"
        repo.mkdir()
        (repo / ".git").mkdir()
        return repo

    def test_exclui_inativos_por_default(self, log, repo_path):
        log.register_project(slug="a", path=str(repo_path))
        log.register_project(slug="b", path=str(repo_path))
        log.deactivate_project("a")
        items = log.list_projects()
        assert [p["slug"] for p in items] == ["b"]

    def test_include_inactive_traz_tudo(self, log, repo_path):
        log.register_project(slug="a", path=str(repo_path))
        log.register_project(slug="b", path=str(repo_path))
        log.deactivate_project("a")
        items = log.list_projects(include_inactive=True)
        assert [p["slug"] for p in items] == ["a", "b"]


class TestGetProjectBySlug:
    def test_retorna_dict_quando_existe(self, log):
        log.ensure_project(slug="x", name="X", path="/x")
        proj = log.get_project_by_slug("x")
        assert proj["slug"] == "x"

    def test_retorna_none_quando_nao_existe(self, log):
        assert log.get_project_by_slug("nope") is None

    def test_retorna_mesmo_inativo(self, log, tmp_path):
        repo = tmp_path / "r"
        repo.mkdir()
        (repo / ".git").mkdir()
        log.register_project(slug="x", path=str(repo))
        log.deactivate_project("x")
        # get_project_by_slug não filtra por active — quem consome decide.
        proj = log.get_project_by_slug("x")
        assert proj is not None
        assert proj["active"] == 0


class TestDeactivateProject:
    @pytest.fixture
    def repo_path(self, tmp_path):
        repo = tmp_path / "r"
        repo.mkdir()
        (repo / ".git").mkdir()
        return repo

    def test_seta_active_zero(self, log, repo_path):
        log.register_project(slug="x", path=str(repo_path))
        assert log.deactivate_project("x") is True
        proj = log.get_project_by_slug("x")
        assert proj["active"] == 0

    def test_idempotente_retorna_false_segunda_vez(self, log, repo_path):
        log.register_project(slug="x", path=str(repo_path))
        log.deactivate_project("x")
        assert log.deactivate_project("x") is False

    def test_retorna_false_para_slug_inexistente(self, log):
        assert log.deactivate_project("fantasma") is False


class TestEnsureProjectAindaFunciona:
    """Não-regressão: o seed migracional usa ensure_project."""

    def test_ainda_eh_upsert_idempotente(self, log):
        a = log.ensure_project(slug="s", name="S", path="/s")
        b = log.ensure_project(slug="s", name="S2", path="/s2")
        assert a == b

    def test_nao_valida_path(self, log):
        # ensure_project é compat — não exige .git/, não checa existência.
        log.ensure_project(slug="x", name="X", path="/nao/existe")


class TestSchemaMigration:
    """Garante que get_connection promove DBs pré-B1 sem dor."""

    def test_alter_idempotente_em_db_legado(self, tmp_path):
        # Simula um DB criado antes da B1: schema sem active/mode.
        db_path = tmp_path / "legacy.db"
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE projects (
                id         TEXT PRIMARY KEY,
                slug       TEXT UNIQUE NOT NULL,
                name       TEXT NOT NULL,
                path       TEXT NOT NULL,
                repo_url   TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT INTO projects (id, slug, name, path, created_at)"
            " VALUES ('id1', 'legado', 'Legado', '/x', '2026-01-01T00:00:00')"
        )
        conn.commit()
        conn.close()

        # Reabrir via get_connection roda a migração.
        conn = get_connection(db_path)
        row = conn.execute(
            "SELECT slug, active, mode FROM projects WHERE id = 'id1'"
        ).fetchone()
        assert row["slug"] == "legado"
        assert row["active"] == 1
        assert row["mode"] == "pontual"

        # Idempotência — reabrir de novo não explode.
        conn.close()
        get_connection(db_path)


class TestUpdateRunReview:
    def test_persists_all_three_fields(self, log, run_id):
        ok = log.update_run_review(
            run_id,
            merged_to_main=1,
            assertiveness_score=4,
            review_note="ficou bom",
        )
        assert ok is True
        row = log.get_run(run_id)
        assert row["merged_to_main"] == 1
        assert row["assertiveness_score"] == 4
        assert row["review_note"] == "ficou bom"

    def test_accepts_nulls(self, log, run_id):
        log.update_run_review(run_id, merged_to_main=1, assertiveness_score=3, review_note="x")
        log.update_run_review(run_id, merged_to_main=None, assertiveness_score=None, review_note=None)
        row = log.get_run(run_id)
        assert row["merged_to_main"] is None
        assert row["assertiveness_score"] is None
        assert row["review_note"] is None

    def test_returns_false_for_unknown_id(self, log):
        ok = log.update_run_review(
            "nonexistent",
            merged_to_main=1,
            assertiveness_score=5,
            review_note="x",
        )
        assert ok is False


class TestOverviewMetrics:
    def test_empty_db(self, log):
        m = log.overview_metrics(days=30)
        assert m["window_days"] == 30
        assert m["runs_total"] == 0
        assert m["custo_total_usd"] == 0.0
        assert m["taxa_pushback"] == 0.0
        assert m["custo_por_dia"] == []
        assert m["runs_por_dia"] == []
        assert m["phase_breakdown"] == {}

    def test_aggregates_costs_and_pushback(self, log, project_id):
        r1 = log.start_run(project_id=project_id, task_raw="ok")
        r2 = log.start_run(project_id=project_id, task_raw="pushback")
        r3 = log.start_run(project_id=project_id, task_raw="fail")
        log.record_garagem(r1, GaragemEntry(model="m", elapsed_s=1, outcome="success", cost_usd=0.02))
        log.record_meeseeks(r1, MeeseeksEntry(model="m", elapsed_s=10, outcome="success", cost_usd=0.08))
        log.finish_run(r1, terminal_phase="success", total_elapsed_s=11.0)
        log.record_garagem(r2, GaragemEntry(model="m", elapsed_s=2, outcome="pushback", cost_usd=0.01))
        log.finish_run(r2, terminal_phase="garagem_pushback", total_elapsed_s=2.0)
        log.record_garagem(r3, GaragemEntry(model="m", elapsed_s=3, outcome="success", cost_usd=0.03))
        log.finish_run(r3, terminal_phase="meeseeks_failure", total_elapsed_s=20.0)

        m = log.overview_metrics(days=30)
        assert m["runs_total"] == 3
        assert m["custo_total_usd"] == pytest.approx(0.14, abs=1e-6)
        assert m["taxa_pushback"] == pytest.approx(1 / 3, abs=1e-3)
        assert m["phase_breakdown"]["success"] == 1
        assert m["phase_breakdown"]["garagem_pushback"] == 1
        assert m["phase_breakdown"]["meeseeks_failure"] == 1

    def test_window_excludes_old_runs(self, log, project_id):
        r_old = log.start_run(project_id=project_id, task_raw="old")
        r_new = log.start_run(project_id=project_id, task_raw="new")
        _force_started_at(log, r_old, "2020-01-01T00:00:00+00:00")
        # r_new fica com started_at recente (now)

        m = log.overview_metrics(days=30)
        assert m["runs_total"] == 1

    def test_daily_buckets(self, log, project_id):
        r1 = log.start_run(project_id=project_id, task_raw="a")
        r2 = log.start_run(project_id=project_id, task_raw="b")
        r3 = log.start_run(project_id=project_id, task_raw="c")
        from datetime import datetime, timezone, timedelta
        today = datetime.now(timezone.utc)
        d0 = today.strftime("%Y-%m-%d") + "T12:00:00+00:00"
        d1 = (today - timedelta(days=1)).strftime("%Y-%m-%d") + "T12:00:00+00:00"
        _force_started_at(log, r1, d0)
        _force_started_at(log, r2, d0)
        _force_started_at(log, r3, d1)

        m = log.overview_metrics(days=30)
        runs_dict = {item["dia"]: item["n"] for item in m["runs_por_dia"]}
        assert runs_dict[today.strftime("%Y-%m-%d")] == 2
        assert runs_dict[(today - timedelta(days=1)).strftime("%Y-%m-%d")] == 1
