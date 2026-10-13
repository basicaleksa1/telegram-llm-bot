import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from userbot.autoreply import AutoReplier
from userbot.bot import setup_handoff
from userbot.config import Config
from userbot.handoff import (
    PausedChats,
    format_notification,
    parse_chat_id,
    register_remote_control,
    resume_hint,
    run_remote_command,
    split_handoff,
)

# --- The marker ------------------------------------------------------------------


def test_reply_without_marker_is_unchanged():
    assert split_handoff("hey how many models?") == ("hey how many models?", None)


def test_marker_gives_the_summary_as_reason():
    text, reason = split_handoff("[[HANDOFF]] 2 models, paid $3, no accounts and no supplier")

    assert text == ""
    assert reason == "2 models, paid $3, no accounts and no supplier"


def test_marker_is_found_case_and_space_insensitive_and_mid_text():
    text, reason = split_handoff("hmm ok\n[[ handoff ]]\nno supplier")

    assert text == "hmm ok"
    assert reason == "no supplier"


def test_marker_without_summary_still_hands_off():
    assert split_handoff("[[HANDOFF]]")[1] == "the AI handed this chat over to you"


# --- Paused chats ----------------------------------------------------------------


def test_paused_chats_round_trip(tmp_path):
    paused = PausedChats(tmp_path / "paused.json")
    assert not paused.is_paused(42)

    paused.pause(42, name="Pera", reason="no supplier")

    assert paused.is_paused(42)
    assert PausedChats(tmp_path / "paused.json").is_paused(42)  # stored on disk
    assert paused.items()[0][0] == 42
    assert "Pera" in paused.describe() and "no supplier" in paused.describe()

    assert paused.resume(42) is True
    assert paused.resume(42) is False
    assert not paused.is_paused(42)
    assert "No paused chats" in paused.describe()


def test_broken_paused_file_counts_as_nothing_paused(tmp_path):
    (tmp_path / "paused.json").write_text("{not json")

    assert not PausedChats(tmp_path / "paused.json").is_paused(1)


# --- The alert -------------------------------------------------------------------


HISTORY = [
    {"role": "user", "content": "but i dont have accounts"},
    {"role": "assistant", "content": "hmm can you get them?"},
    {"role": "user", "content": "i dont have a supplier", "images": [b"x"]},
]


def test_notification_has_reason_history_and_chat_id():
    alert = format_notification("Pera (@pera)", 555, "no supplier", HISTORY)

    assert "Pera (@pera)" in alert
    assert "Why: no supplier" in alert
    assert "them: i dont have a supplier" in alert
    assert "bot: hmm can you get them?" in alert
    assert parse_chat_id(alert) == 555


def test_notification_keeps_only_the_last_messages():
    history = [{"role": "user", "content": f"m{i}"} for i in range(20)]

    alert = format_notification("P", 1, "r", history)

    assert "them: m19" in alert and "them: m11" not in alert


def test_parse_chat_id_handles_negative_ids_and_other_text():
    assert parse_chat_id("bla\nchat -100123\nmore") == -100123
    assert parse_chat_id("just a message") is None
    assert parse_chat_id(None) is None


def test_resume_hint_depends_on_where_the_alert_goes():
    assert '".resume"' in resume_hint(".", to_saved_messages=True)
    assert '"resume"' in resume_hint(".", to_saved_messages=False)


# --- Remote control --------------------------------------------------------------


def test_remote_resume_as_reply_to_an_alert(tmp_path):
    paused = PausedChats(tmp_path / "p.json")
    paused.pause(555)

    answer = run_remote_command("Resume", paused, replied_text=format_notification("P", 555, "r", []))

    assert "555" in answer
    assert not paused.is_paused(555)


def test_remote_resume_and_pause_by_id(tmp_path):
    paused = PausedChats(tmp_path / "p.json")

    assert "Paused" in run_remote_command("pause 7", paused, None)
    assert paused.is_paused(7)
    assert "Resumed" in run_remote_command("resume 7", paused, None)
    assert "wasn't paused" in run_remote_command("resume 7", paused, None)


def test_remote_resume_without_target_explains_usage(tmp_path):
    assert "resume <chat id>" in run_remote_command("resume", PausedChats(tmp_path / "p.json"), None)


def test_remote_list_and_help(tmp_path):
    paused = PausedChats(tmp_path / "p.json")

    assert "No paused chats" in run_remote_command("paused", paused, None)
    assert "resume" in run_remote_command("help", paused, None)


def test_normal_messages_are_not_commands(tmp_path):
    paused = PausedChats(tmp_path / "p.json")

    assert run_remote_command("hey whats up", paused, None) is None
    assert run_remote_command("resume the meeting tomorrow?", paused, None) is None


def test_remote_control_listens_only_to_the_alert_account(tmp_path):
    client = MagicMock()
    register_remote_control(client, PausedChats(tmp_path / "p.json"), controller_id=999)

    handler, builder = client.add_event_handler.call_args.args
    assert builder.incoming is True
    assert builder.from_users == 999


def test_remote_control_handler_replies(tmp_path):
    paused = PausedChats(tmp_path / "p.json")
    paused.pause(555)
    client = MagicMock()
    register_remote_control(client, paused, controller_id=999)
    handler = client.add_event_handler.call_args.args[0]
    alert = SimpleNamespace(raw_text=format_notification("P", 555, "r", []))
    event = SimpleNamespace(raw_text="resume", is_reply=True, get_reply_message=AsyncMock(return_value=alert), reply=AsyncMock())

    asyncio.run(handler(event))

    assert not paused.is_paused(555)
    event.reply.assert_awaited_once()


# --- Startup: where alerts go ---------------------------------------------------


def _replier(tmp_path, **overrides):
    config = Config(api_id=1, api_hash="x", paused_chats_file=tmp_path / "p.json", **overrides)
    return config, AutoReplier(config)


def test_alerts_go_to_the_configured_account(tmp_path):
    config, replier = _replier(tmp_path, handoff_notify_chat="@my_alt")
    other = SimpleNamespace(id=999)
    client = MagicMock(get_entity=AsyncMock(return_value=other))

    asyncio.run(setup_handoff(client, config, replier, me=SimpleNamespace(id=1)))

    client.get_entity.assert_awaited_once_with("@my_alt")
    assert replier.notify_target is other
    assert replier.notify_user_id == 999
    client.add_event_handler.assert_called_once()  # remote control


def test_numeric_notify_chat_is_looked_up_as_an_id(tmp_path):
    config, replier = _replier(tmp_path, handoff_notify_chat="12345")
    client = MagicMock(get_entity=AsyncMock(return_value=SimpleNamespace(id=12345)))

    asyncio.run(setup_handoff(client, config, replier, me=SimpleNamespace(id=1)))

    client.get_entity.assert_awaited_once_with(12345)


def test_unknown_notify_account_falls_back_to_saved_messages(tmp_path):
    config, replier = _replier(tmp_path, handoff_notify_chat="@nobody_here")
    client = MagicMock(get_entity=AsyncMock(side_effect=ValueError("No user has that username")))

    asyncio.run(setup_handoff(client, config, replier, me=SimpleNamespace(id=1)))

    assert replier.notify_target == "me"
    client.add_event_handler.assert_not_called()


def test_empty_notify_chat_means_saved_messages(tmp_path):
    config, replier = _replier(tmp_path)
    client = MagicMock(get_entity=AsyncMock())

    asyncio.run(setup_handoff(client, config, replier, me=SimpleNamespace(id=1)))

    client.get_entity.assert_not_awaited()
    assert replier.notify_target == "me"
