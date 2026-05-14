"""Discord embeds com paleta temática.

Duas naturezas de função:

1. **Status** (curtas, usadas em heartbeat e edits durante o pipeline)
   — devolvem `discord.Embed` direto.
2. **Final response** (sucesso/falha/dev — podem ter relatório longo)
   — devolvem `tuple[discord.Embed, str | None]`. O segundo elemento,
   quando presente, é o texto completo pra anexar como arquivo no
   Discord (caso a `description` estoure o limite de 4096 chars).
"""

from pathlib import Path

import discord

from formatters import (
    fmt_time,
    formatar_cleanup,
    formatar_falha_meeseeks,
    formatar_pushback,
    formatar_sucesso,
    meeseeks_decay,
)
from meeseeks import MeeseeksResult


# ─── paleta ──────────────────────────────────────────────────────────────

COR_GARAGEM = 0x5D5D5D       # cinza-oficina
COR_MEESEEKS = 0x8FCDDC      # azul Meeseeks (canon do show)
COR_SUCESSO = 0x57F287       # verde Discord
COR_FALHA = 0xED4245         # vermelho Discord
COR_AVISO = 0xFEE75C         # amarelo Discord
COR_PUSHBACK = 0xEB7E2F      # laranja


# Limite de chars da `description` de um embed do Discord.
DESC_LIMIT = 4096
# Margem pra mensagem "...(continua no anexo)" caber dentro do limite.
DESC_OVERFLOW_MARGIN = 60


# ─── helper de overflow ──────────────────────────────────────────────────

def _embed_or_overflow(
    *,
    title: str,
    body: str,
    color: int,
) -> tuple[discord.Embed, str | None]:
    """Constrói embed com `body` em description. Se `body` ultrapassa
    o limite, trunca a description e devolve o texto completo como
    overflow pro caller anexar como arquivo."""
    if len(body) <= DESC_LIMIT:
        return discord.Embed(title=title, description=body, color=color), None

    truncated = (
        body[: DESC_LIMIT - DESC_OVERFLOW_MARGIN]
        + "\n\n_…(continua no anexo)_"
    )
    return discord.Embed(title=title, description=truncated, color=color), body


# ─── Garagem (status) ────────────────────────────────────────────────────

def embed_garagem_working(task: str, elapsed: float) -> discord.Embed:
    """Heartbeat enquanto a Garagem explora o projeto."""
    embed = discord.Embed(
        title="🔧 A Garagem cavando isso aí…",
        description=f"> {task}",
        color=COR_GARAGEM,
    )
    embed.set_footer(text=fmt_time(elapsed))
    return embed


def embed_garagem_engasgou(
    tempo: str, error: str, raw: str
) -> discord.Embed:
    """Erro técnico durante a Garagem (timeout, exit code, etc)."""
    desc = f"❌ `{error}`"
    if raw:
        desc += f"\n\n```\n{raw[:1500]}\n```"
    return discord.Embed(
        title=f"🔧 A Garagem engasgou em `{tempo}`",
        description=desc,
        color=COR_FALHA,
    )


def embed_garagem_pushback(
    briefing: dict, tempo: str
) -> discord.Embed:
    """Garagem disse que o escopo não está claro."""
    embed = discord.Embed(
        title="🔧 Não, Rick. Volta com isso melhor.",
        description=formatar_pushback(briefing),
        color=COR_PUSHBACK,
    )
    embed.set_footer(text=f"Garagem em {tempo}")
    return embed


def embed_garagem_no_slug(tempo: str) -> discord.Embed:
    """Edge case: briefing válido mas sem slug pra nomear a branch."""
    embed = discord.Embed(
        title="❌ Briefing sem slug",
        description=(
            "Garagem entregou um briefing válido mas sem `slug`. "
            "Precisa corrigir o schema."
        ),
        color=COR_FALHA,
    )
    embed.set_footer(text=f"Garagem em {tempo}")
    return embed


# ─── Meeseeks (status) ───────────────────────────────────────────────────

