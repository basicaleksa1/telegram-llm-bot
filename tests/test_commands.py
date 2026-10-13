import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from userbot import handlers  # noqa: F401  (registers the commands)
from userbot.commands import COMMANDS, Context, build_pattern, register_commands
from userbot.config import Config
from userbot.handlers.basic import chat_id, format_help, ping
from userbot.handlers.handoff import pause, resume
from userbot.handlers.handoff import paused as paused_command
from userbot.handoff import PausedChats, format_notification

CONFIG = Config(api_id=1, api_hash="x", command_prefix=".")
CTX = Context(config=CONFIG, commands=COMMANDS)


def fake_event(chat=42, reply=None):
    return SimpleNamespace(
        chat_id=chat,
        edit=AsyncMock(),
        get_reply_message=AsyncMock(return_value=reply),
    )


def test_expected_commands_are_registered():
    assert {c.name for c in COMMANDS} >= {"ping", "id", "help", "pause", "resume", "paused"}


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


# --- Pause / resume -----------------------------------------------------------------

ME = 1000


def handoff_event(tmp_path, chat=42, args=None, reply=None):
    ctx = Context(config=Config(api_id=1, api_hash="x", paused_chats_file=tmp_path / "p.json"), commands=COMMANDS)
    event = SimpleNamespace(
        chat_id=chat,
        is_reply=reply is not None,
        get_reply_message=AsyncMock(return_value=reply),
        pattern_match=SimpleNamespace(group=lambda i: args),
        client=SimpleNamespace(get_me=AsyncMock(return_value=SimpleNamespace(id=ME)), send_message=AsyncMock()),
        edit=AsyncMock(),
        delete=AsyncMock(),
    )
    return event, ctx, PausedChats(tmp_path / "p.json")


def test_pause_in_their_chat_pauses_it_and_deletes_the_command(tmp_path):
    event, ctx, paused = handoff_event(tmp_path, chat=42)

    asyncio.run(pause(event, ctx))

    assert paused.is_paused(42)
    event.delete.assert_awaited_once()  # they must not see ".pause"
    event.edit.assert_not_awaited()


def test_resume_by_id_from_saved_messages(tmp_path):
    event, ctx, paused = handoff_event(tmp_path, chat=ME, args="42")
    paused.pause(42)

    asyncio.run(resume(event, ctx))

    assert not paused.is_paused(42)
    assert "42" in event.edit.await_args.args[0]


def test_resume_as_reply_to_a_handoff_alert(tmp_path):
    alert = SimpleNamespace(raw_text=format_notification("Pera", 42, "no supplier", []))
    event, ctx, paused = handoff_event(tmp_path, chat=ME, reply=alert)
    paused.pause(42)

    asyncio.run(resume(event, ctx))

    assert not paused.is_paused(42)


def test_resume_in_saved_messages_without_target_explains(tmp_path):
    event, ctx, _ = handoff_event(tmp_path, chat=ME)

    asyncio.run(resume(event, ctx))

    assert "<chat id>" in event.edit.await_args.args[0]


def test_paused_lists_chats(tmp_path):
    event, ctx, paused = handoff_event(tmp_path, chat=ME)
    paused.pause(42, name="Pera", reason="no supplier")

    asyncio.run(paused_command(event, ctx))

    assert "Pera" in event.edit.await_args.args[0]


def test_paused_in_their_chat_sends_the_list_to_saved_messages(tmp_path):
    event, ctx, paused = handoff_event(tmp_path, chat=42)
    paused.pause(7, name="Pera")

    asyncio.run(paused_command(event, ctx))

    event.delete.assert_awaited_once()
    event.edit.assert_not_awaited()
    to, text = event.client.send_message.await_args.args
    assert to == "me" and "Pera" in text
