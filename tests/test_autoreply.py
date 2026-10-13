import asyncio
import random
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from userbot.autoreply import (
    QUICK_REPLY_DELAY,
    TELEGRAM_SERVICE_USER_ID,
    AutoReplier,
    is_image,
    register_auto_reply,
    to_llm_message,
)
from userbot.handoff import PausedChats, parse_chat_id
from userbot.config import Config
from userbot.llm import LLMError


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class FakeClient:
    """Just enough of TelegramClient for the auto-replier."""

    def __init__(self, history=(), first_name="Aleksa"):
        self.history = list(history)  # newest first, like Telegram
        self.first_name = first_name
        self.actions = []
        self.sent = []  # (to, text) for send_message

    async def iter_messages(self, chat_id, limit):
        for message in self.history[:limit]:
            yield message

    @asynccontextmanager
    async def action(self, chat_id, kind):
        self.actions.append((chat_id, kind))
        yield

    async def get_me(self):
        return SimpleNamespace(first_name=self.first_name)

    async def send_message(self, to, text):
        self.sent.append((to, text))


def msg(id, text, out=False, media=None):
    return SimpleNamespace(id=id, raw_text=text, out=out, media=media)


def photo_msg(id, caption="", data=b"jpeg-bytes"):
    message = msg(id, caption, media=type("MessageMediaPhoto", (), {})())
    message.photo = object()
    message.download_media = AsyncMock(return_value=data)
    return message


def make_config(**overrides):
    overrides.setdefault("auto_reply_delay", 0)
    overrides.setdefault("auto_reply_quote", True)
    overrides.setdefault("paused_chats_file", Path(tempfile.mkdtemp()) / "paused_chats.json")
    return Config(api_id=1, api_hash="x", **overrides)


def fake_event(chat=42, sender_id=42, bot=False, message=None, client=None):
    message = message or msg(100, "hej")
    return SimpleNamespace(
        chat_id=chat,
        sender_id=sender_id,
        id=message.id,
        message=message,
        client=client or FakeClient(history=[message]),
        get_sender=AsyncMock(return_value=SimpleNamespace(bot=bot, first_name="Pera", last_name=None, username="pera")),
        reply=AsyncMock(),
        respond=AsyncMock(),
    )


def fake_llm(reply="ćao, javiću se"):
    return SimpleNamespace(model="test-model", reply=AsyncMock(return_value=reply))


# --- Fixed-text replies (no LLM) ---------------------------------------------


def test_replies_with_default_text():
    event = fake_event()
    asyncio.run(AutoReplier(make_config()).handle(event))

    event.reply.assert_awaited_once_with("brate radim")


def test_replies_with_custom_text():
    event = fake_event()
    asyncio.run(AutoReplier(make_config(auto_reply_text="zauzet sam")).handle(event))

    event.reply.assert_awaited_once_with("zauzet sam")


def test_replies_to_every_message_without_delay_or_cooldown():
    replier = AutoReplier(make_config())
    events = [fake_event(), fake_event()]
    for e in events:
        asyncio.run(replier.handle(e))

    assert all(e.reply.await_count == 1 for e in events)


def test_ignores_bots():
    event = fake_event(bot=True)
    asyncio.run(AutoReplier(make_config()).handle(event))

    event.reply.assert_not_awaited()


def test_ignores_telegram_service_account():
    event = fake_event(chat=TELEGRAM_SERVICE_USER_ID, sender_id=TELEGRAM_SERVICE_USER_ID)
    asyncio.run(AutoReplier(make_config()).handle(event))

    event.reply.assert_not_awaited()


def test_cooldown_is_per_chat():
    clock = FakeClock()
    replier = AutoReplier(make_config(auto_reply_cooldown=60), clock=clock)

    first, again, other_chat = fake_event(chat=1), fake_event(chat=1), fake_event(chat=2)
    asyncio.run(replier.handle(first))
    clock.now += 30
    asyncio.run(replier.handle(again))
    asyncio.run(replier.handle(other_chat))

    first.reply.assert_awaited_once()
    again.reply.assert_not_awaited()
    other_chat.reply.assert_awaited_once()

    clock.now += 31
    after_cooldown = fake_event(chat=1)
    asyncio.run(replier.handle(after_cooldown))
    after_cooldown.reply.assert_awaited_once()


