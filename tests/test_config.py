import pytest

from userbot.config import ConfigError, load_config, read_settings, write_setting
from userbot.paths import Home, set_home


@pytest.fixture(autouse=True)
def home(tmp_path):
    home = Home(tmp_path)
    set_home(home)
    yield home
    set_home(None)


def test_minimal_config_uses_defaults(home):
    config = load_config({"API_ID": "123", "API_HASH": "abc"})

    assert config.api_id == 123
    assert config.api_hash == "abc"
    assert config.phone is None
    assert config.session_name == "userbot"
    assert config.command_prefix == "."
    assert config.log_level == "INFO"
    assert config.session_path == home.sessions_dir / "userbot"


def test_optional_values_are_read():
    config = load_config(
        {
            "API_ID": "123",
            "API_HASH": "abc",
            "PHONE": "+381601234567",
            "SESSION_NAME": "main",
            "COMMAND_PREFIX": "!",
            "LOG_LEVEL": "debug",
        }
    )

    assert config.phone == "+381601234567"
    assert config.session_name == "main"
    assert config.command_prefix == "!"
    assert config.log_level == "DEBUG"


@pytest.mark.parametrize("env", [{}, {"API_ID": "123"}, {"API_HASH": "abc"}, {"API_ID": " ", "API_HASH": "abc"}])
def test_missing_required_values_raise(env):
    with pytest.raises(ConfigError, match="Missing required"):
        load_config(env)


def test_non_numeric_api_id_raises():
    with pytest.raises(ConfigError, match="API_ID must be a number"):
        load_config({"API_ID": "not-a-number", "API_HASH": "abc"})


def test_auto_reply_defaults():
    config = load_config({"API_ID": "123", "API_HASH": "abc"})

    assert config.auto_reply_enabled is True
    assert config.auto_reply_text == "brate radim"
    assert config.auto_reply_cooldown == 0


def test_auto_reply_settings_are_read():
    config = load_config(
        {
            "API_ID": "123",
            "API_HASH": "abc",
            "AUTO_REPLY_ENABLED": "false",
            "AUTO_REPLY_TEXT": "zauzet sam",
            "AUTO_REPLY_COOLDOWN": "30",
        }
    )

    assert config.auto_reply_enabled is False
    assert config.auto_reply_text == "zauzet sam"
    assert config.auto_reply_cooldown == 30


@pytest.mark.parametrize(
    "key, value, message",
    [("AUTO_REPLY_ENABLED", "maybe", "true/false"), ("AUTO_REPLY_COOLDOWN", "soon", "AUTO_REPLY_COOLDOWN")],
)
def test_invalid_auto_reply_settings_raise(key, value, message):
    with pytest.raises(ConfigError, match=message):
        load_config({"API_ID": "123", "API_HASH": "abc", key: value})


def test_llm_defaults(home):
    config = load_config({"API_ID": "123", "API_HASH": "abc"})

    assert config.auto_reply_delay == 3
    assert config.llm_enabled is True
    assert config.llm_host == "http://localhost:11434"
    assert config.llm_model == "qwen3.5:9b"
    assert config.llm_system_prompt_file == home.prompts_dir / "chat.txt"
    assert config.llm_history_limit == 20
    assert config.auto_reply_quote is False
    assert config.llm_timeout == 60
    assert config.llm_allowed_chats == frozenset()
    assert config.llm_reply_language == ""
    assert config.auto_reply_delay_max == 0
    assert config.auto_reply_delay_enabled is True
    assert config.llm_typo_rate == 0
    assert config.llm_vision is True
    assert config.llm_max_images == 3
    assert config.handoff_notify_chat == ""
    assert config.handoff_client_message == ""
    assert config.paused_chats_file == home.root / "paused_chats.json"


