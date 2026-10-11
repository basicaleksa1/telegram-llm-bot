"""Things the user can do, shared by the interactive menu and the subcommands."""

import asyncio
import logging
import re
import shutil
import sys
from pathlib import Path

import questionary
from rich.markup import escape
from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn, TimeRemainingColumn, TransferSpeedColumn
from rich.table import Table
from telethon import errors

from . import bot, ollama_setup, playground
from .config import EDITABLE_SETTINGS, Config, ConfigError, load_config, read_settings, write_setting
from .paths import Home
from .ui import ask_code, ask_password, ask_phone, console, open_in_editor, setup_logging


log = logging.getLogger("userbot")


def ask(question):
    """Ask a questionary question; Ctrl+C (None) stops the current flow instead of continuing."""
    answer = question.ask()
    if answer is None:
        raise KeyboardInterrupt
    return answer


def load(home: Home, require_telegram: bool = False) -> Config | None:
    try:
        return load_config(home=home, require_telegram=require_telegram)
    except ConfigError as e:
        console.print(f"[red]Settings problem:[/] {escape(str(e))}")
        console.print(f"[dim]Settings file: {home.settings_file}[/]")
        return None


def friendly_error(e: BaseException) -> str:
    """Explain common Telegram errors in plain words."""
    if isinstance(e, errors.ApiIdInvalidError):
        return "Telegram rejected the API ID / hash. Copy them again from my.telegram.org (setup step 1)."
    if isinstance(e, errors.PhoneNumberInvalidError):
        return "That phone number isn't valid. Use international format with + and the country code, e.g. +381601234567."
    if isinstance(e, (errors.PhoneCodeInvalidError, errors.PhoneCodeExpiredError)):
        return "The login code was wrong or expired. Try again and use the newest code."
    if isinstance(e, errors.PasswordHashInvalidError):
        return "Wrong two-step verification password."
    if isinstance(e, errors.FloodWaitError):
        return f"Telegram asks to wait {e.seconds} seconds before trying again (rate limit)."
    if isinstance(e, ConnectionError | OSError):
        return f"Network problem: {e}. Check your internet connection."
    return f"{type(e).__name__}: {e}"


# --- Telegram -----------------------------------------------------------------


def start_bot(home: Home) -> None:
    config = load(home, require_telegram=True)
    if config is None:
        return
    if config.llm_enabled and config.auto_reply_enabled and not ensure_ollama(home, config, install=False):
        console.print(f"[yellow]Starting anyway: replies will be {config.auto_reply_text!r} until the AI is ready.[/]")
    setup_logging(config.log_level, home.logs_dir)
    console.rule("[bold]Bot running[/] · press [bold]Ctrl+C[/] to stop")
    try:
        asyncio.run(bot.run_bot(config, ask_phone, ask_code, ask_password))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        console.print(f"[red]The bot stopped:[/] {escape(friendly_error(e))}")
        console.print(f"[dim]Details are in {home.logs_dir / 'userbot.log'}[/]")
        log.exception("Bot stopped with an error")
    console.rule("[bold]Bot stopped[/]")


def telegram_login(home: Home) -> bool:
    config = load(home, require_telegram=True)
    if config is None:
        return False
    try:
        me = asyncio.run(bot.current_account(config))
        if me is None:
            console.print(
                "Logging in to Telegram. This happens once; the login is saved on this computer "
                f"([dim]{config.sessions_dir}[/]).\n"
            )
            me = asyncio.run(bot.login(config, ask_phone, ask_code, ask_password))
    except KeyboardInterrupt:
        console.print("\n[yellow]Login cancelled.[/]")
        raise
    except Exception as e:
        console.print(f"[red]Login failed:[/] {escape(friendly_error(e))}")
        log.warning("Login failed", exc_info=True)
        return False
    console.print(f"[green]✓ Logged in as {escape(me.first_name or '')} (@{me.username or '-'}).[/]")
    return True


def telegram_logout(home: Home) -> None:
    config = load(home, require_telegram=True)
    if config is None:
        return
    if not bot.has_saved_login(config):
        console.print("Not logged in on this computer.")
        return
    try:
        asyncio.run(bot.logout(config))
    except Exception as e:
        console.print(f"[red]Couldn't reach Telegram ({escape(friendly_error(e))}).[/]")
        console.print("End the session in Telegram instead: Settings → Devices → tap this session → Terminate.")
        bot.session_file(config).unlink(missing_ok=True)
        console.print("The local login file was deleted.")
        return
    console.print("[green]✓ Logged out. The session is ended on Telegram and deleted from this computer.[/]")


# --- Playground -----------------------------------------------------------------


def run_chat(home: Home, name: str | None = None) -> None:
    config = load(home)
    if config is None:
        return
    if not name:
        saved = read_settings(home).get("PLAYGROUND_NAME", "").strip()
        name = ask(questionary.text("Your first name (the prompt's {name}):", default=saved or "Me"))
        if not name.strip():
            return
        if name != saved:
            write_setting("PLAYGROUND_NAME", name.strip(), home)
    if not ensure_ollama(home, config, install=False):
        return
    try:
        asyncio.run(playground.chat(config, home, name.strip()))
    except KeyboardInterrupt:
        console.print()


