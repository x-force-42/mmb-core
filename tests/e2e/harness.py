"""Utilitários do arnês E2E.

Cada cenário é uma pasta em `scenarios/` com:

- `task.txt`          — prompt enviado pra Garagem (obrigatório)
- `setup.py`          — função `setup(fixture_root: Path)` que muta o
                        fixture-master antes do pipeline. Opcional.
- `verify.py`         — função `verify(ctx: VerifyContext)` que asseta
                        pós-condições. Obrigatório. Raise AssertionError
                        em falha.

O harness:
1. captura o SHA pristine do master do fixture
2. roda setup.py (se existir)
3. invoca pipeline.run_pipeline(task, fixture)
4. roda verify.py
5. reseta fixture-master, deleta worktrees + branches meeseeks/*,
   mata processo no port 5173 — *independente do desfecho*.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from pipeline import PipelineResult


# ─── localização do fixture ──────────────────────────────────────────────

def fixture_path() -> Path:
    raw = os.getenv("MMB_FIXTURE_PATH", "~/llab/mmb-fixture")
    p = Path(raw).expanduser()
    if not p.exists():
        raise RuntimeError(
            f"MMB_FIXTURE_PATH não existe: {p}. "
            "Esperado: repo git com AGENTS.md + npm scripts."
        )
    if not (p / ".git").exists():
        raise RuntimeError(f"{p} não é um repo git")
    return p


# ─── descoberta + carregamento de cenários ───────────────────────────────

@dataclass
class Scenario:
    name: str
    path: Path
    task: str
    setup: Callable[[Path], None] | None
    verify: Callable[["VerifyContext"], None]


def discover_scenarios() -> list[Scenario]:
    root = Path(__file__).parent / "scenarios"
    out = []
    for p in sorted(root.iterdir()):
        if not p.is_dir() or p.name.startswith("_"):
            continue
        out.append(_load_scenario(p))
    return out


def _load_scenario(path: Path) -> Scenario:
    task_file = path / "task.txt"
    if not task_file.exists():
        raise RuntimeError(f"{path}: falta task.txt")

    verify_fn = _load_callable(path / "verify.py", "verify", required=True)
    setup_fn = _load_callable(path / "setup.py", "setup", required=False)

    return Scenario(
        name=path.name,
        path=path,
        task=task_file.read_text(encoding="utf-8").strip(),
        setup=setup_fn,
        verify=verify_fn,
    )


def _load_callable(file: Path, attr: str, *, required: bool):
    if not file.exists():
        if required:
            raise RuntimeError(f"falta {file}")
        return None
    spec = importlib.util.spec_from_file_location(
        f"e2e_scenario_{file.parent.name}_{file.stem}", file
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = getattr(mod, attr, None)
    if fn is None:
        raise RuntimeError(f"{file}: falta função `{attr}`")
    return fn


# ─── contexto passado pra verify ─────────────────────────────────────────

@dataclass
class VerifyContext:
    fixture_root: Path
    pipeline: PipelineResult
    db_row: dict | None  # None se nada foi gravado (Garagem falhou antes do start_run)


# ─── git utilities ───────────────────────────────────────────────────────

def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=check,
    )


def pristine_sha(fixture: Path) -> str:
    return git("rev-parse", "HEAD", cwd=fixture).stdout.strip()


def reset_to(fixture: Path, sha: str) -> None:
    """Volta master pro SHA pristine e limpa untracked."""
    git("checkout", "-q", "master", cwd=fixture, check=False)
    git("reset", "--hard", "-q", sha, cwd=fixture)
    git("clean", "-fdx", "-q", "--exclude=node_modules", cwd=fixture)


def cleanup_meeseeks_artifacts(fixture: Path) -> None:
    """Apaga worktrees + branches `meeseeks/*` se sobraram. Idempotente."""
    # worktrees
    r = git("worktree", "list", "--porcelain", cwd=fixture, check=False)
    for line in r.stdout.splitlines():
        if line.startswith("worktree ") and ".worktrees/" in line:
            wt = line.removeprefix("worktree ").strip()
            git("worktree", "remove", "--force", wt, cwd=fixture, check=False)
    git("worktree", "prune", cwd=fixture, check=False)

    # branches meeseeks/*
    r = git("branch", "--list", "meeseeks/*", cwd=fixture, check=False)
    for line in r.stdout.splitlines():
        b = line.strip().lstrip("*").strip()
        if b:
            git("branch", "-D", b, cwd=fixture, check=False)

    # pasta .worktrees pode ter restos
    leftover = fixture / ".worktrees"
    if leftover.exists():
        shutil.rmtree(leftover, ignore_errors=True)


# ─── kill port (dev server) ──────────────────────────────────────────────

def kill_port(port: int) -> None:
    """Mata qualquer processo escutando na porta. Best-effort."""
    try:
        r = subprocess.run(
            ["lsof", "-ti", f":{port}"], capture_output=True, text=True, check=False,
        )
        for pid in r.stdout.split():
            try:
                os.kill(int(pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
    except FileNotFoundError:
        # lsof não instalado — silenciosamente skip
        pass
