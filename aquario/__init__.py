"""Aquário — side-car observável que empurra eventos do ciclo de vida
do Meeseeks pra um WebSocket externo.

Espelha o padrão do `logger/`: completamente desacoplado do core. Zero
`import discord` aqui dentro. O bot puxa o cliente como adapter externo
e chama `emit(...)` nos pontos canônicos. Falha do aquário nunca
derruba o bot.
"""

from aquario.client import AquarioClient
from aquario.lifecycle import (
    FREAKING_OUT_S,
    event_for_phase,
    health_from_elapsed,
)
from aquario.messages import Event, Meeseeks, Snapshot, State

__all__ = [
    "AquarioClient",
    "Event",
    "FREAKING_OUT_S",
    "Meeseeks",
    "Snapshot",
    "State",
    "event_for_phase",
    "health_from_elapsed",
]