def test_llm_settings_are_read(home):
    config = load_config(
        {
            "API_ID": "123",
            "API_HASH": "abc",
            "AUTO_REPLY_DELAY": "0",
            "AUTO_REPLY_QUOTE": "true",
            "LLM_ENABLED": "no",
            "LLM_HOST": "http://127.0.0.1:1234",
            "LLM_MODEL": "gemma4:12b",
            "LLM_SYSTEM_PROMPT_FILE": "prompts/me.txt",
            "LLM_HISTORY_LIMIT": "4",
            "LLM_TIMEOUT": "15",
            "LLM_ALLOWED_CHATS": "123, -100456,789",
            "LLM_REPLY_LANGUAGE": "English",
            "AUTO_REPLY_DELAY_MAX": "600",
            "AUTO_REPLY_DELAY_ENABLED": "false",
            "LLM_TYPO_RATE": "0.05",
            "LLM_VISION": "false",
            "LLM_MAX_IMAGES": "2",
            "HANDOFF_NOTIFY_CHAT": "@my_other_account",
            "HANDOFF_CLIENT_MESSAGE": "ill get back to you",
        }
    )

    assert config.auto_reply_delay == 0
    assert config.auto_reply_quote is True
    assert config.llm_enabled is False
    assert config.llm_host == "http://127.0.0.1:1234"
    assert config.llm_model == "gemma4:12b"
    assert config.llm_system_prompt_file == home.root / "prompts/me.txt"
    assert config.llm_history_limit == 4
    assert config.llm_timeout == 15
    assert config.llm_allowed_chats == frozenset({123, -100456, 789})
    assert config.llm_reply_language == "English"
    assert config.auto_reply_delay_max == 600
    assert config.auto_reply_delay_enabled is False
    assert config.llm_typo_rate == 0.05
    assert config.llm_vision is False
    assert config.llm_max_images == 2
    assert config.handoff_notify_chat == "@my_other_account"
    assert config.handoff_client_message == "ill get back to you"


@pytest.mark.parametrize(
    "key, value",
    [
        ("LLM_ENABLED", "sometimes"),
        ("LLM_HISTORY_LIMIT", "0"),
        ("LLM_HISTORY_LIMIT", "ten"),
        ("LLM_TIMEOUT", "fast"),
        ("AUTO_REPLY_DELAY", "later"),
        ("AUTO_REPLY_QUOTE", "maybe"),
        ("LLM_ALLOWED_CHATS", "123,abc"),
        ("AUTO_REPLY_DELAY_MAX", "soon"),
        ("AUTO_REPLY_DELAY_ENABLED", "sometimes"),
        ("LLM_TYPO_RATE", "lots"),
        ("LLM_TYPO_RATE", "1.5"),
        ("LLM_TYPO_RATE", "-0.1"),
        ("LLM_VISION", "maybe"),
        ("LLM_MAX_IMAGES", "0"),
    ],
)
def test_invalid_llm_settings_raise(key, value):
    with pytest.raises(ConfigError, match=key):
        load_config({"API_ID": "123", "API_HASH": "abc", key: value})


def test_credentials_can_be_missing_for_the_menu_and_playground():
    config = load_config({}, require_telegram=False)

    assert config.api_id == 0
    assert config.has_telegram_credentials is False


def test_absolute_prompt_path_is_kept(tmp_path):
    prompt = tmp_path / "elsewhere" / "mine.txt"
    config = load_config({"API_ID": "1", "API_HASH": "x", "LLM_SYSTEM_PROMPT_FILE": str(prompt)})

    assert config.llm_system_prompt_file == prompt


def test_settings_file_is_read_and_environment_wins(home, monkeypatch):
    home.settings_file.write_text("API_ID=5\nAPI_HASH=abc\nAUTO_REPLY_TEXT=brb\nLOG_LEVEL=INFO\n")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    config = load_config()

    assert (config.api_id, config.auto_reply_text, config.log_level) == (5, "brb", "DEBUG")


def test_legacy_env_file_is_used_when_present(home):
    (home.root / ".env").write_text("API_ID=7\nAPI_HASH=abc\n")

    assert home.settings_file.name == ".env"
    assert load_config().api_id == 7


def test_write_setting_updates_the_file_and_is_read_back(home):
    home.settings_file.write_text("# comment stays\nAUTO_REPLY_DELAY=3\n")

    write_setting("AUTO_REPLY_DELAY", "5")
    write_setting("AUTO_REPLY_TEXT", "brb, busy #1")

    assert "# comment stays" in home.settings_file.read_text()
    settings = read_settings()
    assert settings["AUTO_REPLY_DELAY"] == "5"
    assert settings["AUTO_REPLY_TEXT"] == "brb, busy #1"
    assert load_config(require_telegram=False).auto_reply_text == "brb, busy #1"


def test_invalid_setting_is_rejected_and_the_old_value_kept(home):
    home.settings_file.write_text("AUTO_REPLY_DELAY=3\n")

    with pytest.raises(ConfigError, match="AUTO_REPLY_DELAY"):
        write_setting("AUTO_REPLY_DELAY", "soon")
    with pytest.raises(ConfigError, match="LLM_TIMEOUT"):
        write_setting("LLM_TIMEOUT", "fast")

    assert read_settings()["AUTO_REPLY_DELAY"] == "3"
    assert "LLM_TIMEOUT" not in home.settings_file.read_text()
