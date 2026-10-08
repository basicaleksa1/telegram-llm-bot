"""Automatically replies to messages other people send you in private chats.

Replies are written by a local LLM (see llm.py) using the recent chat history.
If the LLM is disabled, not allowed for the chat, or fails, the fixed
AUTO_REPLY_TEXT is sent instead.

Groups and channels are ignored on purpose: auto-replying there is spammy and
a quick way to get the account limited. Bots and Telegram's own service
account (the one that sends login codes) are ignored too.
"""

import asyncio
import logging
import time
from collections.abc import Callable

from telethon import TelegramClient, events
from telethon.tl.custom import Message

from .config import Config
from .llm import LLM, LLMError

log = logging.getLogger(__name__)

TELEGRAM_SERVICE_USER_ID = 777000


def to_llm_message(message: Message) -> dict[str, str] | None:
    """Convert a Telegram message to an LLM chat message (None if it has no content)."""
    text = message.raw_text or ""
    if message.media is not None:
        kind = type(message.media).__name__.removeprefix("MessageMedia").lower() or "media"
        text = f"[sent a {kind}] {text}".strip()
    if not text:
        return None
    return {"role": "assistant" if message.out else "user", "content": text}


class AutoReplier:
    def __init__(
        self,
        config: Config,
        llm: LLM | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.text = config.auto_reply_text
        self.cooldown = config.auto_reply_cooldown
        self.delay = config.auto_reply_delay
        self.quote = config.auto_reply_quote
        self.history_limit = config.llm_history_limit
        self.allowed_chats = config.llm_allowed_chats
        self.llm = llm
        self._clock = clock
        self._last_reply: dict[int, float] = {}
        self._waiting: dict[int, asyncio.Task[None]] = {}
        self._owner_name: str | None = None

    def _cooling_down(self, chat_id: int) -> bool:
        last = self._last_reply.get(chat_id)
        return last is not None and self._clock() - last < self.cooldown

    async def handle(self, event: events.NewMessage.Event) -> None:
        if event.sender_id == TELEGRAM_SERVICE_USER_ID:
            return

        sender = await event.get_sender()
        if getattr(sender, "bot", False):
            return

        if self._cooling_down(event.chat_id):
            log.debug("Skipping auto-reply to chat %s (cooldown)", event.chat_id)
            return

        if self.delay <= 0:
            await self.respond(event)
            return

        # People often send several messages in a row. Restart the timer on
        # every message and answer once, after they've been quiet for `delay`.
        previous = self._waiting.pop(event.chat_id, None)
        if previous is not None:
            previous.cancel()
        self._waiting[event.chat_id] = asyncio.create_task(self._respond_after_delay(event))

    async def _respond_after_delay(self, event: events.NewMessage.Event) -> None:
        await asyncio.sleep(self.delay)
        # From here on a newer message must not cancel the reply in progress.
        if self._waiting.get(event.chat_id) is asyncio.current_task():
            del self._waiting[event.chat_id]
        try:
            await self.respond(event)
        except Exception:
            log.exception("Auto-reply failed")

    async def respond(self, event: events.NewMessage.Event) -> None:
        text = await self.compose(event)
        if self.quote:
            await event.reply(text)  # shows their message quoted above the reply
        else:
            await event.respond(text)  # plain message, like a normal chat
        self._last_reply[event.chat_id] = self._clock()
        log.info("Auto-replied in chat %s: %r", event.chat_id, text[:80])

    def _llm_allowed(self, chat_id: int) -> bool:
        return self.llm is not None and (not self.allowed_chats or chat_id in self.allowed_chats)

    async def compose(self, event: events.NewMessage.Event) -> str:
        if not self._llm_allowed(event.chat_id):
            return self.text
        try:
            history = await self._history(event)
            owner = await self._owner(event.client)
            async with event.client.action(event.chat_id, "typing"):
                return await self.llm.reply(owner, history)
        except LLMError as e:
            log.warning("%s; sending fallback text instead", e)
        except Exception:
            log.exception("LLM reply failed; sending fallback text instead")
        return self.text

    async def _history(self, event: events.NewMessage.Event) -> list[dict[str, str]]:
        messages = [m async for m in event.client.iter_messages(event.chat_id, limit=self.history_limit)]
        messages.reverse()  # Telegram returns newest first
        if not any(m.id == event.id for m in messages):
            messages.append(event.message)
        return [converted for m in messages if (converted := to_llm_message(m)) is not None]

    async def _owner(self, client: TelegramClient) -> str:
        if self._owner_name is None:
            me = await client.get_me()
            self._owner_name = me.first_name or "the account owner"
        return self._owner_name


def register_auto_reply(client: TelegramClient, config: Config, llm: LLM | None = None) -> None:
    if not config.auto_reply_enabled:
        log.info("Auto-reply is disabled")
        return

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
