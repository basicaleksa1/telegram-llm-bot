"""Running the userbot, and logging in / out of Telegram."""

import logging
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import RPCError
from telethon.tl.types import User

from . import __version__
from . import handlers  # noqa: F401  (registers the commands)
from .autoreply import AutoReplier, register_auto_reply
from .commands import register_commands
from .config import Config, ConfigError
from .handoff import register_remote_control
from .llm import LLM

log = logging.getLogger("userbot")


def make_client(config: Config) -> TelegramClient:
    if not config.has_telegram_credentials:
        raise ConfigError("API_ID / API_HASH are not set. Run the setup first.")
    config.sessions_dir.mkdir(parents=True, exist_ok=True)
    # device_model / app_version are what Telegram shows under Settings -> Devices.
    return TelegramClient(
        str(config.session_path),
        config.api_id,
        config.api_hash,
        device_model="Telegram Userbot",
        app_version=__version__,
    )


def session_file(config: Config) -> Path:
    return config.session_path.with_name(config.session_path.name + ".session")


def has_saved_login(config: Config) -> bool:
    return session_file(config).exists()


async def login(config: Config, ask_phone, ask_code, ask_password) -> User:
    """Log in (interactive the first time) and return the account. The login is saved in sessions/."""
    client = make_client(config)
    try:
        await client.start(
            phone=(lambda: config.phone) if config.phone else ask_phone,
            code_callback=ask_code,
            password=ask_password,
        )
        return await client.get_me()
    finally:
        await client.disconnect()


async def current_account(config: Config) -> User | None:
    """The logged-in account, or None if the saved login is missing or no longer valid."""
    if not has_saved_login(config):
        return None
    client = make_client(config)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            return None
        return await client.get_me()
    finally:
        await client.disconnect()


async def logout(config: Config) -> bool:
    """End the session on Telegram's side and delete the local session file."""
    if not has_saved_login(config):
        return False
    client = make_client(config)
    try:
        await client.connect()
        if await client.is_user_authorized():
            await client.log_out()
    finally:
        await client.disconnect()
    session_file(config).unlink(missing_ok=True)
    return True


async def run_bot(config: Config, ask_phone, ask_code, ask_password) -> None:
    """Log in if needed, then handle messages until disconnected (or Ctrl+C)."""
    client = make_client(config)
    register_commands(client, config)
    llm = LLM(config) if config.llm_enabled else None
    replier = register_auto_reply(client, config, llm)

    try:
        await client.start(
            phone=(lambda: config.phone) if config.phone else ask_phone,
            code_callback=ask_code,
            password=ask_password,
        )
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
                log.info("LLM ready: %s via %s, prompt %s", llm.model, llm.host, config.llm_system_prompt_file.name)
        if replier is not None:
            await setup_handoff(client, config, replier, me)
        await client.run_until_disconnected()
    finally:
        await client.disconnect()


async def setup_handoff(client: TelegramClient, config: Config, replier: AutoReplier, me: User) -> None:
    """Point handoff alerts at HANDOFF_NOTIFY_CHAT and let that account resume/pause chats."""
    target = config.handoff_notify_chat
    if target:
        try:
            entity = await client.get_entity(int(target) if target.lstrip("-").isdigit() else target)
        except (ValueError, TypeError, RPCError) as e:
            log.warning(
                "HANDOFF_NOTIFY_CHAT=%r not found (%s). Use an @username; a phone or ID only works if "
                "the account is in your contacts or has messaged you. Alerts go to Saved Messages.",
                target,
                e,
            )
        else:
            if entity.id != me.id:
                replier.notify_target = entity
                replier.notify_user_id = entity.id
                register_remote_control(client, replier.paused, entity.id)
    if replier.notify_target == "me":
        log.info("Handoff alerts go to your Saved Messages (reply %sresume to one to resume)", config.command_prefix)
    else:
        log.info("Handoff alerts go to %s", target)
    paused = replier.paused.items()
    if paused:
        log.info("%d chat(s) are paused (handed over to you); send %spaused to list them", len(paused), config.command_prefix)
