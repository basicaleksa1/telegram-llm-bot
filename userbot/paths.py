"""Where the userbot keeps its files.

Everything a user can change lives in one *data folder*:

    settings.env      settings (same KEY=VALUE format as .env.example)
    prompts/          the AI's instructions; edit freely, they're never overwritten
    sessions/         the Telegram login. PRIVATE: it grants access to the account
    logs/             log files, handy for bug reports

The folder is, in order of preference:
1. the --home option or the USERBOT_HOME environment variable;
2. this repository, if it has a .env file (development checkout: keeps the
   existing .env, sessions/ and prompts/ working as before);
3. the per-user app data folder (e.g. ~/Library/Application Support/TelegramUserbot
   on macOS, %APPDATA%\\TelegramUserbot on Windows, ~/.local/share/TelegramUserbot
   on Linux). Unzipping a newer version keeps using the same folder.
"""

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_dir

APP_NAME = "TelegramUserbot"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Shipped defaults, copied into the data folder on first run.
DEFAULT_PROMPTS_DIR = PROJECT_ROOT / "prompts"
SETTINGS_TEMPLATE = PROJECT_ROOT / ".env.example"


@dataclass(frozen=True)
class Home:
    root: Path

    @property
    def settings_file(self) -> Path:
        legacy = self.root / ".env"
        return legacy if legacy.exists() else self.root / "settings.env"

    @property
    def prompts_dir(self) -> Path:
        return self.root / "prompts"

    @property
    def sessions_dir(self) -> Path:
        return self.root / "sessions"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    def resolve(self, path: str | Path) -> Path:
        """Resolve a path from the settings: relative paths are relative to the data folder."""
        path = Path(path).expanduser()
        return path if path.is_absolute() else self.root / path


def resolve_home(override: str | Path | None = None) -> Home:
    chosen = override or os.environ.get("USERBOT_HOME", "").strip()
    if chosen:
        return Home(Path(chosen).expanduser().resolve())
    if (PROJECT_ROOT / ".env").exists():
        return Home(PROJECT_ROOT)
    return Home(Path(user_data_dir(APP_NAME, appauthor=False, roaming=True)))


_home: Home | None = None


def get_home() -> Home:
    global _home
    if _home is None:
        _home = resolve_home()
    return _home


def set_home(home: Home) -> None:
    global _home
    _home = home


def ensure_home(home: Home) -> None:
    """Create the data folder, the settings file and the default prompts if missing."""
    for folder in (home.root, home.prompts_dir, home.sessions_dir, home.logs_dir):
        folder.mkdir(parents=True, exist_ok=True)

    if not home.settings_file.exists() and SETTINGS_TEMPLATE.exists():
        shutil.copyfile(SETTINGS_TEMPLATE, home.settings_file)

    if home.prompts_dir.resolve() != DEFAULT_PROMPTS_DIR.resolve():
        for default in DEFAULT_PROMPTS_DIR.glob("*.txt"):
            target = home.prompts_dir / default.name
            if not target.exists():
                shutil.copyfile(default, target)


def default_prompt_names() -> list[str]:
    """The prompt files shipped with the app, e.g. ["chat.txt"]."""
    return sorted(p.name for p in DEFAULT_PROMPTS_DIR.glob("*.txt"))


def restore_default_prompts(home: Home) -> list[str]:
    """Overwrite the shipped prompt files in the data folder with the defaults."""
    if home.prompts_dir.resolve() == DEFAULT_PROMPTS_DIR.resolve():
        return []
    restored = []
    for default in sorted(DEFAULT_PROMPTS_DIR.glob("*.txt")):
        shutil.copyfile(default, home.prompts_dir / default.name)
        restored.append(default.name)
    return restored
