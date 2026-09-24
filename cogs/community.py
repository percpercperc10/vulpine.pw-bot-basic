"""Community management: settings, warnings, polls, reports and backups."""

from __future__ import annotations

import os
import re
import shutil
import time
from datetime import datetime, timezone
from typing import Any

from core import CommandContext, ROOT, is_owner, load_json, save_json

SETTINGS_FILE = os.path.join(ROOT, "community_settings.json")
WARNINGS_FILE = os.path.join(ROOT, "warnings.json")
POLLS_FILE = os.path.join(ROOT, "polls.json")
BACKUP_DIR = os.path.join(ROOT, "backups")

COMMANDS = {
    "settings": "Configure this group",
    "warn": "Warn a group member",
    "warnings": "View member warnings",
    "clearwarnings": "Clear member warnings",
    "poll": "Create a button poll",
    "report": "Report a user or message",
    "backup": "Create a data backup",
}


def _group(ctx: CommandContext) -> bool:
    return ctx.client.conversation(ctx.conversation_id).get("type") == "group"


def _manager(ctx: CommandContext) -> bool:
    conversation = ctx.client.conversation(ctx.conversation_id)
    return is_owner(ctx) or conversation.get("creatorId") == ctx.sender_id


def _load_map(path: str) -> dict[str, Any]:
    data = load_json(path, {})
    return data if isinstance(data, dict) else {}


def _save_map(path: str, data: dict[str, Any]) -> None:
    save_json(path, data)


def settings_for(conversation_id: str) -> dict[str, Any]:
    settings = _load_map(SETTINGS_FILE)
    stored = settings.get(conversation_id, {})
    if not isinstance(stored, dict):
        stored = {}
    return {
        "welcome": bool(stored.get("welcome", True)),
        "verify": bool(stored.get("verify", True)),
    }


def welcome_enabled(conversation_id: str) -> bool:
    return settings_for(conversation_id)["welcome"]


def handle_settings(ctx: CommandContext, args: list[str]) -> None:
    if not _group(ctx):
        ctx.reply("# Group settings\n\n> Settings are only available in group conversations.")
        return
    settings = _load_map(SETTINGS_FILE)
    current = settings_for(ctx.conversation_id)
    if not args:
        ctx.reply(
            "# Group settings\n\n"
            "| Feature | Status |\n| --- | --- |\n"
            f"| Welcome messages | `{'ON' if current['welcome'] else 'OFF'}` |\n"
            f"| Verification button | `{'ON' if current['verify'] else 'OFF'}` |\n\n"
            "Use `!settings welcome on|off` or `!settings verify on|off`."
        )
        return
    if not _manager(ctx):
        ctx.reply("# Permission denied\n\n> Only the group creator or bot owner can change settings.")
        return
    if len(args) != 2 or args[0].lower() not in {"welcome", "verify"} or args[1].lower() not in {"on", "off"}:
        ctx.reply("Usage: `!settings welcome on|off` or `!settings verify on|off`")
        return
    current[args[0].lower()] = args[1].lower() == "on"
    settings[ctx.conversation_id] = current
    _save_map(SETTINGS_FILE, settings)
    ctx.reply(f"# Settings updated\n\n**{args[0].title()} messages:** `{args[1].upper()}`\n\n> This setting is saved for this group.")


def _target(ctx: CommandContext, value: str) -> str:
    from core import resolve_user_id
    return resolve_user_id(ctx.client, ctx.conversation_id, value)


def handle_warning(ctx: CommandContext, command: str, args: list[str]) -> None:
    if not _group(ctx):
        ctx.reply("# Warnings\n\n> Warnings are only available in groups.")
        return
    if not _manager(ctx):
        ctx.reply("# Permission denied\n\n> Only the group creator or bot owner can manage warnings.")
        return
    if not args:
        ctx.reply(f"Usage: `!{command} @handle [reason]`")
        return
    target_id = _target(ctx, args[0])
    target = ctx.client.user(target_id)
    warnings = _load_map(WARNINGS_FILE)
    key = f"{ctx.conversation_id}:{target_id}"
    entries = warnings.setdefault(key, [])
    if command == "clearwarnings":
        warnings.pop(key, None)
        _save_map(WARNINGS_FILE, warnings)
        ctx.reply(f"# Warnings cleared\n\nNo active warnings remain for **@{target.get('handle', args[0])}**.")
        return
    if command == "warnings":
        if not entries:
            ctx.reply(f"# Warning history\n\n**@{target.get('handle', args[0])}** has no warnings.")
            return
        rows = "\n".join(f"| `{index}` | {item.get('reason', 'No reason')} | `{item.get('by', '?')}` |" for index, item in enumerate(entries, 1))
        ctx.reply(f"# Warning history\n\n| # | Reason | Issued by |\n| ---: | --- | --- |\n{rows}")
        return
    reason = " ".join(args[1:]).strip() or "No reason provided"
    entries.append({"reason": reason[:500], "by": ctx.sender_id, "createdAt": int(time.time())})
    _save_map(WARNINGS_FILE, warnings)
    count = len(entries)
    auto_mute = ""
    if count >= 3:
        try:
            ctx.client.moderate("mute", ctx.conversation_id, target_id, 10)
            auto_mute = "\n\n> Automatic 10-minute mute applied after 3 warnings."
        except Exception:
            auto_mute = "\n\n> The warning was saved, but automatic mute is not available."
    ctx.reply(f"# Warning issued\n\n| Member | Total warnings | Reason |\n| --- | ---: | --- |\n| **@{target.get('handle', args[0])}** | `{count}` | {reason} |{auto_mute}")


