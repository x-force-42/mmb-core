import asyncio
import io
import time

import discord
from discord import app_commands
from discord.errors import NotFound

from config import DISCORD_BOT_TOKEN, DISCORD_GUILD_ID, TARGET_PROJECT_PATH
from garagem import invocar_garagem
from meeseeks import (
    MeeseeksResult,
    invocar_meeseeks,
    start_dev_server,
)


intents = discord.Intents.default()


class MeeseeksBox(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
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


# ─── helpers ─────────────────────────────────────────────────────────────

def _fmt_time(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60:02d}:{s % 60:02d}"


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


def _formatar_pushback(p: dict) -> str:
    duvidas = p.get("duvidas_pro_rick") or [
        "_(sem dúvidas listadas, mas escopo marcado como pouco claro)_"
    ]
    bloco = "\n".join(f"- {d}" for d in duvidas)
    return f"🛑 **A Garagem empurrou de volta.**\n\n**Dúvidas:**\n{bloco}"


def _formatar_cleanup(result: MeeseeksResult) -> str:
    if result.worktree is None or result.branch is None:
        return ""
    try:
        rel = result.worktree.relative_to(TARGET_PROJECT_PATH)
    except ValueError:
        rel = result.worktree
    return (
        "\n\n**Cleanup quando aprovar**\n"
        f"```bash\n"
        f"cd {TARGET_PROJECT_PATH}\n"
        f"git worktree remove {rel}\n"
        f"git branch -D {result.branch}\n"
        f"```"
    )


def _formatar_sucesso(result: MeeseeksResult, dev_port: int) -> str:
    relatorio = result.relatorio or "_(Meeseeks não devolveu relatório)_"
    dev_info = (
        f"\n\n**Dev server**\n"
        f"- `http://localhost:{dev_port}` "
        f"(worktree `{result.worktree.name if result.worktree else '?'}`)"
    )
    return relatorio + dev_info + _formatar_cleanup(result)


def _formatar_falha_meeseeks(result: MeeseeksResult) -> str:
    cabecalho = "❌ **Meeseeks falhou.**"
    detalhe = f" `{result.error}`" if result.error else ""
    relatorio = (
        f"\n\n**Relatório parcial:**\n{result.relatorio}"
        if result.relatorio else ""
    )
    raw = (
        f"\n\n```\n{result.raw[:1200]}\n```"
        if result.raw and not result.relatorio else ""
    )
    return cabecalho + detalhe + relatorio + raw + _formatar_cleanup(result)


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

    def render_garagem(elapsed: float) -> str:
        return (
            f"🔧 *A Garagem trabalhando...* `{_fmt_time(elapsed)}`\n"
            f"> {task}"
        )

    try:
        status_msg = await interaction.followup.send(render_garagem(0), wait=True)
    except NotFound:
        print(f"[warn] followup falhou após defer (task={task!r})")
        return

    # ── Garagem ──
    g_start = time.monotonic()
    hb = asyncio.create_task(_heartbeat(status_msg, render_garagem))
    try:
        g_result = await invocar_garagem(task, TARGET_PROJECT_PATH)
    finally:
        hb.cancel()
        await asyncio.gather(hb, return_exceptions=True)
    g_tempo = _fmt_time(time.monotonic() - g_start)

    if g_result.error:
        await _try_edit(status_msg, f"❌ *A Garagem engasgou em `{g_tempo}`.*")
        excerpt = g_result.raw[:1500] if g_result.raw else ""
        await interaction.followup.send(
            f"❌ Erro: `{g_result.error}`"
            + (f"\n```\n{excerpt}\n```" if excerpt else "")
        )
        return

    p = g_result.parsed or {}

    if not p.get("escopo_claro"):
        await _try_edit(
            status_msg,
            f"🛑 *A Garagem empurrou de volta em `{g_tempo}`.*",
        )
        await interaction.followup.send(_formatar_pushback(p))
        return

    slug = (p.get("slug") or "").strip()
    if not slug:
        await _try_edit(
            status_msg,
            f"❌ *A Garagem entregou em `{g_tempo}` sem `slug`.*",
        )
        await interaction.followup.send(
            "❌ Briefing válido mas sem `slug` — Garagem precisa corrigir o schema."
        )
        return

    # ── Meeseeks ──
    await _try_edit(
        status_msg,
        f"✅ *Garagem entregou em `{g_tempo}`.* 🌀 Meeseeks acordando…",
    )

    def render_meeseeks(elapsed: float) -> str:
        return (
            f"🌀 *Meeseeks executando…* `{_fmt_time(elapsed)}`\n"
            f"> branch: `meeseeks/{slug}`"
        )

    m_start = time.monotonic()
    hb = asyncio.create_task(_heartbeat(status_msg, render_meeseeks))
    try:
        m_result = await invocar_meeseeks(p, TARGET_PROJECT_PATH)
    finally:
        hb.cancel()
        await asyncio.gather(hb, return_exceptions=True)
    m_tempo = _fmt_time(time.monotonic() - m_start)

    if not m_result.success:
        await _try_edit(
            status_msg,
            f"❌ *Meeseeks falhou em `{m_tempo}`.*",
        )
        await _send_long(
            interaction,
            _formatar_falha_meeseeks(m_result),
            "meeseeks-fail.md",
        )
        return

    # ── sobe dev server ──
    try:
        dev_port = start_dev_server(m_result.worktree)
    except Exception as e:
        await _try_edit(
            status_msg,
            f"⚠️ *Meeseeks ok em `{m_tempo}`, mas dev server falhou.*",
        )
        await _send_long(
            interaction,
            f"{m_result.relatorio}\n\n⚠️ Falha ao subir `npm run dev`: `{e}`"
            + _formatar_cleanup(m_result),
            "meeseeks-report.md",
        )
        return

    await _try_edit(
        status_msg,
        f"✅ *Meeseeks entregou em `{m_tempo}`.*",
    )
    await _send_long(
        interaction,
        _formatar_sucesso(m_result, dev_port),
        "meeseeks-report.md",
    )


client.run(DISCORD_BOT_TOKEN)
