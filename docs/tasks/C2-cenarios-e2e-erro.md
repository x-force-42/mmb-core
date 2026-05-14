# Task C2 — Cenários E2E de erro

## ID
C2

## Trilha
C — Robustez

## Status
🎯 pronto pra delegar

## Intenção

A suite E2E hoje (Ato VII, commit `d279e6c`) tem 2 cenários, ambos
de **sucesso**: rename e implementação contra teste. Isso cobre o
caminho feliz do pipeline, mas deixa todos os branches de erro
fora — exatamente onde bugs sutis tendem a se esconder, porque
testes manuais raramente passam por eles.

Esta task adiciona 3 cenários de erro que exercitam as fases
terminais não-sucesso do `PipelineResult`: `garagem_pushback`,
`garagem_no_slug`, `meeseeks_failure`.

Quando completa, a suite verifica que o pipeline **falha onde
deveria falhar**, e o logger grava a fase correta com tokens/custo
populados mesmo nos casos de erro.

## Escopo

### Dentro
- Cenário `03_vague_prompt_pushback`: task.txt deliberadamente
  vaga ("melhore o código"), verify confirma que o pipeline parou
  em `garagem_pushback` com `duvidas_pro_rick` não-vazio.
- Cenário `04_meeseeks_failure_impossible`: task.txt pede algo
  tecnicamente impossível (ex.: usar biblioteca inexistente), verify
  confirma `meeseeks_failure` com 0 commits.
- Cenário `05_garagem_no_slug`: task.txt construída pra induzir
  Garagem a aceitar escopo mas devolver slug vazio. **Difícil de
  forçar**, vide nota em "Decisões em aberto" abaixo.

### Fora
- Cenários de `dev_server_failure` — esses dependem do dev server
  do fixture, que hoje funciona limpo. Não vale ferir o fixture
  só pra esse caminho.
- Refactor do harness E2E — ele já suporta cenários de erro;
  é só configurar verify pra esperar fase diferente.
- Cenário anti-escopo (C3) — task separada.

## Critério de pronto

1. `scripts/e2e.sh` roda 5 cenários (2 antigos + 3 novos), todos
   verdes.
2. Pelo menos para `03` e `04`, o `verify.py` confere que:
   - `ctx.pipeline.phase` é o esperado.
   - O DB row tem `garagem_outcome` correto.
   - `garagem_cost_usd > 0` (o run **chegou** a invocar a Garagem,
     mesmo terminando em erro depois).
3. `03` adicionalmente confere `garagem.parsed["duvidas_pro_rick"]`
   tem ≥1 entrada.
4. `04` adicionalmente confere `meeseeks.commits == []` e que
   `meeseeks_cost_usd > 0`.

## Contexto técnico

### Arquivos relevantes
- `tests/e2e/scenarios/01_rename_greet_to_welcome/` — modelo a
  imitar. Tem `task.txt` + `verify.py`.
- `tests/e2e/scenarios/02_implement_farewell/` — modelo com
  `setup.py`. Você não vai precisar de setup nos cenários de erro.
- `tests/e2e/harness.py` — define `VerifyContext` (campos:
  `fixture_root`, `pipeline`, `db_row`).
- `tests/e2e/conftest.py` — cleanup automático já cobre cenários
  de erro (não precisa adicionar nada).
- `pipeline.py` — defines `PipelinePhase` literal: as fases válidas
  são `garagem_error`, `garagem_pushback`, `garagem_no_slug`,
  `meeseeks_failure`, `dev_server_failure`, `success`.
- `docs/cenarios-e2e.md` — guia de autoria. **Leia antes de criar.**

### Padrões do projeto
- Nomes de pasta: `NN_descricao_em_snake_case`.
- `task.txt`: texto livre, pt-BR, sem markdown.
- `verify.py`: define função `verify(ctx) -> None`, raises
  `AssertionError` em falha.

## Implementação sugerida

Cenário `03_vague_prompt_pushback`:

```
task.txt:
"Melhore o código."

verify.py:
- assert phase == "garagem_pushback"
- assert garagem.parsed and not garagem.parsed.get("escopo_claro")
- assert len(garagem.parsed.get("duvidas_pro_rick", [])) >= 1
- assert db_row["terminal_phase"] == "garagem_pushback"
- assert db_row["garagem_outcome"] == "pushback"
- assert db_row["garagem_cost_usd"] is not None and > 0
```

Cenário `04_meeseeks_failure_impossible`:

```
task.txt:
"Importe a biblioteca `nao-existe-9000` no arquivo src/index.js,
faça `nao-existe.usar()` ser chamado no startup, e garanta que o
npm test continue passando."
```

Esse prompt é claro o suficiente pra Garagem aceitar (escopo
explícito, arquivos definidos, critério de pronto), mas
tecnicamente impossível — `npm test` vai falhar porque a lib não
existe. Meeseeks tenta, falha em `npm test`, não consegue commitar
sem testes verdes (skills/meeseeks.md), termina com 0 commits.

verify.py:
- assert phase == "meeseeks_failure"
- assert meeseeks and not meeseeks.success
- assert meeseeks.commits == []
- assert db_row["meeseeks_outcome"] == "failure"
- assert db_row["garagem_cost_usd"] > 0 and db_row["meeseeks_cost_usd"] > 0

## Testes a adicionar
Nenhum unit/integration novo. Só os 3 cenários E2E descritos.

## Decisões em aberto

### Cenário 05 (no_slug) é problemático

`garagem_no_slug` é uma fase teoricamente atingível: a Garagem
retorna `escopo_claro=true` mas `slug=""`. Na prática a Garagem
do MMB está calibrada a sempre produzir slug junto com o briefing
— mesmo que apenas como reflexo do `commit_descricao`. Forçar essa
fase exigiria:

- (a) editar `skills/garagem.md` temporariamente pra um cenário
  específico (péssima ideia — vaza estado entre cenários).
- (b) mockar `invocar_garagem` no test_scenarios.py especificamente
  pra esse cenário (acopla harness ao cenário).
- (c) aceitar que a fase `no_slug` não é triggerável organicamente
  e cobrir só via unit test.

**Recomendação:** apenas implemente `03` e `04`. Documente no
relatório final que `05` ficou aberto e por quê, e pergunte ao
Rick se ele quer caminho (b) ou (c).

## Dependências
- Bloqueia: C4 (calibração depende de ter cenários estabilizados).
- Bloqueado por: nada.

## Conflito potencial com
Nada. Só cria arquivos novos em `tests/e2e/scenarios/`. Roda em
paralelo com qualquer outra task.

## Estimativa
~2-3h. Maior parte do tempo é rodar os cenários ao vivo pra
validar que o prompt provoca a fase certa. Conta ~10 runs de
calibração a US$0.05 cada = US$0.50 de custo.
