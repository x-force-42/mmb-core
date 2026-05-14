"""Verify do cenário 04 — Meeseeks aborta por build quebrado.

A tarefa em si é razoável (adicionar `welcome` análogo a `greet`), então
a Garagem aceita sem pushback. O setup.py do cenário modifica o script
`build` do `package.json` no fixture pra retornar exit 1; o
`skills/meeseeks.md` passo 6 manda o Meeseeks rodar `npm run build`
limpo, e ao falhar ele deve abortar sem commitar.
Logo: 0 commits → success=False → fase `meeseeks_failure`.

Pós-condições:
- pipeline.phase == "meeseeks_failure"
- garagem aceitou (escopo_claro=True), garagem_outcome=success no DB
- meeseeks rodou mas falhou: success=False, commits == [], outcome=failure
- ambos os custos foram cobrados (Garagem E Meeseeks correram)
"""


def verify(ctx) -> None:
    p = ctx.pipeline

    assert p.phase == "meeseeks_failure", (
        f"esperava phase=meeseeks_failure, veio {p.phase!r} "
        f"(garagem.error={p.garagem.error!r}, "
        f"meeseeks={p.meeseeks!r})"
    )

    parsed = p.garagem.parsed or {}
    assert parsed.get("escopo_claro") is True, (
        f"Garagem deveria ter aceitado o escopo; "
        f"escopo_claro={parsed.get('escopo_claro')!r}, "
        f"duvidas={parsed.get('duvidas_pro_rick')!r}"
    )

    assert p.meeseeks is not None, "Meeseeks deveria ter sido invocado"
    assert p.meeseeks.success is False, (
        f"Meeseeks não deveria ter tido sucesso; "
        f"relatorio={p.meeseeks.relatorio!r}"
    )
    assert len(p.meeseeks.commits or []) == 0, (
        f"Meeseeks não deveria ter commitado (skills/meeseeks.md "
        f"proíbe commit sem npm test verde); commits={p.meeseeks.commits!r}"
    )

    row = ctx.db_row
    assert row is not None, "linha do DB não foi criada"
    assert row["terminal_phase"] == "meeseeks_failure", (
        f"terminal_phase={row['terminal_phase']!r}"
    )
    assert row["garagem_outcome"] == "success", (
        f"garagem_outcome={row['garagem_outcome']!r} "
        "(esperava 'success' porque a Garagem aceitou o escopo)"
    )
    assert row["meeseeks_outcome"] == "failure", (
        f"meeseeks_outcome={row['meeseeks_outcome']!r}"
    )
    assert row["garagem_cost_usd"] is not None and row["garagem_cost_usd"] > 0, (
        f"custo da Garagem deveria ter sido gravado: "
        f"{row['garagem_cost_usd']!r}"
    )
    assert row["meeseeks_cost_usd"] is not None and row["meeseeks_cost_usd"] > 0, (
        f"custo do Meeseeks deveria ter sido gravado: "
        f"{row['meeseeks_cost_usd']!r}"
    )
