"""Loads settings from environment variables (and the project's .env file)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSIONS_DIR = PROJECT_ROOT / "sessions"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
DEFAULT_SYSTEM_PROMPT_FILE = PROMPTS_DIR / "chat.txt"


class ConfigError(Exception):
    """Raised when required settings are missing or invalid."""


@dataclass(frozen=True)
class Config:
    api_id: int
    api_hash: str
    phone: str | None = None
    session_name: str = "userbot"
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
    llm_system_prompt_file: Path = DEFAULT_SYSTEM_PROMPT_FILE
    llm_history_limit: int = 20
    llm_timeout: float = 60.0
    llm_allowed_chats: frozenset[int] = frozenset()
    llm_reply_language: str = ""

    @property
    def session_path(self) -> Path:
        return SESSIONS_DIR / self.session_name


def load_config(env: Mapping[str, str] | None = None) -> Config:
    """Build a Config from `env`, or from .env + the process environment."""
    if env is None:
        load_dotenv(PROJECT_ROOT / ".env")
        env = os.environ

    def get(key: str) -> str:
        return env.get(key, "").strip()

    missing = [key for key in ("API_ID", "API_HASH") if not get(key)]
    if missing:
        raise ConfigError(
            f"Missing required setting(s): {', '.join(missing)}. "
            "Copy .env.example to .env and fill in the values from https://my.telegram.org."
        )

    try:
        api_id = int(get("API_ID"))
    except ValueError:
        raise ConfigError(f"API_ID must be a number, got {env['API_ID']!r}.") from None

    prompt_file = get("LLM_SYSTEM_PROMPT_FILE")
    prompt_path = Path(prompt_file) if prompt_file else DEFAULT_SYSTEM_PROMPT_FILE
    if not prompt_path.is_absolute():
        prompt_path = PROJECT_ROOT / prompt_path

    return Config(
        api_id=api_id,
        api_hash=get("API_HASH"),
        phone=get("PHONE") or None,
        session_name=get("SESSION_NAME") or "userbot",
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
        llm_system_prompt_file=prompt_path,
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
