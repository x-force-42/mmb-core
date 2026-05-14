import asyncio
import io
import json
import time
from pathlib import Path
from typing import Awaitable, Callable, TypeVar

import discord
from discord import app_commands
from discord.errors import NotFound

from aquario import (
    AquarioClient,
    Event,
    FREAKING_OUT_S,
    Meeseeks,
    Snapshot,
    State,
    event_for_phase,
    health_from_elapsed,
)
from config import (
    AQUARIUM_ENABLED,
    AQUARIUM_WS_URL,
    DISCORD_BOT_TOKEN,
    DISCORD_GUILD_ID,
    MMB_DB_PATH,
    TARGET_PROJECT_PATH,
)
from logger import (
    DevServerEntry,
    GaragemEntry,
    MeeseeksEntry,
    ProjectError,
    RunLogger,
)
from embeds import (
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
from formatters import fmt_time
from garagem import GaragemResult, invocar_garagem
from meeseeks import MeeseeksResult, invocar_meeseeks, start_dev_server


T = TypeVar("T")

_logger = RunLogger(MMB_DB_PATH)

# Aquário (side-car visual). Pode ser None se desligado ou se a
# inicialização falhou — `_emit_aquario` lida com isso.
_aquario: AquarioClient | None = None

# Registry dos Meeseeks ainda vivos pro aquário, indexado por id.
# Mantém o último estado conhecido pra que o snapshot no reconnect
# consiga reanunciar todo mundo que está em curso.
_meeseeks_vivos: dict[str, dict] = {}

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


def _seed_default_project_if_needed() -> None:
    """Migração suave: se `TARGET_PROJECT_PATH` está setado e a tabela
    `projects` está vazia, cadastra ele como projeto default.

    Existe só pra usuários que rodavam o MMB pré-B1 — quem nunca rodou
    cadastra via `/project add`. Pós-B1 o handler do `/meeseeks` resolve
    o projeto sempre pelo slug informado em runtime.
    """
    if TARGET_PROJECT_PATH is None:
        return
    if _logger.list_projects(include_inactive=True):
        return
    slug = TARGET_PROJECT_PATH.name
    _logger.ensure_project(
        slug=slug,
        name=slug,
        path=str(TARGET_PROJECT_PATH),
    )
    print(f"[migração] projeto default registrado: {slug}")


@client.event
async def on_ready():
    global _aquario
    _seed_default_project_if_needed()
    print(f"Bot conectado como {client.user}")
    n = len(_logger.list_projects())
    print(f"{n} projeto(s) ativo(s).")
    print(f"Logger: {MMB_DB_PATH}")

    if AQUARIUM_ENABLED:
        try:
            _aquario = AquarioClient(
                AQUARIUM_WS_URL, snapshot_provider=_aquario_snapshot
            )
            await _aquario.start()
            print(f"Aquário ligado: {AQUARIUM_WS_URL}")
        except Exception as e:
            print(f"[warn] aquário não inicializou: {e!r}")
            _aquario = None
    else:
        print("Aquário desligado (AQUARIUM_ENABLED=false)")


# ─── aquário (side-car visual) ───────────────────────────────────────────

def _emit_aquario(msg) -> None:
    """Best-effort emit pro aquário. Cliente já é silencioso em falha
    — esta indireção só protege o caso de aquário desligado."""
    if _aquario is not None:
        _aquario.emit(msg)


def _aquario_snapshot() -> Snapshot:
    """Reanuncia todos os Meeseeks ainda vivos. Chamado pelo cliente
    em cada (re)conexão — o aquário trata snapshot como reset
    completo."""
    return Snapshot(meeseeks=[
        Meeseeks(
            id=info["id"],
            health=info["health"],
            isFreakingOut=info["isFreakingOut"],
            name=info["name"],
            task=info["task"],
        )
        for info in _meeseeks_vivos.values()
    ])


def _aquario_born(aquario_id: str, name: str, task: str) -> None:
    """Anuncia o nascimento de um Meeseeks. Precisa vir ANTES de qualquer
    state/event subsequente pro mesmo id — o aquário dropa silenciosamente
    mensagens pra ids desconhecidos."""
    _meeseeks_vivos[aquario_id] = {
        "id": aquario_id,
        "health": 1.0,
        "isFreakingOut": False,
        "name": name,
        "task": task,
    }
    _emit_aquario(
        Event(kind="born", id=aquario_id, name=name, task=task)
    )


def _aquario_tick(aquario_id: str, elapsed: float) -> None:
    """Tick periódico do heartbeat: emite state com health derivada e,
    no cruzamento do limite, emite freaking_out UMA vez."""
    info = _meeseeks_vivos.get(aquario_id)
    if info is None:
        return
    health = health_from_elapsed(elapsed)
    info["health"] = health
    _emit_aquario(State(id=aquario_id, health=health))
    if elapsed >= FREAKING_OUT_S and not info["isFreakingOut"]:
        info["isFreakingOut"] = True
        _emit_aquario(Event(kind="freaking_out", id=aquario_id))


def _aquario_die(aquario_id: str, phase: str) -> None:
    """Emite o evento de morte correspondente à phase terminal e
    remove o Meeseeks do pool de vivos. Phases pré-Meeseeks (garagem_*)
    são silenciosas porque o `born` nem chegou a sair."""
    kind = event_for_phase(phase)
    if kind is None:
        return
    _emit_aquario(Event(kind=kind, id=aquario_id))
    _meeseeks_vivos.pop(aquario_id, None)


# ─── helpers genéricos ───────────────────────────────────────────────────

async def _heartbeat(
    message,
    render_fn,
    interval: int = 5,
    on_tick: Callable[[float], None] | None = None,
):
    """Edita `message` periodicamente com novo embed até ser cancelada.

    `on_tick`, se fornecido, é chamado a cada tick com o tempo decorrido
    — usado pra emitir state pro aquário no mesmo ritmo do heartbeat
    do Discord. Falha em `on_tick` é silenciada pra não atrapalhar a
    edição da mensagem."""
    start = time.monotonic()
    try:
        while True:
            await asyncio.sleep(interval)
            elapsed = time.monotonic() - start
            try:
                await message.edit(embed=render_fn(elapsed))
            except (discord.HTTPException, NotFound):
                pass
            if on_tick is not None:
                try:
                    on_tick(elapsed)
                except Exception as e:
                    print(f"[warn] heartbeat on_tick falhou: {e!r}")
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
    on_tick: Callable[[float], None] | None = None,
) -> tuple[T, float]:
    """Roda `coro` enquanto um heartbeat reedita `status_msg` a cada
    5s usando `render_fn(elapsed)`. Devolve (resultado, tempo decorrido).
    Cancela o heartbeat mesmo se a coro levantar.

    `on_tick` é repassado pro heartbeat — usado pelo bloco do Meeseeks
    pra empurrar state pro aquário no mesmo ritmo dos edits do Discord.
    """
    start = time.monotonic()
    hb = asyncio.create_task(_heartbeat(status_msg, render_fn, on_tick=on_tick))
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
    interaction, status_msg, m: MeeseeksResult, tempo: str, project_path: Path,
):
    embed, overflow = embed_meeseeks_falha(m, tempo, project_path)
    await _try_edit(status_msg, embed)
    await _send_embed(interaction, embed, overflow, "meeseeks-fail.md")


