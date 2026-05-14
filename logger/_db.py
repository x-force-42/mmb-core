from pathlib import Path
import sqlite3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id         TEXT PRIMARY KEY,
    slug       TEXT UNIQUE NOT NULL,
    name       TEXT NOT NULL,
    path       TEXT NOT NULL,
    repo_url   TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    -- envelope
    id                      TEXT PRIMARY KEY,
    project_id              TEXT NOT NULL REFERENCES projects(id),
    started_at              TEXT NOT NULL,
    task_raw                TEXT NOT NULL,
    terminal_phase          TEXT,
    total_elapsed_s         REAL,
    rerun_of                TEXT REFERENCES runs(id),

    -- garagem
    garagem_model           TEXT,
    garagem_elapsed_s       REAL,
    garagem_tokens_input    INTEGER,
    garagem_tokens_output   INTEGER,
    garagem_cost_usd        REAL,
    garagem_turns           INTEGER,
    garagem_outcome         TEXT,
    garagem_briefing_json   TEXT,
    garagem_meeseeks_prompt TEXT,
    garagem_criticality     TEXT,
    garagem_complexity      TEXT,
    garagem_commit_type     TEXT,
    garagem_slug            TEXT,

    -- meeseeks
    meeseeks_model          TEXT,
    meeseeks_elapsed_s      REAL,
    meeseeks_tokens_input   INTEGER,
    meeseeks_tokens_output  INTEGER,
    meeseeks_cost_usd       REAL,
    meeseeks_outcome        TEXT,
    meeseeks_branch         TEXT,
    meeseeks_commits_json   TEXT,
    meeseeks_report         TEXT,
    meeseeks_confidence     REAL,
    meeseeks_diff_added     INTEGER,
    meeseeks_diff_deleted   INTEGER,
    meeseeks_diff_files     INTEGER,

    -- dev server
    dev_server_outcome      TEXT,
    dev_server_port         INTEGER,

    -- manual review (filled via dashboard)
    merged_to_main          INTEGER,
    assertiveness_score     INTEGER,
    review_note             TEXT
);
"""


def get_connection(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn
