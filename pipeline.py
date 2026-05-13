"""Pipeline headless: Garagem -> Meeseeks -> dev server, sem Discord.

Existe pra cenários de calibração e testes poderem rodar o fluxo
ponta-a-ponta sem precisar do bot. O bot.py ainda chama as fases
individualmente porque intercala heartbeat visual entre elas.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from garagem import GaragemResult, invocar_garagem
from meeseeks import MeeseeksResult, invocar_meeseeks, start_dev_server


PipelinePhase = Literal[
    "garagem_error",
    "garagem_pushback",
    "garagem_no_slug",
    "meeseeks_failure",
    "dev_server_failure",
    "success",
]


@dataclass
class PipelineResult:
    """Resultado completo de uma execução de pipeline.

    `phase` indica até onde o fluxo chegou e qual foi o desfecho.
    Os campos parciais (`meeseeks`, `dev_port`, `dev_server_error`)
    ficam None quando o fluxo não chegou neles.
    """
    phase: PipelinePhase
    garagem: GaragemResult
    meeseeks: MeeseeksResult | None = None
    dev_port: int | None = None
    dev_server_error: str | None = None


async def run_pipeline(task: str, project_path: Path) -> PipelineResult:
    """Roda o pipeline completo end-to-end, sem efeitos colaterais
    visuais. Devolve PipelineResult com a fase final e os artefatos
    de cada estágio que chegou a rodar."""

    g = await invocar_garagem(task, project_path)
    if g.error:
        return PipelineResult(phase="garagem_error", garagem=g)

    parsed = g.parsed or {}
    if not parsed.get("escopo_claro"):
        return PipelineResult(phase="garagem_pushback", garagem=g)

    slug = (parsed.get("slug") or "").strip()
    if not slug:
        return PipelineResult(phase="garagem_no_slug", garagem=g)

    m = await invocar_meeseeks(parsed, project_path)
    if not m.success:
        return PipelineResult(
            phase="meeseeks_failure", garagem=g, meeseeks=m
        )

    try:
        dev_port = start_dev_server(m.worktree)
    except Exception as e:
        return PipelineResult(
            phase="dev_server_failure",
            garagem=g,
            meeseeks=m,
            dev_server_error=str(e),
        )

    return PipelineResult(
        phase="success", garagem=g, meeseeks=m, dev_port=dev_port
    )