# --- Prompts --------------------------------------------------------------------


def list_prompts(home: Home) -> list[Path]:
    return sorted(home.prompts_dir.glob("*.txt"))


def prompt_file(home: Home, name: str) -> Path:
    return home.prompts_dir / (name if name.endswith(".txt") else f"{name}.txt")


def active_prompt(home: Home) -> Path:
    config = load(home)
    return config.llm_system_prompt_file if config else prompt_file(home, "chat")


def use_prompt(home: Home, name: str) -> bool:
    path = prompt_file(home, name)
    if not path.exists():
        console.print(f"[red]No prompt called {escape(name)!r}.[/] Available: {', '.join(p.stem for p in list_prompts(home))}")
        return False
    write_setting("LLM_SYSTEM_PROMPT_FILE", f"prompts/{path.name}", home)
    console.print(f"[green]✓ Using prompt {escape(path.name)}.[/] Restart the bot if it's running.")
    return True


def edit_prompt(home: Home, path: Path) -> None:
    console.print(f"Opening [cyan]{escape(str(path))}[/]")
    console.print(
        "[dim]Save the file and the change applies to the next reply, no restart needed. "
        "{name} is replaced with your Telegram first name.[/]"
    )
    if not open_in_editor(path):
        console.print("[yellow]Couldn't open an editor. Open the file above yourself.[/]")


def new_prompt(home: Home, name: str, copy_from: Path) -> Path | None:
    if not re.fullmatch(r"[\w\- ]+", name):
        console.print("[red]Use only letters, numbers, spaces, - and _ in the name.[/]")
        return None
    path = prompt_file(home, name.strip())
    if path.exists():
        console.print(f"[red]{escape(path.name)} already exists.[/]")
        return None
    shutil.copyfile(copy_from, path)
    console.print(f"[green]✓ Created {escape(path.name)} (a copy of {escape(copy_from.name)}).[/]")
    return path


# --- Settings -------------------------------------------------------------------


def print_settings(home: Home) -> None:
    values = read_settings(home)
    table = Table(box=None, padding=(0, 1))
    table.add_column("Setting", style="bold")
    table.add_column("Value", style="cyan")
    table.add_column("What it does", style="dim")
    for setting in EDITABLE_SETTINGS:
        table.add_row(setting.key, values.get(setting.key, "") or "[dim](default)[/]", setting.help)
    console.print(table)
    console.print(f"\n[dim]File: {home.settings_file}[/]")


def set_setting(home: Home, key: str, value: str) -> bool:
    key = key.strip().upper()
    if key in ("API_ID", "API_HASH") and not value.strip():
        console.print("[red]API_ID / API_HASH can't be empty.[/]")
        return False
    try:
        write_setting(key, value.strip(), home)
    except ConfigError as e:
        console.print(f"[red]Not saved:[/] {escape(str(e))}")
        return False
    console.print(f"[green]✓ {key} = {escape(value.strip()) or '(default)'}[/]. Restart the bot if it's running.")
    return True


# --- Ollama and models --------------------------------------------------------------


def _is_local(host: str) -> bool:
    return any(h in host for h in ("localhost", "127.0.0.1", "[::1]"))


