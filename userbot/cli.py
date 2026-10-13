"""Command-line interface. Without a command it opens the interactive menu.

    userbot                      menu (what the Start Userbot launcher opens)
    userbot setup | start | chat | doctor | login | logout | folder
    userbot prompt list | use NAME | edit [NAME] | show [NAME] | new NAME | reset
    userbot settings show | set KEY VALUE | edit
    userbot model list | recommend | use MODEL | pull [MODEL]

From source: `python -m userbot ...`. With the tester bundle, the launcher takes
the same commands: `./start.sh ...`, `"./Start Userbot.command" ...` or
`"Start Userbot.bat" ...`.
"""

import asyncio
import logging
from pathlib import Path

import questionary
import typer
from rich.markup import escape

from . import __version__, actions, doctor, ollama_setup
from .config import read_settings
from .menu import run_menu
from .paths import default_prompt_names, ensure_home, get_home, resolve_home, restore_default_prompts, set_home
from .setup_wizard import run_setup
from .ui import console, open_folder, open_in_editor, prepare_console, setup_logging

app = typer.Typer(add_completion=False, rich_markup_mode="rich", help="Telegram userbot that auto-replies with a local AI.")
prompt_app = typer.Typer(help="List, switch, edit and create prompts.", no_args_is_help=True)
settings_app = typer.Typer(help="Show and change settings.", no_args_is_help=True)
model_app = typer.Typer(help="Choose and download the AI model.", no_args_is_help=True)
app.add_typer(prompt_app, name="prompt")
app.add_typer(settings_app, name="settings")
app.add_typer(model_app, name="model")


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    home: Path | None = typer.Option(None, "--home", help="Use this data folder instead of the default one."),
    version: bool = typer.Option(False, "--version", help="Show the version and exit."),
) -> None:
    if version:
        console.print(__version__)
        raise typer.Exit()
    resolved = resolve_home(home)
    set_home(resolved)
    ensure_home(resolved)
    # Log to logs/userbot.log from the start, so setup problems end up there too.
    setup_logging(read_settings(resolved).get("LOG_LEVEL", "").strip().upper() or "INFO", resolved.logs_dir)
    if ctx.invoked_subcommand is None:
        run_menu(resolved)


@app.command()
def setup() -> None:
    """Step-by-step setup: Telegram API ID/hash, Ollama + model, prompt, login."""
    run_setup(get_home())


@app.command()
def start() -> None:
    """Start the bot (Ctrl+C stops it)."""
    actions.start_bot(get_home())


@app.command()
def chat(name: str | None = typer.Option(None, "--name", help="Your first name, as the prompt's {name}.")) -> None:
    """Chat with the AI in the terminal, without Telegram (to test prompts)."""
    actions.run_chat(get_home(), name)


@app.command("doctor")
def doctor_command(offline: bool = typer.Option(False, "--offline", help="Don't contact Telegram.")) -> None:
    """Check everything the bot needs and show how to fix problems."""
    checks = asyncio.run(doctor.run_checks(get_home(), online=not offline))
    doctor.print_checks(checks)
    if any(c.status == doctor.FAIL for c in checks):
        raise typer.Exit(1)


@app.command()
def login() -> None:
    """Log in to Telegram (only needed once)."""
    if not actions.telegram_login(get_home()):
        raise typer.Exit(1)


@app.command()
def logout(yes: bool = typer.Option(False, "--yes", "-y", help="Don't ask for confirmation.")) -> None:
    """End the Telegram session and delete the saved login."""
    if yes or questionary.confirm("Log out of Telegram on this computer?", default=False).ask():
        actions.telegram_logout(get_home())


@app.command()
def folder() -> None:
    """Show (and open) the data folder with settings, prompts and logs."""
    home = get_home()
    console.print(str(home.root))
    open_folder(home.root)


# --- prompt ---------------------------------------------------------------------


@prompt_app.command("list")
def prompt_list() -> None:
    """List prompt files (* = active)."""
    home = get_home()
    active = actions.active_prompt(home)
    for path in actions.list_prompts(home):
        console.print(f"{'*' if path == active else ' '} {path.stem}")
    console.print(f"[dim]{home.prompts_dir}[/]")


