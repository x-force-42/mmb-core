"""Testes de meeseeks: _montar_user_prompt (pura) e invocar_meeseeks
(orquestração com mocks).

Não cobre setup_worktree nem _list_commits — esses tocam git/FS e vão
em tests/integration depois.
"""

import subprocess
from pathlib import Path

import meeseeks
from claude_runner import ClaudeRunResult
from meeseeks import (
    MeeseeksResult,
    _montar_user_prompt,
    _parse_shortstat,
    invocar_meeseeks,
)


# ─── _montar_user_prompt (pura) ──────────────────────────────────────────

class TestMontarUserPrompt:
    def _full_briefing(self):
        return {
            "prompt_meeseeks": "faz a refatoração X",
            "criterio_de_pronto": "teste foo passa",
            "arquivos_alvo": ["src/a.ts", "src/b.ts"],
            "commit_tipo": "refactor",
            "commit_descricao": "extract foo helper",
        }

    def test_includes_briefing_body(self):
        out = _montar_user_prompt(
            self._full_briefing(),
            worktree=Path("/p/.worktrees/x"),
            branch="meeseeks/x",
        )
        assert "faz a refatoração X" in out

    def test_includes_worktree_and_branch(self):
        out = _montar_user_prompt(
            self._full_briefing(),
            worktree=Path("/p/.worktrees/x"),
            branch="meeseeks/x",
        )
        assert "/p/.worktrees/x" in out
        assert "meeseeks/x" in out

    def test_includes_commit_message_in_conventional_format(self):
        out = _montar_user_prompt(
            self._full_briefing(),
            worktree=Path("/p/.worktrees/x"),
            branch="meeseeks/x",
        )
        assert "refactor: extract foo helper" in out

    def test_includes_criterio_de_pronto(self):
        out = _montar_user_prompt(
            self._full_briefing(),
            worktree=Path("/p/.worktrees/x"),
            branch="meeseeks/x",
        )
        assert "teste foo passa" in out

    def test_lists_arquivos_alvo_as_bullets(self):
        out = _montar_user_prompt(
            self._full_briefing(),
            worktree=Path("/p/.worktrees/x"),
            branch="meeseeks/x",
        )
        assert "`src/a.ts`" in out
        assert "`src/b.ts`" in out

    def test_uses_fallback_when_arquivos_alvo_empty(self):
        b = self._full_briefing()
        b["arquivos_alvo"] = []
        out = _montar_user_prompt(b, Path("/p/x"), "meeseeks/x")
        assert "nenhum identificado pela Garagem" in out

    def test_uses_fallback_when_criterio_missing(self):
        b = self._full_briefing()
        del b["criterio_de_pronto"]
        out = _montar_user_prompt(b, Path("/p/x"), "meeseeks/x")
        assert "não informado" in out


# ─── helpers de mock pra invocar_meeseeks ────────────────────────────────

def _patch_runner(monkeypatch, result: ClaudeRunResult):
    async def fake(**kwargs):
        return result
    monkeypatch.setattr(meeseeks, "run_claude_p", fake)


def _patch_loader(monkeypatch):
    monkeypatch.setattr(
        meeseeks, "load_system_prompt", lambda path: "fake meeseeks prompt"
    )


def _patch_worktree(monkeypatch, worktree: Path, branch: str):
    def fake(project_path, slug, base="master"):
        return worktree, branch
    monkeypatch.setattr(meeseeks, "setup_worktree", fake)


def _patch_worktree_raises(monkeypatch, exc):
    def fake(project_path, slug, base="master"):
        raise exc
    monkeypatch.setattr(meeseeks, "setup_worktree", fake)


def _patch_list_commits(monkeypatch, commits):
    async def fake(worktree, base="master"):
        return commits
    monkeypatch.setattr(meeseeks, "_list_commits", fake)


def _patch_diff_stats(monkeypatch, stats=(0, 0, 0)):
    async def fake(worktree, base="master"):
        return stats
    monkeypatch.setattr(meeseeks, "_diff_stats", fake)


