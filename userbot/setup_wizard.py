"""First-run setup: Telegram API credentials, Ollama + model, prompt, Telegram login.

Every step can be skipped and the whole setup re-run at any time.
"""

import re
import webbrowser

import questionary
from rich.markup import escape
from rich.panel import Panel

from . import actions
from .config import write_setting
from .paths import Home
from .ui import console

TELEGRAM_APPS_URL = "https://my.telegram.org"


def run_setup(home: Home) -> None:
    console.print(
        Panel(
            "This sets up four things:\n"
            "  1. Your Telegram API ID and hash (from my.telegram.org)\n"
            "  2. The local AI (Ollama and a model)\n"
            "  3. Which prompt the AI follows\n"
            "  4. Logging in to your Telegram account\n\n"
            f"[dim]Everything is saved in {escape(str(home.root))}\nPress Ctrl+C to stop; you can run the setup again later.[/]",
            title="Setup",
            expand=False,
        )
    )
    steps = [
        ("Telegram API ID and hash", _telegram_credentials),
        ("The local AI", _ai),
        ("Prompt", _prompt),
        ("Telegram login", _login),
    ]
    for number, (title, step) in enumerate(steps, start=1):
        console.rule(f"[bold]Step {number} of {len(steps)}: {title}")
        try:
            step(home)
        except KeyboardInterrupt:
            console.print("\n[yellow]Setup stopped. Run it again from the menu any time.[/]")
            return
        console.print()
    console.rule("[bold green]Setup finished")
    console.print("Choose [bold]Start the bot[/] in the menu. Try the AI first with [bold]Test the AI here in the terminal[/].")


def _ask(question):
    """questionary returns None on Ctrl+C; turn that into KeyboardInterrupt to stop the setup."""
    answer = question.ask()
    if answer is None:
        raise KeyboardInterrupt
    return answer


def _telegram_credentials(home: Home) -> None:
    config = actions.load(home)
    if config and config.has_telegram_credentials:
        console.print(f"Already set (API_ID {config.api_id}).")
        if not _ask(questionary.confirm("Change them?", default=False)):
            return

    console.print(
        "Telegram requires every program that logs in to an account to have its own API ID. "
        "Getting one is free and takes 2 minutes:\n\n"
        f"  1. Open [cyan]{TELEGRAM_APPS_URL}[/] and log in with your phone number.\n"
        "     The code arrives [bold]in the Telegram app[/], not by SMS.\n"
        "  2. Click [bold]API development tools[/].\n"
        "  3. Fill in [bold]App title[/] (anything, e.g. My Userbot) and [bold]Short name[/]\n"
        "     (5–32 letters/numbers, e.g. myuserbot2026). Platform: Desktop. Leave the rest empty.\n"
        "  4. Click [bold]Create application[/] and copy [bold]App api_id[/] and [bold]App api_hash[/].\n\n"
        "[dim]If the form only says ERROR: turn off VPN/ad blockers, try another browser, or a different short name.\n"
        "Keep these values private, like a password.[/]\n"
    )
    if _ask(questionary.confirm("Open my.telegram.org in your browser now?", default=True)):
        webbrowser.open(TELEGRAM_APPS_URL)

    api_id = _ask(
        questionary.text(
            "App api_id (a number):",
            validate=lambda v: bool(re.fullmatch(r"\s*\d{3,12}\s*", v)) or "It's a number, e.g. 1234567",
        )
    ).strip()
    api_hash = _ask(
        questionary.text(
            "App api_hash (32 characters):",
            validate=lambda v: bool(re.fullmatch(r"\s*[0-9a-fA-F]{32}\s*", v)) or "It's 32 characters of 0-9 and a-f",
        )
    ).strip().lower()
    write_setting("API_ID", api_id, home)
    write_setting("API_HASH", api_hash, home)
    console.print("[green]✓ Saved.[/]")


def _ai(home: Home) -> None:
    console.print(
        "Replies are written by an AI model that runs on this computer through [bold]Ollama[/]. "
        "Messages never leave your computer. Without it, the bot sends a fixed text instead."
    )
    if not _ask(questionary.confirm("Set up the local AI now?", default=True)):
        console.print("[dim]Skipped. Choose this step later via 'Run setup again' or the Model menu.[/]")
        return
    write_setting("LLM_ENABLED", "true", home)
    if not actions.setup_model(home):
        console.print(
            "[yellow]The AI isn't ready yet.[/] Until it is, the bot replies with the fixed text. "
            "Run the setup again when you're ready."
        )


def _prompt(home: Home) -> None:
    prompts = actions.list_prompts(home)
    current = actions.active_prompt(home)
    console.print(
        "The prompt is a plain text file with the AI's instructions. It's sent to the model as-is "
        "({name} becomes your Telegram first name). Edit it any time; changes apply to the next reply.\n"
        "[dim]chat = chats as you · busy = says you're not around and will reply later[/]"
    )
    choice = _ask(
        questionary.select(
            "Which prompt should the AI use?",
            choices=[questionary.Choice(p.stem, value=p) for p in prompts],
            default=next((p for p in prompts if p == current), None),
        )
    )
    actions.use_prompt(home, choice.stem)
    if _ask(questionary.confirm("Open it in an editor now to read or change it?", default=False)):
        actions.edit_prompt(home, choice)


def _login(home: Home) -> None:
    config = actions.load(home)
    if not config or not config.has_telegram_credentials:
        console.print("[yellow]Skipped: the API ID and hash from step 1 are needed first.[/]")
        return
    console.print(
        "Log in with the Telegram account the bot should answer for. You'll get a code in the "
        "Telegram app, and see a 'new login' notification: that's this program."
    )
    if not _ask(questionary.confirm("Log in now?", default=True)):
        console.print("[dim]Skipped. The bot asks when you start it.[/]")
        return
    actions.telegram_login(home)
