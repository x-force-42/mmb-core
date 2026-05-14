"""Testes dos embeds do Discord.

discord.Embed pode ser instanciado sem conexão. Verificamos title, cor
da barra lateral, conteúdo da description, e o comportamento de
overflow (anexar texto completo quando ultrapassa 4096 chars).
"""

from pathlib import Path

from embeds import (
    COR_AVISO,
    COR_FALHA,
    COR_GARAGEM,
    COR_MEESEEKS,
    COR_PUSHBACK,
    COR_SUCESSO,
    DESC_LIMIT,
    embed_dev_server_falhou,
    embed_garagem_engasgou,
    embed_garagem_no_slug,
    embed_garagem_pushback,
    embed_garagem_working,
    embed_meeseeks_falha,
    embed_meeseeks_spawn,
    embed_meeseeks_working,
    embed_project_erro,
    embed_project_list,
    embed_project_ok,
    embed_sucesso,
)
from meeseeks import MeeseeksResult


def _result(**kwargs) -> MeeseeksResult:
    defaults = dict(success=True, relatorio="OK", commits=["abc1234"])
    defaults.update(kwargs)
    return MeeseeksResult(**defaults)


# ─── status embeds (curtos) ──────────────────────────────────────────────

class TestEmbedGaragemWorking:
    def test_uses_garagem_color(self):
        e = embed_garagem_working("task", 0)
        assert e.color.value == COR_GARAGEM

    def test_title_invokes_garagem_voice(self):
        e = embed_garagem_working("task", 0)
        assert "Garagem" in e.title
        assert "cavando" in e.title

    def test_description_quotes_the_task(self):
        e = embed_garagem_working("ajustar botão", 0)
        assert "ajustar botão" in e.description

    def test_footer_shows_formatted_elapsed(self):
        e = embed_garagem_working("x", 90)
        assert e.footer.text == "01:30"


class TestEmbedGaragemEngasgou:
    def test_uses_failure_color(self):
        e = embed_garagem_engasgou("01:00", "timeout", "")
        assert e.color.value == COR_FALHA

    def test_includes_error_message(self):
        e = embed_garagem_engasgou("01:00", "timeout (300s)", "")
        assert "timeout (300s)" in e.description

    def test_appends_raw_excerpt_when_present(self):
        e = embed_garagem_engasgou("01:00", "exit 2", "stderr blowup")
        assert "stderr blowup" in e.description

    def test_omits_code_block_when_raw_empty(self):
        e = embed_garagem_engasgou("01:00", "boom", "")
        assert "```" not in e.description


class TestEmbedGaragemPushback:
    def test_uses_pushback_color(self):
        e = embed_garagem_pushback({"duvidas_pro_rick": ["x"]}, "00:30")
        assert e.color.value == COR_PUSHBACK

    def test_title_in_garagem_voice(self):
        e = embed_garagem_pushback({}, "00:30")
        assert "Rick" in e.title

    def test_description_lists_duvidas(self):
        e = embed_garagem_pushback(
            {"duvidas_pro_rick": ["onde X?", "qual cor?"]}, "00:30"
        )
        assert "onde X?" in e.description
        assert "qual cor?" in e.description

    def test_footer_shows_garagem_time(self):
        e = embed_garagem_pushback({}, "00:30")
        assert "00:30" in e.footer.text


class TestEmbedGaragemNoSlug:
    def test_uses_failure_color(self):
        e = embed_garagem_no_slug("00:30")
        assert e.color.value == COR_FALHA

    def test_mentions_slug_in_description(self):
        e = embed_garagem_no_slug("00:30")
        assert "slug" in e.description.lower()


class TestEmbedMeeseeksSpawn:
    def test_uses_meeseeks_color(self):
        e = embed_meeseeks_spawn("00:30")
        assert e.color.value == COR_MEESEEKS

    def test_title_uses_canonical_meeseeks_line(self):
        e = embed_meeseeks_spawn("00:30")
        assert "Meeseeks" in e.title
        assert "look at me" in e.title.lower()

    def test_description_references_garagem_time(self):
        e = embed_meeseeks_spawn("00:42")
        assert "00:42" in e.description


class TestEmbedMeeseeksWorking:
    def test_uses_meeseeks_color(self):
        e = embed_meeseeks_working("any-slug", 0)
        assert e.color.value == COR_MEESEEKS

    def test_title_uses_decay_phrase_by_elapsed(self):
        # 0–3min → "Working on it!"
        early = embed_meeseeks_working("x", 60)
        assert "Working on it" in early.title

        # 25min+ → "Pleeease let me finish..."
        late = embed_meeseeks_working("x", 60 * 30)
        assert "Pleeease" in late.title

    def test_description_includes_branch_with_slug(self):
        e = embed_meeseeks_working("fix-icon-collision", 30)
        assert "meeseeks/fix-icon-collision" in e.description

    def test_footer_shows_formatted_elapsed(self):
        e = embed_meeseeks_working("x", 65)
        assert e.footer.text == "01:05"


