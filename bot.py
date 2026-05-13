import asyncio
import io
import time
from typing import Awaitable, Callable, TypeVar

import discord
from discord import app_commands
from discord.errors import NotFound

from config import DISCORD_BOT_TOKEN, DISCORD_GUILD_ID, TARGET_PROJECT_PATH
from formatters import (
    fmt_time,
    formatar_cleanup,
    formatar_falha_meeseeks,
    formatar_pushback,
    formatar_sucesso,
    render_garagem_status,
    render_meeseeks_status,
)
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
    """Edita `message` periodicamente até ser cancelada."""
    start = time.monotonic()
    try:
        while True:
            await asyncio.sleep(interval)
            elapsed = time.monotonic() - start
            try:
                await message.edit(content=render_fn(elapsed))
            except (discord.HTTPException, NotFound):
                pass
    except asyncio.CancelledError:
        pass


async def _try_edit(message, content: str):
    try:
        await message.edit(content=content)
    except (discord.HTTPException, NotFound):
        pass


async def _send_long(interaction, content: str, filename: str):
    """Envia content como mensagem se couber em 2000 chars, senão anexo."""
    if len(content) <= 2000:
        await interaction.followup.send(content)
        return
    file = discord.File(
        io.BytesIO(content.encode("utf-8")),
        filename=filename,
    )
    await interaction.followup.send(
        content="📄 Relatório longo, segue em anexo.",
        file=file,
    )


async def _run_with_heartbeat(
    status_msg,
    render_fn: Callable[[float], str],
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
    await _try_edit(status_msg, f"🔧 *A Garagem engasgou em `{tempo}`.*")
    excerpt = g.raw[:1500] if g.raw else ""
    await interaction.followup.send(
        f"❌ Erro: `{g.error}`"
        + (f"\n```\n{excerpt}\n```" if excerpt else "")
    )


async def _send_garagem_pushback(
    interaction, status_msg, briefing: dict, tempo: str
):
    await _try_edit(
        status_msg,
        f"🔧 *A Garagem empurrou de volta em `{tempo}`.*",
    )
    await interaction.followup.send(formatar_pushback(briefing))


async def _send_garagem_no_slug(interaction, status_msg, tempo: str):
    await _try_edit(
        status_msg,
        f"❌ *A Garagem entregou em `{tempo}` sem `slug`.*",
    )
    await interaction.followup.send(
        "❌ Briefing válido mas sem `slug` — Garagem precisa corrigir o schema."
    )


async def _send_meeseeks_failure(
    interaction, status_msg, m: MeeseeksResult, tempo: str
):
    await _try_edit(
        status_msg,
        f"💀 *Existing is pain... travou em `{tempo}`.*",
    )
    await _send_long(
        interaction,
        formatar_falha_meeseeks(m, TARGET_PROJECT_PATH),
        "meeseeks-fail.md",
    )


async def _send_dev_server_failure(
    interaction, status_msg, m: MeeseeksResult, error: Exception, tempo: str
):
    await _try_edit(
        status_msg,
        f"✨ *Can do em `{tempo}`!* ⚠️ Mas o dev server falhou.",
    )
    await _send_long(
        interaction,
        f"{m.relatorio}\n\n⚠️ Falha ao subir `npm run dev`: `{error}`"
        + formatar_cleanup(m, TARGET_PROJECT_PATH),
        "meeseeks-report.md",
    )


async def _send_success(
    interaction, status_msg, m: MeeseeksResult, tempo: str, dev_port: int
):
    await _try_edit(
        status_msg,
        f"✨ *Can do!* **Missão cumprida em `{tempo}`.**",
    )
    await _send_long(
        interaction,
        formatar_sucesso(m, dev_port, TARGET_PROJECT_PATH),
        "meeseeks-report.md",
    )


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
            render_garagem_status(task, 0), wait=True
        )
    except NotFound:
        print(f"[warn] followup falhou após defer (task={task!r})")
        return

    # ── Garagem ──
    g, g_elapsed = await _run_with_heartbeat(
        status_msg,
        lambda elapsed: render_garagem_status(task, elapsed),
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
    await _try_edit(
        status_msg,
        f"🔧 *Garagem entregou em `{g_tempo}`.* 💨 *POOF!* "
        f"**I'm Mr. Meeseeks, look at me!**",
    )

    m, m_elapsed = await _run_with_heartbeat(
        status_msg,
        lambda elapsed: render_meeseeks_status(slug, elapsed),
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
