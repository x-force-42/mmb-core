"""Verify do cenário 02 — implementação de farewell.

Pós-condições:
- pipeline chegou a Meeseeks com sucesso (≥1 commit)
- worktree contém `farewell` exportado em src/messages.js
- `npm test` no worktree passa (o teste pre-escrito vira verde)
- DB row populado com tokens/custo de ambas as fases
"""

import subprocess
from pathlib import Path


def verify(ctx) -> None:
    p = ctx.pipeline

    assert p.phase in ("success", "dev_server_failure"), (
        f"pipeline parou em fase inesperada: {p.phase}"
    )
    assert p.meeseeks is not None and p.meeseeks.success, (
        f"Meeseeks falhou: error={p.meeseeks and p.meeseeks.error}"
    )

    worktree = p.meeseeks.worktree
    assert worktree is not None and worktree.exists()

    # ── farewell existe e está exportado ──
    messages = (worktree / "src" / "messages.js").read_text(encoding="utf-8")
    assert "farewell" in messages, "função farewell não foi adicionada"
    assert "export" in messages.split("farewell", 1)[0][-40:] or \
           "export function farewell" in messages or \
           "export const farewell" in messages or \
           "export { farewell" in messages or \
           "export {farewell" in messages, (
        "farewell não parece estar exportado"
    )

    # ── npm test passa no worktree ──
    r = subprocess.run(
        ["npm", "test"], cwd=str(worktree),
        capture_output=True, text=True, timeout=60,
    )
    assert r.returncode == 0, (
        f"npm test falhou no worktree:\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}"
    )

    # ── DB row ──
    row = ctx.db_row
    assert row is not None
    assert row["meeseeks_outcome"] == "success"
    assert row["garagem_cost_usd"] is not None and row["garagem_cost_usd"] > 0
    assert row["meeseeks_cost_usd"] is not None and row["meeseeks_cost_usd"] > 0
    assert row["meeseeks_diff_added"] is not None and row["meeseeks_diff_added"] >= 1