def _polls() -> dict[str, Any]:
    return _load_map(POLLS_FILE)


def handle_poll(ctx: CommandContext, args: list[str]) -> None:
    if len(args) < 2:
        ctx.reply("Usage: `!poll Question | Option one | Option two`")
        return
    parts = [part.strip() for part in " ".join(args).split("|") if part.strip()]
    if len(parts) < 3 or len(parts) > 7:
        ctx.reply("A poll needs a question and 2-6 options separated with `|`.")
        return
    polls = _polls()
    poll_id = f"{int(time.time())}-{len(polls) + 1}"
    polls[poll_id] = {"conversationId": ctx.conversation_id, "question": parts[0], "options": parts[1:], "votes": {}, "status": "open", "creatorId": ctx.sender_id}
    _save_map(POLLS_FILE, polls)
    buttons = [{"label": option[:32], "data": f"poll:{poll_id}:{index}"} for index, option in enumerate(parts[1:])]
    ctx.reply(f"# {parts[0]}\n\n> Choose one option below. You can vote once.\n\n" + "\n".join(f"- [ ] {option}" for option in parts[1:]), buttons=buttons, buttons_layout="column")


def handle_poll_button(ctx: CommandContext, data: str) -> bool:
    if not data.startswith("poll:"):
        return False
    pieces = data.split(":")
    if len(pieces) != 3:
        return True
    _, poll_id, option_value = pieces
    polls = _polls()
    poll = polls.get(poll_id)
    if not poll or poll.get("status") != "open":
        ctx.reply("# Poll closed\n\n> This poll is no longer accepting votes.")
        return True
    votes = poll.setdefault("votes", {})
    if ctx.sender_id in votes:
        ctx.reply("# Vote already recorded\n\n> You can only vote once in this poll.")
        return True
    try:
        option_index = int(option_value)
        option = poll["options"][option_index]
    except (ValueError, IndexError, TypeError):
        ctx.reply("That poll option is no longer available.")
        return True
    votes[ctx.sender_id] = option_index
    _save_map(POLLS_FILE, polls)
    ctx.reply(f"# Vote recorded\n\n> Your vote for **{option}** has been saved.\n\nUse `!poll results {poll_id}` to see the current results.")
    return True


def poll_results(ctx: CommandContext, poll_id: str) -> None:
    poll = _polls().get(poll_id)
    if not poll:
        ctx.reply("No poll was found with that ID.")
        return
    votes = list(poll.get("votes", {}).values())
    rows = []
    for index, option in enumerate(poll.get("options", [])):
        rows.append(f"| **{option}** | `{votes.count(index)}` |")
    ctx.reply(f"# {poll.get('question', 'Poll results')}\n\n| Option | Votes |\n| --- | ---: |\n" + "\n".join(rows) + f"\n\nPoll ID: `{poll_id}`")


def handle_report(ctx: CommandContext, args: list[str]) -> None:
    if not _group(ctx):
        ctx.reply("# Reports\n\n> Reports are only available in group conversations so they can be delivered privately to the owner.")
        return
    if not args:
        ctx.reply("Usage: `!report @handle reason`")
        return
    target = args[0]
    reason = " ".join(args[1:]).strip() or "No reason provided"
    owner_id = ctx.bot.get("ownerId")
    if not owner_id:
        ctx.reply("Reports are temporarily unavailable because no bot owner is configured.")
        return
    report = f"# New report\n\n| Reporter | Target | Conversation |\n| --- | --- | --- |\n| `@{ctx.sender.get('handle', ctx.sender_id)}` | `{target}` | `{ctx.conversation_id}` |\n\n**Reason:**\n> {reason[:1000]}"
    ctx.client.send(ctx.conversation_id, report, target_user_ids=[owner_id])
    ctx.reply("# Report submitted\n\n> Thank you. The bot owner has been notified.")


def handle_backup(ctx: CommandContext) -> None:
    if not is_owner(ctx):
        ctx.reply("# Permission denied\n\n> Only the bot owner can create backups.")
        return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    copied = []
    for filename in ("giveaways.json", "stock.json", "community_settings.json", "warnings.json", "polls.json"):
        source = os.path.join(ROOT, filename)
        if os.path.exists(source):
            destination = os.path.join(BACKUP_DIR, f"{stamp}-{filename}")
            shutil.copy2(source, destination)
            copied.append(filename)
    ctx.reply("# Backup created\n\n" + "\n".join(f"- [x] `{filename}`" for filename in copied) + f"\n\nTimestamp: `{stamp} UTC`")


def handle(ctx: CommandContext, command: str, args: list[str]) -> bool:
    if command == "settings":
        handle_settings(ctx, args)
    elif command in {"warn", "warnings", "clearwarnings"}:
        handle_warning(ctx, command, args)
    elif command == "poll":
        if args and args[0].lower() == "results" and len(args) == 2:
            poll_results(ctx, args[1])
        else:
            handle_poll(ctx, args)
    elif command == "report":
        handle_report(ctx, args)
    elif command == "backup":
        handle_backup(ctx)
    else:
        return False
    return True
