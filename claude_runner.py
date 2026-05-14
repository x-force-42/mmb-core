"""Wrapper único pra invocação do `claude -p`.

Centraliza:
- montagem do comando
- env com DISABLE_AUTOUPDATER (evita corrida com auto-update)
- captura de FileNotFoundError (binário sumiu durante reinstall)
- timeout
- check de returncode
- parse do envelope JSON do CLI

Cada caller (Garagem, Meeseeks) passa user_prompt, system_prompt,
cwd, timeout e flags específicas; recebe um ClaudeRunResult com
o `output` (envelope.result) ou um `error` estruturado.
"""

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path

from config import CLAUDE_CLI


@dataclass
class ClaudeRunResult:
    output: str
    error: str | None
    raw: str
    tokens_input: int | None = None
    tokens_output: int | None = None
    cost_usd: float | None = None


def load_system_prompt(path: Path) -> str:
    """Lê um arquivo de prompt do disco a cada chamada — permite iterar
    sem reiniciar o bot. O custo de IO é insignificante perto do tempo
    do `claude -p`.

    Levanta RuntimeError se arquivo não existir ou estiver vazio.
    """
    if not path.exists():
        raise RuntimeError(f"Prompt não encontrado em {path}")
    texto = path.read_text(encoding="utf-8").strip()
    if not texto:
        raise RuntimeError(f"Prompt está vazio: {path}")
    return texto


async def run_claude_p(
    *,
    user_prompt: str,
    system_prompt: str,
    cwd: Path,
    timeout: int,
    extra_args: list[str] | None = None,
    cli_path: str | None = None,
) -> ClaudeRunResult:
    """Roda `claude -p` com output JSON e devolve o envelope parseado.

    Parâmetros são keyword-only pra deixar callsites legíveis.
    """
    cmd = [
        cli_path or CLAUDE_CLI,
        "-p", user_prompt,
        "--output-format", "json",
        "--append-system-prompt", system_prompt,
        *(extra_args or []),
    ]

    env = {**os.environ, "DISABLE_AUTOUPDATER": "1"}

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return ClaudeRunResult(
            output="",
            error=(
                f"binário do claude indisponível em {cli_path or CLAUDE_CLI} — "
                "pode estar atualizando, tenta de novo em alguns segundos"
            ),
            raw="",
        )

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        return ClaudeRunResult(
            output="",
            error=f"timeout ({timeout}s)",
            raw="",
        )

    stdout_text = stdout.decode("utf-8", errors="replace")
    stderr_text = stderr.decode("utf-8", errors="replace")

    if proc.returncode != 0:
        return ClaudeRunResult(
            output="",
            error=f"claude exit code {proc.returncode}",
            raw=stderr_text[:2000],
        )

    try:
        envelope = json.loads(stdout_text)
    except json.JSONDecodeError as e:
        return ClaudeRunResult(
            output="",
            error=f"envelope JSON inválido: {e}",
            raw=stdout_text[:2000],
        )

    usage = envelope.get("usage") or {}
    return ClaudeRunResult(
        output=envelope.get("result", ""),
        error=None,
        raw="",
        tokens_input=usage.get("input_tokens"),
        tokens_output=usage.get("output_tokens"),
        cost_usd=envelope.get("total_cost_usd"),
    )
