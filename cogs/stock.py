"""Persistent stock inventory commands."""

from __future__ import annotations

from core import CommandContext, ROOT, is_owner, load_json, save_json

STOCK_FILE = f"{ROOT}/stock.json"
COMMANDS = {"stock": "Show and manage inventory"}


def _load() -> dict[str, int]:
    data = load_json(STOCK_FILE, {})
    if not isinstance(data, dict):
        return {}
    stock: dict[str, int] = {}
    for name, quantity in data.items():
        try:
            stock[str(name)] = max(0, int(quantity))
        except (TypeError, ValueError):
            continue
    return stock


def _message(stock: dict[str, int]) -> str:
    available = [(name, quantity) for name, quantity in stock.items() if quantity > 0]
    if not available:
        return "# Community stock\n\n> Nothing is available right now.\n\n:::drop Owner controls\nUse `!stock add name amount` to publish new inventory.\n:::"
    rows = "\n".join(f"| **{name}** | `{quantity}` |" for name, quantity in sorted(available))
    return "# Community stock\n\n> Available items, updated by the bot owner.\n\n| Item | Available |\n| --- | ---: |\n" + rows + "\n\n---\n`!stock add name amount`  Update inventory."


def handle(ctx: CommandContext, args: list[str]) -> bool:
    stock = _load()
    if not args:
        ctx.reply(_message(stock))
        return True
    action = args[0].lower()
    if action not in {"add", "set", "remove", "delete"}:
        ctx.reply("Usage: `!stock`, `!stock add|set|remove name amount`, `!stock delete name`")
        return True
    if not is_owner(ctx):
        ctx.reply("Only the bot owner can change stock.")
        return True
    if action == "delete":
        name = " ".join(args[1:]).strip()
        if name not in stock:
            ctx.reply("Provide an existing item: `!stock delete name`.")
            return True
        del stock[name]
        save_json(STOCK_FILE, stock)
        ctx.reply(f"Removed **{name}** from stock.")
        return True
    if len(args) < 3 or not args[-1].isdigit():
        ctx.reply(f"Usage: `!stock {action} name amount`")
        return True
    name = " ".join(args[1:-1]).strip()
    quantity = int(args[-1])
    current = stock.get(name, 0)
    stock[name] = quantity if action == "set" else max(0, current + quantity if action == "add" else current - quantity)
    save_json(STOCK_FILE, stock)
    ctx.reply(f"# Stock updated\n\n| Item | New quantity |\n| --- | ---: |\n| **{name}** | `{stock[name]}` |\n\n> Inventory changes are saved automatically.")
    return True
