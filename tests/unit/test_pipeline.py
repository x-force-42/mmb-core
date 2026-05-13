"""Testes de pipeline.run_pipeline.

Mocka invocar_garagem, invocar_meeseeks e start_dev_server (em nível
do módulo pipeline) e verifica que cada combinação de resultados leva
à fase terminal correta.

São 6 fases possíveis: garagem_error, garagem_pushback, garagem_no_slug,
meeseeks_failure, dev_server_failure, success.
"""

from pathlib import Path

import pipeline
from garagem import GaragemResult
from meeseeks import MeeseeksResult


# ─── helpers de mock ─────────────────────────────────────────────────────

def _patch_garagem(monkeypatch, result: GaragemResult):
    async def fake(task, project_path):
        return result
    monkeypatch.setattr(pipeline, "invocar_garagem", fake)


def _patch_meeseeks(monkeypatch, result: MeeseeksResult):
    async def fake(briefing, project_path):
        return result
    monkeypatch.setattr(pipeline, "invocar_meeseeks", fake)


def _patch_dev_server(monkeypatch, port_or_exception):
    def fake(worktree):
        if isinstance(port_or_exception, BaseException):
            raise port_or_exception
        return port_or_exception
    monkeypatch.setattr(pipeline, "start_dev_server", fake)


def _briefing_ok(slug="add-x") -> dict:
    return {
        "escopo_claro": True,
        "slug": slug,
        "prompt_meeseeks": "faz X",
        "criterio_de_pronto": "teste y verde",
        "commit_tipo": "feat",
        "commit_descricao": "add x",
    }


# ─── fase 1: garagem_error ───────────────────────────────────────────────

class TestGaragemError:
    async def test_returns_garagem_error_phase(self, monkeypatch):
        g = GaragemResult(parsed=None, error="timeout (300s)", raw="")
        _patch_garagem(monkeypatch, g)

        result = await pipeline.run_pipeline("qualquer task", Path("/p"))

        assert result.phase == "garagem_error"
        assert result.garagem is g
        assert result.meeseeks is None
        assert result.dev_port is None
        assert result.dev_server_error is None

    async def test_does_not_call_meeseeks_or_dev_when_garagem_fails(
        self, monkeypatch
    ):
        called = {"meeseeks": False, "dev": False}

        async def fake_meeseeks(b, p):
            called["meeseeks"] = True
            return MeeseeksResult(success=True, relatorio="")

        def fake_dev(w):
            called["dev"] = True
            return 5173

        _patch_garagem(
            monkeypatch,
            GaragemResult(parsed=None, error="boom", raw=""),
        )
        monkeypatch.setattr(pipeline, "invocar_meeseeks", fake_meeseeks)
        monkeypatch.setattr(pipeline, "start_dev_server", fake_dev)

        await pipeline.run_pipeline("any", Path("/p"))

        assert not called["meeseeks"]
        assert not called["dev"]


# ─── fase 2: garagem_pushback ────────────────────────────────────────────

class TestGaragemPushback:
    async def test_returns_pushback_when_escopo_claro_false(self, monkeypatch):
        briefing = {
            "escopo_claro": False,
            "duvidas_pro_rick": ["onde fica X?"],
        }
        _patch_garagem(
            monkeypatch,
            GaragemResult(parsed=briefing, error=None, raw=""),
        )

        result = await pipeline.run_pipeline("vaga", Path("/p"))

        assert result.phase == "garagem_pushback"
        assert result.garagem.parsed["escopo_claro"] is False
        assert result.meeseeks is None

    async def test_returns_pushback_when_escopo_claro_absent(self, monkeypatch):
        # campo escopo_claro nem aparece no briefing
        _patch_garagem(
            monkeypatch,
            GaragemResult(parsed={"foo": "bar"}, error=None, raw=""),
        )

        result = await pipeline.run_pipeline("x", Path("/p"))
        assert result.phase == "garagem_pushback"

    async def test_returns_pushback_when_parsed_is_none(self, monkeypatch):
        # parsed=None com error=None é um caso fronteiriço — pipeline
        # interpreta como pushback porque get("escopo_claro") cai em falsy
        _patch_garagem(
            monkeypatch,
            GaragemResult(parsed=None, error=None, raw=""),
        )

        result = await pipeline.run_pipeline("x", Path("/p"))
        assert result.phase == "garagem_pushback"


# ─── fase 3: garagem_no_slug ─────────────────────────────────────────────

