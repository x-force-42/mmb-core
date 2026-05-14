"""Testes dos handlers /project (add/list/remove) do bot.

Os handlers do bot são decorados com @app_commands.command. discord.py
expõe a função original via `.callback` — chamamos ela diretamente
com um mock de Interaction e um RunLogger real em tmp_path.

Não exercitamos sync/sign-on do Discord; testamos a fachada fina
sobre `_logger`.
"""

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# Setup mínimo de env pra importar config.py sem ele explodir.
os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token-fake")


@pytest.fixture
def repo_path(tmp_path):
    repo = tmp_path / "fake-repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    return repo


@pytest.fixture
def fresh_logger(tmp_path, monkeypatch):
    """Substitui o _logger do módulo bot por um RunLogger em tmp_path.
    Faz import tardio do bot pra herdar a substituição."""
    from logger import RunLogger
    log = RunLogger(tmp_path / "test.db")

    import bot
    monkeypatch.setattr(bot, "_logger", log)
    return log


@pytest.fixture
def mock_interaction():
    """Mock discord.Interaction com response.send_message awaitable."""
    inter = MagicMock()
    inter.response = MagicMock()
    inter.response.send_message = AsyncMock()
    return inter


def _embed_titulo(send_message_mock) -> str:
    """Extrai o title do embed enviado em send_message(embed=...)."""
    _, kwargs = send_message_mock.call_args
    return kwargs["embed"].title


def _embed_desc(send_message_mock) -> str:
    _, kwargs = send_message_mock.call_args
    return kwargs["embed"].description or ""


class TestProjectAdd:
    @pytest.mark.asyncio
    async def test_happy_path_cadastra_e_responde(
        self, fresh_logger, mock_interaction, repo_path
    ):
        import bot
        await bot.project_add.callback(
            mock_interaction,
            path=str(repo_path),
            slug="meu-app",
            name="",
            mode=None,
        )
        # Persistiu
        assert fresh_logger.get_project_by_slug("meu-app") is not None
        # Respondeu com embed de sucesso
        assert "cadastrado" in _embed_titulo(mock_interaction.response.send_message)

    @pytest.mark.asyncio
    async def test_path_inexistente_responde_erro_ephemeral(
        self, fresh_logger, mock_interaction, tmp_path
    ):
        import bot
        await bot.project_add.callback(
            mock_interaction,
            path=str(tmp_path / "nao-existe"),
            slug="x",
            name="",
            mode=None,
        )
        _, kwargs = mock_interaction.response.send_message.call_args
        assert kwargs.get("ephemeral") is True
        assert "não cadastrado" in kwargs["embed"].title

    @pytest.mark.asyncio
    async def test_slug_duplicado_responde_erro(
        self, fresh_logger, mock_interaction, repo_path
    ):
        import bot
        fresh_logger.register_project(slug="dup", path=str(repo_path))
        await bot.project_add.callback(
            mock_interaction,
            path=str(repo_path),
            slug="dup",
            name="",
            mode=None,
        )
        assert "não cadastrado" in _embed_titulo(
            mock_interaction.response.send_message
        )

    @pytest.mark.asyncio
    async def test_mode_construtor_persiste(
        self, fresh_logger, mock_interaction, repo_path
    ):
        import bot
        import discord
        from discord import app_commands

        choice = app_commands.Choice(name="construtor", value="construtor")
        await bot.project_add.callback(
            mock_interaction,
            path=str(repo_path),
            slug="ctor",
            name="",
            mode=choice,
        )
        proj = fresh_logger.get_project_by_slug("ctor")
        assert proj["mode"] == "construtor"


class TestProjectList:
    @pytest.mark.asyncio
    async def test_lista_vazia_orienta_usar_add(
        self, fresh_logger, mock_interaction
    ):
        import bot
        await bot.project_list.callback(mock_interaction)
        desc = _embed_desc(mock_interaction.response.send_message)
        assert "Nenhum projeto" in desc

    @pytest.mark.asyncio
    async def test_lista_traz_projetos_ativos(
        self, fresh_logger, mock_interaction, repo_path
    ):
        import bot
        fresh_logger.register_project(slug="alpha", path=str(repo_path))
        fresh_logger.register_project(slug="beta", path=str(repo_path))
        await bot.project_list.callback(mock_interaction)
        desc = _embed_desc(mock_interaction.response.send_message)
        assert "alpha" in desc
        assert "beta" in desc

    @pytest.mark.asyncio
    async def test_lista_esconde_inativos(
        self, fresh_logger, mock_interaction, repo_path
    ):
        import bot
        fresh_logger.register_project(slug="alpha", path=str(repo_path))
        fresh_logger.register_project(slug="beta", path=str(repo_path))
        fresh_logger.deactivate_project("beta")
        await bot.project_list.callback(mock_interaction)
        desc = _embed_desc(mock_interaction.response.send_message)
        assert "alpha" in desc
        assert "beta" not in desc


class TestProjectRemove:
    @pytest.mark.asyncio
    async def test_remove_existente_responde_ok(
        self, fresh_logger, mock_interaction, repo_path
    ):
        import bot
        fresh_logger.register_project(slug="x", path=str(repo_path))
        await bot.project_remove.callback(mock_interaction, slug="x")
        # Foi soft-deletado
        assert fresh_logger.get_project_by_slug("x")["active"] == 0
        assert "desativado" in _embed_titulo(
            mock_interaction.response.send_message
        )

    @pytest.mark.asyncio
    async def test_remove_inexistente_responde_erro_ephemeral(
        self, fresh_logger, mock_interaction
    ):
        import bot
        await bot.project_remove.callback(mock_interaction, slug="fantasma")
        _, kwargs = mock_interaction.response.send_message.call_args
        assert kwargs.get("ephemeral") is True
        assert "Nada" in kwargs["embed"].title

    @pytest.mark.asyncio
    async def test_remove_ja_inativo_responde_erro(
        self, fresh_logger, mock_interaction, repo_path
    ):
        import bot
        fresh_logger.register_project(slug="x", path=str(repo_path))
        fresh_logger.deactivate_project("x")
        await bot.project_remove.callback(mock_interaction, slug="x")
        _, kwargs = mock_interaction.response.send_message.call_args
        assert kwargs.get("ephemeral") is True
