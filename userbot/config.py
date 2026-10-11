"""Loads settings from the data folder's settings file (and environment variables).

Environment variables win over the file, so `LOG_LEVEL=DEBUG userbot start`
works for a one-off run. See paths.py for where the settings file lives.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, set_key, unset_key

from .paths import Home, get_home

DEFAULT_PROMPT = "prompts/chat.txt"


class ConfigError(Exception):
    """Raised when required settings are missing or invalid."""


@dataclass(frozen=True)
class Config:
    api_id: int
    api_hash: str
    phone: str | None = None
    session_name: str = "userbot"
    sessions_dir: Path = Path("sessions")
    command_prefix: str = "."
    log_level: str = "INFO"

    auto_reply_enabled: bool = True
    auto_reply_text: str = "brate radim"
    auto_reply_cooldown: float = 0.0
    auto_reply_delay: float = 3.0
    auto_reply_quote: bool = False

    llm_enabled: bool = True
    llm_host: str = "http://localhost:11434"
    llm_model: str = "qwen3.5:9b"
    llm_system_prompt_file: Path = Path(DEFAULT_PROMPT)
    llm_history_limit: int = 20
    llm_timeout: float = 60.0
    llm_allowed_chats: frozenset[int] = frozenset()
    llm_reply_language: str = ""

    @property
    def session_path(self) -> Path:
        return self.sessions_dir / self.session_name

    @property
    def has_telegram_credentials(self) -> bool:
        return self.api_id > 0 and bool(self.api_hash)


@dataclass(frozen=True)
class Setting:
    """A setting that can be changed from the menu / `userbot settings set`."""

    key: str
    kind: str  # "bool", "text", "seconds", "int", "chats"
    help: str


EDITABLE_SETTINGS = [
    Setting("AUTO_REPLY_ENABLED", "bool", "Reply automatically to private messages (AI or fixed text)."),
    Setting("AUTO_REPLY_TEXT", "text", "Fixed reply, used when the AI is off, not allowed for the chat, or fails."),
    Setting("AUTO_REPLY_DELAY", "seconds", "Wait until the person stops typing for this long, then reply once. 0 = reply immediately."),
    Setting("AUTO_REPLY_COOLDOWN", "seconds", "Minimum seconds between auto-replies in the same chat. 0 = no limit."),
    Setting("AUTO_REPLY_QUOTE", "bool", "Quote their message above each reply (false looks more like a normal chat)."),
    Setting("LLM_ENABLED", "bool", "Let the local AI write the replies. false = always send the fixed text."),
    Setting("LLM_MODEL", "text", "Ollama model to use, e.g. qwen3.5:4b. Use the Model menu to download one."),
    Setting("LLM_SYSTEM_PROMPT_FILE", "text", "Prompt file the AI follows. Use the Prompts menu to switch."),
    Setting("LLM_REPLY_LANGUAGE", "text", "Force every reply into one language, e.g. English. Empty = whatever the prompt says."),
    Setting("LLM_HISTORY_LIMIT", "int", "How many recent messages of the chat the AI sees."),
    Setting("LLM_TIMEOUT", "seconds", "Seconds to wait for the AI before sending the fixed text instead."),
    Setting("LLM_ALLOWED_CHATS", "chats", "Comma-separated chat IDs that get AI replies (find them with .id). Empty = everyone."),
    Setting("COMMAND_PREFIX", "text", "What your commands start with, e.g. . for .ping"),
    Setting("LOG_LEVEL", "text", "INFO, or DEBUG for much more detail (DEBUG also logs message text)."),
    Setting("LLM_HOST", "text", "Where Ollama runs. Only change this if you know you need to."),
]


def read_settings(home: Home | None = None) -> dict[str, str]:
    """The settings file's values, overridden by environment variables."""
    home = home or get_home()
    values: dict[str, str] = {}
    if home.settings_file.exists():
        values = {key: value or "" for key, value in dotenv_values(home.settings_file).items()}
    values.update(os.environ)
    return values


def write_setting(key: str, value: str, home: Home | None = None) -> None:
    """Change one setting in the settings file. Raises ConfigError (and keeps the old value) if invalid."""
    home = home or get_home()
    path = home.settings_file
    path.touch(exist_ok=True)
    old = dotenv_values(path).get(key)
    set_key(path, key, value, quote_mode="never" if _plain(value) else "always")
    try:
        load_config(home=home, require_telegram=False)
    except ConfigError:
        if old is None:
            unset_key(path, key, quote_mode="never")
        else:
            set_key(path, key, old, quote_mode="never" if _plain(old) else "always")
        raise