@prompt_app.command("use")
def prompt_use(name: str) -> None:
    """Make NAME the active prompt (e.g. chat, or one you created)."""
    if not actions.use_prompt(get_home(), name):
        raise typer.Exit(1)


@prompt_app.command("edit")
def prompt_edit(name: str | None = typer.Argument(None, help="Prompt to edit (default: the active one).")) -> None:
    """Open a prompt in a text editor. Changes apply to the next reply."""
    home = get_home()
    path = actions.prompt_file(home, name) if name else actions.active_prompt(home)
    if not path.exists():
        console.print(f"[red]{escape(str(path))} doesn't exist.[/]")
        raise typer.Exit(1)
    actions.edit_prompt(path)


@prompt_app.command("show")
def prompt_show(name: str | None = typer.Argument(None, help="Prompt to show (default: the active one).")) -> None:
    """Print a prompt."""
    home = get_home()
    path = actions.prompt_file(home, name) if name else actions.active_prompt(home)
    console.print(f"[dim]{path}[/]\n")
    console.print(escape(path.read_text(encoding="utf-8")))


@prompt_app.command("new")
def prompt_new(name: str, use: bool = typer.Option(True, help="Make it the active prompt.")) -> None:
    """Create a new prompt as a copy of the active one, and open it."""
    home = get_home()
    path = actions.new_prompt(home, name, actions.active_prompt(home))
    if path is None:
        raise typer.Exit(1)
    if use:
        actions.use_prompt(home, path.stem)
    actions.edit_prompt(path)


@prompt_app.command("reset")
def prompt_reset(yes: bool = typer.Option(False, "--yes", "-y", help="Don't ask for confirmation.")) -> None:
    """Restore the original prompts (other prompt files are kept)."""
    names = " and ".join(default_prompt_names())
    if yes or questionary.confirm(f"Overwrite {names} with the original version?", default=False).ask():
        restored = restore_default_prompts(get_home())
        console.print(f"Restored: {', '.join(restored)}" if restored else "Nothing to restore here.")


# --- settings -------------------------------------------------------------------


@settings_app.command("show")
def settings_show() -> None:
    """Show all settings with their current values."""
    actions.print_settings(get_home())


@settings_app.command("set")
def settings_set(key: str, value: str = typer.Argument("", help="New value (empty = default).")) -> None:
    """Change one setting, e.g. `settings set AUTO_REPLY_DELAY 5`."""
    if not actions.set_setting(get_home(), key, value):
        raise typer.Exit(1)


@settings_app.command("edit")
def settings_edit() -> None:
    """Open the settings file in a text editor."""
    path = get_home().settings_file
    console.print(str(path))
    open_in_editor(path)


# --- model ----------------------------------------------------------------------


@model_app.command("list")
def model_list() -> None:
    """List downloaded models."""
    config = actions.load(get_home())
    if config is None:
        raise typer.Exit(1)
    models = actions.installed_models(config)
    for name in models:
        console.print(f"{'*' if name == config.llm_model else ' '} {name}")
    if not models:
        console.print("[yellow]No models found (or Ollama isn't running).[/]")


@model_app.command("recommend")
def model_recommend() -> None:
    """Show which model suits this computer."""
    hw = ollama_setup.detect_hardware()
    console.print(f"{hw.describe()} → [bold]{ollama_setup.recommend_model(hw)}[/]")


@model_app.command("use")
def model_use(model: str) -> None:
    """Switch to MODEL (downloads it if needed)."""
    if not actions.setup_model(get_home(), model):
        raise typer.Exit(1)


@model_app.command("pull")
def model_pull(model: str | None = typer.Argument(None, help="Model to download (default: the configured one).")) -> None:
    """Download a model without switching to it."""
    home = get_home()
    config = actions.load(home)
    if config is None or not actions.ensure_ollama(home, config):
        raise typer.Exit(1)
    if not actions.pull_model(config, model or config.llm_model):
        raise typer.Exit(1)


def main(argv: list[str] | None = None) -> None:
    prepare_console()
    try:
        app(args=argv, prog_name="userbot")
    except Exception:
        logging.getLogger("userbot").exception("Unexpected error")
        raise
