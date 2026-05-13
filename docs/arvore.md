# Árvore do projeto

Visualização do caminho percorrido + próximos passos. Atos concluídos
ficam verdes, o atual amarelo, os próximos cinza (e cinza opaco quando
bloqueados por dependência).

## Como visualizar

Em ordem de fricção (menor → maior):

1. **VSCode + extensão "Markdown Preview Mermaid Support"**
   (`bierner.markdown-mermaid`) — grátis, oficial. Abre este `.md` e
   dá `Ctrl+Shift+V` pro preview lateral.
2. **GitHub** renderiza `.md` com Mermaid nativamente.
3. **[mermaid.live](https://mermaid.live)** — cola o bloco, vê na hora.
4. **Obsidian / Notion / Confluence** — renderizam nativo.

## Legenda

| Cor | Símbolo | Significado |
|---|---|---|
| 🟢 verde | ✅ | Ato concluído, em produção, smoke testado |
| 🟡 amarelo | 🟡 | Ato em curso (você está aqui) |
| ⬜ cinza | ⬜ | Próximo ato, escopo definido mas não iniciado |
| 🔒 cinza apagado | 🔒 | Ato bloqueado por dependência ou decisão externa |

---

## Mindmap — árvore conceitual

Cada nó central é um **ato** do projeto. Os filhos detalham o conteúdo.
Atos pintados conforme a legenda acima.

```mermaid
mindmap
  root((Mr. Meeseeks<br/>Box))
    ✅ ATO I — Pipeline funcional
      commit 5ab35c3
        Discord bot + /meeseeks
        Garagem read-only
          Schema JSON estrito
          slug + commit em inglês
        Meeseeks full perms
          test → write tests → build → commit
        Auto-chain determinístico
        Worktree isolada
        Dev server background
      side auto-updater
        DISABLE_AUTOUPDATER=1
        FileNotFoundError graceful
      side calibração Garagem
        Orçamento ≤5 Reads
        Refactor 3 casos
        Critério rigoroso
    ✅ ATO II — Imersão A+B 🏷️ v0.1.0
      commit 4d17319
      Microcopy POOF Look at me
      Heartbeat decay 5 fases
      Activity Watching Rick
      docs viva: plano-imersao, progresso
    ✅ ATO III — Refactor modular 🏷️ v0.2.0
      commit fba05fc
      formatters.py funções puras
      parsing.py extrair_json
      claude_runner.py subprocess único
      pipeline.py headless
      bot.py linear
    ✅ ATO IV — Guardrails de teste 🏷️ v0.3.0
      commit c4cafbb
        61 testes formatters+parsing
        pytest infra
      commit e64e7ac
        146 testes 91% cov
        integration test worktree
    ✅ ATO V — Imersão visual D 🏷️ v0.4.0
      commit 45269d0
      embeds.py paleta 6 cores
      overflow elegante
      31 testes embeds 100%
    🟡 ATO VI — Observabilidade
      🏷️ v0.5.0 iminente
      logger/ SDK desacoplado
        tabela projects
        tabela runs — métricas completas por fase
        GaragemEntry · MeeseeksEntry · DevServerEntry
        SQLite · agnóstico ao core
        29 testes 100%
      integração ao core bot.py
      dashboard front futuro
    ⬜ ATO VII — Calibração científica
      5 cenários reais PO/DEV catalogados
      runner headless via pipeline
      relatório de performance comparativo
      depende Ato VI
    🔒 ATO VIII — Polish
      Camada C Meeseeks nome único
      Camada E botões interativos
      Fase 3 Config dataclass
      Fase 4 DevServer class
      depende Ato VII
```

---

## gitGraph — timeline de commits e tags

Espelha o `git log` real, com tags marcando os marcos. Estende com
**bolinhas previstas** pros próximos atos — texto em parênteses
indica que ainda não existem no histórico.

```mermaid
gitGraph
   commit id: "init"
   commit id: "5ab35c3"
   commit id: "4d17319" tag: "v0.1.0"
   commit id: "fba05fc" tag: "v0.2.0"
   commit id: "c4cafbb"
   commit id: "e64e7ac" tag: "v0.3.0"
   commit id: "45269d0" tag: "v0.4.0"
   commit id: "(logger integrado)" type: HIGHLIGHT
   commit id: "(calibração)" type: REVERSE
   commit id: "(polish acts)" type: REVERSE
```

> Bolinhas tipo **HIGHLIGHT** (Camada D) já foram produzidas mas estão
> pendentes de commit/tag. Bolinhas tipo **REVERSE** (visualmente
> vazadas) são previsões — ainda não existem.

---

## Onde estamos agora

```
PASSADO ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ FUTURO
●━━●━━●━━●━━●━━●━━🟡 ┄┄┄ ⬜ ┄┄┄ 🔒
               ↑
          você está aqui
          Ato VI — logger SDK pronto
          falta integrar ao core + tag v0.5.0
```

## Próximos ramos a brotar

Atos VI e VII já estão no mindmap acima como nós cinza. Quando
entrarmos em cada um, vão amadurecendo pra amarelo (atual) e depois
verde (concluído). Este arquivo é vivo — atualizo a cada milestone.