async def _send_dev_server_failure(
    interaction, status_msg, m: MeeseeksResult, error: Exception, tempo: str,
    project_path: Path,
):
    embed, overflow = embed_dev_server_falhou(
        m, error, tempo, project_path
    )
    await _try_edit(status_msg, embed)
    await _send_embed(interaction, embed, overflow, "meeseeks-report.md")


async def _send_success(
    interaction, status_msg, m: MeeseeksResult, tempo: str, dev_port: int,
    project_path: Path,
):
    embed, overflow = embed_sucesso(
        m, dev_port, tempo, project_path
    )
    await _try_edit(status_msg, embed)
    await _send_embed(interaction, embed, overflow, "meeseeks-report.md")


# ─── adaptadores pro logger ──────────────────────────────────────────────

def _garagem_entry(
    g: GaragemResult, elapsed: float, outcome: str
) -> GaragemEntry:
    parsed = g.parsed or {}
    return GaragemEntry(
        model="claude",
        elapsed_s=elapsed,
        outcome=outcome,
        tokens_input=g.tokens_input,
        tokens_output=g.tokens_output,
        cost_usd=g.cost_usd,
        briefing_json=json.dumps(parsed) if parsed else None,
        meeseeks_prompt=parsed.get("prompt_meeseeks"),
        commit_type=parsed.get("commit_tipo"),
        slug=parsed.get("slug"),
        criticality=parsed.get("criticidade"),
        complexity=parsed.get("complexidade"),
    )