def test_default_sends_a_plain_message_instead_of_quoting():
    event = fake_event()
    asyncio.run(AutoReplier(Config(api_id=1, api_hash="x", auto_reply_delay=0)).handle(event))

    event.respond.assert_awaited_once_with("brate radim")
    event.reply.assert_not_awaited()


def test_quote_mode_replies_to_the_message():
    event = fake_event()
    asyncio.run(AutoReplier(make_config(auto_reply_quote=True)).handle(event))

    event.reply.assert_awaited_once_with("brate radim")
    event.respond.assert_not_awaited()


# --- Waiting for the person to stop typing -----------------------------------


def test_burst_of_messages_gets_one_reply_to_the_last_one():
    async def scenario():
        replier = AutoReplier(make_config(auto_reply_delay=0.05))
        burst = [fake_event(message=msg(i, f"poruka {i}")) for i in range(3)]
        for e in burst:
            await replier.handle(e)
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.1)
        return burst

    first, second, last = asyncio.run(scenario())
    first.reply.assert_not_awaited()
    second.reply.assert_not_awaited()
    last.reply.assert_awaited_once_with("brate radim")


def test_new_message_does_not_cancel_a_reply_in_progress():
    async def scenario():
        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_reply(owner, history):
            started.set()
            await release.wait()
            return "odgovor"

        llm = SimpleNamespace(model="m", reply=slow_reply)
        replier = AutoReplier(make_config(auto_reply_delay=0.01), llm=llm)
        first, second = fake_event(message=msg(1, "a")), fake_event(message=msg(2, "b"))

        await replier.handle(first)
        await started.wait()  # first reply is now being generated
        await replier.handle(second)
        release.set()
        await asyncio.sleep(0.05)
        return first, second

    first, second = asyncio.run(scenario())
    first.reply.assert_awaited_once_with("odgovor")
    second.reply.assert_awaited_once_with("odgovor")


# --- LLM replies ---------------------------------------------------------------


def test_llm_writes_the_reply_from_chat_history():
    history = [msg(3, "jesi tu?"), msg(2, "brate radim", out=True), msg(1, "hej")]  # newest first
    client = FakeClient(history=history, first_name="Aleksa")
    event = fake_event(message=history[0], client=client)
    llm = fake_llm("tu sam, javim se kasnije")

    asyncio.run(AutoReplier(make_config(), llm=llm).handle(event))

    event.reply.assert_awaited_once_with("tu sam, javim se kasnije")
    owner, messages = llm.reply.await_args.args
    assert owner == "Aleksa"
    assert messages == [
        {"role": "user", "content": "hej"},
        {"role": "assistant", "content": "brate radim"},
        {"role": "user", "content": "jesi tu?"},
    ]
    assert client.actions == [(42, "typing")]


def test_history_respects_the_limit():
    history = [msg(i, f"m{i}") for i in range(20, 0, -1)]
    event = fake_event(message=history[0], client=FakeClient(history=history))
    llm = fake_llm()

    asyncio.run(AutoReplier(make_config(llm_history_limit=5), llm=llm).handle(event))

    _, messages = llm.reply.await_args.args
    assert [m["content"] for m in messages] == ["m16", "m17", "m18", "m19", "m20"]


def test_current_message_is_added_if_history_does_not_include_it_yet():
    client = FakeClient(history=[msg(1, "staro")])
    event = fake_event(message=msg(2, "novo"), client=client)
    llm = fake_llm()

    asyncio.run(AutoReplier(make_config(), llm=llm).handle(event))

    _, messages = llm.reply.await_args.args
    assert messages[-1] == {"role": "user", "content": "novo"}


def test_llm_error_falls_back_to_fixed_text():
    llm = SimpleNamespace(model="m", reply=AsyncMock(side_effect=LLMError("Ollama is down")))
    event = fake_event()

    asyncio.run(AutoReplier(make_config(), llm=llm).handle(event))

    event.reply.assert_awaited_once_with("brate radim")


def test_unexpected_error_falls_back_to_fixed_text():
    llm = SimpleNamespace(model="m", reply=AsyncMock(side_effect=RuntimeError("boom")))
    event = fake_event()

    asyncio.run(AutoReplier(make_config(), llm=llm).handle(event))

    event.reply.assert_awaited_once_with("brate radim")


def test_allowlist_limits_llm_to_listed_chats():
    llm = fake_llm("llm odgovor")
    replier = AutoReplier(make_config(llm_allowed_chats=frozenset({1})), llm=llm)
    allowed, other = fake_event(chat=1), fake_event(chat=2)

    asyncio.run(replier.handle(allowed))
    asyncio.run(replier.handle(other))

    allowed.reply.assert_awaited_once_with("llm odgovor")
    other.reply.assert_awaited_once_with("brate radim")
    assert llm.reply.await_count == 1


