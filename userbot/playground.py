"""Chat with the auto-reply AI in your terminal, without Telegram.

    python -m userbot.playground --name Aleksa

You play the person messaging you; the bot answers using the same prompt,
model and settings as the real userbot. Commands: /reset, /quit.
"""

import argparse
import asyncio
import sys

from .config import ConfigError, load_config
from .llm import LLM, LLMError


async def main(name: str) -> None:
    try:
        config = load_config()
    except ConfigError as e:
        sys.exit(f"Configuration error: {e}")

    llm = LLM(config)
    problem = await llm.check()
    if problem:
        sys.exit(f"LLM not ready: {problem}")

    print(f"Chatting as a friend of {name!r} | model {llm.model} | prompt {config.llm_system_prompt_file.name}")
    print("Type a message and press Enter. /reset starts over, /quit exits.\n")

    history: list[dict[str, str]] = []
    while True:
        try:
            text = (await asyncio.to_thread(input, "you: ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not text:
            continue
        if text == "/quit":
            return
        if text == "/reset":
            history.clear()
            print("(conversation cleared)\n")
            continue

        history.append({"role": "user", "content": text})
        try:
            reply = await llm.reply(name, history[-config.llm_history_limit :])
        except LLMError as e:
            print(f"(error: {e}; the real bot would send {config.auto_reply_text!r})\n")
            history.pop()
            continue
        history.append({"role": "assistant", "content": reply})
        print(f"bot: {reply}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", default="Me", help="your first name, as the bot will use it (default: Me)")
    asyncio.run(main(parser.parse_args().name))
