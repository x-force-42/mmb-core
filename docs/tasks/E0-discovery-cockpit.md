# Discovery — Cockpit de Operações

## ID
E0

## Trilha
E — Cockpit de Operações

## Status
🟡 em curso — conversação ativa com o Rick

## Objetivo

Mapear escopo, vistas, stack, MVP e aspirações futuras do **Cockpit
de Operações** — o painel de visualização retrospectiva (e
parcialmente em tempo real) do MMB. Distinto do aquário (A1), que
é presença ao vivo das criaturas; o cockpit é o painel de bordo
do Rick pra operar a frota.

Este doc não é uma task implementável — é o **doc de design**. O
output é este arquivo preenchido + briefs subsequentes (E1, E2, …)
prontos pra delegar via `task-start.sh`.

## Princípios herdados

- **Read-only** sobre o SQLite do logger. Zero acoplamento com
  `bot.py`/`garagem.py`/`meeseeks.py`. Mesma filosofia "side car
  observável" do `logger/` e do (futuro) `aquario/`.
- **Localhost / dev-friendly** por padrão. Pode evoluir, mas a
  primeira versão roda na máquina do Rick.
- **Itera sobre conversa antes de código.** Decisões fechadas
  primeiro, brief implementável depois.

## Decisões fechadas

_(preenchido conforme alinhamos)_

## Decisões em aberto

_(preenchido conforme aparecem)_

## Personas & uso

_(a preencher: quem usa, quando, com que frequência, em que
contextos)_

## Entidades a expor

_(a preencher: projetos, garagens, runs, meeseeks ativos,
meeseeks históricos, métricas agregadas, campos de review manual)_

## Vistas

_(a preencher: telas / páginas / componentes)_

## Stack

_(a preencher: linguagem, framework, server, build, deploy)_

## MVP

_(a preencher: o mínimo viável que já entrega valor)_

## Aspirações futuras

_(a preencher: coisas pra v2+, fora do MVP)_

## Relação com vizinhança

_(a preencher: como o cockpit se posiciona em relação a:
- Datasette atual
- Aquário (A1) — overlap de Meeseeks ativos
- Multi-projeto (B1) — consumidor do schema final
- Garagem com contexto (B2) — exibição de contexto persistido)_