def _meeseeks_entry(
    m: MeeseeksResult, elapsed: float, outcome: str
) -> MeeseeksEntry:
    return MeeseeksEntry(
        model="claude",
        elapsed_s=elapsed,
        outcome=outcome,
        tokens_input=m.tokens_input,
        tokens_output=m.tokens_output,
        cost_usd=m.cost_usd,
        branch=m.branch,
        commits=m.commits,
        report=m.relatorio,
        diff_added=m.diff_added,
        diff_deleted=m.diff_deleted,
        diff_files=m.diff_files,
    )


# ─── /project ────────────────────────────────────────────────────────────
# Fachada fina sobre a API do RunLogger. Toda validação vive no logger;
# aqui só traduzimos ProjectError em embed e enviamos.

project_group = app_commands.Group(
    name="project", description="Gerenciar projetos do MMB"
)


@project_group.command(name="add", description="Cadastra um novo projeto")
@app_commands.describe(
    path="Caminho absoluto do repo git (precisa conter .git/)",
    slug="Identificador curto kebab-case (≤30 chars)",
    name="Nome amigável (default = slug)",
    mode="Modo de operação (default = pontual)",
)
@app_commands.choices(mode=[
    app_commands.Choice(name="pontual", value="pontual"),
    app_commands.Choice(name="construtor", value="construtor"),
])
async def project_add(
    interaction: discord.Interaction,
    path: str,
    slug: str,
    name: str = "",
    mode: app_commands.Choice[str] | None = None,
):
    try:
        proj = _logger.register_project(
            slug=slug,
            path=path,
            name=name or None,
            mode=mode.value if mode else "pontual",
        )
    except ProjectError as e:
        await interaction.response.send_message(
            embed=embed_project_erro(
                "📂 Projeto não cadastrado", str(e)
            ),
            ephemeral=True,
        )
        return
    await interaction.response.send_message(
        embed=embed_project_ok(
            "📂 Projeto cadastrado",
            f"`{proj['slug']}` (`{proj['mode']}`) → `{proj['path']}`",
        )
    )


@project_group.command(name="list", description="Lista os projetos ativos")
async def project_list(interaction: discord.Interaction):
    projetos = _logger.list_projects()
    await interaction.response.send_message(embed=embed_project_list(projetos))


@project_group.command(name="remove", description="Desativa um projeto (soft delete)")
@app_commands.describe(slug="Slug do projeto a desativar")
async def project_remove(interaction: discord.Interaction, slug: str):
    ok = _logger.deactivate_project(slug)
    if ok:
        await interaction.response.send_message(
            embed=embed_project_ok(
                "📂 Projeto desativado",
                f"`{slug}` não aparece mais em `/project list` "
                f"nem no autocomplete do `/meeseeks`. Histórico preservado.",
            )
        )
    else:
        await interaction.response.send_message(
            embed=embed_project_erro(
                "📂 Nada a desativar",
                f"Slug `{slug}` não está ativo (não existe ou já estava inativo).",
            ),
            ephemeral=True,
        )


client.tree.add_command(project_group)


# ─── /meeseeks ───────────────────────────────────────────────────────────

