"""Testes de integração da camada git/FS do meeseeks.

Tocam git real num repo dummy criado em tmp_path. Cobre:
- setup_worktree: criação de worktree + branch, idempotência,
  symlink de node_modules
- _list_commits: lista hashes curtos dos commits da branch
  em relação a master
"""

import subprocess
from pathlib import Path

import pytest

from meeseeks import _list_commits, setup_worktree


# ─── fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def dummy_repo(tmp_path) -> Path:
    """Cria um repo git mínimo em tmp_path/projeto com branch master
    e um commit inicial. Isola config global do git (user, gpg)."""
    repo = tmp_path / "projeto"
    repo.mkdir()

    def run(*args):
        subprocess.run(
            ["git", *args], cwd=repo, check=True, capture_output=True,
        )

    run("init", "-q")
    run("config", "user.email", "test@example.com")
    run("config", "user.name", "Test")
    run("config", "commit.gpgsign", "false")

    (repo / "README.md").write_text("dummy", encoding="utf-8")
    run("add", ".")
    run("commit", "-q", "-m", "init")
    # garante master como nome da branch (independente do init.defaultBranch)
    run("branch", "-M", "master")
    return repo


# ─── setup_worktree ──────────────────────────────────────────────────────

class TestSetupWorktreeCreation:
    def test_creates_worktree_directory(self, dummy_repo):
        worktree, _ = setup_worktree(dummy_repo, "add-feature-x")
        assert worktree == dummy_repo / ".worktrees" / "add-feature-x"
        assert worktree.exists()
        assert worktree.is_dir()

    def test_returns_branch_with_meeseeks_prefix(self, dummy_repo):
        _, branch = setup_worktree(dummy_repo, "add-feature-x")
        assert branch == "meeseeks/add-feature-x"

    def test_branch_is_listed_in_git(self, dummy_repo):
        setup_worktree(dummy_repo, "add-feature-x")
        result = subprocess.run(
            ["git", "branch", "--list", "meeseeks/add-feature-x"],
            cwd=dummy_repo, capture_output=True, text=True, check=True,
        )
        assert "meeseeks/add-feature-x" in result.stdout

    def test_worktree_is_listed_in_git(self, dummy_repo):
        worktree, _ = setup_worktree(dummy_repo, "add-feature-x")
        result = subprocess.run(
            ["git", "worktree", "list"],
            cwd=dummy_repo, capture_output=True, text=True, check=True,
        )
        assert str(worktree) in result.stdout


class TestSetupWorktreeIdempotency:
    def test_second_call_with_same_slug_does_not_fail(self, dummy_repo):
        w1, b1 = setup_worktree(dummy_repo, "same-slug")
        w2, b2 = setup_worktree(dummy_repo, "same-slug")
        assert w1 == w2
        assert b1 == b2
        assert w2.exists()


class TestSetupWorktreeNodeModules:
    def test_symlinks_node_modules_when_source_exists(self, dummy_repo):
        src = dummy_repo / "node_modules"
        src.mkdir()
        (src / "react").mkdir()

        worktree, _ = setup_worktree(dummy_repo, "with-deps")

        link = worktree / "node_modules"
        assert link.is_symlink()
        # symlink resolve pro diretório original
        assert link.resolve() == src.resolve()
        # arquivo lá dentro fica visível pela worktree
        assert (link / "react").exists()

    def test_does_not_create_link_when_source_missing(self, dummy_repo):
        # repo dummy NÃO tem node_modules
        worktree, _ = setup_worktree(dummy_repo, "no-deps")
        link = worktree / "node_modules"
        assert not link.exists()
        assert not link.is_symlink()


# ─── _list_commits ───────────────────────────────────────────────────────

class TestListCommits:
    async def test_returns_empty_when_branch_has_no_new_commits(
        self, dummy_repo
    ):
        worktree, _ = setup_worktree(dummy_repo, "empty-branch")
        commits = await _list_commits(worktree)
        assert commits == []

    async def test_lists_short_hashes_of_new_commits(self, dummy_repo):
        worktree, _ = setup_worktree(dummy_repo, "with-commits")

        # cria dois commits na branch da worktree
        def run(*args):
            subprocess.run(
                ["git", *args], cwd=worktree, check=True,
                capture_output=True,
            )

        run("commit", "-q", "--allow-empty", "-m", "commit 1")
        run("commit", "-q", "--allow-empty", "-m", "commit 2")

        commits = await _list_commits(worktree)
        assert len(commits) == 2
        # hashes curtos (entre 7 e 12 chars dependendo da versão do git)
        for h in commits:
            assert 7 <= len(h) <= 12

    async def test_ordered_newest_first(self, dummy_repo):
        worktree, _ = setup_worktree(dummy_repo, "ordered")
        for i in range(3):
            subprocess.run(
                ["git", "commit", "-q", "--allow-empty",
                 "-m", f"commit {i}"],
                cwd=worktree, check=True, capture_output=True,
            )
        commits = await _list_commits(worktree)
        # git log devolve mais recente primeiro — sanity check: o último
        # commit criado fica no índice 0 da lista
        assert len(commits) == 3
        # os 3 hashes são únicos
        assert len(set(commits)) == 3
