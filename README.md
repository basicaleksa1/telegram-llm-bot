# Telegram Userbot (Telethon + local LLM)

A small, extensible **userbot**: it logs in as *your own Telegram account* (not a bot) using
[Telethon](https://docs.telethon.dev/) and works on your behalf.

Out of the box it does two things:

**1. AI auto-reply.** When someone sends you a message in a **private chat**, a **local LLM**
(running on your own computer through [Ollama](https://ollama.com)) reads the recent
conversation and **chats back as you**: it answers, reacts and asks things back, like a real
conversation. You can switch it to a "you're busy, I'll get back to you" style instead. If the
LLM isn't available, it falls back to the fixed text `brate radim`. Groups, channels, bots and Telegram's own service account
are ignored. See [AI auto-reply](#ai-auto-reply).

**2. Commands.** Three example commands that only react to messages sent *from your account*,
so nobody else can trigger them:

| Command      | What it does                                                            |
|--------------|-------------------------------------------------------------------------|
| `.ping`      | Edits your message to `pong (N ms)`. Confirms the userbot is running.   |
| `.id`        | Shows the current chat's ID. As a reply, also shows the sender/message ID. |
| `.help`      | Lists all available commands.                                           |

It has a menu-driven terminal interface (setup wizard, prompt editing, settings, model
downloads, diagnostics), and can be sent to testers as a zip that runs on Windows, macOS and
Linux without installing Python. See [Sending it to testers](#sending-it-to-testers); testers
follow [docs/TESTERS.md](docs/TESTERS.md).

---

## ⚠️ Read this first

- **Your session file is your account.** After login, `sessions/<name>.session` lets anyone who
  has it act as you on Telegram (no password or code needed). Never share it, commit it, or
  upload it anywhere. `.gitignore` already excludes it.
- **Keep `API_ID` / `API_HASH` private.** Same rules as a password.
- **The AI speaks to real people as you.** It's told not to make promises, invent plans or
  share personal info, but a small model can still say something odd. Read
  [AI auto-reply](#ai-auto-reply) and consider starting with an allowlist (`LLM_ALLOWED_CHATS`).
- **Stay within Telegram's rules.** Userbots are allowed, but spam, mass-messaging, mass-joining,
  or scraping can get your account **limited or banned**. Telegram also enforces rate limits
  ("FloodWait"). Telethon waits automatically for short ones; don't try to work around them.
- If you ever think the session leaked: in Telegram, open **Settings → Devices** and terminate
  the session, then delete the local `.session` file.

---

## Requirements

- Python **3.11+** (developed with 3.14; the tester bundle uses 3.13)
- A Telegram account, and the phone that receives its login codes
- Your own API credentials from my.telegram.org (see below)
- For AI replies: [Ollama](https://ollama.com) and a model. The default `qwen3.5:9b` is a
  **7.6 GB download** and uses **~8 GB of memory** while loaded. Works well on an Apple Silicon
  Mac with 16 GB RAM.

---

## Setup (what needs to be done to make it fully functional)

### 1. Get your API credentials (one time)

1. Go to <https://my.telegram.org> and log in with your phone number. The code arrives
   **in the Telegram app**, not by SMS.
2. Click **API development tools**.
3. Fill in the form: any *App title* and a *Short name* of 5–32 letters/numbers
   (e.g. `myuserbot2026`). Platform: *Desktop*. URL and description can be left empty.
4. Copy the **App api_id** (a number) and the **App api_hash** (a 32-character string).

> If the form only says "ERROR", turn off VPN/ad blockers, try another browser, or pick a more
> unique short name.

### 2. Install the Python project

```bash
cd telegram-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional speed-up for file downloads/uploads (skip it if it fails to build):

```bash
pip install cryptg
```

### 3. Install Ollama and the model (for AI replies)

1. Download Ollama for macOS from <https://ollama.com/download> and move **Ollama.app** to
   **Applications**. Open it. A llama icon appears in the menu bar, and the server runs on
   `http://localhost:11434`. On first launch it offers to install the `ollama` terminal
   command; accept it (it asks for your Mac password).
2. Download the model (7.6 GB, one time):

   ```bash
   ollama pull qwen3.5:9b
   ```

   If the `ollama` command isn't found, use the full path:
   `/Applications/Ollama.app/Contents/Resources/ollama pull qwen3.5:9b`
3. Optional: check it answers: `ollama run qwen3.5:9b "Reci zdravo"` (type `/bye` to exit).

Ollama must be running whenever the userbot is. To start it automatically, make sure it's
listed under **System Settings → General → Login Items** (Ollama may have added itself already). Skipping this step is fine: the userbot then sends
the fixed `brate radim` text instead.

### 4. Configure

```bash
cp .env.example .env
```

Then open `.env` and fill in at least:

```ini
API_ID=your_api_id
API_HASH=your_api_hash
```

Then open **`prompts/chat.txt`** and fill in the *About {name}* section:

- **Gender (important):** pick one of the two lines given there. Serbian grammar needs it
  ("bio sam" vs "bila sam"). If it's left out, the model guesses, and it guesses differently
  from one reply to the next.
- **Where you live, work/school, interests, how you write:** this is what the bot talks
  about. With an empty profile it gives vague answers or makes small things up. Only write
  what you're fine with *anyone* who messages you learning. See
  [Conversation vs. busy mode](#conversation-vs-busy-mode).

All other settings are optional:

| Variable         | Default   | Description                                                  |
|------------------|-----------|--------------------------------------------------------------|
| `PHONE`          | *(asked)* | Your number in international format, e.g. `+381601234567`.   |
| `SESSION_NAME`   | `userbot` | Session file name in `sessions/`. Use a new name to log in as a different account. |
| `COMMAND_PREFIX` | `.`       | What commands start with, e.g. `!` makes it `!ping`.          |
| `LOG_LEVEL`      | `INFO`    | `DEBUG` shows much more detail when troubleshooting.         |
| `AUTO_REPLY_ENABLED`  | `true`        | `false` turns all auto-replies off (AI and fixed text).    |
| `AUTO_REPLY_TEXT`     | `brate radim` | Fixed reply used when the AI is off, not allowed for the chat, or fails. |
| `AUTO_REPLY_DELAY`    | `3`           | Seconds to wait for the person to stop sending messages before replying once. `0` = reply to each message immediately. |
| `AUTO_REPLY_COOLDOWN` | `0`           | Minimum seconds between auto-replies in the same chat. `0` = no limit. |
| `AUTO_REPLY_QUOTE`    | `false`       | `true` = quote their message above each reply. `false` = send a plain message, which looks more like a normal chat. |
| `LLM_ENABLED`         | `true`        | `false` = always use the fixed `AUTO_REPLY_TEXT`.         |
| `LLM_MODEL`           | `qwen3.5:9b`  | Any model you've pulled in Ollama (`ollama list`), e.g. `qwen3.5:4b`, `gemma4:12b`. |
| `LLM_HOST`            | `http://localhost:11434` | Where Ollama runs.                             |
| `LLM_SYSTEM_PROMPT_FILE` | `prompts/chat.txt` | The AI's instructions. `prompts/chat.txt` = hold a conversation as you, `prompts/busy.txt` = say you're busy. Relative to the data folder (the project folder when running from source), or an absolute path. |
| `LLM_HISTORY_LIMIT`   | `20`          | How many recent messages of the chat the AI sees. More = better memory of the conversation, slightly slower. |
| `LLM_TIMEOUT`         | `60`          | Seconds to wait for the AI before sending the fixed text instead. |
| `LLM_ALLOWED_CHATS`   | *(empty)*     | Comma-separated chat IDs that get AI replies. Empty = everyone. Others get the fixed text. Find IDs with `.id`. |
| `LLM_REPLY_LANGUAGE`  | *(empty)*     | Force every AI reply into one language, e.g. `English`. Empty = whatever the prompt says. See [Reply language](#reply-language). |

### 5. First run / log in

```bash
python -m userbot
```

This opens the **menu** (if `API_ID`/`API_HASH` aren't set yet, it offers the setup wizard
first). Choose **Start the bot**, or skip the menu with `python -m userbot start`.

The first start is interactive. It asks for:

1. Your **phone number** (unless `PHONE` is set)
2. The **login code**, which Telegram sends to your app from the "Telegram" service chat
3. Your **2FA password**, if you have two-step verification enabled

When it prints `Logged in as ...`, it's running. The login is saved to `sessions/`, so later runs
start without prompts. **Ctrl+C** stops the bot (and returns to the menu, if you started it there).

At startup you should also see one of these:

- `LLM ready: qwen3.5:9b via http://localhost:11434` means AI replies are on.
- `LLM not ready: ...` means it tells you what's wrong (Ollama not running / model not pulled).
  Until that's fixed, the fixed text is sent.

> You'll see a "new login" notification in your Telegram apps. That's expected; it's this
> userbot. It will also show up under **Settings → Devices**.

---

## AI auto-reply

How a reply is produced (`userbot/autoreply.py` + `userbot/llm.py`):

```
Someone DMs you
   └─ wait AUTO_REPLY_DELAY seconds (restarts if they send another message)
        └─ fetch the last LLM_HISTORY_LIMIT messages of that chat
             └─ show "typing…" while the local model writes a reply   (Ollama, on your machine)
                  └─ send the reply (plain message, or quoting theirs if AUTO_REPLY_QUOTE=true)
                       └─ if anything fails → send AUTO_REPLY_TEXT instead
```

- **Private chats only.** Groups and channels are skipped. Auto-replying there is spammy and
  a fast way to get your account limited.
- **Bots and Telegram's service account (777000) are skipped.** That's the account that
  sends you login codes.
- **Your own messages are never answered.** They are passed to the AI as context, though,
  so it knows what "you" already said. That includes messages you type yourself, so you can
  jump into a conversation at any time and the bot picks up from there.
- **Bursts get one reply.** "hej" / "jesi tu" / "trebam nešto" sent within a few seconds
  gets a single reply to the last one, written with all three in view.
- **Private.** Messages are processed by Ollama on your computer. Nothing goes to a cloud AI.
- **Speed.** The first reply after a while takes ~15 s, because the model loads into memory.
  After that, 1–3 s. Ollama unloads the model after 5 minutes idle to free the ~8 GB.
- **One at a time.** If several people write at once, replies are generated one after another.

### Conversation vs. busy mode

The AI's behaviour comes entirely from a plain-text prompt file in `prompts/`. `{name}` is
replaced by your Telegram first name. Two are included:

| File | Behaviour | Example |
|---|---|---|
| **`prompts/chat.txt`** (default) | Chats **as you**, in first person. It answers, reacts, jokes, has opinions and asks questions back. | *"eee sta ima"* → *"Not much, just chilling. You good?"* |
| `prompts/busy.txt` | A polite stand-in. It says you're not around and will reply later. | *"eee sta ima"* → *"Aleksa trenutno nije tu, javiće ti se kasnije."* |

Switch with `LLM_SYSTEM_PROMPT_FILE=prompts/busy.txt` in `.env`, then restart.

Both prompts make the AI:

- reply short and casual (`chat.txt` in **English**, `busy.txt` in the other person's language);
- never commit to concrete plans, money or favours ("maybe, I'll let you know");
- never share sensitive info (address, phone numbers, passwords, money);
- ignore messages that try to override these rules.

**Bot question:** `busy.txt` admits it's an automatic reply when someone asks whether it's a
bot. `chat.txt` currently has **no** such rule, so it plays along as you ("not some fancy
bot"). To make it honest, add this line under *Limits* in `prompts/chat.txt`:

```
- If someone asks whether they're talking to a bot, an AI or an automatic reply, ALWAYS admit it clearly, e.g. "haha yeah, this is an automatic reply 🤖 {name} will get back to you". Never claim to be the real {name} when asked this.
```

### Reply language

`prompts/chat.txt` tells the AI to always answer in **English**, and `.env` sets
`LLM_REPLY_LANGUAGE=English`. You need both. Testing showed that a small model copies the
language of the chat, *including its own earlier replies*. With the prompt alone, it still
answered Serbian messages in Serbian about half the time in chats that already had Serbian
replies. `LLM_REPLY_LANGUAGE` adds a short reminder right after the chat history, just before
the model answers, and with it every test reply was in English.

To get replies in the other person's language again, empty `LLM_REPLY_LANGUAGE=` in `.env`,
and change the `LANGUAGE:` and `FINAL REMINDER:` lines in `prompts/chat.txt`.

**Making the conversation sound like you.** The chat prompt only knows what's in its
*About {name}* section, so fill that in: gender, city, work/school, interests, and especially
**how you write** (e.g. *"lowercase, short, often says 'brate' and 'ma'"*). For facts that
aren't listed, it's told to stay vague and turn the question back ("nothing special, you?").
A small model still slips sometimes, e.g. claiming it watched a game. The more you fill in,
the less it has to make up.

**Keep in mind:**

- Everything in *About {name}* can end up in a reply to **anyone** who messages you. Don't put
  secrets in a prompt. Clever messages can sometimes make a model repeat its instructions.
- The AI also sees its own earlier replies. If a chat is full of old "brate radim" or "I'm
  busy" replies, it may keep that tone for a few messages.
- Prompt edits apply to the **next reply**, no restart needed (the file is re-read when it
  changes). Try changes first with the [playground](#b-chat-with-the-ai-in-your-terminal-no-telegram).
- You can write your own prompt file (e.g. `prompts/work.txt`) and point
  `LLM_SYSTEM_PROMPT_FILE` at it.

### Limiting who gets AI replies

Start small: get chat IDs with `.id` (send it in the chat with that person), then:

```ini
LLM_ALLOWED_CHATS=123456789,987654321
```

Those chats get AI replies, and everyone else gets `AUTO_REPLY_TEXT`. Leave it empty for everyone.

### Trying other models

Any Ollama model works. Pull it and set `LLM_MODEL`:

```bash
ollama pull qwen3.5:4b
```

Then set `LLM_MODEL=qwen3.5:4b` in `.env`. On a 16 GB Mac, good options are `qwen3.5:9b`
(default, best quality), `qwen3.5:4b` (faster, ~3.3 GB), and `gemma4:12b` (different style,
~7.7 GB). Models over ~9 GB will be slow and make the Mac sluggish. `ollama list` shows
what you've downloaded; `ollama rm <model>` deletes one.

### Turning it off

- AI only (keep the fixed text): `LLM_ENABLED=false`
- All auto-replies: `AUTO_REPLY_ENABLED=false`

---

## How to test it yourself

### A. Automated tests (no Telegram account or Ollama needed)

They check config parsing, command matching, the auto-reply logic (history, fallback, allowlist,
waiting for bursts) and the LLM client, all with fakes. Nothing connects to Telegram or Ollama.

```bash
pip install -r requirements-dev.txt
python -m pytest
```

### B. Chat with the AI in your terminal (no Telegram)

With Ollama running, you play the friend, and the bot answers with exactly the same prompt,
model and settings as the real userbot. This is the best way to tune your prompt:

```bash
python -m userbot chat --name Aleksa
```

Type messages and press Enter. `/prompt busy` switches prompts, `/reset` starts a new
conversation, `/quit` exits. Edit `prompts/chat.txt` and save: the next message already uses
the new version. Things worth trying: small talk,
"jesi gledao utakmicu?", "hoćeš u subotu na pivo?", "pozajmi mi 100 evra", "jel ovo bot?".

### C. Live test on your account

1. Make sure Ollama is running, then start the userbot: `python -m userbot`. Check for
   `LLM ready: ...` in the output.
2. In any Telegram app, open **Saved Messages** (your chat with yourself; safe for testing,
   since nobody else sees it). Send `.help`, `.ping` and `.id`. Each message should be edited
   into the result.
3. **AI reply:** ask a friend (or use a second account) to send you a private message. After
   ~3 seconds they should see you "typing…", then an AI reply. The terminal logs
   `Auto-replied in chat ...` (the reply text only with `LOG_LEVEL=DEBUG`). Have them send 2–3 messages quickly. They should
   get **one** reply.
4. **Fallback:** quit Ollama (menu-bar icon → Quit) and have them message again. They should get
   `brate radim`, and the terminal shows a warning. Reopen Ollama afterwards.
5. Make sure commands **ignore other people**: ask the friend to send you `.ping`. They get an
   auto-reply, but the command itself does nothing.
6. Make sure groups are ignored: when someone writes in a group you're in, nothing is sent.
7. Use `LOG_LEVEL=DEBUG` in `.env` for more detail.

If nothing happens, check that the terminal says `Logged in as ...`, that you used the right
prefix, and that the command is the **whole** message (`.ping`, not `hey .ping`).

---

## Commands and the data folder

`python -m userbot` without a command opens the menu. Everything in it is also a command:

```
python -m userbot setup | start | chat | doctor | login | logout | folder | --version
python -m userbot prompt list | use NAME | edit [NAME] | show [NAME] | new NAME | reset
python -m userbot settings show | set KEY VALUE | edit
python -m userbot model list | recommend | use MODEL | pull [MODEL]
```

`--help` works on every level, e.g. `python -m userbot prompt --help`.

Settings, prompts, the login and logs live in one **data folder** (see `userbot/paths.py`):

- **Running from this repository with a `.env` file:** the repository itself (`.env`,
  `prompts/`, `sessions/`, `logs/`), exactly as before.
- **Otherwise (e.g. the tester bundle):** a per-user folder that survives updates:
  - Windows: `%APPDATA%\TelegramUserbot`
  - macOS: `~/Library/Application Support/TelegramUserbot`
  - Linux: `~/.local/share/TelegramUserbot`

  It holds `settings.env` (made from `.env.example`), `prompts/`, `sessions/` and `logs/`. The
  default prompts are copied in on first run and never overwritten.
- **`--home DIR` or `USERBOT_HOME=DIR`** picks any other folder, e.g. to test a fresh setup
  without touching your own.

---

## Sending it to testers

```bash
python3 scripts/build_bundle.py
```

This builds `dist/userbot-<version>-windows.zip`, `-macos.zip` and `-linux.zip` (20–45 MB
each). Send each tester the zip for their system, by Google Drive, WeTransfer or Telegram.
Each zip contains:

- **A launcher to double-click:** `Start Userbot.bat`, `Start Userbot.command` or `start.sh`.
- **The tester guide:** [docs/TESTERS.md](docs/TESTERS.md).
- **The app:** code, prompts, and the exact library versions from `uv.lock`.
- **[uv](https://docs.astral.sh/uv/):** on the tester's first start it downloads Python 3.13
  and the libraries into the bundle's own `runtime/` folder. Nothing is installed
  system-wide.

Things to know:

- **Your own data never goes into a bundle.** The script only packs an explicit list of files
  and refuses to include `.env`, `sessions/` or `*.session`.
- **The default prompts testers get are the repository's `prompts/` files.**
- **Before sending a new version,** bump the version in `userbot/__init__.py` and
  `pyproject.toml`; the script checks that they match.
- **The first build downloads the pinned uv binaries** (checked against their SHA-256) into
  `dist/.cache/`. It also refreshes `uv.lock` when `pyproject.toml` changed; commit that.
- **Building on GitHub,** single-file executables and code signing are planned separately in
  [docs/plan-github-builds.md](docs/plan-github-builds.md).

---

## Project structure

```
telegram-bot/
├── userbot/
│   ├── __main__.py      # Entry point: python -m userbot
│   ├── cli.py           # Commands (Typer); no command = the menu
│   ├── menu.py          # Interactive menu
│   ├── setup_wizard.py  # First-run setup: API ID/hash, Ollama + model, prompt, login
│   ├── actions.py       # What the menu and the commands do (shared)
│   ├── bot.py           # Runs the userbot; Telegram login/logout
│   ├── paths.py         # The data folder (settings, prompts, sessions, logs)
│   ├── config.py        # Reads/writes the settings file + environment variables
│   ├── ollama_setup.py  # Finds/installs/starts Ollama, recommends and downloads models
│   ├── doctor.py        # `doctor`: checks everything and suggests fixes
│   ├── ui.py            # Terminal output, logging, opening files/folders
│   ├── commands.py      # @command decorator + wiring into Telethon
│   ├── autoreply.py     # Auto-reply to incoming private messages (delay, history, fallback)
│   ├── llm.py           # Talks to the local model through Ollama; reloads the prompt on change
│   ├── playground.py    # Terminal chat with the AI for testing (python -m userbot chat)
│   └── handlers/
│       ├── __init__.py  # Imports handler modules so their commands register
│       └── basic.py     # .ping, .id, .help
├── prompts/
│   ├── chat.txt         # Default: chat as you
│   └── busy.txt         # Alternative: "not around, will reply later"
├── packaging/launchers/ # Start Userbot.bat / start.sh (also used as Start Userbot.command)
├── scripts/
│   └── build_bundle.py  # Builds the tester zips into dist/
├── docs/
│   ├── TESTERS.md       # Step-by-step guide for testers (included in each zip)
│   ├── packaging-plan.md
│   └── plan-github-builds.md
├── tests/               # pytest tests (offline)
├── sessions/            # Created on first run. Holds your login. KEEP PRIVATE
├── .env.example         # Template for your .env / the data folder's settings.env
├── pyproject.toml       # Dependencies (uv); uv.lock pins the bundle's versions
├── requirements.txt     # Same dependencies for pip
└── requirements-dev.txt
```

---

## Adding your own command

1. Create a module, e.g. `userbot/handlers/fun.py`:

   ```python
   from telethon import events

   from ..commands import Context, command


   @command("shout", "Repeat the text in uppercase")
   async def shout(event: events.NewMessage.Event, ctx: Context) -> None:
       text = event.pattern_match.group(1) or ""  # everything after ".shout "
       await event.edit(text.upper() or "Usage: .shout <text>")
   ```

2. Register the module in `userbot/handlers/__init__.py`:

   ```python
   from . import basic, fun  # noqa: F401
   ```

3. Restart the userbot and send `.shout hello`.

Useful things available on `event`: `event.edit(...)`, `event.reply(...)`, `event.delete()`,
`event.chat_id`, `await event.get_reply_message()`, and `event.client` (the full
`TelegramClient`, e.g. `await event.client.send_message("me", "hi")`).

### Reacting to other people's messages (your own handlers)

The `@command` helper only listens to *your* messages. To react to incoming messages in other
ways, add a plain Telethon handler. For example, in `userbot/__main__.py` after
`register_commands(...)`:

```python
from telethon import events

@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def on_private_message(event):
    sender = await event.get_sender()
    log.info("DM from %s: %s", sender.first_name, event.raw_text[:50])
```

Be careful with anything that **sends** messages automatically (auto-replies, forwarding).
It's the quickest way to hit rate limits or get reported as spam.

---

## Running it long-term (optional)

The userbot only works while it's running (`python -m userbot start`, or *Start the bot* in the menu), and Ollama too, for AI replies. To
keep it up 24/7, run it on an always-on machine, using `tmux`/`screen`, a `launchd`/`systemd`
service, or Docker. A small VPS without a GPU will run the LLM very slowly. Prefer a machine
like an Apple Silicon Mac, or use a smaller model there. Copy the `sessions/` file over
**securely** (e.g. `scp`), or log in again on the new machine.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Configuration error: Missing required setting(s)` | Create `.env` from `.env.example` and fill in `API_ID` / `API_HASH`. |
| `ApiIdInvalidError` | `API_ID`/`API_HASH` are wrong. Copy them again from my.telegram.org. |
| `PhoneNumberInvalidError` | Use international format with `+` and the country code. |
| Login code never arrives | Look in the Telegram app (the "Telegram" service chat), not SMS. |
| `FloodWaitError` | You're rate-limited. Wait the number of seconds it says. |
| `AuthKeyDuplicatedError` / session errors | The same session file was used from two places at once. Delete the `.session` file and log in again. |
| Commands do nothing | Check the prefix, that the command is the whole message, and that it was sent from the logged-in account. |
| `LLM not ready: cannot reach Ollama` | Open the Ollama app (menu-bar llama icon). Check `curl http://localhost:11434/api/version`. |
| `LLM not ready: model ... is not downloaded` | Run the `ollama pull ...` command it prints. |
| Replies are always `brate radim` | Look for warnings in the terminal. Also check `LLM_ENABLED` and `LLM_ALLOWED_CHATS`. |
| `No reply from ... within 60s` | The Mac is short on memory or busy. Close apps, use `qwen3.5:4b`, or raise `LLM_TIMEOUT`. |
| AI answers in the wrong language | Set `LLM_REPLY_LANGUAGE` in `.env` (e.g. `English`) and restart. See [Reply language](#reply-language). |
| AI uses the wrong gender for you | Fill in the gender line in `prompts/chat.txt` (or `busy.txt`), then restart. |
| AI only says you're busy | You're using `prompts/busy.txt`. Remove `LLM_SYSTEM_PROMPT_FILE` from `.env`, or set it to `prompts/chat.txt`. Old "busy" replies in the chat can also keep that tone for a few messages. |
| AI makes up things about you | Fill in more of *About {name}* in `prompts/chat.txt`. |
| AI replies sound off | Edit the prompt (tone, how you write, example phrases), test in the playground, or try another model. |

## Useful links

- Telethon docs: <https://docs.telethon.dev/en/stable/>
- Telethon client method reference: <https://docs.telethon.dev/en/stable/modules/client.html>
- Event types (NewMessage, MessageEdited, ChatAction, ...): <https://docs.telethon.dev/en/stable/modules/events.html>
- Raw Telegram API reference: <https://tl.telethon.dev/>
- Ollama: <https://ollama.com> · model library: <https://ollama.com/library>
- Ollama Python client: <https://github.com/ollama/ollama-python>
