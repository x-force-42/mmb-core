"""Testes das funções puras de formatters.py.

Cada classe agrupa testes da mesma função pública. Nada aqui depende
de Discord, asyncio, subprocess ou IO — roda em segundos.
"""

from pathlib import Path

import pytest

from formatters import (
    fmt_time,
    formatar_cleanup,
    formatar_falha_meeseeks,
    formatar_pushback,
    formatar_sucesso,
    meeseeks_decay,
    render_garagem_status,
    render_meeseeks_status,
)
from meeseeks import MeeseeksResult


# ─── helpers ─────────────────────────────────────────────────────────────

def _result(**kwargs) -> MeeseeksResult:
    """Monta MeeseeksResult com defaults razoáveis pra sucesso.
    Sobrescrever só os campos que importam pra cada teste."""
    defaults = dict(success=True, relatorio="OK", commits=["abc1234"])
    defaults.update(kwargs)
    return MeeseeksResult(**defaults)


# ─── fmt_time ────────────────────────────────────────────────────────────

class TestFmtTime:
    @pytest.mark.parametrize("seconds, expected", [
        (0, "00:00"),
        (5, "00:05"),
        (59, "00:59"),
        (60, "01:00"),
        (125, "02:05"),
        (3599, "59:59"),
        (3600, "60:00"),
    ])
    def test_formats_minutes_and_seconds_with_zero_padding(
        self, seconds, expected
    ):
        assert fmt_time(seconds) == expected

    def test_truncates_fractional_seconds(self):
        assert fmt_time(59.999) == "00:59"


# ─── meeseeks_decay ──────────────────────────────────────────────────────

class TestMeeseeksDecay:
    @pytest.mark.parametrize("seconds, expected_substr", [
        # faixa 0–3min: "Working on it!"
        (0, "Working on it"),
        (60, "Working on it"),
        (60 * 3 - 1, "Working on it"),
        # boundary: 3min entra na próxima faixa
        (60 * 3, "Caaaaan do"),
        (60 * 8 - 1, "Caaaaan do"),
        # boundary: 8min
        (60 * 8, "Oh boy"),
        (60 * 15 - 1, "Oh boy"),
        # boundary: 15min
        (60 * 15, "Existing is becoming pain"),
        (60 * 25 - 1, "Existing is becoming pain"),
        # boundary: 25min entra na última faixa, sem teto
        (60 * 25, "Pleeease let me finish"),
        (60 * 60, "Pleeease let me finish"),
        (60 * 60 * 5, "Pleeease let me finish"),
    ])
    def test_phrase_matches_time_range(self, seconds, expected_substr):
        assert expected_substr in meeseeks_decay(seconds)


# ─── render_garagem_status ───────────────────────────────────────────────

class TestRenderGaragemStatus:
    def test_includes_task_text(self):
        out = render_garagem_status("ajusta o botão", 0)
        assert "ajusta o botão" in out

    def test_includes_formatted_elapsed_in_backticks(self):
        out = render_garagem_status("x", 65)
        assert "`01:05`" in out

    def test_uses_garagem_voice(self):
        out = render_garagem_status("x", 0)
        assert "Garagem" in out


# ─── render_meeseeks_status ──────────────────────────────────────────────

class TestRenderMeeseeksStatus:
    def test_shows_branch_with_slug(self):
        out = render_meeseeks_status("fix-icon-collision", 30)
        assert "meeseeks/fix-icon-collision" in out

    def test_uses_decay_phrase_for_elapsed_time(self):
        # 5 minutos cai na faixa "Caaaaan do!"
        out = render_meeseeks_status("any-slug", 60 * 5)
        assert "Caaaaan do" in out

    def test_includes_formatted_elapsed_in_backticks(self):
        out = render_meeseeks_status("any-slug", 90)
        assert "`01:30`" in out


# ─── formatar_pushback ───────────────────────────────────────────────────

class TestFormatarPushback:
    def test_lists_duvidas_as_bullets(self):
        briefing = {"duvidas_pro_rick": ["onde fica X?", "qual cor?"]}
        out = formatar_pushback(briefing)
        assert "- onde fica X?" in out
        assert "- qual cor?" in out

    def test_fallback_when_no_duvidas_key(self):
        out = formatar_pushback({})
        assert "sem dúvidas listadas" in out

    def test_fallback_when_duvidas_empty_list(self):
        out = formatar_pushback({"duvidas_pro_rick": []})
        assert "sem dúvidas listadas" in out

    def test_uses_garagem_voice_in_header(self):
        out = formatar_pushback({})
        assert "Rick" in out
        assert "Meeseeks" in out


