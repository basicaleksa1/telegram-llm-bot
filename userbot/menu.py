"""The interactive menu shown when the userbot is started without a command."""

import asyncio

import questionary
from rich.markup import escape
from rich.table import Table

from . import __version__, actions, bot, doctor, ollama_setup
from .config import EDITABLE_SETTINGS, read_settings
from .paths import Home, default_prompt_names, restore_default_prompts
from .setup_wizard import run_setup
from .ui import console, open_folder, open_in_editor


def run_menu(home: Home) -> None:
    config = actions.load(home)
    if config is not None and not config.has_telegram_credentials:
        console.print(f"[bold]Welcome to Telegram Userbot {__version__}![/] Setup hasn't been done yet.")
        if questionary.confirm("Start the setup now?", default=True).ask():
            run_setup(home)

    while True:
        console.print()
        _print_status(home)
        choice = questionary.select(
            "What do you want to do?",
            choices=[
                questionary.Choice("Start the bot", "start"),
                questionary.Choice("Test the AI here in the terminal (playground)", "chat"),
                questionary.Choice("Prompts: edit / switch / create", "prompts"),
                questionary.Choice("Settings", "settings"),
                questionary.Choice("AI model", "model"),
                questionary.Choice("Check everything (doctor)", "doctor"),
                questionary.Choice("Run setup again", "setup"),
                questionary.Choice("Open data folder", "folder"),
                questionary.Choice("Log out of Telegram", "logout"),
                questionary.Choice("Quit", "quit"),
            ],
        ).ask()
        if choice in (None, "quit"):
            return
        try:
            _ACTIONS[choice](home)
        except KeyboardInterrupt:
            console.print()


def _print_status(home: Home) -> None:
    config = actions.load(home)
    table = Table.grid(padding=(0, 2))
    table.add_row("[bold]Telegram Userbot[/]", f"[dim]{__version__}[/]")
    table.add_row("Data folder", f"[dim]{escape(str(home.root))}[/]")
    if config is None:
        console.print(table)
        return

    if not config.has_telegram_credentials:
        telegram = "[red]API ID / hash missing[/] → Run setup again"
    elif bot.has_saved_login(config):
        telegram = "[green]login saved[/]"
    else:
        telegram = "[yellow]not logged in yet[/] (the bot asks when it starts)"
    table.add_row("Telegram", telegram)

    if not config.llm_enabled:
        ai = f"[yellow]off[/] (always replies {escape(config.auto_reply_text)!r})"
    else:
        running, has_model = asyncio.run(_ai_status(config.llm_host, config.llm_model))
        if not running:
            ai = f"{escape(config.llm_model)} [red]· Ollama not running[/]"
        elif not has_model:
            ai = f"{escape(config.llm_model)} [red]· not downloaded[/] → AI model menu"
        else:
            ai = f"{escape(config.llm_model)} [green]✓[/]"
    table.add_row("AI model", ai)

    prompt = config.llm_system_prompt_file
    table.add_row("Prompt", escape(prompt.name) + ("" if prompt.exists() else " [red](missing)[/]"))

    if not config.auto_reply_delay_enabled:
        delay = "[yellow]off[/] (replies within seconds; turn on before real use)"
    elif config.auto_reply_delay_max > config.auto_reply_delay:
        delay = f"{_minutes(config.auto_reply_delay)}–{_minutes(config.auto_reply_delay_max)}, random"
    else:
        delay = _minutes(config.auto_reply_delay)
    table.add_row("Reply delay", delay)
    table.add_row("Handoff alerts", escape(config.handoff_notify_chat or "your Saved Messages"))
    console.print(table)


def _minutes(seconds: float) -> str:
    return f"{seconds / 60:g} min" if seconds >= 60 else f"{seconds:g} s"


async def _ai_status(host: str, model: str) -> tuple[bool, bool]:
    if not await ollama_setup.is_running(host, timeout=1.5):
        return False, False
    return True, await ollama_setup.has_model(host, model)


# --- Sub-menus ------------------------------------------------------------------


