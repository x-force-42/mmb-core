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
                entry.meeseeks_prompt,
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

    # ── aggregated readers (cockpit API) ─────────────────────────────────

    def list_runs(
        self,
        *,
        project_slug: str | None = None,
        phase: str | None = None,
        from_iso: str | None = None,
        to_iso: str | None = None,
        limit: int = 50,
        offset: int = 0,
        order: str = "started_at:desc",
    ) -> tuple[list[dict], int]:
        """Lista runs paginada com filtros. Retorna (items, total).

        Items são dicts da linha do banco com `project_slug` joinado.
        `limit` é capado em 200. `order` é validado contra whitelist —
        valores inválidos caem no default.
        """
        if limit > 200:
            limit = 200
        if limit < 1:
            limit = 1
        if offset < 0:
            offset = 0

        order_sql = _ORDER_WHITELIST.get(order, _ORDER_WHITELIST["started_at:desc"])

        where_parts: list[str] = []
        params: list = []
        if project_slug is not None:
            where_parts.append("p.slug = ?")
            params.append(project_slug)
        if phase is not None:
            where_parts.append("r.terminal_phase = ?")
            params.append(phase)
        if from_iso is not None:
            where_parts.append("r.started_at >= ?")
            params.append(from_iso)
        if to_iso is not None:
            where_parts.append("r.started_at <= ?")
            params.append(to_iso)
        where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

        total = self._conn.execute(
            f"SELECT COUNT(*) AS n FROM runs r JOIN projects p ON p.id = r.project_id {where_sql}",
            params,
        ).fetchone()["n"]

        rows = self._conn.execute(
            f"""
            SELECT r.*, p.slug AS project_slug
            FROM runs r JOIN projects p ON p.id = r.project_id
            {where_sql}
            ORDER BY {order_sql}
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
        return [dict(row) for row in rows], total

    def list_projects(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM projects ORDER BY slug"
        ).fetchall()
        return [dict(row) for row in rows]

    def update_run_review(
        self,
        run_id: str,
        *,
        merged_to_main: int | None,
        assertiveness_score: int | None,
        review_note: str | None,
    ) -> bool:
        """Persiste os 3 campos de review manual. Retorna True se a row existia."""
        cur = self._conn.execute(
            """
            UPDATE runs SET
                merged_to_main      = ?,
                assertiveness_score = ?,
                review_note         = ?
            WHERE id = ?
            """,
            (merged_to_main, assertiveness_score, review_note, run_id),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def overview_metrics(self, *, days: int = 30) -> dict:
        """Agregados para o dashboard do cockpit. Janela retroativa em dias."""
        if days < 1:
            days = 1
        since = f"-{days} days"

        base = self._conn.execute(
            """
            SELECT
                COUNT(*) AS runs_total,
                COALESCE(SUM(COALESCE(garagem_cost_usd, 0) + COALESCE(meeseeks_cost_usd, 0)), 0) AS custo_total_usd,
                AVG(total_elapsed_s) AS tempo_medio_s,
                SUM(CASE WHEN terminal_phase LIKE 'garagem_%' THEN 1 ELSE 0 END) AS pushback_n
            FROM runs
            WHERE started_at >= datetime('now', ?)
            """,
            (since,),
        ).fetchone()

        runs_total = base["runs_total"] or 0
        pushback_n = base["pushback_n"] or 0
        taxa_pushback = (pushback_n / runs_total) if runs_total > 0 else 0.0

        custo_rows = self._conn.execute(
            """
            SELECT date(started_at) AS dia,
                   COALESCE(SUM(COALESCE(garagem_cost_usd, 0) + COALESCE(meeseeks_cost_usd, 0)), 0) AS usd
            FROM runs
            WHERE started_at >= datetime('now', ?)
            GROUP BY dia
            ORDER BY dia DESC
            """,
            (since,),
        ).fetchall()

        runs_rows = self._conn.execute(
            """
            SELECT date(started_at) AS dia, COUNT(*) AS n
            FROM runs
            WHERE started_at >= datetime('now', ?)
            GROUP BY dia
            ORDER BY dia DESC
            """,
            (since,),
        ).fetchall()

        phase_rows = self._conn.execute(
            """
            SELECT terminal_phase, COUNT(*) AS n
            FROM runs
            WHERE started_at >= datetime('now', ?)
              AND terminal_phase IS NOT NULL
            GROUP BY terminal_phase
            """,
            (since,),
        ).fetchall()

        return {
            "window_days": days,
            "runs_total": runs_total,
            "custo_total_usd": round(base["custo_total_usd"] or 0.0, 4),
            "tempo_medio_s": base["tempo_medio_s"],
            "taxa_pushback": round(taxa_pushback, 4),
            "custo_por_dia": [
                {"dia": r["dia"], "usd": round(r["usd"] or 0.0, 4)} for r in custo_rows
            ],
            "runs_por_dia": [{"dia": r["dia"], "n": r["n"]} for r in runs_rows],
            "phase_breakdown": {r["terminal_phase"]: r["n"] for r in phase_rows},
        }


# ─── helpers ─────────────────────────────────────────────────────────────

_ORDER_WHITELIST = {
    "started_at:desc": "r.started_at DESC",
    "started_at:asc": "r.started_at ASC",
    "total_elapsed_s:desc": "r.total_elapsed_s DESC",
    "total_elapsed_s:asc": "r.total_elapsed_s ASC",
}

def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