def test_media_messages_are_described_to_the_llm():
    photo = type("MessageMediaPhoto", (), {})()
    assert to_llm_message(msg(1, "", media=photo)) == {"role": "user", "content": "[sent a photo]"}
    assert to_llm_message(msg(1, "pogledaj", media=photo)) == {"role": "user", "content": "[sent a photo] pogledaj"}
    assert to_llm_message(msg(1, "", out=True)) is None


def test_ai_replies_get_markdown_removed_and_typos():
    event = fake_event()
    replier = AutoReplier(make_config(llm_typo_rate=1.0), llm=fake_llm("**sounds** good"), rng=random.Random(1))

    asyncio.run(replier.handle(event))

    sent = event.reply.await_args.args[0]
    assert "*" not in sent
    assert sent != "sounds good" and sent.startswith("s")


def test_fallback_text_never_gets_typos():
    event = fake_event()

    asyncio.run(AutoReplier(make_config(llm_typo_rate=1.0, auto_reply_text="zauzet sam")).handle(event))

    event.reply.assert_awaited_once_with("zauzet sam")


# --- Random delay ----------------------------------------------------------------


def test_delay_is_random_between_min_and_max():
    replier = AutoReplier(make_config(auto_reply_delay=180, auto_reply_delay_max=600), rng=random.Random(0))

    delays = [replier.pick_delay() for _ in range(50)]

    assert all(180 <= d <= 600 for d in delays)
    assert len(set(delays)) > 1


def test_disabled_delay_replies_quickly_whatever_the_delay_settings():
    replier = AutoReplier(make_config(auto_reply_delay_enabled=False, auto_reply_delay=180, auto_reply_delay_max=600))

    assert replier.pick_delay() == QUICK_REPLY_DELAY


def test_disabled_delay_keeps_an_even_shorter_delay():
    replier = AutoReplier(make_config(auto_reply_delay_enabled=False, auto_reply_delay=0))

    assert replier.pick_delay() == 0


def test_delay_is_fixed_when_max_is_not_larger():
    replier = AutoReplier(make_config(auto_reply_delay=3, auto_reply_delay_max=0))

    assert replier.pick_delay() == 3


# --- Photos ----------------------------------------------------------------------


def test_recent_photos_are_shown_to_the_llm():
    photo = photo_msg(2, "evo je")
    history = [photo, msg(1, "hej")]  # newest first
    event = fake_event(message=photo, client=FakeClient(history=history))
    llm = fake_llm()

    asyncio.run(AutoReplier(make_config(), llm=llm).handle(event))

    _, messages = llm.reply.await_args.args
    assert messages[-1] == {"role": "user", "content": "[sent a photo] evo je", "images": [b"jpeg-bytes"]}


def test_only_the_newest_photos_are_downloaded():
    photos = [photo_msg(i) for i in range(5, 0, -1)]  # newest first
    event = fake_event(message=photos[0], client=FakeClient(history=photos))
    llm = fake_llm()

    asyncio.run(AutoReplier(make_config(llm_max_images=2), llm=llm).handle(event))

    _, messages = llm.reply.await_args.args
    assert ["images" in m for m in messages] == [False, False, False, True, True]
    assert photos[-1].download_media.await_count == 0


def test_photos_are_downloaded_once_per_chat():
    photo = photo_msg(1)
    replier = AutoReplier(make_config(), llm=fake_llm())
    for _ in range(2):
        asyncio.run(replier.handle(fake_event(message=photo, client=FakeClient(history=[photo]))))

    assert photo.download_media.await_count == 1


def test_no_photos_downloaded_when_vision_is_off():
    photo = photo_msg(1)
    event = fake_event(message=photo, client=FakeClient(history=[photo]))

    asyncio.run(AutoReplier(make_config(llm_vision=False), llm=fake_llm()).handle(event))

    photo.download_media.assert_not_awaited()


def test_is_image_detects_photos_and_image_files_but_not_stickers():
    image_file = SimpleNamespace(document=SimpleNamespace(mime_type="image/png", size=1000))
    pdf = SimpleNamespace(document=SimpleNamespace(mime_type="application/pdf", size=1000))
    sticker = SimpleNamespace(sticker=object(), document=SimpleNamespace(mime_type="image/webp", size=1000))
    huge = SimpleNamespace(document=SimpleNamespace(mime_type="image/png", size=50 * 1024 * 1024))

    assert is_image(SimpleNamespace(photo=object()))
    assert is_image(image_file)
    assert not is_image(pdf)
    assert not is_image(sticker)
    assert not is_image(huge)


