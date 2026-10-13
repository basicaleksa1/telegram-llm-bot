"""Bringing an existing data folder up to date after a new version is unpacked.

The data folder (settings, prompts, login) outlives the app folder, so a tester
who unzips a newer version keeps their old settings file and prompts. On the
first start of a newer version, apply_updates():

- adds settings that are new in .env.example, and updates the ones the tester
  never changed whose default changed (a value they set themselves is kept);
- replaces the shipped prompts that changed, saving an edited copy to
  prompts/backup/ first;
- returns a notice saying all of that, plus the CHANGELOG entries.

version.json in the data folder records what was installed last: the version,
the template's default values and a hash of each shipped prompt, so the next
update knows what the tester changed.
"""

import hashlib
import json
import logging
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values, set_key
from rich.markup import escape
from rich.panel import Panel

from . import __version__
from .config import is_plain_value
from .paths import DEFAULT_PROMPTS_DIR, PROJECT_ROOT, SETTINGS_TEMPLATE, Home
from .ui import console

log = logging.getLogger(__name__)

CHANGELOG = PROJECT_ROOT / "CHANGELOG.md"
STATE_FILE = "version.json"

# What 0.1.0 shipped, for data folders from before version.json existed.
LEGACY_VERSION = "0.1.0"
LEGACY_DEFAULTS = {
    "API_ID": "",
    "API_HASH": "",
    "PHONE": "",
    "SESSION_NAME": "userbot",
    "COMMAND_PREFIX": ".",
    "LOG_LEVEL": "INFO",
    "AUTO_REPLY_ENABLED": "true",
    "AUTO_REPLY_TEXT": "brate radim",
    "AUTO_REPLY_DELAY": "3",
    "AUTO_REPLY_COOLDOWN": "0",
    "AUTO_REPLY_QUOTE": "false",
    "LLM_ENABLED": "true",
    "LLM_MODEL": "qwen3.5:9b",
    "LLM_HOST": "http://localhost:11434",
    "LLM_SYSTEM_PROMPT_FILE": "prompts/chat.txt",
    "LLM_HISTORY_LIMIT": "20",
    "LLM_TIMEOUT": "60",
    "LLM_ALLOWED_CHATS": "",
    "LLM_REPLY_LANGUAGE": "English",
}
LEGACY_PROMPTS = ("chat.txt", "busy.txt")


@dataclass
class UpdateNotice:
    old_version: str
    new_version: str
    whats_new: list[str] = field(default_factory=list)
    settings_added: list[tuple[str, str]] = field(default_factory=list)  # (key, value)
    settings_changed: list[tuple[str, str, str]] = field(default_factory=list)  # (key, old, new)
    settings_backup: Path | None = None
    prompts_updated: list[tuple[str, Path | None]] = field(default_factory=list)  # (name, backup of their copy)
    retired_prompt: str | None = None  # the active prompt, if it's no longer shipped


def version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version))


def apply_updates(home: Home, first_run: bool) -> UpdateNotice | None:
    """Update the data folder if a newer version runs for the first time. Returns what changed."""
    state_path = home.root / STATE_FILE
    state = _read_state(state_path)
    if state is None and first_run:
        _write_state(state_path)  # a fresh install already has the newest settings and prompts
        return None

    old_version = state.get("version", LEGACY_VERSION) if state else LEGACY_VERSION
    if version_tuple(old_version) >= version_tuple(__version__):
        if state is None:
            _write_state(state_path)
        return None

    notice = UpdateNotice(old_version, __version__, whats_new=changelog_since(old_version))
    old_defaults = state.get("settings_defaults", LEGACY_DEFAULTS) if state else LEGACY_DEFAULTS
    _update_settings(home, old_defaults, notice)
    old_prompt_hashes = state.get("prompts", {}) if state else {}
    _update_prompts(home, old_prompt_hashes, notice)
    _write_state(state_path)
    log.info("Updated the data folder from %s to %s", old_version, __version__)
    return notice


# --- Settings -----------------------------------------------------------------------


def template_defaults() -> dict[str, str]:
    return {key: value or "" for key, value in dotenv_values(SETTINGS_TEMPLATE).items()}


def _template_blocks() -> dict[str, list[str]]:
    """Each setting in the template with the comment lines right above it."""
    blocks: dict[str, list[str]] = {}
    comments: list[str] = []
    for line in SETTINGS_TEMPLATE.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            comments.append(line)
        elif "=" in line:
            blocks[line.split("=", 1)[0].strip()] = [*comments, line]
            comments = []
        else:
            comments = []  # a blank line ends a comment that belongs to a section, not a setting
    return blocks


def _update_settings(home: Home, old_defaults: dict[str, str], notice: UpdateNotice) -> None:
    path = home.settings_file
    if not path.exists():
        return
    current = {key: value or "" for key, value in dotenv_values(path).items()}
    new_defaults = template_defaults()

    missing = [key for key in new_defaults if key not in current]
    changed = [
        (key, current[key], new_value)
        for key, new_value in new_defaults.items()
        if key in current and key in old_defaults
        and current[key] == old_defaults[key] != new_value  # untouched by the tester, and the default moved
    ]
    if not missing and not changed:
        return

    backup = path.with_name(f"{path.name}.before-{__version__}")
    shutil.copyfile(path, backup)
    notice.settings_backup = backup

    for key, old, new in changed:
        set_key(path, key, new, quote_mode="never" if is_plain_value(new) else "always")
        notice.settings_changed.append((key, old, new))

    if missing:
        blocks = _template_blocks()
        text = path.read_text(encoding="utf-8")
        added = [f"\n# --- Added by the {__version__} update ---"]
        for key in missing:
            added += blocks.get(key, [f"{key}={new_defaults[key]}"])
            notice.settings_added.append((key, new_defaults[key]))
        path.write_text(text.rstrip("\n") + "\n" + "\n".join(added) + "\n", encoding="utf-8")


