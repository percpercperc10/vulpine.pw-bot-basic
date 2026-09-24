"""Verification, welcome messages and group moderation."""

from __future__ import annotations

from core import CommandContext, resolve_user_id

COMMANDS = {
    "verify": "Send a verification button",
    "kick": "Kick a group member",
    "ban": "Ban a group member",
    "unban": "Unban a group member",
    "mute": "Mute a group member",
    "unmute": "Remove a member mute",
}


def handle(ctx: CommandContext, command: str, args: list[str]) -> bool:
    if command == "verify":
        ctx.reply("# Verification\n\n> Press the button below to verify your account.\n\n- [ ] Confirm that you are a real member\n- [ ] Follow the group rules\n\n---\nYour verification is recorded by the bot.", buttons=[{"label": "Verify", "data": "verify", "color": "#22c55e"}], buttons_layout="column")
        return True
    if command not in {"kick", "ban", "unban", "mute", "unmute"}:
        return False
    if not args:
        ctx.reply(f"Usage: `!{command} @handle`")
        return True
    target_id = resolve_user_id(ctx.client, ctx.conversation_id, args[0])
    minutes = None
    if command == "mute":
        minutes = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10
        minutes = max(1, min(minutes, 1440))
    ctx.client.moderate(command, ctx.conversation_id, target_id, minutes)
    suffix = f" for {minutes} minutes" if minutes else ""
    ctx.reply(f"# Moderation action complete\n\n| Action | Target | Duration |\n| --- | --- | --- |\n| `{command}` | `{args[0]}` | `{minutes or '-'}`{(' minutes' if minutes else '')} |\n\n> The Vulpine API accepted this action.")
    return True


def handle_button(ctx: CommandContext, data: str) -> bool:
    if data == "verify":
        ctx.reply(f"# Verified\n\n> Welcome, `@{ctx.update.get('from', {}).get('handle', '?')}`.\n\n- [x] Verification complete\n- [ ] Read the group rules\n- [ ] Enjoy the community")
        return True
    return False


def handle_member_join(ctx: CommandContext) -> None:
    user = ctx.update.get("user", {})
    name = user.get("displayName", "new member")
    ctx.reply(f"# Welcome, {name}!\n\n> We are glad to have you here.\n\n- [ ] Read the group rules\n- [ ] Introduce yourself\n- [ ] Have fun\n\nUse `!help` to see what I can do.", buttons=[{"label": "Open Help", "data": "help"}, {"label": "Verify", "data": "verify", "color": "#22c55e"}])


def handle_member_leave(ctx: CommandContext) -> None:
    user = ctx.update.get("user", {})
    name = user.get("displayName") or user.get("handle") or "A member"
    ctx.reply(f"# Member update\n\n> **{name}** has left the conversation.\n\nThe group roster is now up to date.")
