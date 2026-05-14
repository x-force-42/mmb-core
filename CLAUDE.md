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

Este projeto opera com workflow estruturado de orquestrador + agentes
delegados em worktrees paralelas. Dependendo do seu papel nesta
sessão, leia o doc certo:

- **Você é uma sessão Claude na raiz do MMB** (orquestrador), e o
  Rick está conversando contigo sobre planejar, discutir, delegar,
  revisar entregas, atualizar docs? → leia
  [`docs/ORQUESTRADOR.md`](docs/ORQUESTRADOR.md). Ele descreve
  o ciclo das 7 fases, princípios implícitos, anti-padrões.
- **Você é uma sessão Claude em uma worktree** (agente delegado),
  iniciada via `.tooling/bin/task-start.sh mmb-core <id>` (rodado
  da raiz do MMB)? → leia
  [`docs/tasks/PROTOCOLO.md`](docs/tasks/PROTOCOLO.md) primeiro,
  depois o brief da sua task em `docs/tasks/<id>-<slug>.md`.

## Operação como agente de task (bootstrap)

Se você é uma sessão Claude recém-iniciada neste repo e o Rick ainda
não te disse o que fazer, **siga este protocolo antes de qualquer
outra coisa**:

1. **Verifique se está numa worktree de task, não na raiz do repo.**
   Rode `git rev-parse --show-toplevel` e `git branch --show-current`.
   - Se você está na raiz do repo `mmb-core` e na branch default
     (`main`): avise o Rick e ofereça rodar
     `.tooling/bin/task-start.sh mmb-core <id>` (da raiz do MMB)
     pra criar a worktree antes de começar.
   - Se você está numa worktree (`.../.worktrees/<id>-<slug>`) e na
     branch `task/<id>-<slug>`: ok, prossiga.

2. **Liste as tasks abertas**. Leia `docs/tasks/INDEX.md` — é o
   registro canônico. Identifique as marcadas com 🎯 (prontas pra
   delegar) e, se já está numa worktree, qual delas casa com o slug
   da branch atual.

3. **Pergunte ao Rick** via `AskUserQuestion` qual task ele quer que
   você atue (ou se prefere uma conversa exploratória sem entrar em
   task). Se já está numa worktree, sugira como primeira opção a
   task da branch atual.

4. **Quando ele escolher, leia o brief específico**
   (`docs/tasks/<id>-<slug>.md`). Trate o brief como autoritativo —
   ele tem intenção, escopo (dentro/fora), critério de pronto,
   decisões em aberto e conflitos potenciais com outras tasks.

5. **Antes de qualquer edit**, releia `docs/tasks/PROTOCOLO.md`,
   especialmente o pré-flight de 4 invariantes. Eles existem
   porque agentes paralelos só convivem se cada um permanecer
   isolado no seu worktree+branch.

6. **Confirme decisões em aberto** do brief com o Rick antes de
   implementar. Não chute.

7. **Trabalhe**. Commits pequenos, mensagens no estilo do `git log`
   existente, hooks nunca pulados, `master` nunca recebe push
   direto. Você abre PR — só o Rick mergeia.

8. **Ao terminar**, relate em formato curto: o que foi feito, o que
   ficou aberto, decisões tomadas no caminho.

Se nada disso se aplica (Rick está fazendo pergunta exploratória,
debug, ou trabalho fora de uma task formal), apenas responda o que
foi perguntado. O bootstrap é pra quando você é um **agente
delegado** pra entregar uma task específica.