def _briefing(slug="add-x") -> dict:
    return {
        "slug": slug,
        "prompt_meeseeks": "faz X",
        "commit_tipo": "feat",
        "commit_descricao": "add x",
        "criterio_de_pronto": "teste passa",
    }


# ─── invocar_meeseeks ────────────────────────────────────────────────────

class TestInvocarMeeseeksGuards:
    async def test_returns_error_when_slug_absent(self, monkeypatch):
        r = await invocar_meeseeks({"prompt_meeseeks": "x"}, Path("/p"))
        assert r.success is False
        assert "slug" in r.error
        assert r.worktree is None

    async def test_returns_error_when_slug_empty_string(self, monkeypatch):
        r = await invocar_meeseeks({"slug": "   "}, Path("/p"))
        assert r.success is False
        assert "slug" in r.error


class TestInvocarMeeseeksWorktreeFailure:
    async def test_propagates_calledprocesserror_as_error(self, monkeypatch):
        _patch_loader(monkeypatch)
        err = subprocess.CalledProcessError(
            returncode=128,
            cmd=["git", "worktree", "add"],
            stderr="fatal: branch already exists",
        )
        _patch_worktree_raises(monkeypatch, err)

        r = await invocar_meeseeks(_briefing(), Path("/p"))

        assert r.success is False
        assert "falha ao criar worktree" in r.error
        assert "branch already exists" in r.error

    async def test_propagates_oserror_as_error(self, monkeypatch):
        _patch_loader(monkeypatch)
        _patch_worktree_raises(monkeypatch, OSError("disk full"))

        r = await invocar_meeseeks(_briefing(), Path("/p"))

        assert r.success is False
        assert "falha ao preparar worktree" in r.error
        assert "disk full" in r.error


class TestInvocarMeeseeksClaudeFailure:
    async def test_propagates_runner_error(self, monkeypatch):
        _patch_loader(monkeypatch)
        _patch_worktree(
            monkeypatch, Path("/p/.worktrees/x"), "meeseeks/x"
        )
        _patch_runner(
            monkeypatch,
            ClaudeRunResult(
                output="", error="timeout (1800s)", raw="",
            ),
        )

        r = await invocar_meeseeks(_briefing(), Path("/p"))

        assert r.success is False
        assert r.error == "timeout (1800s)"
        # worktree/branch são preenchidos mesmo no erro do claude
        assert r.worktree == Path("/p/.worktrees/x")
        assert r.branch == "meeseeks/x"


class TestInvocarMeeseeksNoCommits:
    async def test_success_false_when_no_commits_created(self, monkeypatch):
        _patch_loader(monkeypatch)
        _patch_worktree(
            monkeypatch, Path("/p/.worktrees/x"), "meeseeks/x"
        )
        _patch_runner(
            monkeypatch,
            ClaudeRunResult(
                output="cheguei a editar mas npm test falhou",
                error=None,
                raw="",
            ),
        )
        _patch_list_commits(monkeypatch, [])

        r = await invocar_meeseeks(_briefing(), Path("/p"))

        assert r.success is False
        assert "nenhum commit" in r.error
        assert r.relatorio == "cheguei a editar mas npm test falhou"
        assert r.commits == []


class TestInvocarMeeseeksSuccess:
    async def test_success_when_commits_created(self, monkeypatch):
        _patch_loader(monkeypatch)
        _patch_worktree(
            monkeypatch, Path("/p/.worktrees/add-x"), "meeseeks/add-x"
        )
        _patch_runner(
            monkeypatch,
            ClaudeRunResult(
                output="✨ tudo certo, chefe.", error=None, raw="",
            ),
        )
        _patch_list_commits(monkeypatch, ["abc1234", "def5678"])

        r = await invocar_meeseeks(_briefing(), Path("/p"))

        assert r.success is True
        assert r.error is None
        assert r.relatorio == "✨ tudo certo, chefe."
        assert r.commits == ["abc1234", "def5678"]
        assert r.worktree == Path("/p/.worktrees/add-x")
        assert r.branch == "meeseeks/add-x"

    async def test_strips_whitespace_around_relatorio(self, monkeypatch):
        _patch_loader(monkeypatch)
        _patch_worktree(
            monkeypatch, Path("/p/.worktrees/x"), "meeseeks/x"
        )
        _patch_runner(
            monkeypatch,
            ClaudeRunResult(
                output="\n\n  relatório  \n", error=None, raw="",
            ),
        )
        _patch_list_commits(monkeypatch, ["abc1234"])

        r = await invocar_meeseeks(_briefing(), Path("/p"))
        assert r.relatorio == "relatório"


