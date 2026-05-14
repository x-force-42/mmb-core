#!/usr/bin/env bash
# Sobe a API do Cockpit de Operações em MMB_API_PORT (default 8765).
#
# Processo separado do bot — compartilha só o SQLite (MMB_DB_PATH).
# Pode rodar simultâneo com bot.py sem conflito.
#
# Override de porta: MMB_API_PORT=9000 scripts/api.sh
# CORS extra:        MMB_API_CORS_ORIGINS="http://localhost:5173,http://localhost:3000" scripts/api.sh

set -euo pipefail

cd "$(dirname "$0")/.."

PORT="${MMB_API_PORT:-8765}"
exec .venv/bin/uvicorn api.app:app --port "$PORT" --reload "$@"
