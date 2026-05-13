import asyncio
import io
import time
from typing import Awaitable, Callable, TypeVar

import discord
from discord import app_commands
from discord.errors import NotFound

from config import DISCORD_BOT_TOKEN, DISCORD_GUILD_ID, TARGET_PROJECT_PATH
from embeds import (
    embed_dev_server_falhou,
    embed_garagem_engasgou,
    embed_garagem_no_slug,
    embed_garagem_pushback,
    embed_garagem_working,
    embed_meeseeks_falha,
    embed_meeseeks_spawn,
    embed_meeseeks_working,
    embed_sucesso,
)
from formatters import fmt_time
from garagem import GaragemResult, invocar_garagem
from meeseeks import MeeseeksResult, invocar_meeseeks, start_dev_server


T = TypeVar("T")


intents = discord.Intents.default()


class MeeseeksBox(discord.Client):
    def __init__(self):
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="Rick press the button",
        )
        super().__init__(intents=intents, activity=activity)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        if DISCORD_GUILD_ID:
            guild = discord.Object(id=int(DISCORD_GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"Comandos sincronizados em {DISCORD_GUILD_ID}")
        else:
            await self.tree.sync()


client = MeeseeksBox()


@client.event
async def on_ready():
    print(f"Bot conectado como {client.user}")
    print(f"Projeto-alvo: {TARGET_PROJECT_PATH}")


# ─── helpers genéricos ───────────────────────────────────────────────────

async def _heartbeat(message, render_fn, interval: int = 5):
    """Edita `message` periodicamente com novo embed até ser cancelada."""
    start = time.monotonic()
    try:
        while True:
            await asyncio.sleep(interval)
            elapsed = time.monotonic() - start
            try:
                await message.edit(embed=render_fn(elapsed))
            except (discord.HTTPException, NotFound):
                pass
    except asyncio.CancelledError:
        pass


async def _try_edit(message, embed: discord.Embed):
    try:
        await message.edit(embed=embed)
    except (discord.HTTPException, NotFound):
        pass


async def _send_embed(
    interaction,
    embed: discord.Embed,
    overflow: str | None,
    filename: str,
):
    """Envia embed. Se houver overflow (description estourou), anexa
    o texto completo como arquivo no mesmo followup."""
    if overflow is None:
        await interaction.followup.send(embed=embed)
        return
    file = discord.File(
        io.BytesIO(overflow.encode("utf-8")),
        filename=filename,
    )
    await interaction.followup.send(embed=embed, file=file)


async def _run_with_heartbeat(
    status_msg,
    render_fn: Callable[[float], discord.Embed],
    coro: Awaitable[T],
) -> tuple[T, float]:
    """Roda `coro` enquanto um heartbeat reedita `status_msg` a cada
    5s usando `render_fn(elapsed)`. Devolve (resultado, tempo decorrido).
    Cancela o heartbeat mesmo se a coro levantar.
    """
    start = time.monotonic()
    hb = asyncio.create_task(_heartbeat(status_msg, render_fn))
    try:
        result = await coro
    finally:
        hb.cancel()
        await asyncio.gather(hb, return_exceptions=True)
    return result, time.monotonic() - start


# ─── respostas finais por fase ───────────────────────────────────────────

async def _send_garagem_error(
    interaction, status_msg, g: GaragemResult, tempo: str
):
    embed = embed_garagem_engasgou(tempo, g.error or "?", g.raw or "")
    await _try_edit(status_msg, embed)
    await interaction.followup.send(embed=embed)


async def _send_garagem_pushback(
    interaction, status_msg, briefing: dict, tempo: str
):
    embed = embed_garagem_pushback(briefing, tempo)
    await _try_edit(status_msg, embed)
    await interaction.followup.send(embed=embed)


async def _send_garagem_no_slug(interaction, status_msg, tempo: str):
    embed = embed_garagem_no_slug(tempo)
    await _try_edit(status_msg, embed)
    await interaction.followup.send(embed=embed)


async def _send_meeseeks_failure(
    interaction, status_msg, m: MeeseeksResult, tempo: str
):
    embed, overflow = embed_meeseeks_falha(m, tempo, TARGET_PROJECT_PATH)
    await _try_edit(status_msg, embed)
    await _send_embed(interaction, embed, overflow, "meeseeks-fail.md")


async def _send_dev_server_failure(
    interaction, status_msg, m: MeeseeksResult, error: Exception, tempo: str
):
    embed, overflow = embed_dev_server_falhou(
        m, error, tempo, TARGET_PROJECT_PATH
    )
    await _try_edit(status_msg, embed)
    await _send_embed(interaction, embed, overflow, "meeseeks-report.md")


async def _send_success(
    interaction, status_msg, m: MeeseeksResult, tempo: str, dev_port: int
):
    embed, overflow = embed_sucesso(
        m, dev_port, tempo, TARGET_PROJECT_PATH
    )
    await _try_edit(status_msg, embed)
    await _send_embed(interaction, embed, overflow, "meeseeks-report.md")


# ─── comando ─────────────────────────────────────────────────────────────

@client.tree.command(
    name="meeseeks",
    description="Invoca um Mr. Meeseeks pra cumprir uma tarefa",
)
@app_commands.describe(task="O que voce precisa que seja feito")
async def meeseeks(interaction: discord.Interaction, task: str):
    try:
        await interaction.response.defer(thinking=True)
    except NotFound:
        print(f"[warn] interaction expirada antes do defer (task={task!r})")
        return

    try:
        status_msg = await interaction.followup.send(
            embed=embed_garagem_working(task, 0), wait=True
        )
    except NotFound:
        print(f"[warn] followup falhou após defer (task={task!r})")
        return

    # ── Garagem ──
    g, g_elapsed = await _run_with_heartbeat(
        status_msg,
        lambda elapsed: embed_garagem_working(task, elapsed),
        invocar_garagem(task, TARGET_PROJECT_PATH),
    )
    g_tempo = fmt_time(g_elapsed)

    if g.error:
        return await _send_garagem_error(interaction, status_msg, g, g_tempo)

    parsed = g.parsed or {}

    if not parsed.get("escopo_claro"):
        return await _send_garagem_pushback(
            interaction, status_msg, parsed, g_tempo
        )

    slug = (parsed.get("slug") or "").strip()
    if not slug:
        return await _send_garagem_no_slug(interaction, status_msg, g_tempo)

    # ── Meeseeks ──
    await _try_edit(status_msg, embed_meeseeks_spawn(g_tempo))

    m, m_elapsed = await _run_with_heartbeat(
        status_msg,
        lambda elapsed: embed_meeseeks_working(slug, elapsed),
        invocar_meeseeks(parsed, TARGET_PROJECT_PATH),
    )
    m_tempo = fmt_time(m_elapsed)

    if not m.success:
        return await _send_meeseeks_failure(
            interaction, status_msg, m, m_tempo
        )

    # ── Dev server ──
    try:
        dev_port = start_dev_server(m.worktree)
    except Exception as e:
        return await _send_dev_server_failure(
            interaction, status_msg, m, e, m_tempo
        )

    await _send_success(interaction, status_msg, m, m_tempo, dev_port)


if __name__ == "__main__":
    client.run(DISCORD_BOT_TOKEN)
