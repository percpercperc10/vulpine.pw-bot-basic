"""Shared configuration, API client, context and persistence helpers."""

from __future__ import annotations

import json
import logging
import mimetypes
import os
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
from urllib import error, parse, request


ROOT = os.path.dirname(__file__)
POLL_TIMEOUT = 25
COMMAND_PREFIX = "!"
OFFSET_FILE = os.path.join(ROOT, "polling_offset.json")
MESSAGE_INTERVAL = 0.5
COMMAND_COOLDOWN = max(0.0, float(os.getenv("COMMAND_COOLDOWN", "1.0")))

def load_local_env() -> None:
    env_path = os.path.join(ROOT, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            os.environ.setdefault(name.strip(), value.strip().strip('"\''))


load_local_env()
API_BASE = os.getenv("VULPINE_API", "https://vulpine.pw/api").rstrip("/")
TOKEN = os.getenv("VULPINE_BOT_TOKEN")
BOT_DISPLAY_NAME = os.getenv("BOT_DISPLAY_NAME", "Vulpine Social")
BOT_USERNAME = os.getenv("BOT_USERNAME", "social_bot")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(message)s",
)
LOGGER = logging.getLogger("vulpine-bot")


@dataclass
class VulpineAPIError(Exception):
    status: int
    message: str

    def __str__(self) -> str:
        return f"Vulpine API error {self.status}: {self.message}"


class CommandRateLimiter:
    """Small in-memory per-user limiter for incoming command messages."""

    def __init__(self, cooldown: float = COMMAND_COOLDOWN) -> None:
        self.cooldown = max(0.0, cooldown)
        self._last_used: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()

    def check(self, conversation_id: str, user_id: str) -> float:
        if self.cooldown <= 0 or not user_id:
            return 0.0
        now = time.monotonic()
        key = (conversation_id, user_id)
        with self._lock:
            last_used = self._last_used.get(key, 0.0)
            remaining = self.cooldown - (now - last_used)
            if remaining > 0:
                return remaining
            self._last_used[key] = now
            if len(self._last_used) > 10000:
                cutoff = now - self.cooldown * 10
                self._last_used = {item: timestamp for item, timestamp in self._last_used.items() if timestamp >= cutoff}
        return 0.0


