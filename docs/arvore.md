# Mr. Meeseeks Box — Plano

Mapa vivo. Norte de médio-longo prazo + decomposição em trilhas
paralelas + dependências explícitas. Atualizado a cada milestone.

## Visão

**Plataforma multi-projeto de execução determinística por agentes.**
O Rick lança uma tarefa em qualquer projeto cadastrado via Discord.
Uma Garagem com contexto persistente daquele projeto planeja; um
Meeseeks com identidade própria executa em worktree isolada; um
aquário ao vivo mostra todo Meeseeks em curso, em todos os projetos,
respirando até morrer feliz ou derrotado. Tudo gravado em SQLite,
calibrável por modelo (Opus na decisão, Sonnet na execução),
auditável retroativamente e reproduzível via cenários E2E.

A versão final deve dar pra Rick gerenciar 5+ projetos sem trocar de
contexto mental — o sistema faz a separação por baixo.

## Como visualizar

`.md` com Mermaid abre em VSCode (ext. `bierner.markdown-mermaid`,
`Ctrl+Shift+V`), GitHub, [mermaid.live](https://mermaid.live),
Obsidian e similares.

## Legenda

| Cor | Símbolo | Significado |
|---|---|---|
| 🟢 verde | ✅ | Concluído, em uso |
| 🟡 amarelo | 🟡 | Em curso agora |
| ⬜ cinza | ⬜ | Próximo, escopo definido |
| 🔒 cinza escuro | 🔒 | Bloqueado por dependência |
| 🎯 alvo | 🎯 | Pronto pra delegar (sem dep pendente, escopo fechado) |

---

## Onde estamos

Pipeline ponta-a-ponta funcional contra **um único** `TARGET_PROJECT_PATH`.
Observabilidade gravada em SQLite com 4 queries prontas via Datasette.
E2E cobre os principais branches do `PipelineResult`: success (×2),
garagem_pushback, meeseeks_failure. Trilha C **inteira** entregue
por agentes externos em ciclo completo de delegação (C1 + C2
mergeadas via PROTOCOLO.md, sem intervenção pontual).

Próximo movimento: **A1** isolado (toca `bot.py` pesado, agente
sequencial), com possibilidade de abrir **C3** ou **C4** em paralelo
sem conflito. Depois de A1 mergear, **B1**. Em paralelo, está
maturando a discussão de **Trilha D** (orquestrador + bootstrap
agêntico de projeto) — ainda em design.

```
PASSADO ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ FUTURO
●━●━●━●━●━●━●━●━●━●━●━●━ ━ ━ ━ ━ ━ ━ ━ →
                      ↑
            Trilha C inteira fechada
            v0.5.0+ candidato sólido
```

---

## Histórico — atos concluídos

```mermaid
mindmap
  root((MMB<br/>passado))
    ✅ ATO I — Pipeline funcional
      commit 5ab35c3
      Discord bot + /meeseeks
      Garagem read-only
      Meeseeks full perms · worktree isolada
    ✅ ATO II — Imersão A+B 🏷️ v0.1.0
      commit 4d17319
      Microcopy + heartbeat decay
    ✅ ATO III — Refactor modular 🏷️ v0.2.0
      commit fba05fc
      formatters · parsing · claude_runner · pipeline
    ✅ ATO IV — Guardrails de teste 🏷️ v0.3.0
      commits c4cafbb · e64e7ac
      192 testes · 89% cobertura
    ✅ ATO V — Imersão visual D 🏷️ v0.4.0
      commit 45269d0
      Embeds Discord · paleta · overflow
    ✅ ATO VI — Observabilidade
      commits 046abdb · 086c002
      Logger SDK · integração ao core
      Datasette + queries salvas
      fix cost_usd · criticidade/complexidade
    ✅ ATO VII — Arnês E2E
      commit d279e6c
      Fixture isolado · cleanup auto
      2 cenários verdes · ~$0.10/suite
      docs/cenarios-e2e.md
```

```mermaid
gitGraph
   commit id: "5ab35c3"
   commit id: "4d17319" tag: "v0.1.0"
   commit id: "fba05fc" tag: "v0.2.0"
   commit id: "e64e7ac" tag: "v0.3.0"
   commit id: "45269d0" tag: "v0.4.0"
   commit id: "046abdb"
   commit id: "086c002"
   commit id: "d279e6c" tag: "v0.5.0?"
   commit id: "ee7fe3f"
   commit id: "b530cca"
   commit id: "51fdce9"
   commit id: "ff08269" type: HIGHLIGHT
```

> A tag `v0.5.0` ainda não foi cravada. Pronta quando você quiser.

---

## Trilhas paralelas

Três trilhas independentes. Atos com 🎯 estão prontos pra delegar a
um agente externo sem você precisar acompanhar passo a passo —
escopo fechado, dependências resolvidas, critério de pronto claro.

```mermaid
mindmap
  root((MMB<br/>futuro))
    Trilha A · Presença
      🎯 A1 Aquário mono-projeto
        WebSocket client com reconnect
        Mapeia decay → health 0..1
        Eventos born/died/freaking_out
        Aceita project mockado por enquanto
      ⬜ A2 Identidade visual
        Camada C · Meeseeks-XXXX nome único
        Camada E · botões inline mergear/descartar
      🔒 A3 Aquário multi-projeto
        Depende B1
        Adiciona campo project ao payload
        Aquário compartilhado entre projetos
    Trilha B · Plataforma
      🎯 B1 Projetos cidadão 1a classe
        Comando /project add list remove
        Discord autocomplete de projeto
        TARGET_PROJECT_PATH some · runtime lookup
        Migração de mmb.db existente
      ⬜ B2 Garagem com contexto persistente
        Decisão de modelo · ver pergunta aberta
        Storage de contexto por projeto
        Inclusão automática no system_prompt
        Depende B1
      ⬜ B3 Modelo por fase
        Garagem Opus 4.7 explícito
        Meeseeks Sonnet 4.6 explícito
        Config via env por fase
        Independente de B1/B2 · pode ir junto
    Trilha C · Robustez
      ✅ C1 Retry transiente no runner
        commit b530cca
        FileNotFound + exit 2 detectados
        2 retries com backoff 1.5s+3s
        _is_transient_autoupdate isolado
        5 testes novos
      ✅ C2 Cenários E2E de erro
        commit ff08269
        03 vague_prompt → pushback
        04 build quebrado → meeseeks_failure
        05 no_slug fora · doc lição p/ C4
        4 cenários E2E totais verdes
      ⬜ C3 Cenário E2E anti-escopo
        Verify falha se briefing inflar
        Trava disciplina da Garagem
      ⬜ C4 Calibração com cenários reais
        5 cenários reais PO/DEV
        Comparativo de modelo
        Desbloqueada por C2
```

### Mapa de dependências

```mermaid
flowchart LR
  classDef ready  fill:#cfa,stroke:#393,stroke-width:2px
  classDef done   fill:#9d9,stroke:#171,stroke-width:2px,color:#000
  classDef todo   fill:#eee,stroke:#999
  classDef locked fill:#ccc,stroke:#666,stroke-dasharray:4

  A1[🎯 A1 Aquário mono]:::ready
  A2[⬜ A2 Camadas C+E]:::todo
  A3[🔒 A3 Aquário multi]:::locked

  B1[🎯 B1 Projetos 1a classe]:::ready
  B2[⬜ B2 Garagem contexto]:::todo
  B3[⬜ B3 Modelo por fase]:::todo

  C1[✅ C1 Retry transiente]:::done
  C2[✅ C2 E2E erro]:::done
  C3[⬜ C3 E2E anti-escopo]:::todo
  C4[⬜ C4 Calibração real]:::todo

  B1 --> A3
  B1 --> B2
  C2 --> C4

  B3 -.opcional.-> B2
```

---

## Coreografia recomendada

Você indicou que rodaria **três frentes em paralelo** (caminho C),
delegando aos agentes CLI. Sugestão de quem vai pra onde, levando em
conta isolamento de mudanças (pra evitar conflito de merge):

| Trilha | Quem | Por quê |
|---|---|---|
| **A1** Aquário mono | Agente focado | Toca arquivos novos (client websocket) + hook no `bot.py` em pontos isolados. Conflito baixo. |
| **B1** Projetos cidadão | Agente focado | Refactor amplo em `config.py`, `bot.py`, `logger`. **Não rode em paralelo com A1** se evitar — ambos tocam `bot.py`. Faça B1 sequencial após A1 ou planeje merge. |
| **C1** Retry transiente | Agente leve | Pequeno, isolado em `claude_runner.py` + testes. Roda em paralelo a qualquer coisa sem conflito. |
| **C2** Cenários E2E erro | Você ou agente leve | Só adiciona arquivos em `tests/e2e/scenarios/`. Conflito zero. |

**Ordem ótima se for delegar 3 agentes esta semana:**

1. Dispara **C1** + **C2** em paralelo (zero risco de merge).
2. Quando C1 fechar, dispara **A1** (aquário precisa do `bot.py` estável).
3. **B1** entra DEPOIS de A1 mergeado — eles concorreriam pelo mesmo arquivo.
4. B2/B3 depois de B1.
5. A2/A3 depois de B1.

---

## Marcos (releases)

| Tag | Conteúdo | Quando |
|---|---|---|
| `v0.5.0` | Atos VI + VII | Pronto — tag a qualquer momento |
| `v0.6.0` | C1 + C2 | Quando trilha C estabilizar |
| `v0.7.0` | A1 + A2 | Primeira entrega visível da trilha A |
| `v0.8.0` | B1 | Multi-projeto operacional |
| `v0.9.0` | A3 + B2 + B3 | Plataforma viva com presença |
| `v1.0.0` | Visão completa | Quando 5 projetos rodarem confortável |

---

## Perguntas em aberto

Decisões que travam atos. Resolver antes ou junto com o início do ato.

1. **B2 — Como Garagem mantém contexto?** Prompt enriquecido auto-editado,
   memória estruturada em DB, ou sessão contínua via `claude -c`?
2. **A1 — `recovered` no protocolo do aquário** — instrumentar
   Meeseeks pra emitir (ex: passou no teste depois de falhar), ou
   deixar não usado e aceitar saúde monotônica decrescente?
3. **Quando taggar v0.5.0?** — não bloqueia nada, mas marca o
   estado consolidado antes da grande virada.

---

Este arquivo é vivo — atualizo a cada milestone. Próxima revisão
quando uma das trilhas fechar primeira entrega.
