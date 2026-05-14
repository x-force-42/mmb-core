# Orquestrador — modus operandi do MMB

Doc espelho de [`tasks/PROTOCOLO.md`](tasks/PROTOCOLO.md): aquele
fala como um **agente delegado** deve operar; este fala como o
**orquestrador** (sessão Claude na raiz do MMB conversando com o
Rick) deve operar.

Não é teoria — é a leitura honesta de um padrão que emergiu nas
primeiras semanas do projeto e entregou de forma consistente. Cinco
tasks delegadas em sequência (C1, C2, E0 discovery, E1, scaffold
multi-agente) sem retrabalho substancial, sem agente saindo de
escopo, sem merge conflict não-previsto.

Este doc existe pra que isso seja replicável — sem depender da
memória de uma sessão específica.

## Os atores

| Ator | Quem é | Onde mora | O que faz |
|---|---|---|---|
| **Rick** | Humano dono do projeto | Termo + Discord | Decide, prioriza, merga, paga a conta |
| **Orquestrador** | Sessão Claude na raiz do MMB | `master` | Discovery, briefs, docs, coordenação |
| **Agente delegado** | Sessão Claude em worktree | `.worktrees/<id>-<slug>` | Executa **uma** task específica |
| **Sub-agente** | Claude rodado pelo bot via `claude -p` | Subprocess do MMB | Garagem ou Meeseeks numa run real |

Orquestrador e agente delegado são **a mesma ferramenta** (Claude
CLI), em papéis diferentes. A worktree é o que separa.

## O ciclo principal — do brainstorm ao merge

Sete fases. Nem toda task passa por todas — hotfix de 1 linha pula
muita coisa; uma trilha nova passa por tudo.

### 1. Brainstorm em conversa

Rick traz uma necessidade — pode vir como "preciso fazer X", "como
a gente faz Y?", ou "isso aqui não tá fazendo sentido". Orquestrador
ouve, valida que entendeu, e sinaliza se acha que é caso de:

- **Resposta direta** — pergunta exploratória, debug, "como funciona
  X". Não vira task.
- **Hotfix pequeno** — orquestrador pode fazer em até ~20min, sem
  brief. Commita direto em `master`.
- **Trilha existente** — cai numa task já mapeada (`docs/tasks/`).
  Pula direto pra fase 5.
- **Discovery formal** — é uma novidade real, vale passar pelas
  fases 2-4.

Aqui o orquestrador desafia o framing: "essa é a coisa certa?",
"você quer mesmo isso agora?", "qual é o ganho?". Só depois de
combinar o porquê é que faz sentido decidir o como.

### 2. Discovery iterativa

Quando a coisa é grande o suficiente pra justificar trilha ou task
nova, vira **conversa estruturada**:

- Orquestrador traz **3 perguntas por rodada**, focadas no que
  destranca a próxima decisão. Mais do que isso vira lista de
  burocracia.
- Cada rodada produz **decisões consolidadas** + **decisões em
  aberto**.
- Decisões viram texto, vivem num doc tipo `docs/tasks/E0-...md`
  no formato discovery (não-implementável).
- Iterar até as **decisões em aberto cheguem a zero**.
- Quando zero: discovery fecha, vira brief.

Sinal de que discovery acabou: o orquestrador consegue escrever o
brief sem precisar inventar nada.

### 3. Brief de delegação

Brief é o documento autoritativo do que o agente vai fazer. Mora em
`docs/tasks/<id>-<slug>.md`. Estrutura definida em
[`tasks/INDEX.md`](tasks/INDEX.md) seção "Esqueleto de brief".

**Princípio central**: o brief deve ser autossuficiente. Um agente
recém-iniciado, sem contexto desta sessão, precisa conseguir entregar
só com:

1. O brief.
2. O código atual do projeto.
3. `docs/tasks/PROTOCOLO.md`.

Se o agente precisar voltar e perguntar algo que não está no brief,
o brief falhou. Nada de "decisão em aberto" no brief de uma task 🎯
pronta — se está aberta, é discovery não terminou ainda.

### 4. Atualização do mapa

Atomicamente com o brief, atualizar:

- **`tasks/INDEX.md`** — entrada na tabela com status, link pro brief.
- **`tasks/INDEX.md`** matriz de paralelismo — quais outros 🎯 tocam
  arquivos em comum.
