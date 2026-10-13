"""Automatically replies to messages other people send you in private chats.

Replies are written by a local LLM (see llm.py) using the recent chat history,
including the most recent photos if the model can see images. If the LLM is
disabled, not allowed for the chat, or fails, the fixed AUTO_REPLY_TEXT is sent
instead.

When the model decides you should take over (see handoff.py), the chat is
paused: the person gets HANDOFF_CLIENT_MESSAGE, you get an alert on the
HANDOFF_NOTIFY_CHAT account, and the bot stays quiet there until resumed.

Groups and channels are ignored on purpose: auto-replying there is spammy and
a quick way to get the account limited. Bots and Telegram's own service
account (the one that sends login codes) are ignored too.
"""

import asyncio
import logging
import random
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from telethon import TelegramClient, events
from telethon.tl.custom import Message

from .config import Config
from .handoff import PausedChats, format_notification, resume_hint, split_handoff
from .humanize import humanize
from .llm import LLM, LLMError

log = logging.getLogger(__name__)

TELEGRAM_SERVICE_USER_ID = 777000
MAX_IMAGE_BYTES = 10 * 1024 * 1024
IMAGE_CACHE_SIZE = 32


def to_llm_message(message: Message) -> dict[str, Any] | None:
    """Convert a Telegram message to an LLM chat message (None if it has no content)."""
    text = message.raw_text or ""
    if message.media is not None:
        kind = type(message.media).__name__.removeprefix("MessageMedia").lower() or "media"
        text = f"[sent a {kind}] {text}".strip()
    if not text:
        return None
    return {"role": "assistant" if message.out else "user", "content": text}


def is_image(message: Message) -> bool:
    """A photo, or a picture sent as a file. Stickers don't count."""
    if getattr(message, "sticker", None) is not None:
        return False
    if getattr(message, "photo", None) is not None:
        return True
    document = getattr(message, "document", None)
    return (
        document is not None
        and str(getattr(document, "mime_type", "")).startswith("image/")
        and (getattr(document, "size", 0) or 0) <= MAX_IMAGE_BYTES
    )


def random_delay(delay: float, delay_max: float, rng: random.Random) -> float:
    """`delay`, or a random time between `delay` and `delay_max` if that's larger."""
    return rng.uniform(delay, delay_max) if delay_max > delay else delay


def display_name(user: Any) -> str:
    name = " ".join(filter(None, [getattr(user, "first_name", None), getattr(user, "last_name", None)])) or "Someone"
    username = getattr(user, "username", None)
    return f"{name} (@{username})" if username else name


@dataclass
class Composed:
    """What compose() decided: a reply to send, or a handoff to you."""

    text: str = ""
    handoff: str | None = None  # the reason, when the AI hands the chat over
    history: list[dict[str, Any]] = field(default_factory=list)


