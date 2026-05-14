"""Funções puras de mapeamento ciclo-de-vida → aquário.

Sem IO, sem asyncio, sem dependências externas. Testáveis passando
entradas e comparando saídas. Casadas com a curva de
`embeds.meeseeks_decay` / `formatters.meeseeks_decay`: cada faixa de
tempo do show ("Working on it!" → "Pleeease let me finish") tem uma
janela de health correspondente.
"""

from typing import Optional


FREAKING_OUT_S = 900  # 15min — quando o Meeseeks entra em pânico


# Pontos da curva piecewise-linear (segundos, health).
# Casa com a tabela do brief A1:
#   0-3min   "Working on it!"          1.00 → 0.85
#   3-8min   "Caaaaan do!"             0.85 → 0.65
#   8-15min  "Oh boy, this is tricky"  0.65 → 0.40
#   15-25min "Existing is pain"        0.40 → 0.15  ← FREAKING_OUT_S
#   25-30min "Pleeease let me finish"  0.15 → 0.05
#   30min+   (mantém 0.05 até morrer)
_HEALTH_CURVE: tuple[tuple[float, float], ...] = (
    (0,    1.00),
    (180,  0.85),
    (480,  0.65),
    (900,  0.40),
    (1500, 0.15),
    (1800, 0.05),
)


def health_from_elapsed(seconds: float) -> float:
    """Health 0..1 derivada do tempo decorrido desde o spawn.

    Interpolação linear entre os pontos da curva. Antes de 0 = 1.0;
    depois de 30min = 0.05 (Meeseeks vivo mas em pain — só morre na
    transição terminal explícita, não por decay sozinho)."""
    if seconds <= 0:
        return _HEALTH_CURVE[0][1]
    for (t0, h0), (t1, h1) in zip(_HEALTH_CURVE, _HEALTH_CURVE[1:]):
        if seconds <= t1:
            ratio = (seconds - t0) / (t1 - t0)
            return h0 + ratio * (h1 - h0)
    return _HEALTH_CURVE[-1][1]


# Mapeamento phase terminal do pipeline → kind de evento do aquário.
# `None` = Meeseeks nem nasceu, não emite nada.
_PHASE_TO_KIND: dict[str, Optional[str]] = {
    "success":            "died_happy",
    "meeseeks_failure":   "died_defeated",
    "dev_server_failure": "died_defeated",
    "garagem_error":      None,
    "garagem_pushback":   None,
    "garagem_no_slug":    None,
}


def event_for_phase(phase: str) -> Optional[str]:
    """Devolve o kind de evento aquário pra uma phase terminal do
    pipeline, ou None se Meeseeks nunca chegou a existir."""
    return _PHASE_TO_KIND.get(phase)
