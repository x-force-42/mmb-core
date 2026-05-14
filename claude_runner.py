"""Wrapper único pra invocação do `claude -p`.

Centraliza:
- montagem do comando
- env com DISABLE_AUTOUPDATER (evita corrida com auto-update)
- captura de FileNotFoundError (binário sumiu durante reinstall)
- timeout
- check de returncode
- parse do envelope JSON do CLI
- retry curto na janela transiente do auto-updater (ver
  RETRY_DELAYS abaixo)

Cada caller (Garagem, Meeseeks) passa user_prompt, system_prompt,
cwd, timeout e flags específicas; recebe um ClaudeRunResult com
o `output` (envelope.result) ou um `error` estruturado.
"""

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from config import CLAUDE_CLI


# Delays (em segundos) ENTRE tentativas, aplicados apenas quando o
# erro casa com _is_transient_autoupdate. Total de tentativas =
# 1 + len(RETRY_DELAYS). Latência adicional no pior caso = soma dos
# valores (~4.5s).
#
# Por que valores fixos: o race do auto-updater dura tipicamente
# poucos segundos. Backoff curto cobre a maior parte sem virar
# espera longa quando o problema é outro.
RETRY_DELAYS: tuple[float, ...] = (1.5, 3.0)

# Marcador no stderr do CLI quando o symlink aponta pra um binário
# que não existe mais (sintoma típico de auto-update em curso).
_AUTOUPDATE_STDERR_HINT = "No claude executable found"


@dataclass
class ClaudeRunResult:
    output: str
    error: str | None
    raw: str
    tokens_input: int | None = None
    tokens_output: int | None = None
    cost_usd: float | None = None


def _is_transient_autoupdate(r: ClaudeRunResult) -> bool:
    """True quando o erro casa com o sintoma de auto-update em curso.

    Dois sinais possíveis:
    - FileNotFoundError no spawn → produz `error` contendo "indisponível"
      (ver _run_claude_p_once).
    - Exit code não-zero com stderr contendo "No claude executable found"
      → Node achou o wrapper mas não a versão dele pra esse Node.

    Qualquer outra falha (timeout, exit code genérico, envelope JSON
    inválido) NÃO é transiente — sinaliza problema real.
    """
    if r.error is None:
        return False
    if "indisponível" in r.error:
        return True
    if r.error.startswith("claude exit code") and _AUTOUPDATE_STDERR_HINT in r.raw:
        return True
    return False


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
    _retry_delays: tuple[float, ...] = RETRY_DELAYS,
) -> ClaudeRunResult:
    """Roda `claude -p` com output JSON e devolve o envelope parseado.

    Aplica retry curto se o erro casar com auto-update transiente
    (ver _is_transient_autoupdate); qualquer outra falha é devolvida
    imediatamente.

    Parâmetros são keyword-only pra deixar callsites legíveis.
    `_retry_delays` é underscored porque é hook interno pra teste —
    callers de produção devem usar o default.
    """
    attempts = 1 + len(_retry_delays)
    last: ClaudeRunResult | None = None

    for attempt_idx in range(attempts):
        if attempt_idx > 0:
            await asyncio.sleep(_retry_delays[attempt_idx - 1])

        last = await _run_claude_p_once(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            cwd=cwd,
            timeout=timeout,
            extra_args=extra_args,
            cli_path=cli_path,
        )

        if not _is_transient_autoupdate(last):
            return last

        if attempt_idx + 1 < attempts:
            print(
                f"[warn] claude_runner: tentativa {attempt_idx + 1}/{attempts} "
                f"caiu em estado transiente ({last.error!r}); retentando em "
                f"{_retry_delays[attempt_idx]:.1f}s",
                file=sys.stderr,
                flush=True,
            )

    assert last is not None  # loop sempre roda pelo menos 1x
    return ClaudeRunResult(
        output="",
        error=(
            f"auto-update do claude em curso — {attempts} tentativas "
            f"esgotadas. Último erro: {last.error}"
        ),
        raw=last.raw,
    )


async def _run_claude_p_once(
    *,
    user_prompt: str,
    system_prompt: str,
    cwd: Path,
    timeout: int,
    extra_args: list[str] | None,
    cli_path: str | None,
) -> ClaudeRunResult:
    """Uma única tentativa de spawn+comunicar+parsear. Sem retry.

    Separada de run_claude_p pra que o retry orquestre múltiplas
    chamadas sem duplicar lógica.
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