# ─── mensagens finais (podem estourar) ───────────────────────────────────

class TestEmbedMeeseeksFalha:
    def test_uses_failure_color(self):
        m = _result(success=False, error="boom")
        embed, _ = embed_meeseeks_falha(m, "01:00", Path("/p"))
        assert embed.color.value == COR_FALHA

    def test_no_overflow_for_short_relatorio(self):
        m = _result(success=False, relatorio="curto", error="boom")
        embed, overflow = embed_meeseeks_falha(m, "01:00", Path("/p"))
        assert overflow is None
        assert "Existing is pain" in embed.title

    def test_overflows_when_relatorio_huge(self):
        m = _result(
            success=False,
            relatorio="x" * (DESC_LIMIT + 100),
            error="boom",
        )
        embed, overflow = embed_meeseeks_falha(m, "01:00", Path("/p"))
        assert overflow is not None
        assert "continua no anexo" in embed.description
        # description respeitou limite do Discord
        assert len(embed.description) <= DESC_LIMIT
        # overflow tem o texto completo
        assert overflow.count("x") >= DESC_LIMIT


class TestEmbedDevServerFalhou:
    def test_uses_warning_color(self):
        m = _result(
            worktree=Path("/p/.worktrees/x"), branch="meeseeks/x"
        )
        embed, _ = embed_dev_server_falhou(
            m, RuntimeError("npm não achado"), "02:00", Path("/p")
        )
        assert embed.color.value == COR_AVISO

    def test_description_mentions_dev_failure_reason(self):
        m = _result(
            worktree=Path("/p/.worktrees/x"), branch="meeseeks/x"
        )
        embed, _ = embed_dev_server_falhou(
            m, RuntimeError("porta ocupada"), "02:00", Path("/p")
        )
        assert "porta ocupada" in embed.description


class TestEmbedSucesso:
    def test_uses_success_color(self):
        m = _result(
            worktree=Path("/p/.worktrees/x"), branch="meeseeks/x"
        )
        embed, _ = embed_sucesso(m, 5173, "03:00", Path("/p"))
        assert embed.color.value == COR_SUCESSO

    def test_title_celebrates(self):
        m = _result(
            worktree=Path("/p/.worktrees/x"), branch="meeseeks/x"
        )
        embed, _ = embed_sucesso(m, 5173, "03:00", Path("/p"))
        assert "Can do" in embed.title

    def test_description_contains_relatorio_and_dev_url_and_cleanup(self):
        m = _result(
            relatorio="missão cumprida.",
            worktree=Path("/p/.worktrees/x"),
            branch="meeseeks/x",
        )
        embed, overflow = embed_sucesso(m, 5173, "03:00", Path("/p"))
        assert overflow is None
        assert "missão cumprida." in embed.description
        assert "http://localhost:5173" in embed.description
        assert "git worktree remove" in embed.description

    def test_overflows_when_relatorio_huge(self):
        m = _result(
            relatorio="z" * (DESC_LIMIT + 500),
            worktree=Path("/p/.worktrees/x"),
            branch="meeseeks/x",
        )
        embed, overflow = embed_sucesso(m, 5173, "03:00", Path("/p"))
        assert overflow is not None
        assert "continua no anexo" in embed.description
        assert len(embed.description) <= DESC_LIMIT


# ─── /project ────────────────────────────────────────────────────────────

class TestProjectEmbeds:
    def test_ok_usa_cor_sucesso(self):
        e = embed_project_ok("ok", "tudo certo")
        assert e.color.value == COR_SUCESSO
        assert e.description == "tudo certo"

    def test_erro_usa_cor_falha(self):
        e = embed_project_erro("erro", "deu ruim")
        assert e.color.value == COR_FALHA

    def test_list_vazio_mostra_dica(self):
        e = embed_project_list([])
        assert "Nenhum projeto" in e.description
        assert "/project add" in e.description

    def test_list_com_projetos_lista_slugs(self):
        e = embed_project_list([
            {"slug": "a", "mode": "pontual", "path": "/a"},
            {"slug": "b", "mode": "construtor", "path": "/b"},
        ])
        assert "a" in e.description
        assert "b" in e.description
        assert "(2)" in e.title

    def test_list_trunca_em_25(self):
        muitos = [
            {"slug": f"s{i}", "mode": "pontual", "path": f"/p{i}"}
            for i in range(30)
        ]
        e = embed_project_list(muitos)
        assert "+5 projeto" in e.description
