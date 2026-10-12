"""Chat with the auto-reply AI in your terminal, without Telegram.

    userbot chat --name Aleksa          (or: python -m userbot chat)

You play the person messaging you; the bot answers using the same prompt,
model and settings as the real userbot. Edits to the prompt file apply to the
next message. Commands: /prompt [name], /reset, /quit.
"""

import asyncio

from rich.markup import escape

from .config import Config
from .llm import LLM, LLMError
from .paths import Home
from .ui import console

HELP = "Type a message and press Enter. [bold]/prompt[/] [dim]name[/] switches prompts, [bold]/reset[/] starts over, [bold]/quit[/] exits."


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
    console.print(HELP + "\n")

    history: list[dict[str, str]] = []
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
            console.print("[dim](conversation cleared)[/]\n")
            continue
        if text.startswith("/prompt"):
            _switch_prompt(llm, home, text.removeprefix("/prompt").strip())
            continue

        history.append({"role": "user", "content": text})
        try:
            with console.status("typing…"):
                reply = await llm.reply(name, history[-config.llm_history_limit :])
        except LLMError as e:
            console.print(f"[red](error: {escape(str(e))}; the real bot would send {config.auto_reply_text!r})[/]\n")
            history.pop()
            continue
        history.append({"role": "assistant", "content": reply})
        console.print(f"[bold magenta]bot:[/] {escape(reply)}\n")


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