async def _projeto_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Completa o parâmetro `projeto:` com slugs ativos. Limite 25
    (regra do Discord)."""
    projetos = _logger.list_projects()
    filtrados = [
        p for p in projetos if current.lower() in p["slug"].lower()
    ]
    return [
        app_commands.Choice(name=p["slug"], value=p["slug"])
        for p in filtrados[:25]
    ]


@client.tree.command(
    name="meeseeks",
    description="Invoca um Mr. Meeseeks pra cumprir uma tarefa",
)
@app_commands.describe(
    projeto="Slug do projeto-alvo (use /project list pra ver)",
    task="O que voce precisa que seja feito",
)
@app_commands.autocomplete(projeto=_projeto_autocomplete)
async def meeseeks(
    interaction: discord.Interaction, projeto: str, task: str
):
    # Resolve projeto ANTES de qualquer defer/followup pra que erros
    # de slug sejam respondidos ephemeralmente, sem poluir o canal.
    proj = _logger.get_project_by_slug(projeto)
    if proj is None or not proj["active"]:
        await interaction.response.send_message(
            embed=embed_project_erro(
                "📂 Projeto não encontrado",
                f"Slug `{projeto}` não está ativo. "
                f"Use `/project list` pra ver os disponíveis.",
            ),
            ephemeral=True,
        )
        return

    project_path = Path(proj["path"])

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

    run_id = _logger.start_run(project_id=proj["id"], task_raw=task)

    # ── Garagem ──
    g, g_elapsed = await _run_with_heartbeat(
        status_msg,
        lambda elapsed: embed_garagem_working(task, elapsed),
        invocar_garagem(task, project_path),
    )
    g_tempo = fmt_time(g_elapsed)

    if g.error:
        _logger.record_garagem(run_id, _garagem_entry(g, g_elapsed, "error"))
        _logger.finish_run(run_id, terminal_phase="garagem_error",
                           total_elapsed_s=g_elapsed)
        return await _send_garagem_error(interaction, status_msg, g, g_tempo)

    parsed = g.parsed or {}

    if not parsed.get("escopo_claro"):
        _logger.record_garagem(run_id, _garagem_entry(g, g_elapsed, "pushback"))
        _logger.finish_run(run_id, terminal_phase="garagem_pushback",
                           total_elapsed_s=g_elapsed)
        return await _send_garagem_pushback(
            interaction, status_msg, parsed, g_tempo
        )

    slug = (parsed.get("slug") or "").strip()
    if not slug:
        _logger.record_garagem(run_id, _garagem_entry(g, g_elapsed, "success"))
        _logger.finish_run(run_id, terminal_phase="garagem_no_slug",
                           total_elapsed_s=g_elapsed)
        return await _send_garagem_no_slug(interaction, status_msg, g_tempo)

    _logger.record_garagem(run_id, _garagem_entry(g, g_elapsed, "success"))

    # ── Meeseeks ──
    await _try_edit(status_msg, embed_meeseeks_spawn(g_tempo))

    # POOF! Anuncia o nascimento ANTES de qualquer state/event —
    # o aquário dropa silenciosamente mensagens pra id sem born.
    aquario_id = run_id
    _aquario_born(aquario_id, name=slug, task=task)

    m, m_elapsed = await _run_with_heartbeat(
        status_msg,
        lambda elapsed: embed_meeseeks_working(slug, elapsed),
        invocar_meeseeks(parsed, project_path),
        on_tick=lambda elapsed: _aquario_tick(aquario_id, elapsed),
    )
    m_tempo = fmt_time(m_elapsed)
    total_elapsed = g_elapsed + m_elapsed

    if not m.success:
        _logger.record_meeseeks(run_id, _meeseeks_entry(m, m_elapsed, "failure"))
        _logger.finish_run(run_id, terminal_phase="meeseeks_failure",
                           total_elapsed_s=total_elapsed)
        _aquario_die(aquario_id, "meeseeks_failure")
        return await _send_meeseeks_failure(
            interaction, status_msg, m, m_tempo, project_path
        )

    _logger.record_meeseeks(run_id, _meeseeks_entry(m, m_elapsed, "success"))

    # ── Dev server ──
    try:
        dev_port = start_dev_server(m.worktree)
    except Exception as e:
        _logger.record_dev_server(run_id, DevServerEntry(outcome="failure"))
        _logger.finish_run(run_id, terminal_phase="dev_server_failure",
                           total_elapsed_s=total_elapsed)
        _aquario_die(aquario_id, "dev_server_failure")
        return await _send_dev_server_failure(
            interaction, status_msg, m, e, m_tempo, project_path
        )

    _logger.record_dev_server(run_id, DevServerEntry(outcome="success", port=dev_port))
    _logger.finish_run(run_id, terminal_phase="success",
                       total_elapsed_s=total_elapsed)
    _aquario_die(aquario_id, "success")

    await _send_success(
        interaction, status_msg, m, m_tempo, dev_port, project_path
    )


if __name__ == "__main__":
    client.run(DISCORD_BOT_TOKEN)
