"""Small, stateless entertainment commands."""

from __future__ import annotations

import secrets

from core import CommandContext

COMMANDS = {
    "coin": "Flip a coin",
    "dice": "Roll a die",
    "roll": "Roll a die",
    "8ball": "Ask the magic 8-ball",
    "rps": "Play rock paper scissors",
}


def handle(ctx: CommandContext, command: str, args: list[str]) -> bool:
    if command == "coin":
        ctx.reply(f"# Coin flip\n\n> The coin landed on **{secrets.choice(('HEADS', 'TAILS'))}**.\n\n---\nPlay again with `!coin`.")
    elif command in {"dice", "roll"}:
        sides = int(args[0]) if args and args[0].isdigit() else 6
        sides = max(2, min(sides, 1000))
        ctx.reply(f"# Dice roll\n\n| Die | Result |\n| --- | ---: |\n| `d{sides}` | **{secrets.randbelow(sides) + 1}** |")
    elif command == "8ball":
        if not args:
            ctx.reply("# Magic 8-ball\n\n> Ask a question first.\n\nExample: `!8ball will I win?`")
            return True
        answers = ("Absolutely.", "The signs point to yes.", "Ask again later.", "The outlook is unclear.", "I would not count on it.", "Definitely not.")
        ctx.reply(f"# Magic 8-ball\n\n> _{' '.join(args)}_\n\n**Answer:** {secrets.choice(answers)}")
    elif command == "rps":
        choices = {"rock", "paper", "scissors"}
        player = args[0].lower() if args else ""
        if player not in choices:
            ctx.reply("# Rock, paper, scissors\n\nChoose one:\n- `rock`\n- `paper`\n- `scissors`\n\nExample: `!rps rock`")
            return True
        computer = secrets.choice(tuple(choices))
        result = "DRAW" if player == computer else "YOU WIN" if (player, computer) in {("rock", "scissors"), ("paper", "rock"), ("scissors", "paper")} else "I WIN"
        ctx.reply(f"# Rock, paper, scissors\n\n| Player | Bot |\n| --- | --- |\n| **{player}** | **{computer}** |\n\n## {result}")
    else:
        return False
    return True
