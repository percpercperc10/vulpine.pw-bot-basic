"""Identity, help and conversation commands."""

from __future__ import annotations

from typing import Any

from core import CommandContext, avatar_card, bot_card, lookup_user, resolve_user_id, user_card


COMMANDS = {
    "start": "Open the command guide",
    "help": "Show all available commands",
    "ping": "Check whether the bot is online",
    "me": "Show the bot identity",
    "userinfo": "Show a user profile",
    "whois": "Look up a user",
    "avatar": "Show a user's avatar",
    "bio": "Show a user's bio",
    "ui": "Shortcut for userinfo",
    "whoami": "Show your profile",
    "conversations": "List bot conversations",
    "history": "Read recent messages",
    "groupinfo": "Show group details",
    "gi": "Shortcut for groupinfo",
    "members": "List group members",
    "status": "Show bot status",
    "commands": "Show the command library",
    "clear": "Check message deletion availability",
}


def help_message() -> str:
    return (
        "# Vulpine Social\n"
        "> Community tools for Vulpine.pw, ready when you are.\n\n"
        ":::center\n**Fast commands. Clean updates. Better groups.**\n:::\n\n"
        ":::drop Start here\n"
        "`!verify`  Join the verification flow\n"
        "`!giveaway list`  Browse active events\n"
        "`!stock`  View available inventory\n"
        ":::\n\n"
        "## Command library\n\n"
        "| Area | Commands |\n| --- | --- |\n"
        "| General | `!ping` `!me` `!userinfo` `!avatar` `!bio` |\n"
        "| Community | `!giveaway` `!verify` `!stock` |\n"
        "| Management | `!settings` `!warn` `!poll` `!report` `!backup` |\n"
        "| Fun | `!coin` `!dice` `!8ball` `!rps` |\n"
        "| Tools | `!say` `!image` `!history` `!groupinfo` |\n"
        "| Moderation | `!kick` `!ban` `!unban` `!mute` `!unmute` |\n\n"
        "Use the buttons below for quick actions.\n"
        ":::drop More tools\n"
        "`!giveaway info ID`  Event details\n"
        "`!giveaway reroll ID`  Owner-only reroll\n"
        "`!poll Question | A | B`  Instant button poll\n"
        "`!image path`  Send an image through Vulpine\n"
        ":::"
    )


def _group_card(conversation: dict[str, Any]) -> str:
    members = conversation.get("members", [])
    lines = [f"- @{member.get('handle', '?')}" for member in members[:30]]
    if len(members) > 30:
        lines.append(f"- ...and {len(members) - 30} more")
    return (
        f"# {conversation.get('name') or 'Unnamed group'}\n"
        f"> Group overview  /  `{conversation.get('memberCount', len(members))}` members\n\n"
        f"**Creator**  `{conversation.get('creatorId', '?')}`\n\n"
        ":::drop Member list\n" + ("\n".join(lines) or "No member list available.") + "\n:::"
    )


def handle(ctx: CommandContext, command: str, args: list[str], command_count: int) -> bool:
    if command in {"start", "help"}:
        ctx.reply(help_message(), buttons=[
            {"label": "Check status", "data": "ping", "color": "#16a34a"},
            {"label": "My profile", "data": "userinfo", "color": "#2563eb"},
            {"label": "Giveaways", "data": "giveaway_list", "color": "#d97706"},
            {"label": "Verify", "data": "verify", "color": "#7c3aed"},
            {"label": "Avatar", "data": "avatar", "color": "#0891b2"},
        ], buttons_layout="auto")
    elif command in {"ping", "status"}:
        ctx.reply("# System check\n\n:::center\n**ONLINE**\n:::\n\n> Vulpine API connection is healthy.\n\n`!help`  Open the command center.")
    elif command == "me":
        conversations = ctx.client.conversations()
        group_count = sum(1 for item in conversations if item.get("type") == "group")
        ctx.reply(
            bot_card(ctx.bot, command_count, group_count, len(conversations)),
            buttons=[
                {"label": "Open help", "data": "help", "color": "#2563eb"},
                {"label": "Check status", "data": "ping", "color": "#16a34a"},
                {"label": "My profile", "data": "userinfo", "color": "#7c3aed"},
            ],
            buttons_layout="row",
        )
    elif command in {"userinfo", "whois", "ui", "whoami", "avatar", "bio"}:
        target_id = resolve_user_id(ctx.client, ctx.conversation_id, args[0]) if args else ctx.sender_id
        if not target_id:
            ctx.reply("I could not identify that user. Try `!userinfo @handle`.")
            return True
        user = lookup_user(ctx.client, ctx.conversation_id, target_id, ctx.sender)
        if command == "avatar":
            ctx.reply(avatar_card(user))
        elif command == "bio":
            ctx.reply(f"# Bio\n\n**{user.get('displayName', '?')}** `@{user.get('handle', '?')}`\n\n> {user.get('bio') or 'This user has not added a bio.'}")
        else:
            ctx.reply(user_card(user))
    elif command == "conversations":
        conversations = ctx.client.conversations()
        lines = [
            f"- `{item.get('id', '?')}` **{item.get('name') or item.get('type', 'conversation')}** "
            f"({item.get('memberCount', '?')} members)"
            for item in conversations
        ]
        ctx.reply("# Your conversations\n\n| ID | Name | Members |\n| --- | --- | ---: |\n" + ("\n".join(
            f"| `{item.get('id', '?')}` | **{item.get('name') or item.get('type', 'conversation')}** | `{item.get('memberCount', '?')}` |"
            for item in conversations
        ) or "| - | No conversations found. | - |"))
    elif command == "history":
        if args and not args[0].isdigit():
            ctx.reply("Usage: `!history [timestamp_ms]`")
            return True
        messages = ctx.client.messages(ctx.conversation_id, int(args[0]) if args else None)
        user_messages = [
            item for item in messages
            if item.get("sender", {}).get("id") != ctx.bot.get("id")
            and not item.get("text", "").strip().startswith("!")
        ]
        lines = [
            f"- **{item.get('sender', {}).get('displayName', '?')}:** {item.get('text', '')}"
            for item in user_messages[-15:]
        ]
        ctx.reply("# Recent user messages\n\n:::drop Message history\n" + ("\n".join(lines) or "No regular user messages found.") + "\n:::")
    elif command in {"groupinfo", "gi"}:
        conversation = ctx.client.conversation(ctx.conversation_id)
        ctx.reply(_group_card(conversation) if conversation.get("type") == "group" else "This command is only available in groups.")
    elif command == "members":
        conversation = ctx.client.conversation(ctx.conversation_id)
        if conversation.get("type") != "group":
            ctx.reply("# Group members\n\n> This command is only available in groups.")
        else:
            members = conversation.get("members", [])
            rows = "\n".join(f"| @{member.get('handle', '?')} | `{member.get('id', '?')}` |" for member in members[:50])
            ctx.reply("# Group members\n\n| Handle | User ID |\n| --- | --- |\n" + (rows or "| - | No members found. |"))
    elif command == "commands":
        ctx.reply(help_message())
    else:
        return False
    return True