def _plain(value: str) -> bool:
    return not any(ch in value for ch in "#'\"\\\n") and value == value.strip()


def load_config(
    env: Mapping[str, str] | None = None,
    *,
    home: Home | None = None,
    require_telegram: bool = True,
) -> Config:
    """Build a Config from `env`, or from the settings file + the process environment.

    With require_telegram=False, missing API credentials are allowed (api_id is 0);
    used by the menu, the playground and the setup wizard.
    """
    home = home or get_home()
    if env is None:
        env = read_settings(home)

    def get(key: str) -> str:
        return env.get(key, "").strip()

    missing = [key for key in ("API_ID", "API_HASH") if not get(key)]
    if missing and require_telegram:
        raise ConfigError(
            f"Missing required setting(s): {', '.join(missing)}. "
            "Run the setup (menu: Run setup again) or fill them in the settings file with the values "
            "from https://my.telegram.org."
        )

    api_id = 0
    if get("API_ID"):
        try:
            api_id = int(get("API_ID"))
        except ValueError:
            raise ConfigError(f"API_ID must be a number, got {get('API_ID')!r}.") from None

    return Config(
        api_id=api_id,
        api_hash=get("API_HASH"),
        phone=get("PHONE") or None,
        session_name=get("SESSION_NAME") or "userbot",
        sessions_dir=home.sessions_dir,
        command_prefix=get("COMMAND_PREFIX") or ".",
        log_level=get("LOG_LEVEL").upper() or "INFO",
        auto_reply_enabled=_parse_bool("AUTO_REPLY_ENABLED", get("AUTO_REPLY_ENABLED"), default=True),
        auto_reply_text=get("AUTO_REPLY_TEXT") or "brate radim",
        auto_reply_cooldown=_parse_seconds("AUTO_REPLY_COOLDOWN", get("AUTO_REPLY_COOLDOWN"), default=0.0),
        auto_reply_delay=_parse_seconds("AUTO_REPLY_DELAY", get("AUTO_REPLY_DELAY"), default=3.0),
        auto_reply_quote=_parse_bool("AUTO_REPLY_QUOTE", get("AUTO_REPLY_QUOTE"), default=False),
        llm_enabled=_parse_bool("LLM_ENABLED", get("LLM_ENABLED"), default=True),
        llm_host=get("LLM_HOST") or "http://localhost:11434",
        llm_model=get("LLM_MODEL") or "qwen3.5:9b",
        llm_system_prompt_file=home.resolve(get("LLM_SYSTEM_PROMPT_FILE") or DEFAULT_PROMPT),
        llm_history_limit=_parse_positive_int("LLM_HISTORY_LIMIT", get("LLM_HISTORY_LIMIT"), default=20),
        llm_timeout=_parse_seconds("LLM_TIMEOUT", get("LLM_TIMEOUT"), default=60.0),
        llm_allowed_chats=_parse_id_list("LLM_ALLOWED_CHATS", get("LLM_ALLOWED_CHATS")),
        llm_reply_language=get("LLM_REPLY_LANGUAGE"),
    )


def _parse_bool(key: str, value: str, default: bool) -> bool:
    value = value.lower()
    if not value:
        return default
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ConfigError(f"{key} must be true/false, got {value!r}.")


def _parse_seconds(key: str, value: str, default: float) -> float:
    if not value:
        return default
    try:
        return max(float(value), 0.0)
    except ValueError:
        raise ConfigError(f"{key} must be a number of seconds, got {value!r}.") from None


def _parse_positive_int(key: str, value: str, default: int) -> int:
    if not value:
        return default
    try:
        number = int(value)
    except ValueError:
        number = 0
    if number < 1:
        raise ConfigError(f"{key} must be a whole number of at least 1, got {value!r}.")
    return number


def _parse_id_list(key: str, value: str) -> frozenset[int]:
    try:
        return frozenset(int(part) for part in value.replace(" ", "").split(",") if part)
    except ValueError:
        raise ConfigError(f"{key} must be a comma-separated list of chat IDs, got {value!r}.") from None
