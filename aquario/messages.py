"""Schema dos 3 tipos de mensagem que o aquário aceita.

Fechado com o time do aquário (ver brief A1). Sem unknown kinds, sem
campos extras — payload inválido é dropado silenciosamente do lado
deles. Aqui a gente garante o formato exato.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional

EventKind = Literal["born", "died_happy", "died_defeated", "freaking_out"]

NAME_MAX_LEN = 32  # acordo com o time do aquário — truncar antes de mandar


def _truncate_name(name: Optional[str]) -> Optional[str]:
    if name is None:
        return None
    return name[:NAME_MAX_LEN]


@dataclass
class Meeseeks:
    """Item dentro de um Snapshot — estado completo de um Meeseeks vivo."""
    id: str
    health: float = 1.0
    isFreakingOut: bool = False
    name: Optional[str] = None
    task: Optional[str] = None

    def to_dict(self) -> dict:
        out: dict = {
            "id": self.id,
            "health": self.health,
            "isFreakingOut": self.isFreakingOut,
        }
        name = _truncate_name(self.name)
        if name is not None:
            out["name"] = name
        if self.task is not None:
            out["task"] = self.task
        return out


@dataclass
class Snapshot:
    """Estado completo no connect. Tratado como reset do lado deles."""
    meeseeks: list[Meeseeks] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "type": "snapshot",
            "meeseeks": [m.to_dict() for m in self.meeseeks],
        }


@dataclass
class State:
    """Update absoluto de saúde de um Meeseeks já nascido."""
    id: str
    health: float

    def to_dict(self) -> dict:
        return {"type": "state", "id": self.id, "health": self.health}


@dataclass
class Event:
    """Transição discreta do ciclo de vida.

    `born` exige `name` e `task` — é o único kind que faz o Meeseeks
    aparecer no aquário. Os outros kinds carregam só id.
    """
    kind: EventKind
    id: str
    name: Optional[str] = None
    task: Optional[str] = None

    def to_dict(self) -> dict:
        out: dict = {"type": "event", "kind": self.kind, "id": self.id}
        name = _truncate_name(self.name)
        if name is not None:
            out["name"] = name
        if self.task is not None:
            out["task"] = self.task
        return out
