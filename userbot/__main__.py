"""Entry point: `python -m userbot` (opens the menu) or `python -m userbot <command>`.

See cli.py for the commands. The first start runs the setup: Telegram API
credentials, the local AI, the prompt, and the Telegram login (saved in the
data folder's sessions/ and reused afterwards).
"""

from .cli import main

if __name__ == "__main__":
    main()
