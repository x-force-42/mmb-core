import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID")
TARGET_PROJECT_PATH = Path(
    os.getenv("TARGET_PROJECT_PATH", "~/vnt/ASUS/jogo")
).expanduser()
CLAUDE_CLI = os.getenv("CLAUDE_CLI", "claude")
GARAGEM_TIMEOUT_S = int(os.getenv("GARAGEM_TIMEOUT_S", "300"))
MEESEEKS_TIMEOUT_S = int(os.getenv("MEESEEKS_TIMEOUT_S", "1800"))
MEESEEKS_DEV_PORT = int(os.getenv("MEESEEKS_DEV_PORT", "5173"))

if not DISCORD_BOT_TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN não setado no .env")
if not TARGET_PROJECT_PATH.exists():
    raise RuntimeError(f"TARGET_PROJECT_PATH não existe: {TARGET_PROJECT_PATH}")