class VulpineClient:
    def __init__(self, token: str, base_url: str = API_BASE) -> None:
        self.base_url = base_url
        self._send_lock = threading.Lock()
        self._last_send_at = 0.0
        self._upload_times: deque[float] = deque()
        self._upload_lock = threading.Lock()
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "vulpine-social-bot/2.0",
        }

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, str | int] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{parse.urlencode(query)}"
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        headers = dict(self.headers)
        if body is not None:
            headers["Content-Type"] = "application/json"
        for attempt in range(4):
            req = request.Request(url, data=payload, headers=headers, method=method)
            try:
                with request.urlopen(req, timeout=POLL_TIMEOUT + 10) as response:
                    raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
            except error.HTTPError as exc:
                details = exc.read().decode("utf-8", errors="replace")
                if exc.code != 429 or attempt == 3:
                    raise VulpineAPIError(exc.code, details or exc.reason) from exc
                try:
                    retry_ms = int(json.loads(details).get("retryAfterMs", 1000))
                except (ValueError, TypeError, json.JSONDecodeError):
                    retry_ms = 1000
                time.sleep(max(0.25, min(retry_ms / 1000, 5)))
            except error.URLError as exc:
                raise VulpineAPIError(0, str(exc.reason)) from exc
        return {}

    def me(self) -> dict[str, Any]:
        return self.request("GET", "/bot/me")

    def conversations(self) -> list[dict[str, Any]]:
        return self.request("GET", "/bot/conversations").get("conversations", [])

    def conversation(self, conversation_id: str) -> dict[str, Any]:
        return self.request("GET", f"/bot/conversations/{parse.quote(conversation_id, safe='')}")

    def user(self, user_id: str) -> dict[str, Any]:
        return self.request("GET", f"/bot/user/{parse.quote(user_id, safe='')}")

    def messages(
        self,
        conversation_id: str,
        after: int | None = None,
        before: int | None = None,
    ) -> list[dict[str, Any]]:
        query: dict[str, str | int] = {"conversationId": conversation_id}
        if after is not None:
            query["after"] = after
        if before is not None:
            query["before"] = before
        return self.request("GET", "/bot/messages", query=query).get("messages", [])

    def updates(self, offset: int) -> dict[str, Any]:
        return self.request("GET", "/bot/updates", query={"offset": offset, "timeout": POLL_TIMEOUT})

    def send(
        self,
        conversation_id: str,
        text: str,
        buttons: list[dict[str, str]] | None = None,
        image_url: str | None = None,
        buttons_layout: str | None = None,
        target_user_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        with self._send_lock:
            wait = MESSAGE_INTERVAL - (time.monotonic() - self._last_send_at)
            if wait > 0:
                time.sleep(wait)
            result = self.request("POST", "/bot/send", body=self._send_payload(
                conversation_id,
                text,
                buttons,
                image_url,
                buttons_layout,
                target_user_ids,
            ))
            self._last_send_at = time.monotonic()
            return result

    @staticmethod
    def _send_payload(
        conversation_id: str,
        text: str,
        buttons: list[dict[str, str]] | None,
        image_url: str | None,
        buttons_layout: str | None,
        target_user_ids: list[str] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"conversationId": conversation_id, "text": text[:4000]}
        if buttons:
            payload["buttons"] = buttons[:6]
        if image_url:
            payload["imageUrl"] = image_url
        if buttons_layout:
            payload["buttonsLayout"] = buttons_layout
        if target_user_ids:
            payload["targetUserIds"] = target_user_ids[:20]
        return payload

    def upload(self, file_path: str) -> str:
        with self._upload_lock:
            now = time.monotonic()
            while self._upload_times and now - self._upload_times[0] >= 60:
                self._upload_times.popleft()
            if len(self._upload_times) >= 10:
                wait = 60 - (now - self._upload_times[0])
                time.sleep(max(0.0, wait))
                now = time.monotonic()
                while self._upload_times and now - self._upload_times[0] >= 60:
                    self._upload_times.popleft()
            self._upload_times.append(now)
        content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        boundary = uuid.uuid4().hex
        with open(file_path, "rb") as image_file:
            content = image_file.read()
        if len(content) > 10 * 1024 * 1024:
            raise ValueError("The image exceeds the 10 MB limit.")
        filename = os.path.basename(file_path)
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
        headers = dict(self.headers)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        req = request.Request(f"{self.base_url}/bot/upload", data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=POLL_TIMEOUT + 10) as response:
                return json.loads(response.read().decode("utf-8"))["url"]
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise VulpineAPIError(exc.code, details or exc.reason) from exc

    def moderate(self, action: str, conversation_id: str, user_id: str, minutes: int | None = None) -> None:
        body: dict[str, Any] = {"conversationId": conversation_id, "userId": user_id}
        if minutes is not None:
            body["minutes"] = minutes
        self.request("POST", f"/bot/{action}", body=body)

    def create_bot(self, handle: str, display_name: str) -> dict[str, Any]:
        return self.request("POST", "/bots", body={"handle": handle, "displayName": display_name})

    def set_commands(self, bot_id: str, commands: list[dict[str, str]]) -> dict[str, Any]:
        return self.request("PUT", f"/bots/{parse.quote(bot_id, safe='')}/commands", body={"commands": commands[:20]})

    def reset_token(self, bot_id: str) -> dict[str, Any]:
        return self.request("POST", f"/bots/{parse.quote(bot_id, safe='')}/token")

    def delete_bot(self, bot_id: str) -> dict[str, Any]:
        return self.request("DELETE", f"/bots/{parse.quote(bot_id, safe='')}")


def command_args(text: str) -> tuple[str, list[str]]:
    parts = text.strip().split()
    if not parts or not parts[0].startswith(COMMAND_PREFIX):
        return "", []
    return parts[0][len(COMMAND_PREFIX):].split("@", 1)[0].lower(), parts[1:]


def load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as data_file:
            return json.load(data_file)
    except (OSError, json.JSONDecodeError):
        LOGGER.exception("Could not read %s", path)
        return default


def save_json(path: str, data: Any) -> None:
    temporary_path = f"{path}.{os.getpid()}.tmp"
    try:
        with open(temporary_path, "w", encoding="utf-8") as data_file:
            json.dump(data, data_file, ensure_ascii=False, indent=2)
        try:
            os.replace(temporary_path, path)
        except PermissionError:
            try:
                with open(path, "w", encoding="utf-8") as data_file:
                    json.dump(data, data_file, ensure_ascii=False, indent=2)
                LOGGER.warning("Atomic replace was unavailable for %s; used direct write.", path)
            except OSError as exc:
                LOGGER.error("Could not persist %s; continuing without saving: %s", path, exc)
    finally:
        try:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)
        except OSError:
            LOGGER.debug("Could not remove temporary file %s", temporary_path)


