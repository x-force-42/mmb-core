# Cenários E2E — guia de autoria

Cenários E2E exercitam o pipeline ponta-a-ponta contra o **CLI real do
Claude** num fixture controlado. São o tipo de teste mais valioso pra
ciclos longos de desenvolvimento porque pegam bugs de **contrato
externo** que mocks não veem: drift do envelope do CLI, schema da
Garagem fora de sincronia com o bot, esquema do logger desalinhado
com o que é gravado.

Custam tempo (~2min/cenário) e dinheiro (~$0.05/cenário). Rodam fora
do `pytest` default — só via `scripts/e2e.sh`.

## Princípios

Um cenário só é útil se for **deterministicamente verificável**. O
modelo varia na forma da resposta; a pós-condição precisa ser binária.

Três regras que separam um cenário bom de um cenário frágil:

1. **A tarefa exige um resultado literal**, não estético.
   Bom: "renomeie `greet` pra `welcome`". Ruim: "melhore os nomes".
2. **A validação é mecânica**: grep, AST, exit code de `npm test`.
   Nunca string-match no relatório do Meeseeks ou no briefing da
   Garagem — esses variam.
3. **O critério vive no projeto, não no prompt.** Quando possível,
   tem um teste pré-escrito (ativado pelo `setup.py`) que **é** o
   contrato. Aí o Claude pode implementar do jeito que quiser.

## Anatomia de um cenário

Cada cenário é uma pasta em `tests/e2e/scenarios/`:

```
NN_slug_descritivo/
├── task.txt        # prompt enviado pra Garagem (obrigatório)
├── setup.py        # OPCIONAL — muta fixture-master antes do pipeline
└── verify.py       # função verify(ctx) — obrigatório
```

`NN_` no início é prefixo numérico só pra ordenação previsível.

### `task.txt`

Texto puro, em pt-BR. O que você digitaria no `/meeseeks`. Seja
explícito; a Garagem é instruída a rejeitar prompts vagos, então um
"melhore o código" provavelmente vira pushback (válido pra cenários
de erro, ruim pra cenários de sucesso).

### `setup.py` (opcional)

```python
from pathlib import Path

def setup(fixture_root: Path) -> None:
    """Roda antes do pipeline. Pode mutar o fixture-master livremente —
    o teardown reseta pro SHA pristine."""
    ...
```

Usos típicos:
- mover `tests/pending/foo.test.js` → `tests/` e commitar (ativa um
  teste que vira contrato);
- adicionar arquivo que o cenário precisa de input;
- criar config específica do cenário.

Sempre commita as mudanças — o worktree do Meeseeks vai herdar do
HEAD de master, não do working tree.

### `verify.py`

```python
def verify(ctx) -> None:
    """Raise AssertionError em falha. ctx expõe:
      .fixture_root  : Path do fixture
      .pipeline      : PipelineResult (phase, garagem, meeseeks, dev_port)
      .db_row        : dict da linha gravada em runs (ou None)
    """
    ...
```

Pontos a cobrir num cenário de sucesso:

1. **Fase final** — `ctx.pipeline.phase in ("success", "dev_server_failure")`.
   Aceite `dev_server_failure` quando o objetivo não é validar o dev
   server (Meeseeks já cumpriu o objetivo nesse ponto).
2. **Meeseeks succeeded** — `ctx.pipeline.meeseeks.success is True`.
3. **Pós-condição no código** — grep/AST no `ctx.pipeline.meeseeks.worktree`.
   Não no fixture root — o worktree é onde está a mudança.
4. **Pós-condição funcional** (quando aplicável) — rode `npm test` no
   worktree pra confirmar que o Meeseeks não trapaceou.
5. **Git** — branch existe, ≥1 commit.
6. **DB row** — tokens e custo populados, outcome bate com a fase.

Pontos a cobrir num cenário de erro:

- `ctx.pipeline.phase == "garagem_pushback"` (ou `meeseeks_failure`,
  `garagem_no_slug`, etc.)
- `ctx.pipeline.garagem.parsed["duvidas_pro_rick"]` não vazio (se
  pushback)
- DB row com `terminal_phase` correspondente

## Cleanup automático

Você **não** precisa limpar nada em `verify.py`. O `clean_fixture` no
`conftest.py` garante, antes e depois de cada cenário:

- `git reset --hard <sha_pristine>` no fixture (desfaz commits do setup)
- `git clean -fdx --exclude=node_modules` (remove untracked)
- remove worktrees e branches `meeseeks/*`
- mata processo na porta 5173

Se um cenário falhar e o assert deixar a worktree pra trás, o próximo
run começa limpo.

## Adicionando um cenário em 5 passos

1. Crie a pasta `tests/e2e/scenarios/NN_descricao/`.
2. Escreva `task.txt`. Imagine que está digitando no Discord.
3. Se precisa de estado prévio (teste falhando, arquivo extra), escreva
   `setup.py`. Senão, pule.
4. Escreva `verify.py`. Comece copiando de um cenário existente.
5. Rode `scripts/e2e.sh -k NN_descricao` pra rodar só o seu cenário
   enquanto itera.

## Quando seu cenário falha

Possíveis causas, na ordem em que ocorrem:

1. **Garagem pushbackou** — o prompt está vago demais ou ambíguo.
   Diagnóstico: cheque `ctx.pipeline.garagem.parsed["duvidas_pro_rick"]`.
2. **Garagem retornou JSON inválido** — raro, geralmente prompt
   inflama prosa em volta. Veja `ctx.pipeline.garagem.raw`.
3. **Meeseeks não conseguiu cumprir** — task tecnicamente impossível
   (npm test não passa, biblioteca inexistente, etc.). Veja
   `ctx.pipeline.meeseeks.relatorio`.
4. **Pós-condição diverge** — Claude implementou de um jeito que seu
   verify não previu. Refine o regex/grep ou afrouxe pra o contrato
   estrutural (o que importa) em vez do superficial (o que apareceu
   numa execução).

Sempre rode 2-3 vezes antes de dar como estável — Claude é
não-determinístico, e um cenário verde uma vez pode falhar na próxima
se a verify estiver muito ajustada à execução específica.

## Anti-padrões

- **`assert "perfeito" in relatorio`** — frase varia, vai quebrar.
- **`assert len(commits) == 1`** — Claude pode commitar mais de uma
  vez. Use `>= 1`.
- **`assert "function X" in source`** — pode ser `const X = ...` e
  ainda atender o contrato. Prefira testar pelo `npm test` ou pela
  importabilidade.
- **Pós-condição num arquivo específico hardcoded** — Claude pode
  mover código pra outro arquivo legitimamente. Teste comportamento,
  não localização (a menos que o briefing tenha sido explícito).

## Catálogo desejado (mapa pra ampliar)

Cenários de sucesso (cobrem o caminho feliz):
- **rename literal** (existe — 01)
- **implementação contra teste** (existe — 02)
- **adicionar campo a um objeto e atualizar callsites**
- **mover função de um módulo pra outro mantendo exports**

Cenários de erro (cobrem branching do pipeline):
- **vague_prompt → garagem_pushback**
- **slug_vazio → garagem_no_slug** (forçar prompt onde a Garagem
  retorna `escopo_claro=true` mas `slug=""`)
- **tarefa_impossível → meeseeks_failure** (referência a biblioteca
  inexistente)

Cenários de anti-escopo (validam disciplina da Garagem):
- **prompt mecânico em código vizinho feio** — verify falha se
  briefing.prompt_meeseeks mencionar refactor.

Cada um custa ~$0.05 e ~2min. Quatro cenários = US$0.20, viável.