# ─── formatar_cleanup ────────────────────────────────────────────────────

class TestFormatarCleanup:
    def test_returns_empty_when_worktree_is_none(self):
        r = _result(worktree=None, branch="meeseeks/x")
        assert formatar_cleanup(r, Path("/p")) == ""

    def test_returns_empty_when_branch_is_none(self):
        r = _result(worktree=Path("/p/.worktrees/x"), branch=None)
        assert formatar_cleanup(r, Path("/p")) == ""

    def test_uses_relative_path_when_worktree_inside_target(self):
        target = Path("/home/user/proj")
        wt = target / ".worktrees" / "fix-x"
        r = _result(worktree=wt, branch="meeseeks/fix-x")
        out = formatar_cleanup(r, target)
        assert ".worktrees/fix-x" in out

    def test_uses_absolute_path_when_worktree_outside_target(self):
        target = Path("/home/user/proj")
        wt = Path("/tmp/somewhere")
        r = _result(worktree=wt, branch="meeseeks/x")
        out = formatar_cleanup(r, target)
        assert str(wt) in out

    def test_includes_git_worktree_remove_and_branch_delete(self):
        r = _result(
            worktree=Path("/p/.worktrees/x"),
            branch="meeseeks/x",
        )
        out = formatar_cleanup(r, Path("/p"))
        assert "git worktree remove" in out
        assert "git branch -D meeseeks/x" in out


# ─── formatar_sucesso ────────────────────────────────────────────────────

class TestFormatarSucesso:
    def test_includes_relatorio_dev_url_and_cleanup(self):
        r = _result(
            relatorio="missão cumprida.",
            worktree=Path("/p/.worktrees/x"),
            branch="meeseeks/x",
        )
        out = formatar_sucesso(r, dev_port=5173, target_path=Path("/p"))
        assert "missão cumprida." in out
        assert "http://localhost:5173" in out
        assert "git worktree remove" in out

    def test_fallback_when_relatorio_empty(self):
        r = _result(
            relatorio="",
            worktree=Path("/p/.worktrees/x"),
            branch="meeseeks/x",
        )
        out = formatar_sucesso(r, dev_port=5173, target_path=Path("/p"))
        assert "não devolveu relatório" in out

    def test_worktree_name_appears(self):
        r = _result(
            relatorio="x",
            worktree=Path("/p/.worktrees/my-slug"),
            branch="meeseeks/my-slug",
        )
        out = formatar_sucesso(r, dev_port=5173, target_path=Path("/p"))
        assert "my-slug" in out


# ─── formatar_falha_meeseeks ─────────────────────────────────────────────

class TestFormatarFalhaMeeseeks:
    def test_uses_meeseeks_failure_voice(self):
        r = _result(success=False, relatorio="", error="timeout (1800s)")
        out = formatar_falha_meeseeks(r, Path("/p"))
        assert "Existing is pain" in out

    def test_shows_error_message(self):
        r = _result(success=False, relatorio="", error="exit code 2")
        out = formatar_falha_meeseeks(r, Path("/p"))
        assert "exit code 2" in out

    def test_shows_partial_relatorio_when_present(self):
        r = _result(
            success=False,
            relatorio="cheguei a editar X mas npm test falhou",
            error="nenhum commit foi criado",
        )
        out = formatar_falha_meeseeks(r, Path("/p"))
        assert "cheguei a editar X" in out

    def test_shows_raw_when_relatorio_empty(self):
        r = _result(
            success=False,
            relatorio="",
            error="claude exit code 1",
            raw="some stderr output",
        )
        out = formatar_falha_meeseeks(r, Path("/p"))
        assert "some stderr output" in out

    def test_truncates_raw_to_1200_chars(self):
        r = _result(
            success=False,
            relatorio="",
            error="boom",
            raw="x" * 5000,
        )
        out = formatar_falha_meeseeks(r, Path("/p"))
        assert "x" * 1200 in out
        assert "x" * 1201 not in out

    def test_includes_cleanup_when_worktree_present(self):
        r = _result(
            success=False,
            relatorio="x",
            error="boom",
            worktree=Path("/p/.worktrees/x"),
            branch="meeseeks/x",
        )
        out = formatar_falha_meeseeks(r, Path("/p"))
        assert "git worktree remove" in out
