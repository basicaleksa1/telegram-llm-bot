"""`userbot doctor`: checks everything the bot needs and says how to fix problems."""

import os
from dataclasses import dataclass

from rich.markup import escape
from rich.table import Table

from . import bot, ollama_setup
from .autoreply import QUICK_REPLY_DELAY
from .config import Config, ConfigError, load_config
from .handoff import HANDOFF_MARKER, PausedChats, has_handoff_marker
from .paths import Home
from .ui import console

OK, WARN, FAIL = "ok", "warn", "fail"
ICONS = {OK: "[green]✓[/]", WARN: "[yellow]![/]", FAIL: "[red]✗[/]"}


@dataclass
class Check:
    name: str
    status: str
    detail: str
    fix: str = ""


async def run_checks(home: Home, online: bool = True) -> list[Check]:
    checks: list[Check] = []
    add = checks.append

    writable = os.access(home.root, os.W_OK)
    add(Check("Data folder", OK if writable else FAIL, str(home.root), "" if writable else "The folder isn't writable. Check its permissions."))

    try:
        config = load_config(home=home, require_telegram=False)
    except ConfigError as e:
        add(Check("Settings", FAIL, str(e), f"Fix it in the Settings menu or in {home.settings_file}."))
        return checks
    add(Check("Settings", OK, str(home.settings_file)))

    if config.has_telegram_credentials:
        add(Check("Telegram API ID / hash", OK, f"API_ID {config.api_id}"))
    else:
        add(Check("Telegram API ID / hash", FAIL, "not set", "Menu: Run setup again (tester guide, step 1)."))

    prompt = config.llm_system_prompt_file
    if not prompt.exists():
        add(Check("Prompt", FAIL, f"{prompt} doesn't exist", "Menu: Prompts → Switch to another prompt."))
    elif not prompt.read_text(encoding="utf-8").strip():
        add(Check("Prompt", WARN, f"{prompt.name} is empty", "Write instructions into it, or the built-in default is used."))
    else:
        add(Check("Prompt", OK, prompt.name))
        if not has_handoff_marker(prompt.read_text(encoding="utf-8")):
            add(Check(
                "Handoff rule", WARN, f"{prompt.name} never asks for {HANDOFF_MARKER}, so the AI never hands a chat to you",
                "Menu: Prompts → Restore the original prompts, or add a <handoff> section.",
            ))

    if not config.auto_reply_delay_enabled:
        add(Check(
            "Reply delay", WARN, f"off: replies within {QUICK_REPLY_DELAY:.0f} s (AUTO_REPLY_DELAY_ENABLED=false)",
            "Fine for testing. Set it back to true before real use.",
        ))
    elif config.auto_reply_delay_max > config.auto_reply_delay:
        add(Check("Reply delay", OK, f"random {config.auto_reply_delay:.0f}-{config.auto_reply_delay_max:.0f} s"))
    else:
        add(Check("Reply delay", OK, f"{config.auto_reply_delay:.0f} s"))

    paused = len(PausedChats(config.paused_chats_file).items())
    alerts_to = config.handoff_notify_chat or "your Saved Messages"
    add(Check("Handoff", OK, f"alerts go to {alerts_to}" + (f"; {paused} chat(s) paused" if paused else "")))

    if not config.llm_enabled:
        add(Check("AI", WARN, "turned off (LLM_ENABLED=false)", f"Replies are always {config.auto_reply_text!r}."))
    elif not await ollama_setup.is_running(config.llm_host):
        installed = ollama_setup.find_ollama()
        fix = "Start the Ollama app, or run the setup again." if installed else "Install Ollama: run the setup again, or see https://ollama.com/download"
        add(Check("Ollama", FAIL, f"not reachable at {config.llm_host}" + (" (installed, not running)" if installed else " (not installed)"), fix))
    else:
        add(Check("Ollama", OK, f"running at {config.llm_host}"))
        if await ollama_setup.has_model(config.llm_host, config.llm_model):
            add(Check("AI model", OK, config.llm_model))
        else:
            add(Check("AI model", FAIL, f"{config.llm_model} isn't downloaded", "Menu: AI model → Choose / download a model."))

    hw = ollama_setup.detect_hardware()
    option = next((m for m in ollama_setup.MODELS if m.name == config.llm_model), None)
    if option and option.download_gb * 1.5 > hw.ram_gb:
        add(Check("Memory", WARN, f"{hw.describe()}; {config.llm_model} may be slow", f"Try {ollama_setup.recommend_model(hw)} (menu: AI model)."))
    else:
        add(Check("Memory", OK, hw.describe()))

    if config.has_telegram_credentials:
        add(await _login_check(config, online))
    return checks


async def _login_check(config: Config, online: bool) -> Check:
    if not bot.has_saved_login(config):
        return Check("Telegram login", WARN, "not logged in yet", "Run the setup, or just start the bot: it asks for your phone and code.")
    if not online:
        return Check("Telegram login", OK, "saved (not verified, --offline)")
    try:
        me = await bot.current_account(config)
    except Exception as e:  # network problems, revoked keys, ...
        return Check("Telegram login", WARN, f"couldn't check: {e}", "Check your internet connection.")
    if me is None:
        return Check("Telegram login", FAIL, "the saved login is no longer valid", "Log out and start the bot again to log in.")
    return Check("Telegram login", OK, f"{me.first_name} (@{me.username or '-'})")


def print_checks(checks: list[Check]) -> None:
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(no_wrap=True)
    table.add_column(no_wrap=True)
    table.add_column(overflow="fold")
    for check in checks:
        detail = escape(check.detail)
        if check.fix:
            detail += f"\n[dim]→ {escape(check.fix)}[/]"
        table.add_row(ICONS[check.status], f"[bold]{check.name}[/]", detail)
    console.print(table)
    failed = sum(c.status == FAIL for c in checks)
    console.print("\n[green]Everything looks good.[/]" if not failed else f"\n[red]{failed} problem(s) to fix.[/]")