class AutoReplier:
    def __init__(
        self,
        config: Config,
        llm: LLM | None = None,
        clock: Callable[[], float] = time.monotonic,
        rng: random.Random | None = None,
    ) -> None:
        self.text = config.auto_reply_text
        self.cooldown = config.auto_reply_cooldown
        self.delay = config.auto_reply_delay
        self.delay_max = config.auto_reply_delay_max
        self.quote = config.auto_reply_quote
        self.history_limit = config.llm_history_limit
        self.allowed_chats = config.llm_allowed_chats
        self.typo_rate = config.llm_typo_rate
        self.max_images = config.llm_max_images if config.llm_vision else 0
        self.handoff_message = config.handoff_client_message
        self.command_prefix = config.command_prefix
        self.paused = PausedChats(config.paused_chats_file)
        # Where handoff alerts go; run_bot sets it once the client is connected.
        self.notify_target: Any = "me"
        self.notify_user_id: int | None = None
        self.llm = llm
        self._clock = clock
        self._rng = rng or random.Random()
        self._last_reply: dict[int, float] = {}
        self._waiting: dict[int, asyncio.Task[None]] = {}
        self._owner_name: str | None = None
        self._images: OrderedDict[tuple[int, int], bytes | None] = OrderedDict()

    def _cooling_down(self, chat_id: int) -> bool:
        last = self._last_reply.get(chat_id)
        return last is not None and self._clock() - last < self.cooldown

    def pick_delay(self) -> float:
        return random_delay(self.delay, self.delay_max, self._rng)

    async def handle(self, event: events.NewMessage.Event) -> None:
        if event.sender_id == TELEGRAM_SERVICE_USER_ID:
            return
        if self.notify_user_id is not None and event.sender_id == self.notify_user_id:
            return  # the account that gets the alerts talks to you, not to the AI

        if self.paused.is_paused(event.chat_id):
            log.debug("Skipping auto-reply to chat %s (handed over to you)", event.chat_id)
            return

        sender = await event.get_sender()
        if getattr(sender, "bot", False):
            return

        if self._cooling_down(event.chat_id):
            log.debug("Skipping auto-reply to chat %s (cooldown)", event.chat_id)
            return

        delay = self.pick_delay()
        if delay <= 0:
            await self.respond(event)
            return

        # People often send several messages in a row. Restart the timer on
        # every message and answer once, after they've been quiet for `delay`.
        previous = self._waiting.pop(event.chat_id, None)
        if previous is not None:
            previous.cancel()
        self._waiting[event.chat_id] = asyncio.create_task(self._respond_after_delay(event, delay))
        if delay >= 60:
            log.info("Will reply in chat %s in %.0f s unless they write again", event.chat_id, delay)

    async def _respond_after_delay(self, event: events.NewMessage.Event, delay: float) -> None:
        await asyncio.sleep(delay)
        # From here on a newer message must not cancel the reply in progress.
        if self._waiting.get(event.chat_id) is asyncio.current_task():
            del self._waiting[event.chat_id]
        try:
            await self.respond(event)
        except Exception:
            log.exception("Auto-reply failed")

    async def respond(self, event: events.NewMessage.Event) -> None:
        if self.paused.is_paused(event.chat_id):
            return  # paused while we were waiting to answer
        composed = await self.compose(event)
        if composed.handoff is not None:
            await self.hand_off(event, composed.handoff, composed.history)
            return
        await self._send(event, composed.text)
        # Message text only at DEBUG: log files may be sent along with bug reports.
        log.info("Auto-replied in chat %s (%d characters)", event.chat_id, len(composed.text))
        log.debug("Reply text: %r", composed.text[:200])

    async def _send(self, event: events.NewMessage.Event, text: str) -> None:
        if self.quote:
            await event.reply(text)  # shows their message quoted above the reply
        else:
            await event.respond(text)  # plain message, like a normal chat
        self._last_reply[event.chat_id] = self._clock()

    def _llm_allowed(self, chat_id: int) -> bool:
        return self.llm is not None and (not self.allowed_chats or chat_id in self.allowed_chats)

    async def compose(self, event: events.NewMessage.Event) -> Composed:
        if not self._llm_allowed(event.chat_id):
            return Composed(self.text)
        try:
            history = await self._history(event)
            owner = await self._owner(event.client)
            async with event.client.action(event.chat_id, "typing"):
                raw = await self.llm.reply(owner, history)
        except LLMError as e:
            log.warning("%s; sending fallback text instead", e)
            return Composed(self.text)
        except Exception:
            log.exception("LLM reply failed; sending fallback text instead")
            return Composed(self.text)

        text, reason = split_handoff(raw)
        if reason is not None:
            return Composed(handoff=reason, history=history)
        return Composed(humanize(text, self.typo_rate, self._rng) or self.text)

    async def hand_off(self, event: events.NewMessage.Event, reason: str, history: list[dict[str, Any]]) -> None:
        """Stop answering this chat, tell the person you'll be back, and alert you."""
        name = display_name(await event.get_sender())
        self.paused.pause(event.chat_id, name=name, reason=reason)
        log.info("Handed chat %s over to you: %s", event.chat_id, reason)
        if self.handoff_message:
            await self._send(event, self.handoff_message)

        hint = resume_hint(self.command_prefix, to_saved_messages=self.notify_target == "me")
        alert = format_notification(name, event.chat_id, reason, history, resume_hint=hint)
        try:
            await event.client.send_message(self.notify_target, alert)
        except Exception:
            log.exception("Could not send the handoff alert to %s; sending it to Saved Messages", self.notify_target)
            if self.notify_target != "me":
                await event.client.send_message("me", alert)

    async def _history(self, event: events.NewMessage.Event) -> list[dict[str, Any]]:
        messages = [m async for m in event.client.iter_messages(event.chat_id, limit=self.history_limit)]
        messages.reverse()  # Telegram returns newest first
        if not any(m.id == event.id for m in messages):
            messages.append(event.message)

        # Only the newest few photos: each one costs the model time and memory.
        sees_images = self.max_images and getattr(self.llm, "vision", True)
        photos = [m for m in messages if not m.out and is_image(m)][-self.max_images :] if sees_images else []
        photo_ids = {m.id for m in photos}

        history = []
        for m in messages:
            converted = to_llm_message(m)
            if converted is None:
                continue
            if m.id in photo_ids and (image := await self._image(event.chat_id, m)):
                converted["images"] = [image]
            history.append(converted)
        return history

    async def _image(self, chat_id: int, message: Message) -> bytes | None:
        key = (chat_id, message.id)
        if key not in self._images:
            try:
                self._images[key] = await message.download_media(file=bytes)
            except Exception:
                log.exception("Could not download photo %s in chat %s", message.id, chat_id)
                self._images[key] = None
            while len(self._images) > IMAGE_CACHE_SIZE:
                self._images.popitem(last=False)
        return self._images[key]

    async def _owner(self, client: TelegramClient) -> str:
        if self._owner_name is None:
            me = await client.get_me()
            self._owner_name = me.first_name or "the account owner"
        return self._owner_name


def register_auto_reply(client: TelegramClient, config: Config, llm: LLM | None = None) -> AutoReplier | None:
    if not config.auto_reply_enabled:
        log.info("Auto-reply is disabled")
        return None

    replier = AutoReplier(config, llm)

    async def run(event: events.NewMessage.Event) -> None:
        try:
            await replier.handle(event)
        except Exception:
            log.exception("Auto-reply failed")

    client.add_event_handler(run, events.NewMessage(incoming=True, func=lambda e: e.is_private))
    if llm is not None:
        scope = f"chats {sorted(config.llm_allowed_chats)}" if config.llm_allowed_chats else "all private chats"
        log.info("Auto-reply enabled: %s writes replies for %s (fallback: %r)", llm.model, scope, config.auto_reply_text)
    else:
        log.info("Auto-reply enabled for private chats: %r", config.auto_reply_text)
    return replier
