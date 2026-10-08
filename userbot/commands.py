"""A tiny command registry.

Handler modules decorate functions with @command(...). register_commands()
then wires every registered command into the Telethon client so that it fires
only on messages *you* send (outgoing=True) that start with the prefix.
"""

import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from telethon import TelegramClient, events

from .config import Config

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Context:
    """Passed to every command handler alongside the Telethon event."""

    config: Config
    commands: list["Command"] = field(default_factory=list)


Handler = Callable[[events.NewMessage.Event, Context], Awaitable[None]]


@dataclass(frozen=True)
class Command:
    name: str
    description: str
    handler: Handler


COMMANDS: list[Command] = []


def command(name: str, description: str) -> Callable[[Handler], Handler]:
    """Register `fn` as the handler for `<prefix><name> [args]`."""

    def decorator(fn: Handler) -> Handler:
        if any(c.name == name for c in COMMANDS):
            raise ValueError(f"Command {name!r} is already registered")
        COMMANDS.append(Command(name, description, fn))
        return fn

    return decorator


def build_pattern(prefix: str, name: str) -> re.Pattern[str]:
    # Matches ".name" or ".name some args"; the args land in group 1.
    return re.compile(rf"^{re.escape(prefix)}{re.escape(name)}(?:\s+(.*))?$", re.DOTALL)


def register_commands(client: TelegramClient, config: Config) -> None:
    ctx = Context(config=config, commands=COMMANDS)

    for cmd in COMMANDS:

        async def run(event: events.NewMessage.Event, _cmd: Command = cmd) -> None:
            try:
                await _cmd.handler(event, ctx)
            except Exception:
                log.exception("Command %r failed", _cmd.name)

        client.add_event_handler(
            run,
            events.NewMessage(outgoing=True, pattern=build_pattern(config.command_prefix, cmd.name)),
        )
        log.debug("Registered command %s%s", config.command_prefix, cmd.name)
