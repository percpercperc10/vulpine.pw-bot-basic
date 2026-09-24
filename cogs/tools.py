"""Content tools backed by the Vulpine upload and send endpoints."""

from __future__ import annotations

from core import CommandContext

COMMANDS = {
    "say": "Send rich text",
    "image": "Upload and send an image",
}


def handle(ctx: CommandContext, command: str, args: list[str]) -> bool:
    if command == "say":
        text = " ".join(args).strip()
        ctx.reply(text or "Usage: `!say text`")
    elif command == "image":
        if not args:
            ctx.reply("# Image upload\n\n> Provide a local image path.\n\nSupported: `PNG`, `JPEG`, `GIF`, `WebP`\n\nExample: `!image banner.png`")
            return True
        image_url = ctx.client.upload(" ".join(args))
        ctx.reply("# Image uploaded\n\nYour image is ready to share.", image_url=image_url)
    else:
        return False
    return True
