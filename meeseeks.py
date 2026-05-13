import asyncio
import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from config import CLAUDE_CLI, MEESEEKS_DEV_PORT, MEESEEKS_TIMEOUT_S


PROMPT_PATH = Path(__file__).parent / "skills" / "meeseeks.md"


@dataclass
class MeeseeksResult:
    success: bool
    relatorio: str
    commits: list[str] = field(default_factory=list)
    worktree: Path | None = None
    branch: str | None = None
    error: str | None = None
    raw: str = ""


# ─── worktree ────────────────────────────────────────────────────────────

def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )


def setup_worktree(
    project_path: Path, slug: str, base: str = "master"
) -> tuple[Path, str]:
    """Cria worktree em <project>/.worktrees/<slug> com branch
    meeseeks/<slug>, symlinka node_modules. Idempotente: se a worktree
    já existe, devolve sem recriar."""
    worktree = project_path / ".worktrees" / slug
    branch = f"meeseeks/{slug}"

    if not worktree.exists():
        worktree.parent.mkdir(parents=True, exist_ok=True)
        _git(
            ["worktree", "add", "-b", branch, str(worktree), base],
            cwd=project_path,
        )

    src = project_path / "node_modules"
    dst = worktree / "node_modules"
    if src.exists() and not dst.exists():
        dst.symlink_to(src, target_is_directory=True)

    return worktree, branch


# ─── invocação do meeseeks ───────────────────────────────────────────────

def _carregar_system_prompt() -> str:
    if not PROMPT_PATH.exists():
        raise RuntimeError(f"Prompt do Meeseeks não encontrado em {PROMPT_PATH}")
    texto = PROMPT_PATH.read_text(encoding="utf-8").strip()
    if not texto:
        raise RuntimeError(f"Prompt do Meeseeks está vazio: {PROMPT_PATH}")
    return texto


def _montar_user_prompt(briefing: dict, worktree: Path, branch: str) -> str:
    arquivos = briefing.get("arquivos_alvo") or []
    bloco_arquivos = (
        "\n".join(f"- `{a}`" for a in arquivos)
        if arquivos else "_(nenhum identificado pela Garagem)_"
    )
    commit_msg = (
        f"{briefing.get('commit_tipo', '').strip()}: "
        f"{briefing.get('commit_descricao', '').strip()}"
    )
    return (
        "# Briefing da Garagem\n\n"
        f"{briefing.get('prompt_meeseeks', '').strip()}\n\n"
        "## Contexto operacional\n\n"
        f"- Worktree (você está aqui): `{worktree}`\n"
        f"- Branch: `{branch}` (baseada em `master`)\n"
        f"- Commit sugerido: `{commit_msg}`\n\n"
        "## Critério de pronto\n\n"
        f"{briefing.get('criterio_de_pronto', '_não informado_')}\n\n"
        "## Arquivos provavelmente afetados\n\n"
        f"{bloco_arquivos}\n\n"
        "Execute o pipeline definido no seu system prompt. "
        "Devolva o relatório markdown ao final."
    )


async def _list_commits(worktree: Path, base: str = "master") -> list[str]:
    """Hashes curtos dos commits feitos na branch além de master."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "log", "--format=%h", f"{base}..HEAD",
            cwd=str(worktree),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return [h for h in stdout.decode().strip().splitlines() if h]
    except FileNotFoundError:
        return []


async def invocar_meeseeks(
    briefing: dict, project_path: Path
) -> MeeseeksResult:
    slug = (briefing.get("slug") or "").strip()
    if not slug:
        return MeeseeksResult(
            success=False,
            relatorio="",
            error="Garagem não devolveu slug — sem como nomear worktree/branch",
        )

    try:
        worktree, branch = setup_worktree(project_path, slug)
    except subprocess.CalledProcessError as e:
        return MeeseeksResult(
            success=False,
            relatorio="",
            error=f"falha ao criar worktree: {e.stderr.strip() or e}",
        )
    except OSError as e:
        return MeeseeksResult(
            success=False,
            relatorio="",
            error=f"falha ao preparar worktree: {e}",
        )

    system_prompt = _carregar_system_prompt()
    user_prompt = _montar_user_prompt(briefing, worktree, branch)
    env = {**os.environ, "DISABLE_AUTOUPDATER": "1"}

    cmd = [
        CLAUDE_CLI,
        "-p", user_prompt,
        "--output-format", "json",
        "--append-system-prompt", system_prompt,
        "--dangerously-skip-permissions",
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(worktree),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return MeeseeksResult(
            success=False,
            relatorio="",
            worktree=worktree,
            branch=branch,
            error=(
                f"binário do claude indisponível em {CLAUDE_CLI} — "
                "pode estar atualizando, tenta de novo em alguns segundos"
            ),
        )

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=MEESEEKS_TIMEOUT_S
        )
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        return MeeseeksResult(
            success=False,
            relatorio="",
            worktree=worktree,
            branch=branch,
            error=f"timeout ({MEESEEKS_TIMEOUT_S}s)",
        )

    stdout_text = stdout.decode("utf-8", errors="replace")
    stderr_text = stderr.decode("utf-8", errors="replace")

    if proc.returncode != 0:
        return MeeseeksResult(
            success=False,
            relatorio="",
            worktree=worktree,
            branch=branch,
            error=f"claude exit code {proc.returncode}",
            raw=stderr_text[:2000],
        )

    try:
        envelope = json.loads(stdout_text)
        relatorio = envelope.get("result", "")
    except json.JSONDecodeError as e:
        return MeeseeksResult(
            success=False,
            relatorio="",
            worktree=worktree,
            branch=branch,
            error=f"envelope JSON inválido: {e}",
            raw=stdout_text[:2000],
        )

    commits = await _list_commits(worktree)
    success = bool(commits)

    return MeeseeksResult(
        success=success,
        relatorio=relatorio.strip(),
        commits=commits,
        worktree=worktree,
        branch=branch,
        error=None if success else "nenhum commit foi criado",
        raw=relatorio,
    )


# ─── dev server ──────────────────────────────────────────────────────────

_dev_proc: subprocess.Popen | None = None


def _kill_port(port: int) -> None:
    """Mata qualquer processo escutando na porta. Silencioso."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return
    for pid in result.stdout.strip().splitlines():
        try:
            subprocess.run(["kill", "-9", pid], timeout=2, check=False)
        except subprocess.SubprocessError:
            pass


def start_dev_server(worktree: Path, port: int | None = None) -> int:
    """Mata o dev anterior do bot + qualquer ocupante da porta,
    spawna `npm run dev -- --port <port>` em background. Devolve
    a porta usada."""
    global _dev_proc
    port = port or MEESEEKS_DEV_PORT

    stop_dev_server()
    _kill_port(port)

    _dev_proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "--port", str(port)],
        cwd=str(worktree),
        env={**os.environ},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return port


def stop_dev_server() -> None:
    global _dev_proc
    if _dev_proc is not None and _dev_proc.poll() is None:
        try:
            _dev_proc.terminate()
            _dev_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _dev_proc.kill()
        except ProcessLookupError:
            pass
    _dev_proc = None
