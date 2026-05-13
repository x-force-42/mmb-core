"""MMB observability SDK.

Decoupled from the bot core — no discord.py, no MMB dataclasses.
The core calls this like an external library.

Usage:
    from logger import RunLogger, GaragemEntry, MeeseeksEntry, DevServerEntry

    log = RunLogger("mmb.db")
    pid = log.ensure_project(slug="my-app", name="My App", path="/path/to/app")
    run_id = log.start_run(project_id=pid, task_raw="fix login bug")

    log.record_garagem(run_id, GaragemEntry(model="claude-...", elapsed_s=12.3,
                                            outcome="success", ...))
    log.record_meeseeks(run_id, MeeseeksEntry(...))
    log.record_dev_server(run_id, DevServerEntry(outcome="success", port=5173))
    log.finish_run(run_id, terminal_phase="success", total_elapsed_s=45.6)
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import uuid

from logger._db import get_connection


# ─── entry dataclasses ───────────────────────────────────────────────────

@dataclass
class GaragemEntry:
    model: str
    elapsed_s: float
    outcome: str                    # success | pushback | error
    tokens_input: int | None = None
    tokens_output: int | None = None
    cost_usd: float | None = None
    turns: int | None = None
    briefing_json: str | None = None
    meeseeks_prompt: str | None = None
    prompt_tokens: int | None = None
    criticality: str | None = None  # low | medium | high
    complexity: str | None = None   # low | medium | high
    commit_type: str | None = None
    slug: str | None = None


@dataclass
class MeeseeksEntry:
    model: str
    elapsed_s: float
    outcome: str                      # success | failure
    tokens_input: int | None = None
    tokens_output: int | None = None
    cost_usd: float | None = None
    branch: str | None = None
    commits: list[str] | None = None
    report: str | None = None
    confidence: float | None = None   # 0–1, self-reported by Meeseeks
    diff_added: int | None = None
    diff_deleted: int | None = None
    diff_files: int | None = None


@dataclass
class DevServerEntry:
    outcome: str                  # success | failure | skipped
    port: int | None = None


# ─── logger ──────────────────────────────────────────────────────────────

class RunLogger:
    def __init__(self, db_path: str | Path):
        self._conn = get_connection(Path(db_path))

    # ── projects ─────────────────────────────────────────────────────────

    def ensure_project(
        self,
        *,
        slug: str,
        name: str,
        path: str,
        repo_url: str | None = None,
    ) -> str:
        """Upsert project by slug. Returns project id."""
        row = self._conn.execute(
            "SELECT id FROM projects WHERE slug = ?", (slug,)
        ).fetchone()
        if row:
            return row["id"]
        project_id = _new_id()
        self._conn.execute(
            "INSERT INTO projects (id, slug, name, path, repo_url, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, slug, name, path, repo_url, _now()),
        )
        self._conn.commit()
        return project_id

    # ── runs ─────────────────────────────────────────────────────────────

    def start_run(
        self,
        *,
        project_id: str,
        task_raw: str,
        rerun_of: str | None = None,
    ) -> str:
        """Insert a new run row. Returns run_id."""
        run_id = _new_id()
        self._conn.execute(
            "INSERT INTO runs (id, project_id, started_at, task_raw, rerun_of)"
            " VALUES (?, ?, ?, ?, ?)",
            (run_id, project_id, _now(), task_raw, rerun_of),
        )
        self._conn.commit()
        return run_id

    def record_garagem(self, run_id: str, entry: GaragemEntry) -> None:
        self._conn.execute(
            """
            UPDATE runs SET
                garagem_model           = ?,
                garagem_elapsed_s       = ?,
                garagem_tokens_input    = ?,
                garagem_tokens_output   = ?,
                garagem_cost_usd        = ?,
                garagem_turns           = ?,
                garagem_outcome         = ?,
                garagem_briefing_json   = ?,
                garagem_meeseeks_prompt = ?,
                garagem_prompt_tokens   = ?,
                garagem_criticality     = ?,
                garagem_complexity      = ?,
                garagem_commit_type     = ?,
                garagem_slug            = ?
            WHERE id = ?
            """,
            (
                entry.model, entry.elapsed_s,
                entry.tokens_input, entry.tokens_output, entry.cost_usd,
                entry.turns, entry.outcome, entry.briefing_json,
                entry.meeseeks_prompt, entry.prompt_tokens,
                entry.criticality, entry.complexity,
                entry.commit_type, entry.slug,
                run_id,
            ),
        )
        self._conn.commit()

    def record_meeseeks(self, run_id: str, entry: MeeseeksEntry) -> None:
        self._conn.execute(
            """
            UPDATE runs SET
                meeseeks_model         = ?,
                meeseeks_elapsed_s     = ?,
                meeseeks_tokens_input  = ?,
                meeseeks_tokens_output = ?,
                meeseeks_cost_usd      = ?,
                meeseeks_outcome       = ?,
                meeseeks_branch        = ?,
                meeseeks_commits_json  = ?,
                meeseeks_report        = ?,
                meeseeks_confidence    = ?,
                meeseeks_diff_added    = ?,
                meeseeks_diff_deleted  = ?,
                meeseeks_diff_files    = ?
            WHERE id = ?
            """,
            (
                entry.model, entry.elapsed_s,
                entry.tokens_input, entry.tokens_output, entry.cost_usd,
                entry.outcome, entry.branch,
                json.dumps(entry.commits) if entry.commits is not None else None,
                entry.report, entry.confidence,
                entry.diff_added, entry.diff_deleted, entry.diff_files,
                run_id,
            ),
        )
        self._conn.commit()

    def record_dev_server(self, run_id: str, entry: DevServerEntry) -> None:
        self._conn.execute(
            "UPDATE runs SET dev_server_outcome = ?, dev_server_port = ? WHERE id = ?",
            (entry.outcome, entry.port, run_id),
        )
        self._conn.commit()

    def finish_run(
        self,
        run_id: str,
        *,
        terminal_phase: str,
        total_elapsed_s: float,
    ) -> None:
        self._conn.execute(
            "UPDATE runs SET terminal_phase = ?, total_elapsed_s = ? WHERE id = ?",
            (terminal_phase, total_elapsed_s, run_id),
        )
        self._conn.commit()

    # ── reader ───────────────────────────────────────────────────────────

    def get_run(self, run_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM runs WHERE id = ?", (run_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_project(self, project_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        return dict(row) if row else None


# ─── helpers ─────────────────────────────────────────────────────────────

def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
