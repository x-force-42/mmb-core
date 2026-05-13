import asyncio
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from config import CLAUDE_CLI, GARAGEM_TIMEOUT_S


PROMPT_PATH = Path(__file__).parent / "skills" / "garagem.md"


def _carregar_system_prompt() -> str:
    """Lê o prompt do .md a cada chamada — permite iterar sem
    restartar o bot. Custo de IO é insignificante perto do tempo
    do claude -p."""
    if not PROMPT_PATH.exists():
        raise RuntimeError(
            f"Prompt da Garagem não encontrado em {PROMPT_PATH}"
        )
    texto = PROMPT_PATH.read_text(encoding="utf-8").strip()
    if not texto:
        raise RuntimeError(
            f"Prompt da Garagem está vazio: {PROMPT_PATH}"
        )
    return texto


@dataclass
class GaragemResult:
    parsed: dict | None
    error: str | None
    raw: str


def _extrair_json(texto: str) -> dict:
    """Tolera preâmbulo, sufixo, fences. Acha o primeiro objeto JSON
    balanceado e parseia."""
    t = texto.strip()

    # tira fences se vierem
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", t, re.DOTALL)
    if m:
        t = m.group(1).strip()

    # tenta parse direto (caminho feliz)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass

    # fallback: acha primeiro { e varre até } balanceado, respeitando strings
    start = t.find("{")
    if start == -1:
        raise json.JSONDecodeError("nenhum objeto JSON encontrado", t, 0)

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(t)):
        c = t[i]
        if escape:
            escape = False
            continue
        if c == "\\" and in_string:
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return json.loads(t[start:i + 1])

    raise json.JSONDecodeError("JSON desbalanceado", t, start)


async def invocar_garagem(task: str, project_path: Path) -> GaragemResult:
    user_prompt = (
        f"Tarefa do Rick: {task}\n\n"
        "Explore o projeto e devolva o JSON do briefing."
    )

    system_prompt = _carregar_system_prompt()

    cmd = [
        CLAUDE_CLI,
        "-p", user_prompt,
        "--allowed-tools", "Read,Glob,Grep",
        "--output-format", "json",
        "--append-system-prompt", system_prompt,
    ]

    # DISABLE_AUTOUPDATER evita janela em que o postinstall recria o
    # symlink do binário e o spawn cai em FileNotFoundError.
    env = {**os.environ, "DISABLE_AUTOUPDATER": "1"}

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(project_path),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return GaragemResult(
            parsed=None,
            error=(
                f"binário do claude indisponível em {CLAUDE_CLI} — "
                "pode estar atualizando, tenta de novo em alguns segundos"
            ),
            raw="",
        )

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=GARAGEM_TIMEOUT_S
        )
    except asyncio.TimeoutError:
        return GaragemResult(
            parsed=None,
            error=f"timeout ({GARAGEM_TIMEOUT_S}s)",
            raw="",
        )

    if proc.returncode != 0:
        return GaragemResult(
            parsed=None,
            error=f"claude exit code {proc.returncode}",
            raw=stderr.decode("utf-8", errors="replace"),
        )

    stdout_text = stdout.decode("utf-8", errors="replace")

    try:
        envelope = json.loads(stdout_text)
        inner = envelope.get("result", "")
    except json.JSONDecodeError as e:
        return GaragemResult(
            parsed=None,
            error=f"envelope JSON inválido: {e}",
            raw=stdout_text,
        )

    try:
        parsed = _extrair_json(inner)
    except json.JSONDecodeError as e:
        return GaragemResult(
            parsed=None,
            error=f"briefing JSON inválido: {e}",
            raw=inner,
        )

    return GaragemResult(parsed=parsed, error=None, raw=inner)