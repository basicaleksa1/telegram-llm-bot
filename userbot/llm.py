"""Talks to a local LLM served by Ollama (https://ollama.com).

Everything runs on this machine; no message text is sent to any cloud service.
"""

import asyncio
import logging
import re
from collections.abc import Sequence
from pathlib import Path

from ollama import AsyncClient, ResponseError

from .config import Config

log = logging.getLogger(__name__)

# Used when the configured prompt file is missing.
FALLBACK_SYSTEM_PROMPT = (
    "You are {name}, chatting with friends on Telegram, writing in first person. "
    "Hold a real conversation: answer what they said, react, and ask things back. "
    "Reply in the same language they write in, short and casual, like a real text message. "
    "Never invent specific facts about your life, never commit to plans, money or favours, "
    "and never share personal information. "
    "If someone asks whether they are talking to a bot, answer honestly."
)

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)

Message = dict[str, str]


class LLMError(Exception):
    """The model could not produce a usable reply."""


def load_system_prompt(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        log.warning("System prompt file %s not found, using the built-in default", path)
        return FALLBACK_SYSTEM_PROMPT
    return text or FALLBACK_SYSTEM_PROMPT


class PromptFile:
    """A prompt file that is re-read whenever it changes on disk.

    Lets testers edit the prompt while the bot (or the playground) is running:
    the next reply uses the saved version, no restart needed.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._stamp: tuple[int, int] | None = None
        self._text = ""

    def _current_stamp(self) -> tuple[int, int] | None:
        try:
            stat = self.path.stat()
        except OSError:
            return None
        return stat.st_mtime_ns, stat.st_size

    @property
    def text(self) -> str:
        stamp = self._current_stamp()
        if not self._text or stamp != self._stamp:
            if self._text:
                log.info("Prompt file %s changed, using the new version", self.path.name)
            self._text = load_system_prompt(self.path)
            self._stamp = stamp
        return self._text


class LLM:
    def __init__(self, config: Config, client: AsyncClient | None = None) -> None:
        self.model = config.llm_model
        self.host = config.llm_host
        self.timeout = config.llm_timeout
        self.prompt = PromptFile(config.llm_system_prompt_file)
        self.reply_language = config.llm_reply_language
        self._client = client or AsyncClient(host=config.llm_host)
        # A 16 GB machine can only run one generation at a time sensibly.
        self._lock = asyncio.Lock()

    @property
    def system_prompt(self) -> str:
        return self.prompt.text

    def use_prompt_file(self, path: Path) -> None:
        self.prompt = PromptFile(path)

    def build_messages(self, owner_name: str, history: Sequence[Message]) -> list[Message]:
        system = self.system_prompt.replace("{name}", owner_name)
        messages = [{"role": "system", "content": system}, *history]
        if self.reply_language:
            # Small models copy the language of the chat (including their own
            # earlier replies) over an instruction at the top of the prompt.
            # A reminder right before the reply fixes that.
            messages.append(
                {
                    "role": "system",
                    "content": f"Reply in {self.reply_language} only, even if their messages "
                    "or earlier messages in this chat are in another language.",
                }
            )
        return messages

    async def reply(self, owner_name: str, history: Sequence[Message]) -> str:
        messages = self.build_messages(owner_name, history)
        async with self._lock:
            try:
                response = await asyncio.wait_for(
                    self._client.chat(
                        model=self.model,
                        messages=messages,
                        think=False,  # skip step-by-step reasoning: much faster for chat
                        options={"temperature": 0.7, "top_p": 0.8, "num_predict": 300, "num_ctx": 8192},
                    ),
                    timeout=self.timeout,
                )
            except TimeoutError:
                raise LLMError(f"No reply from {self.model} within {self.timeout:.0f}s") from None
            except (ResponseError, ConnectionError, OSError) as e:
                raise LLMError(f"Ollama request failed: {e}") from e

        text = _THINK_BLOCK.sub("", response.message.content or "").strip()
        if not text:
            raise LLMError(f"{self.model} returned an empty reply")
        return text[:4000]  # Telegram's message limit is 4096 characters

    async def check(self) -> str | None:
        """Return a problem description, or None if Ollama and the model are ready."""
        try:
            await self._client.show(self.model)
        except ResponseError as e:
            if e.status_code == 404:
                return f"model {self.model!r} is not downloaded. Download it in the menu (AI model), or run: ollama pull {self.model}"
            return f"Ollama error: {e}"
        except (ConnectionError, OSError):
            return f"cannot reach Ollama at {self.host}. Is the Ollama app running?"
        return None