- **`arvore.md`** — nó na trilha apropriada com 🎯 ready ou 🔒.
- **`arvore.md`** flowchart de dependências.

Tudo num único commit `docs(<id>): ...`. Map e brief sempre andam
juntos.

### 5. Provisionamento da worktree

Rick roda `scripts/task-start.sh <id>`. Script:

- Atualiza `master` (`git pull` se houver remoto, senão skip).
- Cria worktree em `.worktrees/<id>-<slug>/` com branch
  `task/<id>-<slug>` a partir de `master`.
- Se a worktree já existe (re-entrada), só relembra o path.

Esse passo é deliberado — não automatizar pra dentro do agente.
Razões:

- **Estado óbvio**: Rick vê no terminal exatamente o que foi criado.
- **Paralelismo trivial**: 3 terminais, 3 `task-start.sh`, 3 `claude`.
- **Sem slip**: o agente nasce já no path certo, não precisa decidir.
- **Ritual**: o gesto do `task-start.sh` marca "vou trabalhar nisso
  agora".

### 6. Bootstrap do agente

Rick faz `cd` na worktree e roda `claude`. O agente recém-iniciado
lê `CLAUDE.md`, vê a seção "Operação como agente de task", e segue:

1. Pré-flight (worktree ≠ raiz, branch ≠ master, alinhamento com
   master, working tree limpa) — em `PROTOCOLO.md`.
2. Lê `INDEX.md`, identifica qual task casa com o slug da branch.
3. Pergunta ao Rick via `AskUserQuestion` qual task atacar (já
   sugerindo a candidata óbvia).
4. Lê o brief autoritativo.
5. Confirma decisões em aberto se houver (não deveria haver em 🎯).
6. Trabalha.

A barreira de entrada do agente é **uma pergunta**. Tudo o resto
está em docs versionados.

### 7. Entrega, merge, atualização

Agente entrega → Rick revisa (diff, eventualmente roda testes
localmente) → Rick merga → Rick avisa o orquestrador.

Orquestrador então:

- Inspeciona o que foi mergeado (`git log`, `git diff`).
- Dá um veredito honesto: respeitou escopo? Decisões em aberto
  resolvidas com alinhamento? Algum sinal de alerta?
- Atualiza `INDEX.md`, `arvore.md`, `progresso.md`.
- Commita como `docs(<id>): ...`.

Esse commit é o que "fecha o ciclo". A próxima sessão olhando o
log entende imediatamente o que aconteceu.

## Princípios implícitos

Esses não são regras formais, são **observações do que funcionou**.
Quebrar exige decisão consciente, não acidente.

1. **Conversa é pra decisões, brief é pra execução.** Misturar os
   dois tipos de discurso causa briefing inflado ou conversa
   travada por detalhes prematuros.
2. **Brief é autoritativo, agente não negocia escopo.** Se aparece
   algo fora, agente **flagga e segue** com o que tá no brief.
   Anti-padrão clássico: agente "aproveitando o momento" pra
   refatorar coisa adjacente.
3. **Docs são a camada de consenso.** Não chame nada de "decidido"
   se não está em INDEX/arvore/brief. Memória de sessão não conta.
4. **Scripts enforcem invariantes, não são docs.** `task-start.sh`
   cria worktree limpa porque verificar "estado correto" é mais
   barato que "consertar estado errado".
5. **Orquestrador não toca código de produção.** Só docs, mapas,
   scripts. Se aparece tentação de "ah deixa eu corrigir isso
   aqui", é sinal de que falta um brief.
6. **Paralelismo é deliberado.** Toda task 🎯 ganha matriz de
   conflito antes de poder ir simultânea com outra.
7. **Validação é iterativa.** Cada merge atualiza progresso e
   refina próxima rodada. Não tem big-bang.

## Anatomia da camada documental

A camada agêntica tem 5 tipos de doc, com tempo de vida diferente:

