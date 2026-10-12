"""Terminal output, logging, and opening files/folders for the user."""

import logging
import os
import shutil
import subprocess
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.prompt import Prompt

console = Console(highlight=False)

_LOG_HANDLER_FLAG = "_userbot_handler"


def prepare_console() -> None:
    """Make Serbian letters and emoji print correctly on Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def setup_logging(level: str, logs_dir: Path) -> None:
    """Log to the terminal (pretty) and to logs/userbot.log (for bug reports)."""
    root = logging.getLogger()
    for handler in [h for h in root.handlers if getattr(h, _LOG_HANDLER_FLAG, False)]:
        root.removeHandler(handler)
        handler.close()

    screen = RichHandler(console=console, show_path=False, rich_tracebacks=True, markup=False)
    screen.setFormatter(logging.Formatter("%(message)s", datefmt="[%X]"))

    logs_dir.mkdir(parents=True, exist_ok=True)
    file = RotatingFileHandler(logs_dir / "userbot.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s"))

    for handler in (screen, file):
        setattr(handler, _LOG_HANDLER_FLAG, True)
        root.addHandler(handler)
    root.setLevel(level if level in logging.getLevelNamesMapping() else "INFO")

    # These libraries are chatty at INFO; keep the output readable.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telethon").setLevel(logging.INFO if level == "DEBUG" else logging.WARNING)


def open_folder(path: Path) -> bool:
    """Show a folder in Explorer / Finder / the file manager."""
    return _launch(path)


def open_in_editor(path: Path) -> bool:
    """Open a text file in a simple editor (Notepad, TextEdit, or the system default)."""
    if sys.platform == "win32":
        return _run(["notepad.exe", str(path)], wait=False)
    if sys.platform == "darwin":
        return _run(["open", "-t", str(path)])
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        if _launch(path):
            return True
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or shutil.which("nano") or shutil.which("vi")
    return bool(editor) and _run([editor, str(path)])


def _launch(path: Path) -> bool:
    if sys.platform == "win32":
        try:
            os.startfile(path)  # type: ignore[attr-defined]
            return True
        except OSError:
            return False
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    return shutil.which(opener) is not None and _run([opener, str(path)])


def _run(cmd: list[str], wait: bool = True) -> bool:
    try:
        if wait:
            return subprocess.run(cmd, check=False).returncode == 0
        subprocess.Popen(cmd)
        return True
    except OSError:
        return False


# --- Telegram login prompts ---------------------------------------------------


def ask_phone() -> str:
    console.print("Telegram needs your [bold]phone number[/] in international format, e.g. [cyan]+381601234567[/].")
    return Prompt.ask("Phone number", console=console).strip()


def ask_code() -> str:
    console.print(
        "Telegram sent a [bold]login code[/] to your Telegram app (a message from \"Telegram\", "
        "not an SMS). Look on your phone or desktop app."
    )
    return Prompt.ask("Login code", console=console).strip()


def ask_password() -> str:
    console.print("Your account has [bold]two-step verification[/]. Enter that password (it isn't shown while typing).")
    return Prompt.ask("2FA password", console=console, password=True)
