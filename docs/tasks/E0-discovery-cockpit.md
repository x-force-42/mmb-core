# Discovery — Cockpit de Operações

## ID
E0

## Trilha
E — Cockpit de Operações

## Status
✅ fechado em 2026-05-14 — output gerou brief E1 implementável

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

1. **Prioridade do MVP: governança + post-mortem.** As três
   personas importam (operação ao vivo, post-mortem, governança),
   mas o foco inicial é **extrair valor dos logs imediatamente
   pra calibração de modelos**. Operação ao vivo fica pra v2.
   Sem necessidade de real-time na primeira versão.
2. **Stack frontend: Vite + React + Vitest** (TypeScript por
   default). Single Page App rodando local. Mesmo ecossistema do
   fixture E2E (que usa node --test) e do front do aquário.
3. **Cockpit e aquário são vizinhos desacoplados.** Bebem da
   mesma fonte (SQLite do logger) mas vivem em codebases e
   processos independentes. Sem iframe, sem link interno, sem
   sobreposição de UI.
4. **Cockpit vive em repo separado** (`~/llab/mmb-cockpit`, a
   criar futuramente). MMB hospeda a **API** que o cockpit
   consome. Especificação da API mora aqui no MMB.
5. **Data layer = FastAPI thin layer** no MMB, importando o
   `logger/` SDK. Cockpit bate em `localhost:<porta>/api/...`.
   Datasette continua existindo paralelamente como ferramenta
   ad-hoc/power-user — não é substituída.
6. **Telas do MVP**:
   - **(a) Dashboard de governança**: agregados (custo/dia, runs/dia,
     taxa de pushback, tempo médio).
   - **(b) Lista de runs** navegável com filtros (projeto, fase
     terminal, intervalo de datas) e ordenação.
   - **(c) Detalhe de run** completo pra post-mortem, incluindo
     edição dos campos manuais (`merged_to_main`,
     `assertiveness_score`, `review_note`).
   - Telas (d) catálogo de projetos, (e) detalhe de projeto,
     (f) comparativo de modelos ficam pra v2 conforme B1/B2/B3
     forem entregando schema.
7. **API roda em processo separado** do bot (`uvicorn api.app:app`).
   Independência de lifecycle — cockpit funciona mesmo com bot
   fora do ar. Comparativo: bot e API compartilham só o SQLite.
8. **Semântica dos campos editáveis**:
   - `merged_to_main` INTEGER tri-state: `1` mergeado, `0`
     descartado, `NULL` ainda não decidido.
   - `assertiveness_score` INTEGER escala Likert 1-5: `1` errou
     feio, `3` deu pra usar, `5` perfeito. `NULL` não avaliado.
   - `review_note` TEXT livre, sem limite. `NULL` não anotado.
9. **Endpoints da API REST** (porta sugerida 8765):
   - `GET /api/runs` paginado com filtros (`project`, `phase`,
     `from`, `to`, `limit`, `offset`, `order`).
   - `GET /api/runs/{id}` detalhe completo + briefing parseado.
   - `PATCH /api/runs/{id}` aceita apenas os 3 campos manuais.
   - `GET /api/projects` lista de projetos cadastrados.
   - `GET /api/metrics/overview?days=30` agregados pro dashboard.
10. **CORS habilitado** pra `http://localhost:5173` (Vite default
    do cockpit). Sem auth — é localhost.

## Decisões em aberto

_(preenchido conforme aparecem)_

## Personas & uso

**Persona única**: o Rick (você).

**Gatilho principal do MVP**:

- **Post-mortem** — abrir após uma run pra entender o que aconteceu,
  ler briefing+relatório+diff, anotar review.
- **Governança / calibração** — abrir periodicamente pra olhar
  agregados: custo, taxa de pushback, performance por modelo, etc.
  É a base pra C4 (calibração com cenários reais).

**Gatilho futuro (v2)**:

- **Operação ao vivo** — ver Meeseeks ativos em formato lista/tabela.
  Sobreposição parcial com o aquário, mas formato funcional.

## Entidades a expor

| Entidade | Fonte | Read | Edit |
|---|---|---|---|
| Run | tabela `runs` | todos os campos | só `merged_to_main`, `assertiveness_score`, `review_note` |
| Project | tabela `projects` | todos | nenhum (cadastro virá via Discord em B1) |
| Métricas agregadas | derivadas via SQL agregação | somente leitura | n/a |

Entidades adiadas pra v2 (chegam com B1/B2/B3):

- Garagem por projeto (depende B2)
- Comparativo de modelo (depende B3 + dados acumulados)
- Detalhe de projeto com suas runs (B1 mergeie)

## Vistas

MVP do cockpit (a ser implementado no repo separado):

- **(a) Dashboard** — cards/gráficos com agregados de governança.
- **(b) Lista de runs** — tabela paginada com filtros.
- **(c) Detalhe de run** — view completa + form de edição dos 3
  campos manuais.

## Stack

### Lado MMB (este repo, escopo do E1)

- **Framework**: FastAPI.
- **Servidor**: uvicorn.
- **Schemas**: Pydantic v2.
- **Estrutura**: módulo `api/` no repo, espelhando padrão do
  `logger/`. Importa do `logger/` pra ler; SQL agregado direto
  na conexão SQLite quando necessário (métricas).
- **Tests**: `httpx` + `fastapi.testclient.TestClient` em
  `tests/unit/test_api_*.py`. Banco em `tmp_path`.

### Lado cockpit (repo separado futuro — fora do escopo do MMB)

- **Build**: Vite.
- **UI**: React + TypeScript.
- **Tests**: Vitest.
- **Comunicação**: REST JSON via `fetch` ou `react-query` (decisão
  do agente do cockpit).
- **Estilo / gráficos**: a definir no repo do cockpit (Tailwind?
  recharts? CSS modules? — não nos importa aqui).

## MVP

**Escopo total do MVP do cockpit = E1 (API) + cockpit-repo MVP
(frontend)**. Esta task E0 fecha discovery; E1 entrega o backend
implementável. O frontend cabe num projeto à parte (fora deste
repo) e tem seu próprio roadmap.

## Aspirações futuras

Fora do escopo MVP/E1, mas vale ter no radar:

- **Push em tempo real** (WebSocket no MMB pro cockpit) — vem
  quando "operação ao vivo" virar prioridade.
- **Telas adicionais** (catálogo de projetos, detalhe de projeto,
  comparativo de modelos) — entrarão à medida que B1/B2/B3
  destrancarem schema.
- **Auth** — só relevante se sair de localhost.
- **Versionamento de API** (`/api/v1/...`) — não no MVP, mas
  vale planejar pro caso de quebra de contrato com o cockpit.

## Relação com vizinhança

- **Datasette**: continua existindo paralelamente. É ferramenta
  ad-hoc / SQL livre / power-user. Cockpit é a view curada,
  navegável, com edição de campos. **Não substitui Datasette.**
- **Aquário (A1)**: vizinho desacoplado. Mesma fonte de dados
  (SQLite do logger), processos e UIs independentes. Aquário é
  "vida ao vivo" (push WebSocket); cockpit é "histórico
  navegável" (pull REST). Sem overlap funcional no MVP.
- **Multi-projeto (B1)**: cockpit começa monoprojeto. Quando B1
  mergear e a tabela `projects` ganhar `active` + soft delete,
  cockpit adiciona dropdown de filtro por projeto sem refactor
  estrutural — só ajusta queries.
- **Garagem com contexto (B2)**: quando B2 vier, cockpit ganha
  uma seção/aba pra mostrar o contexto persistido por projeto.
  Fora do MVP, fora do E1.
