# Task C1 — Retry transiente no claude_runner

## ID
C1

## Trilha
C — Robustez

## Status
🎯 pronto pra delegar

## Intenção

O CLI do Claude se auto-atualiza periodicamente, reescrevendo o
symlink do binário. Durante uma janela de poucos segundos, o
`claude` aponta pra um arquivo inexistente. Subprocess que tente
spawn nesse instante falha com `FileNotFoundError` ou sai com
`exit code 2` ("No claude executable found for nodejs X").

O bot já documenta esse race em `CLAUDE.md` e seta
`DISABLE_AUTOUPDATER=1` no env do subprocess pra impedir o spawn
de disparar update. Mas isso não cobre o caso onde OUTRO processo
do Claude (ex.: o Claude Code que o Rick usa pra desenvolver)
dispara o updater no mesmo host — o que efetivamente quebra o E2E
e qualquer execução do `/meeseeks` na janela transiente.

Esta task adiciona retry com backoff curto especificamente para
esses dois tipos de erro. Toda outra falha continua sem retry.

## Escopo

### Dentro
- `claude_runner.run_claude_p` ganha retry automático para
  `FileNotFoundError` no `create_subprocess_exec` e para exit
  code != 0 com stderr contendo "No claude executable found".
- Política: 2 retries com sleep de 1.5s e 3.0s entre tentativas.
  Total máximo de latência adicional: ~4.5s.
- Testes mockando o subprocess pra cobrir cada caminho de retry.

### Fora
- Retry de timeouts, exit codes genéricos, ou envelope JSON
  inválido. Esses sinalizam problemas reais, não races.
- Mudança em qualquer outro arquivo além de `claude_runner.py` e
  seus testes.
- Configuração via env de número de retries / delays. Hardcoded
  está bom por enquanto.

## Critério de pronto

1. `.venv/bin/pytest tests/unit/test_claude_runner.py -v` verde.
2. Pelo menos 3 testes novos:
   - Retry e sucesso quando a primeira tentativa cai em
     `FileNotFoundError` e a segunda passa.
   - Retry e sucesso quando primeira tentativa retorna exit 2 com
     stderr "No claude executable found".
   - Falha após esgotar os retries (não fica tentando pra sempre).
3. Logging útil: imprimir uma linha no stderr a cada retry
   indicando qual tentativa e por quê (não usa `logging` — segue
   o padrão do projeto que é `print`).
4. Mensagem de erro final, depois de esgotar retries, distingue
   "auto-update em curso" de outros erros.

## Contexto técnico

### Arquivos relevantes
- `claude_runner.py` — função `run_claude_p`, atual ~80 linhas.
- `tests/unit/test_claude_runner.py` — já tem mocks de subprocess
  via `_FakeProc` e `_patch_spawn`. Reuse.

### Padrões do projeto
- Async/await em todo o codepath.
- Subprocess via `asyncio.create_subprocess_exec`.
- `print(f"[warn] ...")` pra log defensivo (ver `bot.py`).

## Implementação sugerida

Coloque retry no nível de `run_claude_p`, não em `_FakeProc`. Algo
como:

```python
RETRY_DELAYS = (1.5, 3.0)  # 2 retries

async def run_claude_p(...) -> ClaudeRunResult:
    for attempt, delay in enumerate([0.0, *RETRY_DELAYS]):
        if delay:
            await asyncio.sleep(delay)
        r = await _run_claude_p_once(...)
        if not _is_transient(r):
            return r
        print(f"[warn] tentativa {attempt+1} falhou ({r.error}), retentando em {RETRY_DELAYS[attempt]}s")
    return r  # devolve o último resultado, já com mensagem clara
```

Onde `_is_transient` retorna True se:
- `r.error` contém "indisponível" (sintoma do `FileNotFoundError`)
- `r.error == "claude exit code 2"` E `r.raw` contém "No claude executable found"

Cuidado: o stub atual de `_FakeProc` não simula a sequência
"primeira chamada falha, segunda passa". Você vai precisar de um
helper que devolva uma lista de respostas em ordem.

## Testes a adicionar

Em `tests/unit/test_claude_runner.py`:

1. `TestRunClaudePRetry::test_recovers_from_filenotfound_on_retry`
2. `TestRunClaudePRetry::test_recovers_from_exit2_autoupdate_on_retry`
3. `TestRunClaudePRetry::test_gives_up_after_max_retries`
4. `TestRunClaudePRetry::test_no_retry_on_real_exit_code` — exit 1
   sem mensagem de auto-update **não** entra em retry.
5. `TestRunClaudePRetry::test_no_retry_on_timeout`.

Considere parametrizar a tabela de delays via parâmetro
keyword-only com default, pra testes não precisarem esperar 4s
reais. Algo como `run_claude_p(..., _retry_delays=(0.0, 0.0))`.

## Decisões em aberto

- Tabela de delays final (1.5/3.0 é chute). Confirme com o Rick
  se preferir outra. **Default sugerido fica.**

## Dependências
- Bloqueia: nenhuma diretamente. Mas ajuda A1 e B1 a não
  flickarem nos primeiros runs.
- Bloqueado por: nada.

## Conflito potencial com
Nada. Toca só `claude_runner.py` + seu teste. Roda em paralelo
com qualquer outra task.

## Estimativa
~1-2h. Refactor é localizado, testes são naturais sobre o
`_FakeProc` existente.