class TestGaragemNoSlug:
    async def test_returns_no_slug_when_slug_absent(self, monkeypatch):
        briefing = {"escopo_claro": True}  # sem slug
        _patch_garagem(
            monkeypatch,
            GaragemResult(parsed=briefing, error=None, raw=""),
        )

        result = await pipeline.run_pipeline("x", Path("/p"))
        assert result.phase == "garagem_no_slug"

    async def test_returns_no_slug_when_slug_whitespace(self, monkeypatch):
        briefing = {"escopo_claro": True, "slug": "   "}
        _patch_garagem(
            monkeypatch,
            GaragemResult(parsed=briefing, error=None, raw=""),
        )

        result = await pipeline.run_pipeline("x", Path("/p"))
        assert result.phase == "garagem_no_slug"


# ─── fase 4: meeseeks_failure ────────────────────────────────────────────

class TestMeeseeksFailure:
    async def test_returns_failure_when_no_commits(self, monkeypatch):
        _patch_garagem(
            monkeypatch,
            GaragemResult(parsed=_briefing_ok(), error=None, raw=""),
        )
        m = MeeseeksResult(
            success=False,
            relatorio="cheguei a editar mas npm test falhou",
            commits=[],
            worktree=Path("/p/.worktrees/add-x"),
            branch="meeseeks/add-x",
            error="nenhum commit foi criado",
        )
        _patch_meeseeks(monkeypatch, m)

        result = await pipeline.run_pipeline("x", Path("/p"))

        assert result.phase == "meeseeks_failure"
        assert result.meeseeks is m
        assert result.dev_port is None

    async def test_does_not_call_dev_when_meeseeks_fails(self, monkeypatch):
        _patch_garagem(
            monkeypatch,
            GaragemResult(parsed=_briefing_ok(), error=None, raw=""),
        )
        _patch_meeseeks(
            monkeypatch,
            MeeseeksResult(success=False, relatorio="", error="boom"),
        )

        dev_called = {"v": False}

        def fake_dev(w):
            dev_called["v"] = True
            return 5173

        monkeypatch.setattr(pipeline, "start_dev_server", fake_dev)

        await pipeline.run_pipeline("x", Path("/p"))
        assert not dev_called["v"]


# ─── fase 5: dev_server_failure ──────────────────────────────────────────

class TestDevServerFailure:
    async def test_returns_dev_server_failure_when_start_raises(
        self, monkeypatch
    ):
        _patch_garagem(
            monkeypatch,
            GaragemResult(parsed=_briefing_ok(), error=None, raw=""),
        )
        m = MeeseeksResult(
            success=True,
            relatorio="ok",
            commits=["abc1234"],
            worktree=Path("/p/.worktrees/add-x"),
            branch="meeseeks/add-x",
        )
        _patch_meeseeks(monkeypatch, m)
        _patch_dev_server(monkeypatch, FileNotFoundError("npm não achado"))

        result = await pipeline.run_pipeline("x", Path("/p"))

        assert result.phase == "dev_server_failure"
        assert result.meeseeks is m
        assert result.dev_port is None
        assert "npm não achado" in (result.dev_server_error or "")


# ─── fase 6: success ─────────────────────────────────────────────────────

class TestSuccess:
    async def test_returns_success_when_all_phases_ok(self, monkeypatch):
        _patch_garagem(
            monkeypatch,
            GaragemResult(parsed=_briefing_ok(), error=None, raw=""),
        )
        m = MeeseeksResult(
            success=True,
            relatorio="✨ done.",
            commits=["abc1234"],
            worktree=Path("/p/.worktrees/add-x"),
            branch="meeseeks/add-x",
        )
        _patch_meeseeks(monkeypatch, m)
        _patch_dev_server(monkeypatch, 5173)

        result = await pipeline.run_pipeline("x", Path("/p"))

        assert result.phase == "success"
        assert result.meeseeks is m
        assert result.dev_port == 5173
        assert result.dev_server_error is None

    async def test_propagates_dev_port_returned_by_start(self, monkeypatch):
        _patch_garagem(
            monkeypatch,
            GaragemResult(parsed=_briefing_ok(), error=None, raw=""),
        )
        _patch_meeseeks(
            monkeypatch,
            MeeseeksResult(success=True, relatorio="ok", commits=["a"]),
        )
        _patch_dev_server(monkeypatch, 8080)

        result = await pipeline.run_pipeline("x", Path("/p"))
        assert result.dev_port == 8080
