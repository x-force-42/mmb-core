"""Funções puras de formatação de strings e renderização de status.

Sem dependência de Discord, asyncio, subprocess ou IO. Tudo aqui pode
ser testado deterministicamente passando entradas e comparando strings.
"""

from pathlib import Path

from meeseeks import MeeseeksResult


# ─── tempo e decay ───────────────────────────────────────────────────────

def fmt_time(seconds: float) -> str:
    """Formata segundos como MM:SS."""
    s = int(seconds)
    return f"{s // 60:02d}:{s % 60:02d}"


def meeseeks_decay(seconds: float) -> str:
    """Frase do heartbeat do Meeseeks que se deteriora com o tempo.
    Casa com o lore: quanto mais tempo um Meeseeks vive, mais instável fica."""
    m = seconds / 60
    if m < 3:
        return "🌀 Working on it!"
    if m < 8:
        return "💪 Caaaaan do!"
    if m < 15:
        return "😅 Oh boy, this is tricky..."
    if m < 25:
        return "😬 Existing is becoming pain, Rick..."
    return "💀 Pleeease let me finish..."


# ─── status messages (heartbeat) ─────────────────────────────────────────

def render_garagem_status(task: str, elapsed: float) -> str:
    return (
        f"🔧 *A Garagem cavando isso aí…* `{fmt_time(elapsed)}`\n"
        f"> {task}"
    )


def render_meeseeks_status(slug: str, elapsed: float) -> str:
    return (
        f"{meeseeks_decay(elapsed)} `{fmt_time(elapsed)}`\n"
        f"> branch: `meeseeks/{slug}`"
    )


# ─── mensagens finais ────────────────────────────────────────────────────

def formatar_pushback(briefing: dict) -> str:
    duvidas = briefing.get("duvidas_pro_rick") or [
        "_(sem dúvidas listadas, mas escopo marcado como pouco claro)_"
    ]
    bloco = "\n".join(f"- {d}" for d in duvidas)
    return (
        "🔧 **Não, Rick. Volta com isso melhor antes de eu acordar um Meeseeks.**\n\n"
        f"{bloco}"
    )


def formatar_cleanup(result: MeeseeksResult, target_path: Path) -> str:
    if result.worktree is None or result.branch is None:
        return ""
    try:
        rel = result.worktree.relative_to(target_path)
    except ValueError:
        rel = result.worktree
    return (
        "\n\n**Cleanup quando aprovar**\n"
        f"```bash\n"
        f"cd {target_path}\n"
        f"git worktree remove {rel}\n"
        f"git branch -D {result.branch}\n"
        f"```"
    )


def formatar_sucesso(
    result: MeeseeksResult, dev_port: int, target_path: Path
) -> str:
    relatorio = result.relatorio or "_(Meeseeks não devolveu relatório)_"
    dev_info = (
        f"\n\n**Dev server**\n"
        f"- `http://localhost:{dev_port}` "
        f"(worktree `{result.worktree.name if result.worktree else '?'}`)"
    )
    return relatorio + dev_info + formatar_cleanup(result, target_path)


def formatar_falha_meeseeks(
    result: MeeseeksResult, target_path: Path
) -> str:
    cabecalho = "💀 **Existing is pain, Rick.**"
    detalhe = f" `{result.error}`" if result.error else ""
    relatorio = (
        f"\n\n**Relatório parcial:**\n{result.relatorio}"
        if result.relatorio else ""
    )
    raw = (
        f"\n\n```\n{result.raw[:1200]}\n```"
        if result.raw and not result.relatorio else ""
    )
    return cabecalho + detalhe + relatorio + raw + formatar_cleanup(
        result, target_path
    )
