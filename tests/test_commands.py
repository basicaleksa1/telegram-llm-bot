import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from userbot import handlers  # noqa: F401  (registers the commands)
from userbot.commands import COMMANDS, Context, build_pattern, register_commands
from userbot.config import Config
from userbot.handlers.basic import chat_id, format_help, ping

CONFIG = Config(api_id=1, api_hash="x", command_prefix=".")
CTX = Context(config=CONFIG, commands=COMMANDS)


def fake_event(chat=42, reply=None):
    return SimpleNamespace(
        chat_id=chat,
        edit=AsyncMock(),
        get_reply_message=AsyncMock(return_value=reply),
    )


def test_expected_commands_are_registered():
    assert {c.name for c in COMMANDS} >= {"ping", "id", "help"}


def test_pattern_matches_command_with_and_without_args():
    pattern = build_pattern(".", "ping")

    assert pattern.match(".ping")
    assert pattern.match(".ping hello there").group(1) == "hello there"
    assert not pattern.match(".pingpong")
    assert not pattern.match("ping")
    assert not pattern.match("say .ping")


def test_pattern_escapes_regex_characters_in_prefix():
    pattern = build_pattern("$", "id")

    assert pattern.match("$id")
    assert not pattern.match("id")


def test_register_commands_only_listens_to_outgoing_messages():
    client = MagicMock()
    register_commands(client, CONFIG)

    assert client.add_event_handler.call_count == len(COMMANDS)
    for call in client.add_event_handler.call_args_list:
        event_builder = call.args[1]
        assert event_builder.outgoing is True


def test_ping_edits_message_with_latency():
    event = fake_event()
    asyncio.run(ping(event, CTX))

    assert event.edit.await_args_list[0].args == ("pong",)
    assert event.edit.await_args.args[0].startswith("pong (")


def test_id_without_reply_shows_chat_id():
    event = fake_event(chat=-100123)
    asyncio.run(chat_id(event, CTX))

    event.edit.assert_awaited_once_with("Chat ID: -100123")


def test_id_with_reply_shows_sender_and_message():
    event = fake_event(chat=42, reply=SimpleNamespace(sender_id=777, id=5))
    asyncio.run(chat_id(event, CTX))

    text = event.edit.await_args.args[0]
    assert "Chat ID: 42" in text
    assert "Replied-to sender ID: 777" in text
    assert "Replied-to message ID: 5" in text


def test_help_lists_every_command_with_prefix():
    ctx = Context(config=Config(api_id=1, api_hash="x", command_prefix="!"), commands=COMMANDS)
    text = format_help(ctx)

    for cmd in COMMANDS:
        assert f"!{cmd.name} - {cmd.description}" in text
