"""Giveaway system. Existing JSON fields and join behavior stay compatible."""

from __future__ import annotations

import re
import secrets
import time
from typing import Any

from core import CommandContext, ROOT, is_owner, load_json, save_json

GIVEAWAY_FILE = f"{ROOT}/giveaways.json"
COMMANDS = {"giveaway": "Create, join and manage giveaways"}


def _load() -> list[dict[str, Any]]:
    data = load_json(GIVEAWAY_FILE, [])
    return data if isinstance(data, list) else []


def _save(data: list[dict[str, Any]]) -> None:
    save_json(GIVEAWAY_FILE, data)


def parse_duration(value: str) -> int | None:
    match = re.fullmatch(r"([1-9][0-9]*)([smhd])", value.lower())
    if not match:
        return None
    seconds = int(match.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[match.group(2)]
    return seconds if seconds <= 30 * 86400 else None


def _active(data: list[dict[str, Any]], conversation_id: str | None = None) -> list[dict[str, Any]]:
    return [item for item in data if item.get("status") == "active" and (conversation_id is None or item.get("conversationId") == conversation_id)]


def _summary(giveaway: dict[str, Any]) -> str:
    remaining = max(0, int(float(giveaway.get("endsAt", 0)) - time.time()))
    hours, remainder = divmod(remaining, 3600)
    minutes, seconds = divmod(remainder, 60)
    duration = f"{hours}h {minutes}m" if hours else f"{minutes}m {seconds}s"
    return f"| `{giveaway['id']}` | **{giveaway['prize']}** | `{len(giveaway.get('participants', []))}` | `{duration}` |"


def finish(ctx: CommandContext, giveaway: dict[str, Any], status: str = "ended") -> None:
    giveaway["status"] = status
    if status == "cancelled":
        ctx.client.send(giveaway["conversationId"], f"# Giveaway cancelled\n\n> Giveaway `{giveaway['id']}` has been cancelled.\n\n---\nThe event is no longer accepting entries.")
        return
    participants = giveaway.get("participants", [])
    count = min(int(giveaway.get("winners", 1)), len(participants))
    winners = secrets.SystemRandom().sample(participants, count) if count else []
    giveaway["winnersSelected"] = winners
    if winners:
        names = ", ".join(f"@{winner.get('handle', winner.get('id', '?'))}" for winner in winners)
        result = f"**Winner{'s' if len(winners) != 1 else ''}:** {names}\n\nCongratulations!"
    else:
        result = "No one joined this giveaway."
    ctx.client.send(giveaway["conversationId"], f"# Giveaway complete\n\n> The draw is closed. Thanks to everyone who joined.\n\n| Prize | Entries |\n| --- | ---: |\n| **{giveaway['prize']}** | `{len(participants)}` |\n\n{result}\n\n---\nThe next event is only one tap away.", buttons=[{"label": "View active giveaways", "data": "giveaway_list", "color": "#d97706"}])


def reroll(ctx: CommandContext, giveaway: dict[str, Any], data: list[dict[str, Any]]) -> None:
    participants = giveaway.get("participants", [])
    previous = {item.get("id") for item in giveaway.get("winnersSelected", [])}
    candidates = [item for item in participants if item.get("id") not in previous] or participants
    if not candidates:
        ctx.reply("# Giveaway reroll\n\n> There are no participants available for a reroll.")
        return
    winner = secrets.choice(candidates)
    giveaway["winnersSelected"] = [winner]
    _save(data)
    ctx.reply(f"# Giveaway reroll\n\n**Prize:** {giveaway['prize']}\n**New winner:** @{winner.get('handle', winner.get('id', '?'))}\n\n> The reroll has been saved.")


def expire(client: Any) -> None:
    data = _load()
    changed = False
    for giveaway in data:
        if giveaway.get("status") == "active" and float(giveaway.get("endsAt", 0)) <= time.time():
            finish(CommandContext(client, {"conversationId": giveaway["conversationId"]}, {}), giveaway)
            changed = True
    if changed:
        _save(data)


def join(ctx: CommandContext, giveaway: dict[str, Any], data: list[dict[str, Any]]) -> None:
    participant_id = ctx.sender_id
    if not participant_id:
        ctx.reply("I could not identify the participant.")
        return
    if any(item.get("id") == participant_id for item in giveaway.get("participants", [])):
        ctx.reply("You are already participating in this giveaway.")
        return
    giveaway.setdefault("participants", []).append({"id": participant_id, "handle": ctx.sender.get("handle", "user")})
    _save(data)
    ctx.reply(f"You joined giveaway `{giveaway['id']}`. Good luck!")


def handle(ctx: CommandContext, args: list[str]) -> bool:
    data = _load()
    action = args[0].lower() if args else "list"
    active = _active(data, ctx.conversation_id)
    if action == "list":
        rows = "\n".join(_summary(item) for item in active)
        ctx.reply("# Giveaways\n\n> Active events, one tap away.\n\n| ID | Prize | Entries | Time left |\n| --- | --- | ---: | --- |\n" + (rows or "| - | No active giveaways. | - | - |"), buttons=[{"label": "Open help", "data": "help", "color": "#2563eb"}, {"label": "Refresh list", "data": "giveaway_list", "color": "#d97706"}])
    elif action == "join":
        if len(args) != 2:
            ctx.reply("Usage: `!giveaway join ID`")
            return True
        giveaway = next((item for item in active if item.get("id") == args[1]), None)
        if not giveaway:
            ctx.reply("No active giveaway was found with that ID.")
        else:
            join(ctx, giveaway, data)
    elif action == "stats":
        total = sum(len(item.get("participants", [])) for item in active)
        ctx.reply(f"# Giveaway overview\n\n| Active events | Total entries |\n| ---: | ---: |\n| `{len(active)}` | `{total}` |\n\n> Every participant gets one entry per giveaway.")
    elif action == "info":
        if len(args) != 2:
            ctx.reply("Usage: `!giveaway info ID`")
            return True
        giveaway = next((item for item in data if item.get("id") == args[1]), None)
        if not giveaway:
            ctx.reply("No giveaway was found with that ID.")
        else:
            winners = giveaway.get("winnersSelected", [])
            winner_text = ", ".join(f"@{item.get('handle', item.get('id', '?'))}" for item in winners) or "Pending"
            ctx.reply(f"# Giveaway details\n\n| Prize | Status | Entries |\n| --- | --- | ---: |\n| **{giveaway['prize']}** | `{giveaway.get('status', '?')}` | `{len(giveaway.get('participants', []))}` |\n\nWinners: **{winner_text}**\nID: `{giveaway['id']}`")
    elif action == "reroll":
        if len(args) != 2:
            ctx.reply("Usage: `!giveaway reroll ID`")
            return True
        if not is_owner(ctx):
            ctx.reply("Only the bot owner can reroll giveaways.")
            return True
        giveaway = next((item for item in data if item.get("id") == args[1]), None)
        if not giveaway:
            ctx.reply("No giveaway was found with that ID.")
        elif giveaway.get("status") != "ended":
            ctx.reply("Only an ended giveaway can be rerolled.")
        else:
            reroll(ctx, giveaway, data)
    elif not is_owner(ctx):
        ctx.reply("Only the bot owner can manage giveaways.")
    elif action == "start":
        if len(args) < 4:
            ctx.reply("Usage: `!giveaway start 1h 1 prize name`")
            return True
        duration = parse_duration(args[1])
        if duration is None or not args[2].isdigit() or not 1 <= int(args[2]) <= 20:
            ctx.reply("Use a duration up to 30 days, such as `30m`, `2h`, or `1d`; winners must be 1-20.")
            return True
        giveaway = {"id": secrets.token_hex(3), "prize": " ".join(args[3:]).strip(), "winners": int(args[2]), "endsAt": time.time() + duration, "conversationId": ctx.conversation_id, "creatorId": ctx.sender_id, "participants": [], "status": "active"}
        data.append(giveaway)
        _save(data)
        ctx.reply(f"# Giveaway is live\n\n> A new event has opened. Entries are limited to one per person.\n\n| Prize | Winners | Duration |\n| --- | ---: | --- |\n| **{giveaway['prize']}** | `{giveaway['winners']}` | `{args[1]}` |\n\n**Giveaway ID:** `{giveaway['id']}`\n\n- [ ] Enter before the timer ends\n- [ ] Winners are selected automatically\n- [ ] Check stats whenever you like\n\n> Good luck!", buttons=[{"label": "Join giveaway", "data": f"giveaway_join:{giveaway['id']}", "color": "#d97706"}, {"label": "View stats", "data": f"giveaway_stats:{giveaway['id']}", "color": "#2563eb"}], buttons_layout="row")
    elif action in {"end", "cancel"} and len(args) == 2:
        giveaway = next((item for item in active if item.get("id") == args[1]), None)
        if not giveaway:
            ctx.reply("No active giveaway was found with that ID.")
        else:
            finish(ctx, giveaway, "cancelled" if action == "cancel" else "ended")
            _save(data)
    else:
        ctx.reply("Usage: `!giveaway list|start|join|end|cancel|stats|info|reroll ...`")
    return True


def handle_button(ctx: CommandContext, data: str) -> bool:
    if data == "giveaway":
        active = _active(_load(), ctx.conversation_id)
        if active:
            join(ctx, active[-1], _load())
        else:
            ctx.reply("There is no active giveaway in this conversation.")
        return True
    if data.startswith("giveaway_join:") or data.startswith("giveaway_join_"):
        giveaway_id = data.split(":", 1)[1] if ":" in data else data.split("_", 2)[2]
        items = _load()
        giveaway = next((item for item in _active(items, ctx.conversation_id) if item.get("id") == giveaway_id), None)
        if giveaway:
            join(ctx, giveaway, items)
        else:
            ctx.reply("That giveaway is no longer active.")
        return True
    if data.startswith("giveaway_stats:"):
        giveaway_id = data.split(":", 1)[1]
        giveaway = next((item for item in _load() if item.get("id") == giveaway_id), None)
        if giveaway:
            ctx.reply(f"# Giveaway details\n\n| Prize | Entries | Status |\n| --- | ---: | --- |\n| **{giveaway['prize']}** | `{len(giveaway.get('participants', []))}` | `{giveaway.get('status', '?')}` |\n\nID: `{giveaway_id}`")
        return True
    if data == "giveaway_list":
        handle(ctx, ["list"])
        return True
    return False
