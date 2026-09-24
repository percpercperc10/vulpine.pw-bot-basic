# made by @swag on vulpine

# Vulpine Social Bot

A Python bot for Vulpine.pw groups. It handles community utilities, giveaways, polls, moderation, rich messages and image uploads through the Vulpine bot API.

## Setup

1. Install Python 3.10 or newer.
2. Copy `.env.example` to `.env`.
3. Add the bot token from the Vulpine portal.
4. Add the account token if you want autocomplete command registration.
5. Run `start.bat` on Windows or run `python register_commands.py` followed by `python bot.py`.

The bot token is separate from the account token and must never be committed or shared.

## Included

- Rich Vulpine markup: headings, tables, checklists, quotes, dividers and collapsible sections.
- Interactive menus, verification, giveaway entry and giveaway statistics.
- Persistent giveaway and inventory data in `giveaways.json` and `stock.json`.
- Identity cards, user lookup, group member lists, conversation lists and message history.
- Coin, dice, 8-ball and rock-paper-scissors commands.
- Image upload through `/bot/upload` and rich text sending through `/bot/send`.
- Kick, ban, unban, mute and unmute actions through the Vulpine moderation API.
- Automatic welcome messages and giveaway expiration during the polling loop.
- Durable polling offsets so restarts do not replay already acknowledged events.
- Central message throttling for the Vulpine 1-message-per-0.5-second limit.
- Per-user command throttling to prevent command spam; configure it with `COMMAND_COOLDOWN`.
- Giveaway `info` and owner-only `reroll` commands with persisted winner records.
- Clear permission and API failure messages for users.
- Per-group welcome and verification settings, warnings with automatic mute after three warnings, button polls, private owner reports and data backups.
- Full documented bot API client: identity, conversations, user lookup, message history with `after`/`before`, long polling, rich sends, uploads, moderation and account-level bot management helpers.
- Live `memberJoined` and `memberLeft` reactions, URL-safe resource IDs and upload throttling aligned with Vulpine limits.

## Project layout

- `core.py` contains the API client, context, configuration and persistence helpers.
- `cogs/general.py` contains help, identity and conversation commands.
- `cogs/giveaways.py` contains the compatible giveaway system and its buttons.
- `cogs/stock.py` contains inventory management.
- `cogs/fun.py` contains games and random utilities.
- `cogs/tools.py` contains rich text and image tools.
- `cogs/moderation.py` contains verification, welcome and moderation actions.
- `cogs/community.py` contains settings, warnings, polls, reports and backups.
- `bot.py` contains the event loop and command dispatcher.

## Main commands

| Area | Commands |
| --- | --- |
| General | `!help`, `!ping`, `!status`, `!me`, `!userinfo`, `!avatar`, `!bio`, `!members` |
| Community | `!giveaway list`, `!giveaway start 1h 1 Prize`, `!giveaway info ID`, `!giveaway reroll ID`, `!stock`, `!verify` |
| Management | `!settings`, `!warn @user reason`, `!warnings @user`, `!poll Question \| Option A \| Option B`, `!report @user reason`, `!backup` |
| Fun | `!coin`, `!dice 20`, `!8ball question`, `!rps rock` |
| Tools | `!say text`, `!image path_to_file` |
| Moderation | `!kick @user`, `!ban @user`, `!mute @user 10` |

Giveaway and stock mutation commands are owner-only. Moderation also depends on the permissions assigned to the bot role in the group.

## Data files

Local JSON files contain live conversation IDs, user IDs, votes and inventory. They are ignored by Git on purpose. The bot creates missing files automatically when a command needs them. Do not publish `.env`, backups or live JSON data.

## API limits handled

The client respects the 25-second long-poll window, retries rate-limit responses, limits messages to 4000 characters, caps buttons at six, caps private targets at 20, enforces the 1-message-per-0.5-second limit and throttles uploads to 10 per minute. Uploads are limited to 10 MB. Command registration sends at most 20 commands because that is the Vulpine API limit; other commands still work when typed manually.

## Vulpine API configuration

`VULPINE_API` defaults to `https://vulpine.pw/api`. The bot uses `VULPINE_BOT_TOKEN` for runtime calls. `VULPINE_ACCOUNT_TOKEN` and `VULPINE_BOT_ID` are only needed by `register_commands.py`, which updates the autocomplete list through `PUT /bots/:id/commands`.

## Publishing to GitHub

Commit the Python source, `cogs/`, `tests/`, `README.md`, `.env.example`, `.gitignore`, `start.bat`, and `start.ps1`.

Do not commit `.env`, live JSON data, `backups/`, `polling_offset.json`, `__pycache__/`, or any token. The existing `.gitignore` excludes these files. Before the first push, check the staged file list and search it for secrets:

```powershell
git add .
git status --short
git grep -n -I -e "vb" -e "VULPINE_ACCOUNT_TOKEN=" -- ':!README.md' ':!.env.example'
```

If a real token was ever committed, reset it in the Vulpine portal before making the repository public.
