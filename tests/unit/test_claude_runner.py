"""Testes de claude_runner.

- load_system_prompt: arquivo presente / vazio / ausente
- run_claude_p: mockamos asyncio.create_subprocess_exec pra cobrir
  FileNotFoundError (binário sumiu), timeout, exit code != 0,
  envelope JSON inválido e o caminho feliz.
"""

import asyncio
import json
from pathlib import Path

import pytest

import claude_runner
from claude_runner import ClaudeRunResult, load_system_prompt, run_claude_p


# ─── load_system_prompt ──────────────────────────────────────────────────

class TestLoadSystemPrompt:
    def test_reads_file_content(self, tmp_path):
        p = tmp_path / "prompt.md"
        p.write_text("hello world", encoding="utf-8")
        assert load_system_prompt(p) == "hello world"

    def test_strips_surrounding_whitespace(self, tmp_path):
        p = tmp_path / "prompt.md"
        p.write_text("\n\n  conteúdo  \n", encoding="utf-8")
        assert load_system_prompt(p) == "conteúdo"

    def test_raises_when_file_missing(self, tmp_path):
        p = tmp_path / "nope.md"
        with pytest.raises(RuntimeError, match="não encontrado"):
            load_system_prompt(p)

    def test_raises_when_file_empty(self, tmp_path):
        p = tmp_path / "empty.md"
        p.write_text("   \n\n", encoding="utf-8")
        with pytest.raises(RuntimeError, match="vazio"):
            load_system_prompt(p)


# ─── helpers de mock pro subprocess ──────────────────────────────────────

class _FakeProc:
    """Substituto async-compatible do asyncio.subprocess.Process.

    `communicate_delay` permite simular processo lento pra forçar
    timeout no run_claude_p.
    """

    def __init__(
        self,
        stdout: bytes = b"",
        stderr: bytes = b"",
        returncode: int = 0,
        communicate_delay: float = 0.0,
    ):
        self.stdout_bytes = stdout
        self.stderr_bytes = stderr
        self.returncode = returncode
        self.communicate_delay = communicate_delay
        self.killed = False

    async def communicate(self):
        if self.communicate_delay:
            await asyncio.sleep(self.communicate_delay)
        return self.stdout_bytes, self.stderr_bytes

    def kill(self):
        self.killed = True


def _patch_spawn(monkeypatch, proc=None, raise_exc=None):
    """Mocka asyncio.create_subprocess_exec. Use `raise_exc` pra
    simular FileNotFoundError; senão devolve `proc`."""
    async def fake(*args, **kwargs):
        if raise_exc:
            raise raise_exc
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake)


def _envelope(result: str) -> bytes:
    """Envelope JSON que o claude --output-format json devolve."""
    return json.dumps({"result": result}).encode("utf-8")


# ─── run_claude_p ────────────────────────────────────────────────────────

class TestRunClaudePBinaryMissing:
    async def test_returns_error_when_subprocess_raises_filenotfound(
        self, monkeypatch
    ):
        _patch_spawn(monkeypatch, raise_exc=FileNotFoundError())

        r = await run_claude_p(
            user_prompt="x",
            system_prompt="y",
            cwd=Path("/tmp"),
            timeout=5,
        )

        assert isinstance(r, ClaudeRunResult)
        assert r.output == ""
        assert "indisponível" in r.error
        assert "atualizando" in r.error


class TestRunClaudePTimeout:
    async def test_returns_timeout_error_when_communicate_exceeds(
        self, monkeypatch
    ):
        proc = _FakeProc(communicate_delay=0.1)
        _patch_spawn(monkeypatch, proc=proc)

        r = await run_claude_p(
            user_prompt="x",
            system_prompt="y",
            cwd=Path("/tmp"),
            timeout=0.01,
        )

        assert r.output == ""
        assert "timeout" in r.error
        assert proc.killed is True


class TestRunClaudePExitCode:
    async def test_returns_error_with_stderr_when_returncode_nonzero(
        self, monkeypatch
    ):
        proc = _FakeProc(
            stdout=b"",
            stderr=b"some stderr explosion",
            returncode=2,
        )
        _patch_spawn(monkeypatch, proc=proc)

        r = await run_claude_p(
            user_prompt="x",
            system_prompt="y",
            cwd=Path("/tmp"),
            timeout=5,
        )

        assert r.output == ""
        assert "exit code 2" in r.error
        assert "stderr explosion" in r.raw

    async def test_truncates_stderr_raw_to_2000_chars(self, monkeypatch):
        big = b"x" * 5000
        proc = _FakeProc(stdout=b"", stderr=big, returncode=1)
        _patch_spawn(monkeypatch, proc=proc)

        r = await run_claude_p(
            user_prompt="x", system_prompt="y",
            cwd=Path("/tmp"), timeout=5,
        )
        assert len(r.raw) == 2000


class TestRunClaudePEnvelopeInvalid:
    async def test_returns_error_when_envelope_not_json(self, monkeypatch):
        proc = _FakeProc(stdout=b"not a json envelope", returncode=0)
        _patch_spawn(monkeypatch, proc=proc)

        r = await run_claude_p(
            user_prompt="x", system_prompt="y",
            cwd=Path("/tmp"), timeout=5,
        )

        assert r.output == ""
        assert "envelope JSON inválido" in r.error
        assert "not a json envelope" in r.raw


class TestRunClaudePSuccess:
    async def test_returns_inner_result_on_success(self, monkeypatch):
        proc = _FakeProc(stdout=_envelope("o resultado interno"), returncode=0)
        _patch_spawn(monkeypatch, proc=proc)

        r = await run_claude_p(
            user_prompt="x", system_prompt="y",
            cwd=Path("/tmp"), timeout=5,
        )

        assert r.error is None
        assert r.raw == ""
        assert r.output == "o resultado interno"

    async def test_returns_empty_output_when_envelope_lacks_result_field(
        self, monkeypatch
    ):
        # envelope JSON válido mas sem "result"
        proc = _FakeProc(stdout=b'{"other": "field"}', returncode=0)
        _patch_spawn(monkeypatch, proc=proc)

        r = await run_claude_p(
            user_prompt="x", system_prompt="y",
            cwd=Path("/tmp"), timeout=5,
        )
        assert r.error is None
        assert r.output == ""


class TestRunClaudePCommandConstruction:
    """Garante que extra_args entram no cmd e DISABLE_AUTOUPDATER no env."""

    async def test_passes_extra_args_to_subprocess(self, monkeypatch):
        captured = {}

        async def fake_spawn(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return _FakeProc(stdout=_envelope("ok"))

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_spawn)

        await run_claude_p(
            user_prompt="prompt-user",
            system_prompt="prompt-sys",
            cwd=Path("/tmp"),
            timeout=5,
            extra_args=["--allowed-tools", "Read,Grep"],
            cli_path="/usr/bin/claude-fake",
        )

        cmd = list(captured["args"])
        assert cmd[0] == "/usr/bin/claude-fake"
        assert "--allowed-tools" in cmd
        assert "Read,Grep" in cmd
        assert "prompt-user" in cmd
        assert "prompt-sys" in cmd

    async def test_sets_disable_autoupdater_in_env(self, monkeypatch):
        captured = {}

        async def fake_spawn(*args, **kwargs):
            captured["env"] = kwargs.get("env", {})
            return _FakeProc(stdout=_envelope("ok"))

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_spawn)

        await run_claude_p(
            user_prompt="x", system_prompt="y",
            cwd=Path("/tmp"), timeout=5,
        )

        assert captured["env"].get("DISABLE_AUTOUPDATER") == "1"
