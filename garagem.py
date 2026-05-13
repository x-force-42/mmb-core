import json
from dataclasses import dataclass
from pathlib import Path

from claude_runner import load_system_prompt, run_claude_p
from config import GARAGEM_TIMEOUT_S
from parsing import extrair_json


PROMPT_PATH = Path(__file__).parent / "skills" / "garagem.md"


@dataclass
class GaragemResult:
    parsed: dict | None
    error: str | None
    raw: str


async def invocar_garagem(task: str, project_path: Path) -> GaragemResult:
    user_prompt = (
        f"Tarefa do Rick: {task}\n\n"
        "Explore o projeto e devolva o JSON do briefing."
    )

    r = await run_claude_p(
        user_prompt=user_prompt,
        system_prompt=load_system_prompt(PROMPT_PATH),
        cwd=project_path,
        timeout=GARAGEM_TIMEOUT_S,
        extra_args=["--allowed-tools", "Read,Glob,Grep"],
    )

    if r.error:
        return GaragemResult(parsed=None, error=r.error, raw=r.raw)

    try:
        parsed = extrair_json(r.output)
    except json.JSONDecodeError as e:
        return GaragemResult(
            parsed=None,
            error=f"briefing JSON inválido: {e}",
            raw=r.output,
        )

    return GaragemResult(parsed=parsed, error=None, raw=r.output)
