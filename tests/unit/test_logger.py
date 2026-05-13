"""Testes do SDK de observabilidade (logger).

Usa banco em memória (:memory:) — zero I/O, isolado por teste.
"""

import json
import pytest

from logger import (
    DevServerEntry,
    GaragemEntry,
    MeeseeksEntry,
    RunLogger,
)


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
            prompt_tokens=350,
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
        assert run["garagem_prompt_tokens"] == 350
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
