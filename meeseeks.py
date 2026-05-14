import asyncio
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from claude_runner import load_system_prompt, run_claude_p
from config import MEESEEKS_DEV_PORT, MEESEEKS_TIMEOUT_S


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
    tokens_input: int | None = None
    tokens_output: int | None = None
    cost_usd: float | None = None
    diff_added: int | None = None
    diff_deleted: int | None = None
    diff_files: int | None = None


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


def _parse_shortstat(text: str) -> tuple[int, int, int]:
    """Parsea a linha de `git diff --shortstat`.

    Exemplo de entrada: "3 files changed, 42 insertions(+), 7 deletions(-)"
    Pode vir sem `insertions` ou sem `deletions` quando o diff é só de um
    lado. Vazio quando não há diff.
    """
    import re
    files   = int(m.group(1)) if (m := re.search(r"(\d+) files? changed", text)) else 0
    added   = int(m.group(1)) if (m := re.search(r"(\d+) insertion",      text)) else 0
    deleted = int(m.group(1)) if (m := re.search(r"(\d+) deletion",       text)) else 0
    return added, deleted, files


async def _diff_stats(worktree: Path, base: str = "master") -> tuple[int, int, int]:
    """Retorna (added, deleted, files) do diff acumulado na branch."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "diff", "--shortstat", f"{base}..HEAD",
            cwd=str(worktree),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return _parse_shortstat(stdout.decode().strip())
    except Exception:
        return 0, 0, 0


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

    r = await run_claude_p(
        user_prompt=_montar_user_prompt(briefing, worktree, branch),
        system_prompt=load_system_prompt(PROMPT_PATH),
        cwd=worktree,
        timeout=MEESEEKS_TIMEOUT_S,
        extra_args=["--dangerously-skip-permissions"],
    )

    if r.error:
        return MeeseeksResult(
            success=False,
            relatorio="",
            worktree=worktree,
            branch=branch,
            error=r.error,
            raw=r.raw,
        )

    relatorio = r.output
    commits = await _list_commits(worktree)
    success = bool(commits)
    added, deleted, files = await _diff_stats(worktree) if success else (None, None, None)

    return MeeseeksResult(
        success=success,
        relatorio=relatorio.strip(),
        commits=commits,
        worktree=worktree,
        branch=branch,
        error=None if success else "nenhum commit foi criado",
        raw=relatorio,
        tokens_input=r.tokens_input,
        tokens_output=r.tokens_output,
        cost_usd=r.cost_usd,
        diff_added=added,
        diff_deleted=deleted,
        diff_files=files,
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
