"""Funções puras de parsing. Sem dependências externas além de stdlib."""

import json
import re


def extrair_json(texto: str) -> dict:
    """Tolera preâmbulo, sufixo e fences. Acha o primeiro objeto JSON
    balanceado e parseia.

    Estratégia:
    1. Tira fences ``` ou ```json se cercarem o texto inteiro.
    2. Tenta json.loads direto (caminho feliz).
    3. Fallback: varre do primeiro `{` até `}` balanceado, respeitando
       strings e escapes, e tenta parsear esse trecho.

    Levanta json.JSONDecodeError se nada funcionar.
    """
    t = texto.strip()

    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", t, re.DOTALL)
    if m:
        t = m.group(1).strip()

    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass

    start = t.find("{")
    if start == -1:
        raise json.JSONDecodeError("nenhum objeto JSON encontrado", t, 0)

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(t)):
        c = t[i]
        if escape:
            escape = False
            continue
        if c == "\\" and in_string:
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return json.loads(t[start:i + 1])

    raise json.JSONDecodeError("JSON desbalanceado", t, start)
