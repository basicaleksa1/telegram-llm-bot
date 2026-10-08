import pytest

from userbot.config import DEFAULT_SYSTEM_PROMPT_FILE, PROJECT_ROOT, SESSIONS_DIR, ConfigError, load_config


def test_minimal_config_uses_defaults():
    config = load_config({"API_ID": "123", "API_HASH": "abc"})

    assert config.api_id == 123
    assert config.api_hash == "abc"
    assert config.phone is None
    assert config.session_name == "userbot"
    assert config.command_prefix == "."
    assert config.log_level == "INFO"
    assert config.session_path == SESSIONS_DIR / "userbot"


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


def test_llm_defaults():
    config = load_config({"API_ID": "123", "API_HASH": "abc"})

    assert config.auto_reply_delay == 3
    assert config.llm_enabled is True
    assert config.llm_host == "http://localhost:11434"
    assert config.llm_model == "qwen3.5:9b"
    assert config.llm_system_prompt_file == DEFAULT_SYSTEM_PROMPT_FILE
    assert config.llm_history_limit == 20
    assert config.auto_reply_quote is False
    assert config.llm_timeout == 60
    assert config.llm_allowed_chats == frozenset()
    assert config.llm_reply_language == ""


def test_llm_settings_are_read():
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
        }
    )

    assert config.auto_reply_delay == 0
    assert config.auto_reply_quote is True
    assert config.llm_enabled is False
    assert config.llm_host == "http://127.0.0.1:1234"
    assert config.llm_model == "gemma4:12b"
    assert config.llm_system_prompt_file == PROJECT_ROOT / "prompts/me.txt"
    assert config.llm_history_limit == 4
    assert config.llm_timeout == 15
    assert config.llm_allowed_chats == frozenset({123, -100456, 789})
    assert config.llm_reply_language == "English"


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
    ],
)
def test_invalid_llm_settings_raise(key, value):
    with pytest.raises(ConfigError, match=key):
        load_config({"API_ID": "123", "API_HASH": "abc", key: value})
