# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## O que é isto

Um bot do Discord ("Mr. Meeseeks Box") que expõe o slash command
`/meeseeks <task>`. O comando dispara o CLI do `claude` em modo read-only
contra um projeto-alvo *separado* pra produzir um "briefing" JSON
estruturado — que é então formatado e devolvido como mensagem no Discord
pro usuário (Rick) repassar a um agente executor (o Meeseeks).

Este repositório é **só** o bot. O projeto que está sendo analisado mora
em `TARGET_PROJECT_PATH` (setado no `.env`).

A base inteira — strings de UI, comentários, prompts — está em português
brasileiro e usa pesado a terminologia de Rick & Morty (Garagem, Meeseeks,
Rick). Preserve essa voz ao editar strings voltadas pro usuário e o system
prompt; não traduza pra inglês.

## Rodando

```bash
.venv/bin/python bot.py
```

Variáveis obrigatórias no `.env`: `DISCORD_BOT_TOKEN`, `TARGET_PROJECT_PATH`.
Opcionais: `DISCORD_GUILD_ID` (limita o sync dos slash commands a uma guild
específica pra atualização instantânea — sem isso, o sync global pode
levar até uma hora), `CLAUDE_CLI` (default `claude`), `GARAGEM_TIMEOUT_S`
(default 300).

Não existe suíte de testes, config de linter ou etapa de build.

## Arquitetura

Três módulos, um arquivo de prompt:

- `bot.py` — cliente Discord e o comando `/meeseeks`. Cuida do ciclo de
  vida da interaction: `defer` → `followup.send` da mensagem de status →
  spawna uma task `_heartbeat` que reedita o status com tempo decorrido →
  `await invocar_garagem(...)` → cancela o heartbeat → renderiza o estado
  final (sucesso / pushback / erro). O limite de 2000 caracteres do
  Discord é tratado caindo pra anexo `briefing.md`.
- `garagem.py` — `invocar_garagem(task, project_path)` dispara o CLI do
  `claude` com `--allowed-tools Read,Glob,Grep` (estritamente read-only),
  `--output-format json` e `--append-system-prompt <conteúdo de
  skills/garagem.md>`. O CWD é o `project_path`, então o sub-Claude
  enxerga o projeto *alvo*, não este. Devolve um dataclass
  `GaragemResult` (`parsed | error | raw`).
- `config.py` — carregamento de env. Falha rápido em tempo de import se
  `DISCORD_BOT_TOKEN` faltar ou se `TARGET_PROJECT_PATH` não existir.
- `skills/garagem.md` — system prompt do sub-agente Garagem. Define a
  persona, regras de engajamento e o schema JSON de saída
  (`escopo_claro`, `prompt_meeseeks`, `arquivos_alvo`, `criterio_de_pronto`,
  `duvidas_pro_rick`). **Recarregado do disco a cada invocação** — dá pra
  iterar no prompt sem restartar o bot.

## Contrato do protocolo de saída

O branching do `bot.py` espelha o schema do `skills/garagem.md`. Se mudar
o schema, as duas pontas têm que andar juntas:

- `escopo_claro: false` → o bot renderiza o branch de "pushback" usando
  `duvidas_pro_rick`. `prompt_meeseeks` pode vir vazio.
- `escopo_claro: true` → o bot renderiza o branch de "briefing" usando
  `prompt_meeseeks`, `arquivos_alvo`, `criterio_de_pronto`.

A Garagem precisa emitir um objeto JSON puro. O `_extrair_json` em
`garagem.py` tira fences ```` ```json ```` acidentais, mas não recupera
de prosa em volta do JSON — mantenha o prompt rígido nesse ponto.

A chamada `claude -p ... --output-format json` devolve um *envelope*
(`{"result": "<string interna>", ...}`); a string interna é o que o
sub-Claude realmente produziu e é parseada separadamente. Duas camadas
de JSON, dois modos de falha — `garagem.py` distingue no campo `error`.

## Convenções a preservar

- O prompt da Garagem proíbe números de linha em briefings (caducam).
  Ancora em nomes ("logo após `loadGameConfig`"). Não amoleça isso — o
  ponto inteiro é briefing que sobrevive a churn de código.
- A Garagem é read-only por design (`--allowed-tools Read,Glob,Grep`).
  Não dê tools de escrita pra ela — a execução tipo Meeseeks é um
  estágio separado, ainda não construído.
- Edições do heartbeat engolem `discord.HTTPException` e `NotFound` em
  silêncio. É intencional (rate limit / mensagem deletada não pode
  derrubar o fluxo principal). Mantenha novas edições do Discord
  igualmente defensivas.

## Camada agêntica — onde ler antes de operar

Este projeto faz parte do ecossistema MMB, que opera com workflow
estruturado em três papéis cujos perfis vivem no andaime cross-repo
em `/MMB/.tooling/profiles/`. Dependendo do seu papel nesta sessão,
leia o doc certo:

- **Você é uma sessão Claude na raiz `/MMB/`** (Orquestrador Mestre),
  conversando com Rick sobre planejar intenções cross-repo, decompor
  em tarefas, materializar como issues no GitHub? → leia
  [`/MMB/.tooling/profiles/master.md`](/MMB/.tooling/profiles/master.md).
- **Você é uma sessão Claude na raiz deste repo** (Orquestrador de
  Projeto do `mmb-core`), recebendo briefing do Mestre, abrindo
  sub-issues, spawnando atômicos? → leia
  [`/MMB/.tooling/profiles/project-orchestrator.md`](/MMB/.tooling/profiles/project-orchestrator.md).
- **Você é uma sessão Claude numa worktree de task**
  (`.worktrees/<id>-<slug>`), spawnada via
  `/MMB/.tooling/bin/task-start.sh mmb-core <id>`? → leia
  [`/MMB/.tooling/profiles/atomic-agent.md`](/MMB/.tooling/profiles/atomic-agent.md)
  e busque sua sub-issue no GitHub (ela é seu prompt).
