"""Handing a chat over from the AI to you.

The prompt tells the model to answer with HANDOFF_MARKER (plus a one-line
summary) when it reaches a point where you should take over. The auto-replier
then stops answering in that chat ("pauses" it), and you get an alert on a
Telegram account of your choice.

Paused chats are kept in a small JSON file in the data folder, so they stay
paused after a restart. You resume a chat with:
- the account that gets the alerts: reply "resume" to the alert, or send "resume <chat id>";
- your own account: .resume in that chat, or .resume <chat id> anywhere.
"""

import json
import logging
import re
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from telethon import TelegramClient, events

log = logging.getLogger(__name__)

HANDOFF_MARKER = "[[HANDOFF]]"
_MARKER = re.compile(r"\[\[\s*hand\s*-?\s*off\s*\]\]", re.IGNORECASE)
_CHAT_LINE = re.compile(r"^chat (-?\d+)$", re.MULTILINE)
NOTIFICATION_HISTORY = 8


def split_handoff(text: str) -> tuple[str, str | None]:
    """Split a model reply into (text for the person, handoff reason or None).

    Everything after the marker is the model's summary for you. Text before it
    is returned too, but the auto-replier doesn't send it: at a handoff the
    person gets HANDOFF_CLIENT_MESSAGE instead.
    """
    match = _MARKER.search(text)
    if match is None:
        return text, None
    reason = " ".join(text[match.end() :].split()) or "the AI handed this chat over to you"
    return text[: match.start()].strip(), reason


class PausedChats:
    """Chats the auto-replier stays out of, stored in a JSON file.

    The file is read on every call, so the bot, the commands and the remote
    control always agree (and you can edit or delete it by hand).
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            log.exception("Could not read %s; treating no chats as paused", self.path)
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self, data: dict[str, dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def is_paused(self, chat_id: int) -> bool:
        return str(chat_id) in self._load()

    def pause(self, chat_id: int, name: str = "", reason: str = "") -> None:
        data = self._load()
        data[str(chat_id)] = {"name": name, "reason": reason, "since": datetime.now().isoformat(timespec="seconds")}
        self._save(data)

    def resume(self, chat_id: int) -> bool:
        """Un-pause a chat. Returns False if it wasn't paused."""
        data = self._load()
        if data.pop(str(chat_id), None) is None:
            return False
        self._save(data)
        return True

    def items(self) -> list[tuple[int, dict[str, Any]]]:
        return [(int(chat_id), info) for chat_id, info in self._load().items()]

    def describe(self) -> str:
        items = self.items()
        if not items:
            return "No paused chats: the bot is answering everyone."
        lines = ["Paused chats (the bot doesn't answer these):"]
        for chat_id, info in items:
            name = info.get("name") or "?"
            lines.append(f"- {name}, chat {chat_id}, since {info.get('since', '?')}: {info.get('reason') or '-'}")
        return "\n".join(lines)


def resume_hint(command_prefix: str, to_saved_messages: bool) -> str:
    """How to resume, as shown in the alert: alerts in Saved Messages need your own .resume command."""
    word = f"{command_prefix}resume" if to_saved_messages else "resume"
    return f'Reply "{word}" to this message to let the bot answer them again.'


def format_notification(
    name: str,
    chat_id: int,
    reason: str,
    history: Sequence[dict[str, Any]],
    resume_hint: str = 'Reply "resume" to this message to let the bot answer them again.',
) -> str:
    lines = [f"🔔 Your turn: {name} needs you", f"Why: {reason}", ""]
    recent = [m for m in history if m.get("content")][-NOTIFICATION_HISTORY:]
    if recent:
        lines.append("Last messages:")
        for m in recent:
            who = "them" if m["role"] == "user" else "bot"
            content = " ".join(str(m["content"]).split())
            lines.append(f"{who}: {content[:200]}")
        lines.append("")
    lines += [f"chat {chat_id}", resume_hint]
    return "\n".join(lines)


def parse_chat_id(text: str | None) -> int | None:
    """The chat ID from a handoff alert (its "chat <id>" line), or None."""
    match = _CHAT_LINE.search(text or "")
    return int(match.group(1)) if match else None


def _chat_id_arg(arg: str) -> int | None:
    try:
        return int(arg)
    except ValueError:
        return None


REMOTE_HELP = (
    "Commands from this account:\n"
    'resume - as a reply to an alert: the bot answers that chat again\n'
    "resume <chat id> - same, by chat ID\n"
    "pause <chat id> - the bot stops answering that chat\n"
    "paused - list the paused chats"
)


def run_remote_command(text: str, paused: PausedChats, replied_text: str | None) -> str | None:
    """Handle a control message from the alert account. Returns the answer, or None if it isn't a command."""
    word, _, arg = text.strip().partition(" ")
    word, arg = word.lower(), arg.strip()

    if word in ("resume", "pause") and arg and _chat_id_arg(arg) is None:
        return None  # "resume the meeting tomorrow?" is just a message
    if word == "paused" and not arg:
        return paused.describe()
    if word == "help" and not arg:
        return REMOTE_HELP
    if word == "resume":
        chat_id = _chat_id_arg(arg) if arg else parse_chat_id(replied_text)
        if chat_id is None:
            return 'Reply "resume" to an alert, or send "resume <chat id>".'
        if paused.resume(chat_id):
            return f"Resumed: the bot answers chat {chat_id} again."
        return f"Chat {chat_id} wasn't paused."
    if word == "pause":
        chat_id = _chat_id_arg(arg) if arg else parse_chat_id(replied_text)
        if chat_id is None:
            return 'Send "pause <chat id>", or reply "pause" to an alert.'
        paused.pause(chat_id, reason="paused remotely")
        return f"Paused: the bot no longer answers chat {chat_id}."
    return None


def register_remote_control(client: TelegramClient, paused: PausedChats, controller_id: int) -> None:
    """Let the account that gets the alerts resume/pause chats by messaging you."""

    async def run(event: events.NewMessage.Event) -> None:
        try:
            replied = await event.get_reply_message() if event.is_reply else None
            answer = run_remote_command(event.raw_text or "", paused, replied.raw_text if replied else None)
            if answer is not None:
                log.info("Remote control: %r", (event.raw_text or "").strip()[:40])
                await event.reply(answer)
        except Exception:
            log.exception("Remote control command failed")

    client.add_event_handler(
        run, events.NewMessage(incoming=True, from_users=controller_id, func=lambda e: e.is_private)
    )
    log.info("Remote control enabled: user %s can send resume/pause/paused", controller_id)