def load_offset() -> int:
    value = load_json(OFFSET_FILE, 0)
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        LOGGER.warning("Invalid polling offset; starting from zero.")
        return 0


def save_offset(offset: int) -> None:
    save_json(OFFSET_FILE, max(0, int(offset)))


@dataclass
class CommandContext:
    client: VulpineClient
    update: dict[str, Any]
    bot: dict[str, Any]

    @property
    def conversation_id(self) -> str:
        return self.update["conversationId"]

    @property
    def message(self) -> dict[str, Any]:
        return self.update.get("message", {})

    @property
    def sender(self) -> dict[str, Any]:
        return self.message.get("sender", {}) or self.update.get("from", {})

    @property
    def sender_id(self) -> str:
        return self.sender.get("id", "")

    def reply(self, text: str, **kwargs: Any) -> None:
        self.client.send(self.conversation_id, text, **kwargs)


def resolve_user_id(client: VulpineClient, conversation_id: str, value: str) -> str:
    if not value.startswith("@"):
        return value
    handle = value[1:].lower()
    conversation = client.conversation(conversation_id)
    for member in conversation.get("members", []):
        if member.get("handle", "").lower() == handle:
            return member["id"]
    raise ValueError(f"User @{handle} was not found in this conversation.")


def lookup_user(client: VulpineClient, conversation_id: str, user_id: str, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        return client.user(user_id)
    except VulpineAPIError:
        conversation = client.conversation(conversation_id)
        for member in conversation.get("members", []):
            if member.get("id") == user_id:
                return member
        if fallback and fallback.get("id") == user_id:
            return fallback
        raise


def user_card(user: dict[str, Any]) -> str:
    account_type = "Bot" if user.get("isBot") else "Member"
    avatar_url = user.get("avatarUrl")
    avatar_value = f"[Open avatar]({avatar_url})" if avatar_url else "`Not set`"
    return (
        "# Member profile\n"
        f"> **{user.get('displayName', '?')}**  `@{user.get('handle', '?')}`\n\n"
        f"**Account**  `{account_type}`\n"
        f"**User ID**  `{user.get('id', '?')}`\n"
        f"**Avatar**  {avatar_value}\n\n"
        f":::drop About this member\n{user.get('bio') or 'No bio provided.'}\n:::"
    )


def avatar_card(user: dict[str, Any]) -> str:
    avatar_url = user.get("avatarUrl")
    if not avatar_url:
        avatar_line = "> This user has not set an avatar."
    else:
        avatar_line = f"[Open {user.get('displayName', 'user')}'s avatar]({avatar_url})"
    return (
        "# Avatar\n\n"
        f"**{user.get('displayName', '?')}** `@{user.get('handle', '?')}`\n\n"
        f"{avatar_line}\n\n"
        "> The Vulpine API exposes the original avatar URL; remote images cannot be re-uploaded by a bot."
    )


def bot_card(bot: dict[str, Any], command_count: int, group_count: int = 0, conversation_count: int = 0) -> str:
    created_at = bot.get("createdAt")
    created = "Unknown"
    if isinstance(created_at, (int, float)):
        created = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    return (
        f"# {BOT_DISPLAY_NAME}\n"
        f"> `@{BOT_USERNAME}`  /  your Vulpine community desk\n\n"
        ":::center\n**ONLINE**\n:::\n\n"
        f"`{command_count}` commands  /  `{group_count}` groups  /  `{conversation_count}` conversations\n\n"
        "## Ready for\n"
        "Rich messages  /  interactive events  /  moderation\n\n"
        f":::drop Bot details\nCreated: `{created}`\nOwner ID: `{bot.get('ownerId', '?')}`\nBot ID: `{bot.get('id', '?')}`\n:::"
    )


def is_owner(ctx: CommandContext) -> bool:
    return ctx.sender_id == ctx.bot.get("ownerId")


Handler = Callable[[CommandContext, list[str]], bool]
