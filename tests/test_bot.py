from userbot import bot
from userbot.actions import friendly_error
from userbot.config import Config


def make_config(tmp_path, **overrides):
    return Config(api_id=1, api_hash="abc", sessions_dir=tmp_path, **overrides)


def test_new_test_server_login_points_at_the_test_data_center(tmp_path):
    client = bot.make_client(make_config(tmp_path, telegram_test_servers=True))

    assert (client.session.dc_id, client.session.server_address, client.session.port) == (
        bot.TEST_DC,
        bot.TEST_DC_IP,
        bot.TEST_DC_PORT,
    )


def test_real_login_is_not_pointed_at_the_test_servers(tmp_path):
    client = bot.make_client(make_config(tmp_path))

    assert client.session.server_address != bot.TEST_DC_IP


def test_real_phone_is_not_used_on_test_servers(tmp_path):
    asked = []
    kwargs = bot._start_kwargs(
        make_config(tmp_path, telegram_test_servers=True, phone="+381601234567"),
        ask_phone=lambda: asked.append("phone") or "9996621234",
        ask_code=lambda: "22222",
        ask_password=lambda: "",
    )

    assert kwargs["phone"]() == "9996621234"
    assert asked == ["phone"]


def test_test_phone_from_settings_is_used(tmp_path):
    kwargs = bot._start_kwargs(
        make_config(tmp_path, telegram_test_servers=True, phone="9996621234"),
        ask_phone=lambda: "never asked",
        ask_code=lambda: "22222",
        ask_password=lambda: "",
    )

    assert kwargs["phone"]() == "9996621234"


def test_real_servers_use_the_phone_setting(tmp_path):
    kwargs = bot._start_kwargs(
        make_config(tmp_path, phone="+381601234567"), ask_phone=lambda: "x", ask_code=lambda: "1", ask_password=lambda: ""
    )

    assert kwargs["phone"]() == "+381601234567"


def test_test_server_login_hints_at_the_code(tmp_path, caplog):
    kwargs = bot._start_kwargs(
        make_config(tmp_path, telegram_test_servers=True), ask_phone=lambda: "x", ask_code=lambda: "22222", ask_password=lambda: ""
    )

    with caplog.at_level("INFO", logger="userbot"):
        assert kwargs["code_callback"]() == "22222"
    assert "22222" in caplog.text and "222222" in caplog.text


def test_sign_up_error_is_explained():
    error = ValueError("Third-party applications cannot sign up for Telegram. See https://...")

    assert "official Telegram app" in friendly_error(error)
