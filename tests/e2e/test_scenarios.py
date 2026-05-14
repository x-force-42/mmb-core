"""Driver parametrizado dos cenários E2E.

Pra cada pasta em `scenarios/`:
- aplica setup.py (se houver) no fixture-master
- roda pipeline.run_pipeline(task, fixture)
- registra o run no DB de teste isolado
- aplica verify.py

Cleanup é responsabilidade do fixture `clean_fixture` (conftest).
"""

import pytest

from logger import RunLogger
from pipeline import run_pipeline

from .harness import VerifyContext, discover_scenarios


SCENARIOS = discover_scenarios()


@pytest.mark.e2e
@pytest.mark.parametrize(
    "scenario",
    SCENARIOS,
    ids=[s.name for s in SCENARIOS],
)
async def test_scenario(scenario, clean_fixture, tmp_path):
    fixture = clean_fixture

    if scenario.setup is not None:
        scenario.setup(fixture)

    # DB de teste isolado — não polui o mmb.db de produção
    logger = RunLogger(tmp_path / "e2e.db")
    project_id = logger.ensure_project(
        slug=fixture.name, name=fixture.name, path=str(fixture),
    )
    run_id = logger.start_run(project_id=project_id, task_raw=scenario.task)

    result = await run_pipeline(scenario.task, fixture)

    # grava o que conseguir — o pipeline real é o bot.py, aqui replicamos
    # só o suficiente pra verify ter acesso a uma linha do DB.
    _record_pipeline(logger, run_id, result)

    ctx = VerifyContext(
        fixture_root=fixture,
        pipeline=result,
        db_row=logger.get_run(run_id),
    )
    scenario.verify(ctx)


def _record_pipeline(logger, run_id, result) -> None:
    """Replica o flow de gravação do bot.py de forma compacta, pra que
    verify.py consiga afirmar conteúdo da linha do DB."""
    import json
    from logger import DevServerEntry, GaragemEntry, MeeseeksEntry

    g = result.garagem
    parsed = g.parsed or {}
    g_outcome = (
        "error" if g.error else
        "pushback" if not parsed.get("escopo_claro") else
        "success"
    )
    logger.record_garagem(run_id, GaragemEntry(
        model="claude", elapsed_s=0.0, outcome=g_outcome,
        tokens_input=g.tokens_input, tokens_output=g.tokens_output,
        cost_usd=g.cost_usd,
        briefing_json=json.dumps(parsed) if parsed else None,
        meeseeks_prompt=parsed.get("prompt_meeseeks"),
        commit_type=parsed.get("commit_tipo"),
        slug=parsed.get("slug"),
        criticality=parsed.get("criticidade"),
        complexity=parsed.get("complexidade"),
    ))

    if result.meeseeks is not None:
        m = result.meeseeks
        logger.record_meeseeks(run_id, MeeseeksEntry(
            model="claude", elapsed_s=0.0,
            outcome="success" if m.success else "failure",
            tokens_input=m.tokens_input, tokens_output=m.tokens_output,
            cost_usd=m.cost_usd, branch=m.branch,
            commits=m.commits, report=m.relatorio,
            diff_added=m.diff_added, diff_deleted=m.diff_deleted,
            diff_files=m.diff_files,
        ))

    if result.dev_port is not None:
        logger.record_dev_server(run_id, DevServerEntry(
            outcome="success", port=result.dev_port,
        ))
    elif result.dev_server_error is not None:
        logger.record_dev_server(run_id, DevServerEntry(outcome="failure"))

    logger.finish_run(run_id, terminal_phase=result.phase, total_elapsed_s=0.0)
