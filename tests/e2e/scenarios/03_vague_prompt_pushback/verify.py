"""Verify do cenário 03 — prompt vago dispara pushback da Garagem.

A Garagem é treinada pra rejeitar prompts vagos ("melhore o código",
sem alvo, sem critério). O pipeline deve parar em `garagem_pushback`
**sem** entrar no Meeseeks.

Pós-condições:
- pipeline.phase == "garagem_pushback"
- garagem.parsed["escopo_claro"] == False
- garagem.parsed["duvidas_pro_rick"] tem ≥1 entrada
- meeseeks não foi invocado (pipeline.meeseeks is None)
- DB row tem terminal_phase=garagem_pushback, garagem_outcome=pushback,
  garagem_cost_usd > 0 (a Garagem rodou de fato)
- meeseeks_outcome é None (nem foi tentado)
"""


def verify(ctx) -> None:
    p = ctx.pipeline

    assert p.phase == "garagem_pushback", (
        f"esperava phase=garagem_pushback, veio {p.phase!r} "
        f"(garagem.error={p.garagem.error!r}, "
        f"parsed.escopo_claro={(p.garagem.parsed or {}).get('escopo_claro')!r})"
    )

    parsed = p.garagem.parsed
    assert parsed is not None, (
        f"Garagem não devolveu JSON parseável; raw={p.garagem.raw!r}"
    )
    assert parsed.get("escopo_claro") is False, (
        f"escopo_claro deveria ser False; veio {parsed.get('escopo_claro')!r}"
    )

    duvidas = parsed.get("duvidas_pro_rick") or []
    assert len(duvidas) >= 1, (
        f"esperava ≥1 dúvida em duvidas_pro_rick; veio {duvidas!r}"
    )

    assert p.meeseeks is None, (
        f"Meeseeks não devia ter rodado em pushback; veio {p.meeseeks!r}"
    )

    row = ctx.db_row
    assert row is not None, "linha do DB não foi criada"
    assert row["terminal_phase"] == "garagem_pushback", (
        f"terminal_phase={row['terminal_phase']!r}"
    )
    assert row["garagem_outcome"] == "pushback", (
        f"garagem_outcome={row['garagem_outcome']!r}"
    )
    assert row["garagem_cost_usd"] is not None and row["garagem_cost_usd"] > 0, (
        f"custo da Garagem deveria ter sido gravado: "
        f"{row['garagem_cost_usd']!r}"
    )
    assert row["meeseeks_outcome"] is None, (
        f"meeseeks_outcome deveria ser None em pushback; "
        f"veio {row['meeseeks_outcome']!r}"
    )