def _prompts_menu(home: Home) -> None:
    while True:
        active = actions.active_prompt(home)
        choice = questionary.select(
            f"Prompts (active: {active.name})",
            choices=[
                questionary.Choice(f"Edit the active prompt ({active.name})", "edit"),
                questionary.Choice("Switch to another prompt", "use"),
                questionary.Choice("Create a new prompt (copy of the active one)", "new"),
                questionary.Choice("Open the prompts folder", "folder"),
                questionary.Choice("Restore the original prompts", "reset"),
                questionary.Choice("Back", "back"),
            ],
        ).ask()
        if choice in (None, "back"):
            return
        if choice == "edit":
            actions.edit_prompt(active)
        elif choice == "use":
            prompts = actions.list_prompts(home)
            picked = questionary.select("Use which prompt?", choices=[p.stem for p in prompts]).ask()
            if picked:
                actions.use_prompt(home, picked)
        elif choice == "new":
            name = questionary.text("Name for the new prompt (e.g. work):").ask()
            if name and (path := actions.new_prompt(home, name, active)):
                if questionary.confirm(f"Use {path.stem} now?", default=True).ask():
                    actions.use_prompt(home, path.stem)
                actions.edit_prompt(path)
        elif choice == "folder":
            if not open_folder(home.prompts_dir):
                console.print(str(home.prompts_dir))
        elif choice == "reset":
            if questionary.confirm(
                f"Overwrite {' and '.join(default_prompt_names())} with the original version? Your edits to it "
                "are lost (other prompt files are kept).",
                default=False,
            ).ask():
                restored = restore_default_prompts(home)
                console.print(f"[green]✓ Restored {', '.join(restored)}.[/]" if restored else "Nothing to restore here.")


def _settings_menu(home: Home) -> None:
    while True:
        values = read_settings(home)
        choices = [
            questionary.Choice(f"{s.key:<24} {values.get(s.key, '') or '(default)'}", s.key) for s in EDITABLE_SETTINGS
        ]
        choices += [
            questionary.Choice("Open the settings file in an editor", "__edit__"),
            questionary.Choice("Back", "__back__"),
        ]
        key = questionary.select("Which setting?", choices=choices).ask()
        if key in (None, "__back__"):
            return
        if key == "__edit__":
            _open_settings_file(home)
            continue
        setting = next(s for s in EDITABLE_SETTINGS if s.key == key)
        console.print(f"[bold]{setting.key}[/]: {escape(setting.help)}")
        if setting.kind == "bool":
            config = actions.load(home)
            current = bool(getattr(config, key.lower(), True)) if config else True
            value = questionary.select("New value:", choices=["true", "false"], default="true" if current else "false").ask()
        else:
            value = questionary.text("New value (empty = default):", default=values.get(key, "")).ask()
        if value is not None:
            actions.set_setting(home, key, value)


def _open_settings_file(home: Home) -> None:
    console.print(f"Opening [cyan]{escape(str(home.settings_file))}[/]. Restart the bot after saving changes.")
    if not open_in_editor(home.settings_file):
        console.print("[yellow]Couldn't open an editor. Open the file above yourself.[/]")


def _model_menu(home: Home) -> None:
    config = actions.load(home)
    if config is None:
        return
    choice = questionary.select(
        f"AI model (now: {config.llm_model})",
        choices=[
            questionary.Choice("Choose / download a model", "choose"),
            questionary.Choice("Show downloaded models", "list"),
            questionary.Choice("Back", "back"),
        ],
    ).ask()
    if choice == "choose":
        actions.setup_model(home)
    elif choice == "list":
        models = actions.installed_models(config)
        console.print("\n".join(models) if models else "[yellow]No models (or Ollama isn't running).[/]")


def _doctor(home: Home) -> None:
    doctor.print_checks(asyncio.run(doctor.run_checks(home)))


def _logout(home: Home) -> None:
    if questionary.confirm(
        "Log out? This ends the session on Telegram; you'll need a new login code next time.", default=False
    ).ask():
        actions.telegram_logout(home)


def _folder(home: Home) -> None:
    console.print(f"Data folder: {escape(str(home.root))}")
    open_folder(home.root)


_ACTIONS = {
    "start": actions.start_bot,
    "chat": actions.run_chat,
    "prompts": _prompts_menu,
    "settings": _settings_menu,
    "model": _model_menu,
    "doctor": _doctor,
    "setup": run_setup,
    "folder": _folder,
    "logout": _logout,
}