class TestPropagatesUsageAndCost:
    """Trava propagação de tokens/cost/diff stats do runner pro
    MeeseeksResult — campos que silenciariam None se o wiring quebrasse."""

    async def test_propagates_tokens_cost_and_diff_on_success(self, monkeypatch):
        _patch_loader(monkeypatch)
        _patch_worktree(
            monkeypatch, Path("/p/.worktrees/x"), "meeseeks/x"
        )
        _patch_runner(
            monkeypatch,
            ClaudeRunResult(
                output="ok", error=None, raw="",
                tokens_input=8000, tokens_output=2000, cost_usd=0.048,
            ),
        )
        _patch_list_commits(monkeypatch, ["abc1234"])
        _patch_diff_stats(monkeypatch, stats=(42, 7, 3))

        r = await invocar_meeseeks(_briefing(), Path("/p"))

        assert r.tokens_input == 8000
        assert r.tokens_output == 2000
        assert r.cost_usd == 0.048
        assert r.diff_added == 42
        assert r.diff_deleted == 7
        assert r.diff_files == 3

    async def test_diff_stats_none_when_no_commits(self, monkeypatch):
        _patch_loader(monkeypatch)
        _patch_worktree(
            monkeypatch, Path("/p/.worktrees/x"), "meeseeks/x"
        )
        _patch_runner(
            monkeypatch,
            ClaudeRunResult(
                output="ok", error=None, raw="",
                tokens_input=100, tokens_output=20, cost_usd=0.002,
            ),
        )
        _patch_list_commits(monkeypatch, [])
        _patch_diff_stats(monkeypatch, stats=(99, 99, 99))

        r = await invocar_meeseeks(_briefing(), Path("/p"))

        # sem commits → não chama diff_stats, campos ficam None
        assert r.diff_added is None
        assert r.diff_deleted is None
        assert r.diff_files is None
        # mas tokens/custo continuam vindo do runner
        assert r.tokens_input == 100
        assert r.cost_usd == 0.002


# ─── _parse_shortstat (pura) ─────────────────────────────────────────────

class TestParseShortstat:
    """Outputs reais do git diff --shortstat. Sem mock de subprocess —
    testa só o parsing. Se o git mudar o formato, esses testes quebram
    cedo (e nãopassam a vida sendo (0, 0, 0))."""

    def test_full_line_with_inserts_and_deletes(self):
        text = " 3 files changed, 42 insertions(+), 7 deletions(-)"
        assert _parse_shortstat(text) == (42, 7, 3)

    def test_single_file_singular_word(self):
        text = " 1 file changed, 5 insertions(+), 2 deletions(-)"
        assert _parse_shortstat(text) == (5, 2, 1)

    def test_only_insertions(self):
        text = " 2 files changed, 10 insertions(+)"
        assert _parse_shortstat(text) == (10, 0, 2)

    def test_only_deletions(self):
        text = " 1 file changed, 8 deletions(-)"
        assert _parse_shortstat(text) == (0, 8, 1)

    def test_single_insertion_singular_word(self):
        text = " 1 file changed, 1 insertion(+)"
        assert _parse_shortstat(text) == (1, 0, 1)

    def test_single_deletion_singular_word(self):
        text = " 1 file changed, 1 deletion(-)"
        assert _parse_shortstat(text) == (0, 1, 1)

    def test_empty_text_returns_zeros(self):
        assert _parse_shortstat("") == (0, 0, 0)

    def test_unrelated_text_returns_zeros(self):
        # garante que não captura nada de texto que parece similar
        assert _parse_shortstat("nothing to report here") == (0, 0, 0)

    def test_large_numbers(self):
        text = " 127 files changed, 12345 insertions(+), 6789 deletions(-)"
        assert _parse_shortstat(text) == (12345, 6789, 127)