def embed_meeseeks_spawn(g_tempo: str) -> discord.Embed:
    """Transição: Garagem entregou, Meeseeks acabou de nascer."""
    return discord.Embed(
        title="💨 POOF! I'm Mr. Meeseeks, look at me!",
        description=f"_Garagem entregou em `{g_tempo}`._",
        color=COR_MEESEEKS,
    )


def embed_meeseeks_working(slug: str, elapsed: float) -> discord.Embed:
    """Heartbeat do Meeseeks. Título usa a frase de decay correspondente
    ao tempo decorrido (working → caaan do → oh boy → pain → please)."""
    embed = discord.Embed(
        title=meeseeks_decay(elapsed),
        description=f"branch: `meeseeks/{slug}`",
        color=COR_MEESEEKS,
    )
    embed.set_footer(text=fmt_time(elapsed))
    return embed


# ─── Mensagens finais (podem estourar) ───────────────────────────────────

def embed_meeseeks_falha(
    m: MeeseeksResult, tempo: str, target_path: Path
) -> tuple[discord.Embed, str | None]:
    """Pipeline do Meeseeks falhou (sem commit, exception, timeout)."""
    return _embed_or_overflow(
        title=f"💀 Existing is pain... travou em `{tempo}`",
        body=formatar_falha_meeseeks(m, target_path),
        color=COR_FALHA,
    )


def embed_dev_server_falhou(
    m: MeeseeksResult,
    error: Exception,
    tempo: str,
    target_path: Path,
) -> tuple[discord.Embed, str | None]:
    """Meeseeks completou OK mas o npm run dev não subiu."""
    body = (
        f"{m.relatorio}\n\n"
        f"⚠️ Falha ao subir `npm run dev`: `{error}`"
        + formatar_cleanup(m, target_path)
    )
    return _embed_or_overflow(
        title=f"✨ Can do em `{tempo}`! ⚠️ Mas o dev server falhou.",
        body=body,
        color=COR_AVISO,
    )


def embed_sucesso(
    m: MeeseeksResult,
    dev_port: int,
    tempo: str,
    target_path: Path,
) -> tuple[discord.Embed, str | None]:
    """Pipeline completo. Description traz relatório + dev URL + cleanup."""
    return _embed_or_overflow(
        title=f"✨ Can do! Missão cumprida em `{tempo}`.",
        body=formatar_sucesso(m, dev_port, target_path),
        color=COR_SUCESSO,
    )


# ─── /project ────────────────────────────────────────────────────────────
# Minimalistas por design — UI de cadastro vai ser repensada na B3
# (bootstrap interview). Não invistam UX aqui antes disso.

def embed_project_ok(titulo: str, descricao: str) -> discord.Embed:
    return discord.Embed(title=titulo, description=descricao, color=COR_SUCESSO)


def embed_project_erro(titulo: str, descricao: str) -> discord.Embed:
    return discord.Embed(title=titulo, description=descricao, color=COR_FALHA)


def embed_project_list(projetos: list[dict]) -> discord.Embed:
    """Tabela compacta dos projetos. Discord embed aguenta ~25 linhas
    razoavelmente; pra essa task isso é mais que suficiente."""
    if not projetos:
        return discord.Embed(
            title="📂 Projetos",
            description=(
                "_Nenhum projeto registrado._\n\n"
                "Use `/project add path:... slug:...` pra registrar."
            ),
            color=COR_GARAGEM,
        )

    MAX_LINHAS = 25
    visiveis = projetos[:MAX_LINHAS]
    linhas = [
        f"`{p['slug']:<20}` `{p['mode']:<10}` `{p['path']}`"
        for p in visiveis
    ]
    extras = len(projetos) - len(visiveis)
    if extras > 0:
        linhas.append(f"\n_+{extras} projeto(s) não exibido(s)_")
    return discord.Embed(
        title=f"📂 Projetos ({len(projetos)})",
        description="\n".join(linhas),
        color=COR_GARAGEM,
    )
