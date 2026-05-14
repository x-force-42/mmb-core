"""Testes de garagem.invocar_garagem.

Mocka claude_runner.run_claude_p (que vive sob garagem.run_claude_p
após o `from claude_runner import run_claude_p`) e cobre:
- erro propagado do runner
- output válido mas não é JSON de briefing
- briefing JSON válido
"""

import json
from pathlib import Path

import garagem
from claude_runner import ClaudeRunResult
from garagem import GaragemResult, invocar_garagem


def _patch_runner(monkeypatch, result: ClaudeRunResult):
    async def fake(**kwargs):
        return result
    monkeypatch.setattr(garagem, "run_claude_p", fake)


def _patch_loader(monkeypatch, prompt: str = "fake system prompt"):
    """Evita IO de skills/garagem.md durante os testes."""
    monkeypatch.setattr(
        garagem, "load_system_prompt", lambda path: prompt
    )


class TestPropagatesRunnerError:
    async def test_passes_through_runner_error(self, monkeypatch):
        _patch_loader(monkeypatch)
        _patch_runner(
            monkeypatch,
            ClaudeRunResult(output="", error="timeout (300s)", raw=""),
        )

        r = await invocar_garagem("any", Path("/p"))

        assert isinstance(r, GaragemResult)
        assert r.parsed is None
        assert r.error == "timeout (300s)"


class TestInvalidBriefingJson:
    async def test_returns_briefing_json_error_when_output_not_json(
        self, monkeypatch
    ):
        _patch_loader(monkeypatch)
        _patch_runner(
            monkeypatch,
            ClaudeRunResult(
                output="isso aqui não é JSON nenhum, só prosa solta.",
                error=None,
                raw="",
            ),
        )

        r = await invocar_garagem("x", Path("/p"))

        assert r.parsed is None
        assert "briefing JSON inválido" in r.error
        # raw fica com o output bruto pra debug
        assert "prosa solta" in r.raw


class TestSuccessParsedBriefing:
    async def test_parses_briefing_with_fences(self, monkeypatch):
        briefing = {
            "escopo_claro": True,
            "slug": "add-x",
            "prompt_meeseeks": "faz X",
            "commit_tipo": "feat",
            "commit_descricao": "add x",
        }
        _patch_loader(monkeypatch)
        _patch_runner(
            monkeypatch,
            ClaudeRunResult(
                output=f"```json\n{json.dumps(briefing)}\n```",
                error=None,
                raw="",
            ),
        )

        r = await invocar_garagem("x", Path("/p"))

        assert r.error is None
        assert r.parsed == briefing
        assert r.parsed["slug"] == "add-x"

    async def test_parses_briefing_with_prose_around_json(self, monkeypatch):
        briefing = {"escopo_claro": True, "slug": "x"}
        prose = (
            "Aqui está o briefing:\n"
            f"{json.dumps(briefing)}\n"
            "Espero que ajude."
        )
        _patch_loader(monkeypatch)
        _patch_runner(
            monkeypatch,
            ClaudeRunResult(output=prose, error=None, raw=""),
        )

        r = await invocar_garagem("x", Path("/p"))

        assert r.error is None
        assert r.parsed == briefing


class TestPropagatesUsageAndCost:
    """Sem esses asserts o bug de chave errada no envelope passava
    despercebido — runner devolvia None, garagem propagava None, ninguém
    verificava."""

    async def test_propagates_tokens_and_cost_on_success(self, monkeypatch):
        briefing = {"escopo_claro": True, "slug": "x"}
        _patch_loader(monkeypatch)
        _patch_runner(
            monkeypatch,
            ClaudeRunResult(
                output=json.dumps(briefing),
                error=None,
                raw="",
                tokens_input=1500,
                tokens_output=400,
                cost_usd=0.0234,
            ),
        )

        r = await invocar_garagem("x", Path("/p"))

        assert r.tokens_input == 1500
        assert r.tokens_output == 400
        assert r.cost_usd == 0.0234

    async def test_propagates_tokens_and_cost_on_runner_error(self, monkeypatch):
        _patch_loader(monkeypatch)
        _patch_runner(
            monkeypatch,
            ClaudeRunResult(
                output="", error="timeout", raw="",
                tokens_input=100, tokens_output=0, cost_usd=0.001,
            ),
        )

        r = await invocar_garagem("x", Path("/p"))

        assert r.error == "timeout"
        assert r.tokens_input == 100
        assert r.cost_usd == 0.001

    async def test_propagates_tokens_and_cost_on_invalid_briefing(
        self, monkeypatch
    ):
        _patch_loader(monkeypatch)
        _patch_runner(
            monkeypatch,
            ClaudeRunResult(
                output="prosa, não json", error=None, raw="",
                tokens_input=200, tokens_output=50, cost_usd=0.003,
            ),
        )

        r = await invocar_garagem("x", Path("/p"))

        assert "briefing JSON inválido" in r.error
        assert r.tokens_input == 200
        assert r.tokens_output == 50
        assert r.cost_usd == 0.003
