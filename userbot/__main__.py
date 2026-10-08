"""Entry point: `python -m userbot`.

The first run is interactive: Telethon asks for your phone number, the login
code Telegram sends you, and your 2FA password (if you have one). After that
the login is stored in sessions/<SESSION_NAME>.session and reused.
"""

import asyncio
import logging
import sys

from telethon import TelegramClient

from . import handlers  # noqa: F401  (registers the commands)
from .autoreply import register_auto_reply
from .commands import register_commands
from .config import SESSIONS_DIR, ConfigError, load_config
from .llm import LLM

log = logging.getLogger("userbot")


async def main() -> None:
    try:
        config = load_config()
    except ConfigError as e:
        sys.exit(f"Configuration error: {e}")

    logging.basicConfig(
        level=config.log_level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    # The Ollama client logs every HTTP request at INFO; keep the output readable.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    SESSIONS_DIR.mkdir(exist_ok=True)
    client = TelegramClient(str(config.session_path), config.api_id, config.api_hash)
    register_commands(client, config)
    llm = LLM(config) if config.llm_enabled else None
    register_auto_reply(client, config, llm)

    start_kwargs = {"phone": config.phone} if config.phone else {}
    await client.start(**start_kwargs)

    try:
        me = await client.get_me()
        log.info(
            "Logged in as %s (@%s, id=%s). Send %shelp in Saved Messages to try it. Ctrl+C to stop.",
            me.first_name,
            me.username or "-",
            me.id,
            config.command_prefix,
        )
        if llm is not None and config.auto_reply_enabled:
            problem = await llm.check()
            if problem:
                log.warning("LLM not ready: %s. Auto-replies will use %r until it is.", problem, config.auto_reply_text)
            else:
                log.info("LLM ready: %s via %s", llm.model, llm.host)
        await client.run_until_disconnected()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
