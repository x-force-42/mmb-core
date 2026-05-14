"""API REST do Cockpit de Operações do MMB.

Camada thin sobre o RunLogger SDK. Read-only na maior parte;
só PATCH /api/runs/{id} escreve (nos 3 campos de review manual).

Roda em processo separado do bot — compartilha só o arquivo SQLite.
Suba via scripts/api.sh.
"""

from api.app import app

__all__ = ["app"]