# --- Prompts ------------------------------------------------------------------------


def shipped_prompt_hashes() -> dict[str, str]:
    return {p.name: _hash(p) for p in sorted(DEFAULT_PROMPTS_DIR.glob("*.txt"))}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _update_prompts(home: Home, old_hashes: dict[str, str], notice: UpdateNotice) -> None:
    if home.prompts_dir.resolve() == DEFAULT_PROMPTS_DIR.resolve():
        return  # running from the repository: the prompts are the shipped ones
    for name, new_hash in shipped_prompt_hashes().items():
        if old_hashes.get(name) == new_hash:
            continue  # unchanged in this version: keep the tester's copy, edited or not
        shipped, theirs = DEFAULT_PROMPTS_DIR / name, home.prompts_dir / name
        backup = None
        if theirs.exists():
            their_hash = _hash(theirs)
            if their_hash == new_hash:
                continue
            if their_hash != old_hashes.get(name):  # edited, or we can't tell: keep a copy
                backup = home.prompts_dir / "backup" / f"{theirs.stem}-{notice.old_version}{theirs.suffix}"
                backup.parent.mkdir(exist_ok=True)
                shutil.copyfile(theirs, backup)
        home.prompts_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(shipped, theirs)
        notice.prompts_updated.append((name, backup))

    # Using a prompt that used to ship but no longer does (e.g. busy.txt)? Its copy stays, but say so.
    used_to_ship = set(old_hashes) or set(LEGACY_PROMPTS)
    active = dotenv_values(home.settings_file).get("LLM_SYSTEM_PROMPT_FILE") if home.settings_file.exists() else None
    if active and Path(active).name in used_to_ship - set(shipped_prompt_hashes()):
        notice.retired_prompt = Path(active).name


# --- What's new and the state file ----------------------------------------------------


def changelog_since(old_version: str) -> list[str]:
    """The CHANGELOG.md bullet points of every version newer than `old_version`."""
    try:
        text = CHANGELOG.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    items, include = [], False
    for line in text.splitlines():
        if heading := re.match(r"^##\s+\[?(\d[\w.]*)", line):
            version = heading.group(1)
            include = version_tuple(old_version) < version_tuple(version) <= version_tuple(__version__)
        elif include and line.startswith("- "):
            items.append(line[2:].strip())
    return items


def _read_state(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        log.warning("Could not read %s; treating this as an update from %s", path, LEGACY_VERSION)
        return None
    return data if isinstance(data, dict) else None


def _write_state(path: Path) -> None:
    state = {"version": __version__, "settings_defaults": template_defaults(), "prompts": shipped_prompt_hashes()}
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


# --- Telling the tester -------------------------------------------------------------


def show_notice(notice: UpdateNotice, home: Home) -> None:
    def rel(path: Path) -> str:
        try:
            return escape(str(path.relative_to(home.root)))
        except ValueError:
            return escape(str(path))

    lines = []
    if notice.whats_new:
        lines.append("[bold]What's new[/]")
        lines += [f"  • {escape(item)}" for item in notice.whats_new]
        lines.append("")

    if notice.settings_added or notice.settings_changed:
        lines.append("[bold]Your settings were updated[/]")
        for key, value in notice.settings_added:
            lines.append(f"  + {key} = {escape(value) or '(empty)'}  [dim](new setting)[/]")
        for key, old, new in notice.settings_changed:
            lines.append(f"  ~ {key}: {escape(old) or '(empty)'} → {escape(new) or '(empty)'}  [dim](new default)[/]")
        lines.append("  [dim]Settings you had changed yourself were kept. Change any of these in the Settings menu.[/]")
        if ("HANDOFF_NOTIFY_CHAT", "") in notice.settings_added:
            lines.append(
                "  [yellow]Set HANDOFF_NOTIFY_CHAT[/] to your other Telegram account's @username to get the "
                "handoff alerts there (until then they go to your Saved Messages)."
            )
        if notice.settings_backup:
            lines.append(f"  [dim]Your previous settings file: {rel(notice.settings_backup)}[/]")
        lines.append("")

    if notice.prompts_updated:
        lines.append("[bold]Your prompt was updated[/]")
        for name, backup in notice.prompts_updated:
            saved = f"  [dim](your previous copy: {rel(backup)})[/]" if backup else ""
            lines.append(f"  ✓ {escape(name)} is now the new version{saved}")
        lines.append("")
    if notice.retired_prompt:
        lines.append(
            f"[yellow]You're using {escape(notice.retired_prompt)}, which is no longer included.[/] "
            "Switch to chat in the Prompts menu to get the new script."
        )
        lines.append("")

    title = f"Updated to {notice.new_version} (from {notice.old_version})"
    console.print(Panel("\n".join(lines).rstrip() or "Nothing else changed.", title=title, border_style="green", expand=False))