# --- Handoff ---------------------------------------------------------------------


def test_handoff_pauses_chat_sends_holding_message_and_alerts_you():
    config = make_config(handoff_client_message="ill get back to you")
    history = [msg(2, "i dont have a supplier"), msg(1, "hmm can you get them?", out=True)]
    client = FakeClient(history=history)
    event = fake_event(chat=555, message=history[0], client=client)
    replier = AutoReplier(config, llm=fake_llm("[[HANDOFF]] 2 models, no accounts, no supplier"))

    asyncio.run(replier.handle(event))

    event.reply.assert_awaited_once_with("ill get back to you")  # never the model's text
    assert PausedChats(config.paused_chats_file).is_paused(555)
    [(to, alert)] = client.sent
    assert to == "me"  # no HANDOFF_NOTIFY_CHAT: Saved Messages
    assert "Pera (@pera)" in alert
    assert "2 models, no accounts, no supplier" in alert
    assert "them: i dont have a supplier" in alert
    assert '".resume"' in alert
    assert parse_chat_id(alert) == 555


def test_handoff_without_client_message_sends_nothing_to_them():
    client = FakeClient()
    event = fake_event(client=client)

    asyncio.run(AutoReplier(make_config(), llm=fake_llm("[[HANDOFF]] asked if bot")).handle(event))

    event.reply.assert_not_awaited()
    event.respond.assert_not_awaited()
    assert len(client.sent) == 1


def test_handoff_alert_goes_to_the_notify_account():
    client = FakeClient()
    replier = AutoReplier(make_config(), llm=fake_llm("[[HANDOFF]] no supplier"))
    other_account = SimpleNamespace(id=999)
    replier.notify_target, replier.notify_user_id = other_account, 999

    asyncio.run(replier.handle(fake_event(client=client)))

    [(to, alert)] = client.sent
    assert to is other_account
    assert 'Reply "resume"' in alert


def test_failed_alert_falls_back_to_saved_messages():
    client = FakeClient()
    calls = []

    async def send_message(to, text):
        calls.append(to)
        if to != "me":
            raise ValueError("cannot find entity")

    client.send_message = send_message
    replier = AutoReplier(make_config(), llm=fake_llm("[[HANDOFF]] no supplier"))
    replier.notify_target = SimpleNamespace(id=999)

    asyncio.run(replier.handle(fake_event(client=client)))

    assert calls[-1] == "me"


def test_paused_chats_get_no_reply_at_all():
    config = make_config()
    PausedChats(config.paused_chats_file).pause(42)
    llm = fake_llm()
    event = fake_event(chat=42)

    asyncio.run(AutoReplier(config, llm=llm).handle(event))

    event.reply.assert_not_awaited()
    llm.reply.assert_not_awaited()


def test_chat_paused_during_the_delay_gets_no_reply():
    async def scenario():
        config = make_config(auto_reply_delay=0.02)
        replier = AutoReplier(config, llm=fake_llm())
        event = fake_event(chat=42)
        await replier.handle(event)
        PausedChats(config.paused_chats_file).pause(42)
        await asyncio.sleep(0.05)
        return event

    event = asyncio.run(scenario())
    event.reply.assert_not_awaited()


def test_messages_from_the_notify_account_are_not_auto_answered():
    replier = AutoReplier(make_config())
    replier.notify_user_id = 999
    event = fake_event(chat=999, sender_id=999)

    asyncio.run(replier.handle(event))

    event.reply.assert_not_awaited()


# --- Registration ----------------------------------------------------------------


def test_registers_incoming_private_handler_when_enabled():
    client = MagicMock()
    register_auto_reply(client, make_config())

    client.add_event_handler.assert_called_once()
    builder = client.add_event_handler.call_args.args[1]
    assert builder.incoming is True
    assert builder.func(SimpleNamespace(is_private=True)) is True
    assert builder.func(SimpleNamespace(is_private=False)) is False


def test_does_not_register_when_disabled():
    client = MagicMock()
    register_auto_reply(client, make_config(auto_reply_enabled=False), llm=fake_llm())

    client.add_event_handler.assert_not_called()
