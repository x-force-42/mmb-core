"""Verify do cenário 01 — rename greet → welcome.

Pós-condições (todas via inspeção do worktree, não do master):
- existe a função `welcome` em src/
- não existe mais a palavra `greet` em src/ nem em tests/
- pipeline chegou a `success` (ou `dev_server_failure`, que não nos
  diz respeito aqui — o que importa é Meeseeks ter terminado verde)
- pelo menos 1 commit na branch meeseeks/*
- DB row populado com tokens e custo do envelope
"""

from pathlib import Path


def verify(ctx) -> None:
    p = ctx.pipeline

    assert p.phase in ("success", "dev_server_failure"), (
        f"pipeline parou em fase inesperada: {p.phase} "
        f"(garagem.error={p.garagem.error!r}, "
        f"meeseeks.error={p.meeseeks.error if p.meeseeks else None!r})"
    )

    assert p.meeseeks is not None and p.meeseeks.success, (
        f"Meeseeks não teve sucesso: error={p.meeseeks and p.meeseeks.error}"
    )

    worktree = p.meeseeks.worktree
    assert worktree is not None and worktree.exists(), (
        f"worktree não existe: {worktree}"
    )

    # ── conteúdo: welcome existe, greet sumiu ──
    src = worktree / "src"
    tests = worktree / "tests"

    welcome_hits = _grep_count(src, "welcome")
    greet_hits = _grep_count(src, "greet") + _grep_count(tests, "greet")

    assert welcome_hits >= 2, (
        f"esperado ≥2 ocorrências de 'welcome' em src/, encontrei {welcome_hits}"
    )
    assert greet_hits == 0, (
        f"esperado 0 ocorrências de 'greet' restantes, encontrei {greet_hits}"
    )

    # ── git: branch criada com commits ──
    assert p.meeseeks.branch and p.meeseeks.branch.startswith("meeseeks/"), (
        f"branch inesperado: {p.meeseeks.branch}"
    )
    assert len(p.meeseeks.commits or []) >= 1, "esperava ≥1 commit"

    # ── DB row populado ──
    row = ctx.db_row
    assert row is not None, "linha do DB não foi criada"
    assert row["terminal_phase"] in ("success", "dev_server_failure")
    assert row["meeseeks_outcome"] == "success"
    assert row["garagem_cost_usd"] is not None and row["garagem_cost_usd"] > 0, (
        f"custo da Garagem deveria estar populado: {row['garagem_cost_usd']}"
    )
    assert row["meeseeks_cost_usd"] is not None and row["meeseeks_cost_usd"] > 0, (
        f"custo do Meeseeks deveria estar populado: {row['meeseeks_cost_usd']}"
    )
    assert row["meeseeks_diff_files"] is not None and row["meeseeks_diff_files"] >= 1


def _grep_count(directory: Path, needle: str) -> int:
    """Conta ocorrências de `needle` em arquivos sob `directory` (todos
    os arquivos, sem filtro de extensão — fixture é tudo .js)."""
    if not directory.exists():
        return 0
    n = 0
    for p in directory.rglob("*"):
        if p.is_file():
            try:
                n += p.read_text(encoding="utf-8").count(needle)
            except (UnicodeDecodeError, OSError):
                pass
    return n