def _download_progress() -> Progress:
    return Progress(
        TextColumn("[bold]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    )


def ensure_ollama(home: Home, config: Config, install: bool = True) -> bool:
    """Make sure Ollama is running: start it if installed, otherwise offer to install it."""
    host = config.llm_host
    if asyncio.run(ollama_setup.is_running(host)):
        if install:
            console.print("[green]✓ Ollama is running.[/]")
        return True
    if not _is_local(host):
        console.print(f"[red]Ollama isn't reachable at {escape(host)}.[/] Start it there, or reset LLM_HOST.")
        return False

    binary = ollama_setup.find_ollama()
    if binary is None and not install:
        console.print("[yellow]Ollama isn't installed.[/] Run the setup again (menu) to install it.")
        return False
    if binary is None:
        console.print(
            "Ollama isn't installed. It's a free program (ollama.com) that runs the AI model "
            "on this computer, so messages never leave it."
        )
        if not _install_ollama():
            return False
        binary = ollama_setup.find_ollama()
        if asyncio.run(ollama_setup.wait_until_running(host, 60)):
            console.print("[green]✓ Ollama is installed and running.[/]")
            return True
        if binary is None:
            console.print("[yellow]Ollama still isn't found. Finish the installation, then run the setup again.[/]")
            return False

    console.print("Ollama is installed but not running. Starting it…")
    ollama_setup.start_ollama(binary, home.logs_dir)
    with console.status("Waiting for Ollama to start…"):
        running = asyncio.run(ollama_setup.wait_until_running(host))
    if running:
        console.print("[green]✓ Ollama is running.[/]")
    else:
        console.print("[red]Ollama didn't start.[/] Open the Ollama app yourself, then try again.")
    return running


def _install_ollama() -> bool:
    if ollama_setup.can_install_automatically():
        size = "about 1.6 GB" if sys.platform == "win32" else "about 200 MB"
        if not ask(questionary.confirm(f"Download and install Ollama now? ({size})", default=True)):
            console.print(f"Install it later from {ollama_setup.DOWNLOAD_PAGE}, then run the setup again.")
            return False
        console.print("[dim]On Windows the Ollama installer opens; click through it. On macOS, Ollama may show a welcome window.[/]")
        try:
            with _download_progress() as progress:
                task = progress.add_task("Downloading Ollama", total=None)
                asyncio.run(ollama_setup.install_ollama(lambda done, total: progress.update(task, completed=done, total=total or None)))
        except Exception as e:
            console.print(f"[red]Installing Ollama failed:[/] {escape(str(e))}")
            log.warning("Installing Ollama failed", exc_info=True)
            console.print(f"Install it yourself from {ollama_setup.DOWNLOAD_PAGE}, then run the setup again.")
            return False
        return True

    console.print(f"On Linux, Ollama is installed with its official command:\n\n  [cyan]{ollama_setup.LINUX_INSTALL_COMMAND}[/]\n")
    if not ask(questionary.confirm("Run it now? It asks for your computer password (sudo).", default=True)):
        console.print("Run the command above in a terminal, then run the setup again.")
        return False
    if not ollama_setup.run_linux_installer():
        console.print("[red]The install command failed.[/] Run it yourself in a terminal (curl must be installed).")
        return False
    return True


def installed_models(config: Config) -> list[str]:
    try:
        return asyncio.run(ollama_setup.installed_models(config.llm_host))
    except Exception:
        return []


def choose_model(config: Config) -> str | None:
    hw = ollama_setup.detect_hardware()
    recommended = ollama_setup.recommend_model(hw)
    have = installed_models(config)
    console.print(f"This computer: [bold]{hw.describe()}[/]. Recommended model: [bold cyan]{recommended}[/].")

    choices = []
    for option in sorted(ollama_setup.MODELS, key=lambda m: m.name != recommended):
        tags = []
        if option.name == recommended:
            tags.append("recommended")
        if option.name in have:
            tags.append("downloaded")
        label = f"{option.name:<14} ~{option.download_gb:.0f} GB  {option.description}"
        if tags:
            label += f"  [{', '.join(tags)}]"
        choices.append(questionary.Choice(label, value=option.name))
    for name in have:
        if all(name != m.name for m in ollama_setup.MODELS):
            choices.append(questionary.Choice(f"{name:<14} (already downloaded)", value=name))
    choices.append(questionary.Choice("Type another model name (from ollama.com/library)", value="__other__"))

    model = ask(questionary.select("Which model should write the replies?", choices=choices))
    if model == "__other__":
        model = ask(questionary.text("Model name, e.g. gemma4:12b:"))
    return model.strip() or None


def pull_model(config: Config, model: str) -> bool:
    if asyncio.run(ollama_setup.has_model(config.llm_host, model)):
        console.print(f"[green]✓ {escape(model)} is already downloaded.[/]")
        return True

    option = next((m for m in ollama_setup.MODELS if m.name == model), None)
    free = ollama_setup.free_disk_gb()
    if option and free < option.download_gb + 1:
        console.print(f"[yellow]Only {free:.1f} GB free disk space; {model} needs about {option.download_gb:.0f} GB.[/]")
        if not ask(questionary.confirm("Try anyway?", default=False)):
            return False

    console.print(f"Downloading [bold]{escape(model)}[/]. This happens once; you can stop with Ctrl+C and continue later.")

    async def pull() -> None:
        with _download_progress() as progress:
            task = progress.add_task(model, total=None)
            async for step in ollama_setup.pull_model(config.llm_host, model):
                progress.update(task, completed=step.completed, total=step.total or None)

    try:
        asyncio.run(pull())
    except KeyboardInterrupt:
        console.print("\n[yellow]Download paused. Run it again to continue where it stopped.[/]")
        raise
    except Exception as e:
        console.print(f"[red]Download failed:[/] {escape(str(e))}")
        log.warning("Downloading %s failed", model, exc_info=True)
        if "not found" in str(e).lower():
            console.print("[dim]Check the name on https://ollama.com/library[/]")
        return False
    console.print(f"[green]✓ {escape(model)} downloaded.[/]")
    return True


def setup_model(home: Home, model: str | None = None) -> bool:
    """Ollama running + model chosen, downloaded and saved in the settings."""
    config = load(home)
    if config is None or not ensure_ollama(home, config):
        return False
    model = model or choose_model(config)
    if not model or not pull_model(config, model):
        return False
    write_setting("LLM_MODEL", model, home)
    console.print(f"[green]✓ The bot now uses {escape(model)}.[/]")
    return True
