"""Chat with the auto-reply AI in your terminal, without Telegram.

    userbot chat --name Aleksa          (or: python -m userbot chat)

You play the person messaging you; the bot answers using the same prompt,
model and settings as the real userbot, including typos and handoffs. Edits to
the prompt file apply to the next message.
Commands: /photo path [caption], /prompt [name], /resume, /reset, /quit.
"""

import asyncio
import random
import shlex
from pathlib import Path

from rich.markup import escape
from rich.panel import Panel

from .autoreply import random_delay
from .config import Config
from .handoff import format_notification, resume_hint, split_handoff
from .humanize import humanize
from .llm import LLM, LLMError
from .paths import Home
from .ui import console

HELP = (
    "Type a message and press Enter. [bold]/photo[/] [dim]path \\[caption][/] sends a picture, "
    "[bold]/prompt[/] [dim]name[/] switches prompts, [bold]/resume[/] continues after a handoff, "
    "[bold]/reset[/] starts over, [bold]/quit[/] exits."
)
PLAYGROUND_CHAT_ID = 123456789


async def chat(config: Config, home: Home, name: str) -> None:
    llm = LLM(config)
    problem = await llm.check()
    if problem:
        console.print(f"[red]The AI isn't ready:[/] {escape(problem)}")
        return

    console.print(
        f"Chatting with [bold]{escape(name)}[/]'s bot | model [cyan]{llm.model}[/] | "
        f"prompt [cyan]{escape(llm.prompt.path.name)}[/]"
    )
    if config.llm_vision and not llm.vision:
        console.print("[yellow]This model can't see images: /photo only tells it a photo was sent.[/]")
    console.print(HELP + "\n")

    rng = random.Random()
    history: list[dict] = []
    handed_off = False
    while True:
        try:
            text = (await asyncio.to_thread(console.input, "[bold green]you:[/] ")).strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            return
        if not text:
            continue
        if text == "/quit":
            return
        if text == "/reset":
            history.clear()
            handed_off = False
            console.print("[dim](conversation cleared)[/]\n")
            continue
        if text == "/resume":
            handed_off = False
            console.print("[dim](resumed: the bot answers again)[/]\n")
            continue
        if text.startswith("/prompt"):
            _switch_prompt(llm, home, text.removeprefix("/prompt").strip())
            continue

        if text.startswith("/photo"):
            message = _photo_message(text.removeprefix("/photo").strip(), config.llm_vision)
            if message is None:
                continue
        else:
            message = {"role": "user", "content": text}
        history.append(message)

        if handed_off:
            console.print("[dim](chat handed off: the real bot stays quiet. /resume to continue, /reset to start over)[/]\n")
            continue

        delay = random_delay(config.auto_reply_delay, config.auto_reply_delay_max, rng)
        try:
            with console.status("typing…"):
                raw = await llm.reply(name, _with_recent_images(history[-config.llm_history_limit :], config))
        except LLMError as e:
            console.print(f"[red](error: {escape(str(e))}; the real bot would send {config.auto_reply_text!r})[/]\n")
            history.pop()
            continue

        if delay >= 1:
            console.print(f"[dim](the real bot would wait {_duration(delay)} before answering)[/]")

        reply, reason = split_handoff(raw)
        if reason is not None:
            handed_off = True
            _show_handoff(config, name, reason, history)
            continue
        reply = humanize(reply, config.llm_typo_rate, rng) or config.auto_reply_text
        history.append({"role": "assistant", "content": reply})
        console.print(f"[bold magenta]bot:[/] {escape(reply)}\n")


def _photo_message(args: str, vision: bool) -> dict | None:
    """/photo path [caption] -> a user message with the image attached (like a Telegram photo)."""
    try:
        parts = shlex.split(args, posix=True)
    except ValueError:
        parts = args.split()
    if not parts:
        console.print("[red]Usage:[/] /photo path/to/picture.jpg \\[caption]  (tip: drag the file into the terminal)\n")
        return None
    path, caption = Path(parts[0]).expanduser(), " ".join(parts[1:])
    if not path.is_file():
        console.print(f"[red]No file at {escape(str(path))}.[/] Tip: drag the file into the terminal.\n")
        return None
    message = {"role": "user", "content": f"[sent a photo] {caption}".strip()}
    if vision:
        message["images"] = [path.read_bytes()]
    return message


def _with_recent_images(history: list[dict], config: Config) -> list[dict]:
    """Keep the pictures of only the newest LLM_MAX_IMAGES photos, like the real bot."""
    with_images = [i for i, m in enumerate(history) if m.get("images")]
    keep = set(with_images[-config.llm_max_images :])
    return [m if i in keep or "images" not in m else {"role": m["role"], "content": m["content"]} for i, m in enumerate(history)]


def _duration(seconds: float) -> str:
    minutes, seconds = divmod(round(seconds), 60)
    return f"{minutes}m {seconds}s" if minutes else f"{seconds}s"


def _show_handoff(config: Config, name: str, reason: str, history: list[dict]) -> None:
    if config.handoff_client_message:
        console.print(f"[bold magenta]bot:[/] {escape(config.handoff_client_message)}")
        console.print("[dim](the fixed HANDOFF_CLIENT_MESSAGE)[/]")
    else:
        console.print("[dim](HANDOFF_CLIENT_MESSAGE is empty: the person gets no message)[/]")

    target = config.handoff_notify_chat or "your Saved Messages"
    hint = resume_hint(config.command_prefix, to_saved_messages=not config.handoff_notify_chat)
    alert = format_notification("Playground client", PLAYGROUND_CHAT_ID, reason, history, resume_hint=hint)
    console.print(Panel(escape(alert), title=f"Handoff alert → {escape(target)}", border_style="yellow"))
    console.print("[dim](the chat is now paused: the real bot stays quiet. /resume to continue, /reset to start over)[/]\n")


def _switch_prompt(llm: LLM, home: Home, name: str) -> None:
    available = sorted(p.stem for p in home.prompts_dir.glob("*.txt"))
    if not name:
        console.print(f"Current prompt: [cyan]{escape(llm.prompt.path.name)}[/]. Available: {', '.join(available)}\n")
        return
    path = home.prompts_dir / (name if name.endswith(".txt") else f"{name}.txt")
    if not path.exists():
        console.print(f"[red]No prompt called {escape(name)!r}.[/] Available: {', '.join(available)}\n")
        return
    llm.use_prompt_file(path)
    console.print(f"[dim](now using {escape(path.name)}; the conversation continues)[/]\n")


if __name__ == "__main__":
    import sys

    from .cli import main

    main(["chat", *sys.argv[1:]])
