# Discovery — Modos de operação (Trilha B)

## ID
B-discovery

## Trilha
B — Plataforma

## Status
✅ fechado em 2026-05-14 — output gerou reframe da trilha B em 5 tasks

## Objetivo

Definir como o MMB se relaciona com **múltiplos projetos-alvo** —
não só permitir cadastro (B1 original), mas explicitar dois modos
de engajamento, infra de contexto persistente, e proatividade do
orquestrador.

Este doc consolida a conversa que reframeou a trilha B inteira.

## Os dois modos — em uma frase cada

- **Pontual**: MMB executa tarefa discreta no alvo, não toca
  estrutura, stateless entre invocações. É como o MMB opera hoje.
- **Construtor**: MMB **acompanha** o alvo do nascimento ao
  amadurecimento. Implanta camada agêntica mínima, mantém sessão
  Claude persistente como memória, é proativo em sugerir próximos
  passos.

## Decisões fechadas

1. **Cada projeto tem um `mode`**: `construtor` ou `pontual`.
   Default no cadastro: `pontual` (mais seguro/menos invasivo).
2. **Modo evolui organicamente**: o orquestrador percebe sinais
   (volume de runs, complexidade do alvo, tempo de relacionamento)
   e sugere promoção. Rick aprova.
3. **Construtor implanta camada agêntica mínima** no alvo:
   - `AGENTS.md` (regras do projeto pra Garagem)
   - `.mmb/contexto.md` (memória explícita, atualizável)
   - `.mmb/decisoes.md` (registro append-only de decisões
     arquiteturais)

   **Não** replica `docs/tasks/`, `PROTOCOLO.md`, `scripts/` etc.
   Isso seria cosplay agêntico — o Meeseeks já é instruído por
   `skills/meeseeks.md`, não precisa de PROTOCOLO no alvo. Se um
   dia justificar (alvo extremamente complexo, múltiplos
   sub-agentes), escala depois.

4. **Contexto = sessão Claude persistente**. MMB salva
   `session_id` por projeto no SQLite (tabela `project_sessions`
   ou coluna em `projects`). Retoma via `claude -c <id>` ao iniciar
   fluxo de Garagem nesse projeto.
5. **Sessão precisa de compactação periódica**. Histórico cresce a
   cada turn (input tokens escalam). Mecanismo: a cada N turns ou
   X bytes de histórico, orquestrador resume em 1 mensagem síntese
   e abre nova sessão. Detalhe técnico de B2.
6. **`session_id` mora centralizado** no SQLite do MMB, não em
   arquivo no alvo. Alvo não carrega metadado externo. Cockpit
   pode inspecionar.
7. **Construtor é proativo**. Comprometido em fazer o projeto
   andar — sugere próximos passos, lembra do que ficou pendente,
   pinga Rick quando vê sinais de "parou". Requer scheduler novo.
8. **Multissessões coexistem.** Rick pode ter N projetos
   construtor + M projetos pontuais simultaneamente. Cada um com
   estado independente.
9. **Gatilho do bootstrap híbrido**: primeiro `/meeseeks` num
   projeto construtor sem contexto dispara prompt curto — "preciso
   te entrevistar primeiro pra ser útil aqui. Agora ou depois?".
   Friction baixa, previsibilidade preservada. Se "depois", marca
   pra perguntar de novo na próxima invocação.
10. **Entrevista adapta profundidade aos sinais**: se o alvo tem
    estrutura mínima (README, package.json, código real), entrevista
    é curta (5-7 perguntas, ~10min). Se é greenfield total,
    entrevista é longa (modo onboarding completo).
11. **Modelos por modo**: construtor usa Opus (raciocínio profundo,
    decisões arquiteturais sustentadas); pontual usa Sonnet (rápido,
    custo baixo). Decisão pode ser sobrescrita por env. Detalhe
    técnico de B2.

## Princípios herdados

- **Side-car observável**: módulos novos (sessão, scheduler, etc)
  vivem desacoplados do core, igual `logger/`, `aquario/`, `api/`.
- **Falha externa não derruba o bot**: sessão Claude expirou?
  Fallback pra stateless. Scheduler crashou? Outras funções seguem.
- **Decisões viram artefato**: tudo aqui vira código, docs, schema
  do DB — nada vive só na memória.

## Decomposição em tasks

A trilha B foi explodida em 5 tasks (de B1 original):

| ID | Foco | Modo | Pré-requisito |
|---|---|---|---|
| **B1** | Multi-projeto cadastro + `/project` + autocomplete + lookup runtime + campo `mode` | Pontual + base | nada |
| **B3** | Bootstrap interview + geração de camada agêntica mínima no alvo | Construtor | B1 |
| **B2** | Sessão Claude persistente da Garagem + compactação + modelo por modo | Construtor | B1, B3 |
| **B5** | Detecção de sinais + sugestão orgânica de promoção pontual→construtor | Ambos | B2 |
| **B4** | Proatividade — scheduler + canal de comunicação proativa do construtor | Construtor | B2 |

Ordem de implementação recomendada: **B1 → B3 → B2 → B5 → B4**.

Cada task ganha brief próprio quando chegar a vez (B1 já tem,
atualizado pós-discovery). B2-B5 ficam como esqueletos no INDEX
e ganham brief detalhado quando seu turno chegar.

## Relação com vizinhança

- **Trilha A (Presença)**: aquário (A1) é ortogonal — modo
  construtor não afeta payload do aquário direto. Quando A3 vier
  (multi-projeto no aquário), B1 já será pré-requisito.
- **Trilha E (Cockpit)**: cockpit exibe modo do projeto, sessões
  ativas, contexto persistido. Inputs visuais novos quando a
  trilha B avançar. Não bloqueia E2+ frontend.
- **Trilha D futura (orquestrador + bootstrap agêntico)**: tem
  sobreposição conceitual com B3, mas D é sobre MMB-de-meta
  (bootstrappar projetos como o `mmb-cockpit`). B3 é sobre alvos
  reais de produção. Convivem.

## Decisões deliberadamente adiadas

Não tratadas neste discovery, intencionalmente — quando a trilha
B avançar, voltamos:

- **UI da entrevista** (Discord modal? Conversa por mensagens?).
  Detalhe de B3.
- **Frequência do "ping" proativo** (cron diário? trigger por
  inatividade?). Detalhe de B4.
- **Compactação algorítmica vs por LLM** (resumir o histórico
  programaticamente ou usar Claude pra resumir?). Detalhe de B2.
- **Quando "rebaixar" um projeto** de construtor pra pontual
  (esquecer contexto antigo?). Provavelmente nunca — só ativa/
  desativa. Confirmado se necessário em B5.
