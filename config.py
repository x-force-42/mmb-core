import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID")
# Pós-B1: opcional. Se setado e a tabela `projects` estiver vazia
# no `on_ready`, o bot faz seed migracional do projeto default. O
# fluxo runtime usa registro multi-projeto, não esta variável.
_raw_target = os.getenv("TARGET_PROJECT_PATH")
TARGET_PROJECT_PATH: Path | None = (
    Path(_raw_target).expanduser() if _raw_target else None
)
CLAUDE_CLI = os.getenv("CLAUDE_CLI", "claude")
GARAGEM_TIMEOUT_S = int(os.getenv("GARAGEM_TIMEOUT_S", "300"))
MEESEEKS_TIMEOUT_S = int(os.getenv("MEESEEKS_TIMEOUT_S", "1800"))
MEESEEKS_DEV_PORT = int(os.getenv("MEESEEKS_DEV_PORT", "5173"))
MMB_DB_PATH = Path(os.getenv("MMB_DB_PATH", "mmb.db")).expanduser()

# API do cockpit (processo separado, roda independente do bot).
MMB_API_PORT = int(os.getenv("MMB_API_PORT", "8765"))
MMB_API_CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("MMB_API_CORS_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]

# ─── Aquário ─────────────────────────────────────────────────────────────
# Side-car visual: empurra eventos do ciclo de vida do Meeseeks pra um
# WebSocket externo. Desligado por default pra não exigir o servidor de
# pé em dev local nem nos E2E. Sem TLS, sem auth — loopback only.
AQUARIUM_ENABLED = os.getenv("AQUARIUM_ENABLED", "false").lower() == "true"
AQUARIUM_WS_URL = os.getenv("AQUARIUM_WS_URL", "ws://localhost:8080/ws")

if not DISCORD_BOT_TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN não setado no .env")
if TARGET_PROJECT_PATH is not None and not TARGET_PROJECT_PATH.exists():
    raise RuntimeError(f"TARGET_PROJECT_PATH não existe: {TARGET_PROJECT_PATH}")