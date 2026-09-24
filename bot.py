"""Vulpine Social entry point and cog dispatcher."""

from __future__ import annotations

import time
from typing import Any

from core import CommandContext, CommandRateLimiter, LOGGER, TOKEN, VulpineAPIError, VulpineClient, command_args, load_local_env, load_offset, save_offset
from cogs import community, fun, general, giveaways, moderation, stock, tools

load_local_env()

COGS = (general, stock, giveaways, fun, tools, moderation, community)
COMMANDS: dict[str, str] = {}
for cog in COGS:
    COMMANDS.update(cog.COMMANDS)

COMMAND_LIMITER = CommandRateLimiter()


def _context(client: VulpineClient, update: dict[str, Any], bot: dict[str, Any]) -> CommandContext:
    return CommandContext(client=client, update=update, bot=bot)


def dispatch_command(ctx: CommandContext, command: str, args: list[str]) -> None:
    if command == "clear":
        conversation = ctx.client.conversation(ctx.conversation_id)
        if conversation.get("type") != "group":
            ctx.reply("`!clear` is only available in groups.")
        elif conversation.get("creatorId") != ctx.sender_id:
            ctx.reply("Only the group creator can use `!clear`.")
        else:
            ctx.reply("The Vulpine API does not currently provide a delete-messages endpoint.")
        return
    if command in general.COMMANDS and general.handle(ctx, command, args, len(COMMANDS)):
        return
    if command == "stock" and stock.handle(ctx, args):
        return
    if command == "giveaway" and giveaways.handle(ctx, args):
        return
    if command in community.COMMANDS and community.handle(ctx, command, args):
        return
    if command in fun.COMMANDS and fun.handle(ctx, command, args):
        return
    if command in tools.COMMANDS and tools.handle(ctx, command, args):
        return
    if command in moderation.COMMANDS:
        moderation.handle(ctx, command, args)
        return
    ctx.reply("Unknown command. Use `!help` to see what I can do.")


def handle_message(ctx: CommandContext) -> None:
    text = ctx.message.get("text", "")
    if text.strip() in {"🎉", "🎁"}:
        giveaways.handle(ctx, ["join", giveaways._active(giveaways._load(), ctx.conversation_id)[-1]["id"]]) if giveaways._active(giveaways._load(), ctx.conversation_id) else ctx.reply("There is no active giveaway in this conversation.")
        return
    command, args = command_args(text)
    if command:
        if ctx.sender_id != ctx.bot.get("ownerId") and COMMAND_LIMITER.check(ctx.conversation_id, ctx.sender_id) > 0:
            return
        dispatch_command(ctx, command, args)


def handle_button(ctx: CommandContext) -> None:
    data = ctx.update.get("data")
    button = ctx.update.get("button")
    if not data and isinstance(button, dict):
        data = button.get("data") or button.get("value")
    if not isinstance(data, str):
        return
    if giveaways.handle_button(ctx, data) or moderation.handle_button(ctx, data) or community.handle_poll_button(ctx, data):
        return
    if data in {"help", "menu"}:
        general.handle(ctx, "help", [], len(COMMANDS))
    elif data == "ping":
        general.handle(ctx, "ping", [], len(COMMANDS))
    elif data == "giveaway_list":
        giveaways.handle(ctx, ["list"])
    elif data == "coin":
        fun.handle(ctx, "coin", [])
    elif data == "dice":
        fun.handle(ctx, "dice", [])
    elif data == "userinfo":
        general.handle(ctx, "userinfo", [], len(COMMANDS))
    elif data == "avatar":
        general.handle(ctx, "avatar", [], len(COMMANDS))


def handle_update(client: VulpineClient, update: dict[str, Any], bot: dict[str, Any]) -> None:
    ctx = _context(client, update, bot)
    kind = update.get("kind")
    if kind == "message":
        handle_message(ctx)
    elif kind == "button":
        handle_button(ctx)
    elif kind == "memberJoined":
        if community.welcome_enabled(ctx.conversation_id):
            moderation.handle_member_join(ctx)
    elif kind == "memberLeft":
        moderation.handle_member_leave(ctx)


def report_update_error(client: VulpineClient, update: dict[str, Any], error: Exception) -> None:
    conversation_id = update.get("conversationId")
    if not conversation_id:
        return
    if isinstance(error, VulpineAPIError) and error.status in {401, 403}:
        client.send(conversation_id, "# Permission denied\n\n> The bot does not have permission to complete that action.")
    else:
        client.send(conversation_id, "# Something went wrong\n\n> The request could not be completed. Please try again later.")


def main() -> None:
    if not TOKEN:
        raise SystemExit("VULPINE_BOT_TOKEN is missing. Set it in the environment or .env file.")
    client = VulpineClient(TOKEN)
    bot = client.me()
    offset = load_offset()
    LOGGER.info("Started as @%s with %d registered commands", bot.get("handle", "bot"), len(COMMANDS))
    while True:
        try:
            result = client.updates(offset)
            giveaways.expire(client)
            for update in result.get("updates", []):
                offset = max(offset, int(update.get("seq", 0)))
                save_offset(offset)
                try:
                    handle_update(client, update, bot)
                except (ValueError, KeyError, VulpineAPIError) as exc:
                    LOGGER.exception("Could not handle update: %s", exc)
                    try:
                        report_update_error(client, update, exc)
                    except VulpineAPIError:
                        LOGGER.exception("Could not report update failure")
                except Exception as exc:
                    LOGGER.exception("Unexpected error while handling update: %s", exc)
                    try:
                        report_update_error(client, update, exc)
                    except VulpineAPIError:
                        LOGGER.exception("Could not report unexpected update failure")
            offset = max(offset, int(result.get("maxSeq", offset)))
            save_offset(offset)
        except VulpineAPIError as exc:
            LOGGER.error("Polling failed: %s", exc)
            time.sleep(3)


if __name__ == "__main__":
    main()
