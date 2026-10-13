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

# Telegram's test servers (https://core.telegram.org/api/auth#test-accounts):
# test accounts have numbers 99966XYYYY, where X is the data center, and the
# login code is always X five times. We use data center 2. Port 80 per
# Telethon's docs (443 doesn't always work).
TEST_DC, TEST_DC_IP, TEST_DC_PORT = 2, "149.154.167.40", 80
TEST_PHONE_PREFIX = f"99966{TEST_DC}"
TEST_LOGIN_CODE = str(TEST_DC) * 5


def make_client(config: Config) -> TelegramClient:
    if not config.has_telegram_credentials:
        raise ConfigError("API_ID / API_HASH are not set. Run the setup first.")
    config.sessions_dir.mkdir(parents=True, exist_ok=True)
    new_session = not session_file(config).exists()
    # device_model / app_version are what Telegram shows under Settings -> Devices.
    client = TelegramClient(
        str(config.session_path),
        config.api_id,
        config.api_hash,
        device_model="Telegram Userbot",
        app_version=__version__,
    )
    if config.telegram_test_servers and new_session:
        # Only for a new login file: an existing one already points at the test server.
        client.session.set_dc(TEST_DC, TEST_DC_IP, TEST_DC_PORT)
    return client


def _start_kwargs(config: Config, ask_phone, ask_code, ask_password) -> dict:
    """The phone / code / password callbacks for client.start(), with hints on test servers."""
    phone = config.phone
    if config.telegram_test_servers:
        if phone and not phone.lstrip("+").startswith("99966"):
            phone = None  # PHONE is the real number; the test account has its own
        ask_real_phone, ask_real_code = ask_phone, ask_code

        def ask_test_phone() -> str:
            log.info(
                "Telegram TEST servers: use a test account's number, %sXXXX (e.g. %s1234). "
                "The account must already exist: create it once in the Telegram app's test mode.",
                TEST_PHONE_PREFIX,
                TEST_PHONE_PREFIX,
            )
            return ask_real_phone()

        def ask_test_code() -> str:
            # Telegram has changed code lengths before; Telethon's docs suggest the 6-digit form then.
            log.info(
                "Telegram TEST servers: the login code is %s (if that's rejected, %s).",
                TEST_LOGIN_CODE,
                TEST_LOGIN_CODE + TEST_LOGIN_CODE[0],
            )
            return ask_real_code()

        ask_phone, ask_code = ask_test_phone, ask_test_code
    return {
        "phone": (lambda: phone) if phone else ask_phone,
        "code_callback": ask_code,
        "password": ask_password,
    }


def session_file(config: Config) -> Path:
    return config.session_path.with_name(config.session_path.name + ".session")


def has_saved_login(config: Config) -> bool:
    return session_file(config).exists()


async def login(config: Config, ask_phone, ask_code, ask_password) -> User:
    """Log in (interactive the first time) and return the account. The login is saved in sessions/."""
    client = make_client(config)
    try:
        await client.start(**_start_kwargs(config, ask_phone, ask_code, ask_password))
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
        await client.start(**_start_kwargs(config, ask_phone, ask_code, ask_password))
        me = await client.get_me()
        if config.telegram_test_servers:
            log.warning("Connected to Telegram's TEST servers (TELEGRAM_TEST_SERVERS=true), as a test account.")
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
