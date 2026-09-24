"""Register the bot commands shown in Vulpine.pw chat autocomplete."""

from __future__ import annotations

import json
import os
from urllib import error, request

from bot import COMMANDS, VulpineClient, load_local_env


load_local_env()
API_BASE = os.getenv("VULPINE_API", "https://vulpine.pw/api").rstrip("/")
ACCOUNT_TOKEN = os.getenv("VULPINE_ACCOUNT_TOKEN")
BOT_ID = os.getenv("VULPINE_BOT_ID")
BOT_TOKEN = os.getenv("VULPINE_BOT_TOKEN")

REGISTERED_COMMAND_NAMES = tuple(COMMANDS)[:20]
COMMAND_LIST = [
    {"command": command, "description": COMMANDS[command]}
    for command in REGISTERED_COMMAND_NAMES
]


def main() -> None:
    if not ACCOUNT_TOKEN:
        print("Skipping command registration: VULPINE_ACCOUNT_TOKEN is missing.")
        return
    bot_id = BOT_ID
    if not bot_id and BOT_TOKEN:
        bot_id = VulpineClient(BOT_TOKEN).me().get("id")
    if not bot_id:
        raise SystemExit("Could not find the bot ID. Set VULPINE_BOT_ID in .env.")

    payload = json.dumps({"commands": COMMAND_LIST}).encode("utf-8")
    req = request.Request(
        f"{API_BASE}/bots/{bot_id}/commands",
        data=payload,
        headers={
            "Authorization": f"Bearer {ACCOUNT_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="PUT",
    )
    try:
        with request.urlopen(req, timeout=15) as response:
            response.read()
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Vulpine API error {exc.code}: {details or exc.reason}") from exc
    print(f"Registered {len(COMMAND_LIST)} commands for bot {bot_id}.")


if __name__ == "__main__":
    main()