| Doc | Tempo de vida | Quem mantém | Para quem é |
|---|---|---|---|
| `CLAUDE.md` | Permanente | Orquestrador | Toda sessão Claude |
| `docs/ORQUESTRADOR.md` | Permanente | Orquestrador | Outras sessões orquestradoras |
| `docs/tasks/PROTOCOLO.md` | Permanente | Orquestrador | Agentes delegados |
| `docs/tasks/INDEX.md` | Mutável (atualizado a cada task) | Orquestrador | Agentes + Rick |
| `docs/tasks/<id>-<slug>.md` | Permanente como histórico, ativo até ✅ | Orquestrador escreve, agente lê | Agente delegado |
| `docs/arvore.md` | Mutável (atualizado a cada milestone) | Orquestrador | Rick + planejamento futuro |
| `docs/progresso.md` | Append-only (mais novo no topo) | Orquestrador | Histórico narrativo |

**Permanente** = nunca apaga, evolui. **Mutável** = sobrescreve
estado atual. **Append-only** = só cresce.

## Anti-padrões observados (corrigir cedo)

### "Brief com decisões em aberto pendentes"

Sintoma: agente delegado pergunta sobre algo no meio do trabalho,
quebra o fluxo, gasta turn no plumbing.

Causa: discovery não terminou; foi marcado 🎯 cedo demais.

Cura: agente para, orquestrador volta pra discovery, decisões
fecham, brief é atualizado, agente reinicia.

### "Agente delegado refatorando código vizinho"

Sintoma: diff contém arquivos fora do "Dentro" do brief.

Causa: brief não foi explícito o suficiente no "Fora", ou agente
não respeitou.

Cura: rejeitar o merge. Brief atualizado se a delimitação foi
ambígua. Agente reinicia com escopo recortado.

### "Orquestrador implementando 'um detalhezinho'"

Sintoma: orquestrador edita `bot.py`, `garagem.py`, ou outro código
de produção fora de docs/scripts.

Causa: surgiu um pequeno bug ou ajuste durante conversa e parece
"rápido demais pra valer um brief".

Cura: se é mesmo 1-2 linhas trivial e óbvio, ok, commit direto
explicando no commit message. Se passa disso, vira brief.
Tentação se esconde aqui — é onde escopo silenciosamente cresce.

### "Sessão paralela sem matriz de conflito"

Sintoma: duas worktrees mexendo nos mesmos arquivos, conflito de
merge surpresa.

Causa: a matriz em `INDEX.md` não foi atualizada antes da segunda
worktree ser criada.

Cura: orquestrador é responsável por atualizar a matriz quando um
brief novo entra. Rick olha a matriz antes de rodar `task-start.sh`
em paralelo.

### "Hotfix sem rastro"

Sintoma: master ganha commit `fix: ...` sem entrada em
`progresso.md` nem menção em `INDEX.md`.

Causa: hotfix pequeno demais pra "valer" o ritual.

Cura: ok pra commit direto, mas mencionar em `progresso.md` quando
algo material acontecer. A regra é: se daqui a 2 meses você não
consegue reconstruir o "por quê" só do código + commit msg, falta
narrativa em `progresso.md`.

## Quando NÃO seguir o protocolo

O protocolo é otimizado pro caso comum (task discreta, delegável,
em trilha mapeada). Há situações onde ele atrapalha:

- **Conversação exploratória** ("e se a gente fizesse X?") — sem
  comprometimento ainda. Não tentar formalizar prematuro.
- **Debug em produção** — bot caiu, precisa entender por quê
  agora. Pula direto pra investigação, sem brief.
- **Pergunta sobre arquitetura** — Rick quer entender, não fazer.
  Resposta + ponteiros pra código, sem doc.
- **Pivô grande de visão** — quando a estratégia muda (como o
  pivô "feature → plataforma" no `progresso.md` 2026-05-13),
  ferramentas existentes podem não caber. Aí refatora a camada
  agêntica antes de tentar enquadrar.

## Como esta camada agêntica evolui

Quando o orquestrador percebe um padrão repetitivo que não está
documentado — como esse próprio doc surgiu — é hora de codificar.
A heurística:

- Aconteceu 3 vezes seguidas do mesmo jeito? → padrão real.
- Documentar agora custa pouco e poupa muito? → vale.
- A documentação serve sessões futuras, não a atual? → essencial.

A regra de ouro: **a camada agêntica é meta-código.** É código que
faz outro código existir mais rápido. Trate com a mesma seriedade
de manter um framework: refactor regular, deletar o que não usa,
não acumular cruft.
