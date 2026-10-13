# Telegram Userbot (Telethon + local LLM)

A small, extensible **userbot**: it logs in as *your own Telegram account* (not a bot) using
[Telethon](https://docs.telethon.dev/) and works on your behalf.

Out of the box it does two things:

**1. AI auto-reply.** When someone sends you a message in a **private chat**, a **local LLM**
(running on your own computer through [Ollama](https://ollama.com)) reads the recent
conversation, including photos, and **chats back as you**. What it says comes from a plain-text
prompt. The included one, `prompts/chat.txt`, is a sales script for a Reddit promotion service:
it qualifies the client step by step and, at the key point, **hands the chat over to you**. It
stops replying and alerts another Telegram account of your choice. Replies wait a random few
minutes and get small typos, so they read like a person typing. If the LLM isn't available,
it falls back to the fixed text `brate radim`. Groups, channels, bots and Telegram's own
service account are ignored. See [AI auto-reply](#ai-auto-reply).

**2. Commands.** A few commands that only react to messages sent *from your account*,
so nobody else can trigger them:

| Command      | What it does                                                            |
|--------------|-------------------------------------------------------------------------|
| `.ping`      | Edits your message to `pong (N ms)`. Confirms the userbot is running.   |
| `.id`        | Shows the current chat's ID. As a reply, also shows the sender/message ID. |
| `.help`      | Lists all available commands.                                           |
| `.pause` / `.resume` | Stop / restart the AI in a chat (or `.resume <chat id>`). See [Handoff to you](#handoff-to-you). |
| `.paused`    | Lists the chats where the AI is paused: handed over to you, or paused with `.pause`. |

It has a menu-driven terminal interface (setup wizard, prompt editing, settings, model
downloads, diagnostics), and can be sent to testers as a zip that runs on Windows, macOS and
Linux without installing Python. When a tester starts a newer version, their settings and
prompt are brought up to date and they're told what changed. See
[Sending it to testers](#sending-it-to-testers); testers follow [docs/TESTERS.md](docs/TESTERS.md).

---

## ⚠️ Read this first

- **Your session file is your account.** After login, `sessions/<name>.session` lets anyone who
  has it act as you on Telegram (no password or code needed). Never share it, commit it, or
  upload it anywhere. `.gitignore` already excludes it.
- **Keep `API_ID` / `API_HASH` private.** Same rules as a password.
- **The AI speaks to real people as you.** The prompt tells it to stick to the facts it's
  given and hand the chat to you at the key point, but a small model can still say something
  odd. Read [AI auto-reply](#ai-auto-reply) and consider starting with an allowlist
  (`LLM_ALLOWED_CHATS`).
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
- For AI replies: [Ollama](https://ollama.com) (macOS 14+, Windows 10 22H2+ or Linux) and a
  model. The default `qwen3.5:9b` is a **7.6 GB download** and uses **~8 GB of memory** while
  loaded. Works well on an Apple Silicon Mac with 16 GB RAM.

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

The quickest way: create `.env` first (`cp .env.example .env`, step 4), then run
`python -m userbot setup`. It asks for the API ID/hash, installs or starts Ollama, recommends a
model for your computer and downloads it, then asks for the prompt, the account that gets
handoff alerts, and logs you in. (Without a `.env` in the repository, the setup writes
to the per-user data folder instead; see [Commands and the data folder](#commands-and-the-data-folder).)
To do it by hand:

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

(`python -m userbot setup` asks for them and writes them into `.env` for you.)

The prompt, **`prompts/chat.txt`**, is a plain text script that's sent to the model as-is.
Read it and adapt it, especially the `<facts>` (prices, what you need from the client) and
`<handoff>` (when the AI must stop and alert you) sections. See [The prompt](#the-prompt).
**Testers get these files as they are** (see [Sending it to testers](#sending-it-to-testers)).

For the handoff alerts, also set `HANDOFF_NOTIFY_CHAT` to your **other** account's `@username`
(see [Handoff to you](#handoff-to-you)).

All other settings are optional:

| Variable         | Default   | Description                                                  |
|------------------|-----------|--------------------------------------------------------------|
| `PHONE`          | *(asked)* | Your number in international format, e.g. `+381601234567`.   |
| `SESSION_NAME`   | `userbot` | Session file name in `sessions/`. Use a new name to log in as a different account. |
| `COMMAND_PREFIX` | `.`       | What commands start with, e.g. `!` makes it `!ping`.          |
| `LOG_LEVEL`      | `INFO`    | `DEBUG` shows much more detail when troubleshooting.         |
| `TELEGRAM_TEST_SERVERS` | `false` | `true` = log in to Telegram's test servers with a test account. See [D. Telegram test servers](#d-telegram-test-servers-no-real-account). |
| `AUTO_REPLY_ENABLED`  | `true`        | `false` turns all auto-replies off (AI and fixed text).    |
| `AUTO_REPLY_TEXT`     | `brate radim` | Fixed reply used when the AI is off, not allowed for the chat, or fails. |
| `AUTO_REPLY_DELAY`    | `3`           | Seconds to wait for the person to stop sending messages before replying once. `0` = reply to each message immediately. |
| `AUTO_REPLY_COOLDOWN` | `0`           | Minimum seconds between auto-replies in the same chat. Messages that arrive during the cooldown get no reply at all. `0` = no limit. |
| `AUTO_REPLY_QUOTE`    | `false`       | `true` = quote their message above each reply. `false` = send a plain message, which looks more like a normal chat. |
| `LLM_ENABLED`         | `true`        | `false` = always use the fixed `AUTO_REPLY_TEXT`.         |
| `LLM_MODEL`           | `qwen3.5:9b`  | Any model you've pulled in Ollama (`ollama list`), e.g. `qwen3.5:4b`, `gemma4:12b`. |
| `LLM_HOST`            | `http://localhost:11434` | Where Ollama runs.                             |
| `LLM_SYSTEM_PROMPT_FILE` | `prompts/chat.txt` | The AI's instructions (see [The prompt](#the-prompt)). Relative to the data folder (the project folder when running from source), or an absolute path. |
| `LLM_HISTORY_LIMIT`   | `20`          | How many recent messages of the chat the AI sees. More = better memory of the conversation, slightly slower. |
| `LLM_TIMEOUT`         | `60`          | Seconds to wait for the AI before sending the fixed text instead. |
| `LLM_ALLOWED_CHATS`   | *(empty)*     | Comma-separated chat IDs that get AI replies. Empty = everyone. Others get the fixed text. Find IDs with `.id`. |
| `LLM_REPLY_LANGUAGE`  | *(empty)*     | Force every AI reply into one language, e.g. `English`. Empty = whatever the prompt says. See [Reply language](#reply-language). |
| `AUTO_REPLY_DELAY_ENABLED` | `true`   | `false` = ignore the two delay settings and reply after ~2 seconds (still one reply to a burst of messages). Handy while testing. |
| `AUTO_REPLY_DELAY_MAX` | `0`          | If larger than `AUTO_REPLY_DELAY`, each reply waits a random time between the two (e.g. `180`–`600` = 3 to 10 minutes). `0` = always `AUTO_REPLY_DELAY`. |
| `LLM_TYPO_RATE`       | `0`           | Share of words (0–1) that get a small typo in AI replies, e.g. `0.03`. `0` = no typos. |
| `LLM_VISION`          | `true`        | Show the AI the photos people send (needs a model that can see images, like `qwen3.5`). |
| `LLM_MAX_IMAGES`      | `3`           | How many of the most recent photos in the chat the AI sees. |
| `HANDOFF_NOTIFY_CHAT` | *(empty)*     | Who gets the alert when the AI hands a chat over to you: an `@username` (best; a `t.me/…` link or a name without `@` works too), a `+phone` number of a contact, or a numeric user ID. Empty = your Saved Messages. The setup asks for it. See [Handoff to you](#handoff-to-you). |
| `HANDOFF_CLIENT_MESSAGE` | *(empty)*  | Sent to the person when the AI hands the chat over. Empty = send nothing. |

`.env.example` (the template for new settings files) sets the delay to 3–10 minutes, typos to
`0.03` and a holding message, as the sales prompt asks.

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

- `LLM ready: qwen3.5:9b via http://localhost:11434, prompt chat.txt` means AI replies are on.
- `LLM not ready: ...` means it tells you what's wrong (Ollama not running / model not pulled).
  Until that's fixed, the fixed text is sent.

> You'll see a "new login" notification in your Telegram apps. That's expected; it's this
> userbot. It will also show up under **Settings → Devices**.

---

## AI auto-reply

How a reply is produced (`userbot/autoreply.py` + `userbot/llm.py`):

```
Someone DMs you
   └─ chat paused (handed over to you)? → do nothing
   └─ wait AUTO_REPLY_DELAY..AUTO_REPLY_DELAY_MAX seconds (restarts if they send another message)
        └─ you already replied yourself in the meantime? → do nothing
        └─ fetch the last LLM_HISTORY_LIMIT messages of that chat (with up to LLM_MAX_IMAGES of their newest photos)
             └─ show "typing…" while the local model writes a reply   (Ollama, on your machine)
                  ├─ reply contains [[HANDOFF]] → pause the chat, send HANDOFF_CLIENT_MESSAGE, alert you
                  └─ remove markdown, add typos (LLM_TYPO_RATE), send the reply
                       └─ if anything fails → send AUTO_REPLY_TEXT instead
```

- **Private chats only.** Groups and channels are skipped. Auto-replying there is spammy and
  a fast way to get your account limited.
- **Bots and Telegram's service account (777000) are skipped.** That's the account that
  sends you login codes.
- **Your own messages are never answered.** They are passed to the AI as context, though,
  so it knows what "you" already said. That includes messages you type yourself, so you can
  jump into a conversation at any time and the bot picks up from there. If you reply while the
  bot is still waiting to answer, it doesn't send its own reply to that message. To keep the
  AI out of a chat for good, use `.pause`.
- **Bursts get one reply.** "hej" / "jesi tu" / "trebam nešto" sent within a few seconds
  gets a single reply to the last one, written with all three in view.
- **Private.** Messages are processed by Ollama on your computer. Nothing goes to a cloud AI.
- **Speed.** The first reply after a while takes ~15 s, because the model loads into memory.
  After that, 1–3 s. Ollama unloads the model after 5 minutes idle to free the ~8 GB.
- **One at a time.** If several people write at once, replies are generated one after another.

### What the prompt does vs. what the code does

The model can only write text. Anything about timing, seeing photos or stopping a chat has
to be done in code. This is how the sales script in `prompts/chat.txt` is split:

| The script asks for | Done by | How |
|---|---|---|
| Casual, friendly, not AI-sounding; the conversation steps, niche/Reddit rules, pricing | Prompt | `prompts/chat.txt` |
| Typos | Code | `LLM_TYPO_RATE` swaps, drops or doubles a letter in a few words. Small models are bad at typos on purpose. |
| No `#`, no markdown | Both | Prompt rule + the code strips headings, bold, bullets, backticks and em dashes |
| Reply after 3–10 minutes, randomly | Code | `AUTO_REPLY_DELAY=180`, `AUTO_REPLY_DELAY_MAX=600`; switch off with `AUTO_REPLY_DELAY_ENABLED=false` |
| Look at the photos (hair colour, niche) | Both | The code downloads the photos and passes them to the model. The prompt says what to look for. |
| "Notify me" + "stop chatting" at the key point | Both | The model answers `[[HANDOFF]] summary`. The code does the rest (below). |

### Handoff to you

When the prompt's handoff point is reached (in `chat.txt`: the client has no accounts and no
supplier, or asks whether they're talking to a bot), the model answers with only
`[[HANDOFF]] <one-line summary>`. That text never reaches the client. Instead the bot:

1. **pauses the chat**: it won't auto-reply there again, even after a restart (paused chats are
   kept in `paused_chats.json` in the data folder);
2. sends the client `HANDOFF_CLIENT_MESSAGE`, if set;
3. sends you an **alert** with the summary, the last messages and the chat ID, to
   `HANDOFF_NOTIFY_CHAT` (or your Saved Messages if that's empty or can't be found).

To make the bot continue in that chat later:

| From | How |
|---|---|
| The `HANDOFF_NOTIFY_CHAT` account | Reply `resume` to the alert, or send `resume <chat id>`. Also `pause <chat id>` (or `pause` as a reply to an alert), `paused` (list), `help`. |
| Your own account | `.resume` as a reply to an alert in Saved Messages, `.resume <chat id>` anywhere, or `.resume` in the client's chat. |

The notify account must be a **different** account (e.g. your second account or a
colleague). Use its `@username`: a phone number or ID only works if it's in your contacts or
has messaged you before. The bot never auto-replies to that account. On startup the log shows
where alerts go (`Handoff alerts go to ...`).

You can also stop the AI in any chat yourself: `.pause` in that chat (the command message is
deleted right away so they don't see it), or `.pause <chat id>`. `.paused` lists paused chats
(typed in someone's chat, the list goes to your Saved Messages instead).

To add more handoff situations (e.g. "the client wants to negotiate the price"), add them to
the `<handoff>` section of the prompt. The code needs no changes.

### The prompt

The AI's behaviour comes from a plain-text prompt file in `prompts/`. `{name}` is replaced by
your Telegram first name. The included **`prompts/chat.txt`** is split into sections the
model follows:

| Section | What's in it |
|---|---|
| `<style>` | Casual, short, one question per message, no markdown, English |
| `<conversation_flow>` | The steps: number of models → photos → niche → free/paid and price → Reddit history → pricing → accounts |
| `<photos>` | What to say about a niche look, or what to ask when there's none |
| `<reddit_history>` | Ask for the old subreddits, explain why reposting the same photos gets bans |
| `<facts>` | Prices, weekly content, the 3 accounts, when results show. The model is told not to invent anything else. |
| `<handoff>` | When to stop and answer `[[HANDOFF]] summary` instead (see [Handoff to you](#handoff-to-you)) |
| `<example>` | One full example conversation, ending with a handoff |

Things the model can't do on its own (timing, typos, stopping) are settings, not prompt
lines. See [What the prompt does vs. what the code does](#what-the-prompt-does-vs-what-the-code-does).

**Keep in mind:**

- Everything in the prompt can end up in a reply to **anyone** who messages you. Don't put
  secrets in a prompt. Clever messages can sometimes make a model repeat its instructions.
- The AI also sees its own earlier replies. If a chat is full of old "brate radim" replies,
  it may keep that tone for a few messages.
- Prompt edits apply to the **next reply**, no restart needed (the file is re-read when it
  changes). Try changes first with the [playground](#b-chat-with-the-ai-in-your-terminal-no-telegram).
- You can write your own prompt file (e.g. `prompts/work.txt`, or *Prompts → Create a new
  prompt* in the menu) and switch with `python -m userbot prompt use work`. Keep a `<handoff>`
  section with the `[[HANDOFF]]` rule if you want handoffs in it too.
- **Testers get a changed prompt with the next version.** Their data folder has its own copy of
  `chat.txt`. When you ship a new version with a changed `chat.txt`, it replaces theirs on the
  first start (an edited copy is saved in `prompts/backup/`; see [Updating testers](#updating-testers)).
  Within the same version, *Prompts → Restore the original prompts* gets the shipped one back.

### Reply language

`prompts/chat.txt` tells the AI to reply in **English**, and `.env.example` sets
`LLM_REPLY_LANGUAGE=English`. You need both. Testing showed that a small model copies the
language of the chat, *including its own earlier replies*. With the prompt alone, it still
answered Serbian messages in Serbian about half the time in chats that already had Serbian
replies. `LLM_REPLY_LANGUAGE` adds a short reminder right after the chat history, just before
the model answers, and with it every test reply was in English.

To get replies in the other person's language, empty `LLM_REPLY_LANGUAGE=` in `.env` and
remove the "Reply in English" line from the `<style>` section of `prompts/chat.txt`.

### Limiting who gets AI replies

Start small: get chat IDs with `.id` (send it in the chat with that person), then:

```ini
LLM_ALLOWED_CHATS=123456789,987654321
```

Those chats get AI replies, and everyone else gets `AUTO_REPLY_TEXT`. Leave it empty for everyone.

### Trying other models

Any Ollama model works. `python -m userbot model use qwen3.5:4b` downloads it and switches to
it (or *AI model* in the menu; `python -m userbot model recommend` suggests one for this
computer). By hand: pull it and set `LLM_MODEL`:

```bash
ollama pull qwen3.5:4b
```

Then set `LLM_MODEL=qwen3.5:4b` in `.env`. On a 16 GB Mac, good options are `qwen3.5:9b`
(default, best quality), `qwen3.5:4b` (faster, ~4 GB), and `gemma4:12b` (different style,
~7.7 GB). Models over ~9 GB will be slow and make the Mac sluggish. `ollama list` shows
what you've downloaded; `ollama rm <model>` deletes one.

### Turning it off

- AI only (keep the fixed text): `LLM_ENABLED=false`
- All auto-replies: `AUTO_REPLY_ENABLED=false`

---

## How to test it yourself

### A. Automated tests (no Telegram account or Ollama needed)

They check config parsing, commands, the auto-reply logic (history, photos, random delay,
bursts, fallback, allowlist), typos, the handoff (pausing, alerts, resume commands), version
updates (settings and prompts of a 0.1.0 data folder), the test-server login, `doctor` and the
LLM client, all with fakes. Nothing connects to Telegram or Ollama.

```bash
pip install -r requirements-dev.txt
python -m pytest
```

### B. Chat with the AI in your terminal (no Telegram)

With Ollama running, you play the person messaging you (the client), and the bot answers
with the same prompt, model and AI settings as the real userbot (typos, photos, handoff, reply
language). It always uses the AI: `LLM_ENABLED`, `AUTO_REPLY_ENABLED` and `LLM_ALLOWED_CHATS`
don't apply, and each message gets its own reply. This is the best way to tune your prompt:

```bash
python -m userbot chat --name Aleksa
```

Type messages and press Enter. `/photo path/to/picture.jpg [caption]` sends a picture (drag
the file into the terminal to get its path), `/prompt NAME` switches prompts, `/reset` starts
a new conversation, `/quit` exits.

The playground uses the same typos, delay and handoff logic as the real bot, without
sending anything: it prints how long the real bot would wait, and at a handoff it shows the
holding message plus a box with **the exact alert** and where it would go. After that the
chat stays "paused" (your messages get no reply) until you type `/resume` or `/reset`. To
test the sales script, play the client: "hi i have 2 models" → `/photo …` → "paid, 3$" →
"first time" → "how much?" → "what accounts?" → "i dont have accounts" → "i dont have a
supplier". The last message should trigger the handoff. Also try "are you a bot?", a basic
photo with no niche, and "I promoted on Reddit before". Edit `prompts/chat.txt` and save: the
next message already uses the new version.

### C. Live test on your account

1. Start the userbot: `python -m userbot start` (it starts Ollama if needed). Check for
   `LLM ready: ...` in the output.
2. In any Telegram app, open **Saved Messages** (your chat with yourself; safe for testing,
   since nobody else sees it). Send `.help`, `.ping` and `.id`. Each message should be edited
   into the result.
3. **AI reply:** for testing, set `AUTO_REPLY_DELAY_ENABLED=false` so you don't wait
   3–10 minutes per reply (`python -m userbot settings set AUTO_REPLY_DELAY_ENABLED false`, or
   *Settings* in the menu). Ask a friend (or use a second account) to send you a
   private message. After ~2 seconds they should see you "typing…", then an AI reply. The terminal logs
   `Auto-replied in chat ...` (the reply text only with `LOG_LEVEL=DEBUG`). Have them send
   2–3 messages quickly. They should get **one** reply.
4. **Handoff:** set `HANDOFF_NOTIFY_CHAT=@your_other_account` and restart. From a test
   account, play the client until the key point ("i dont have a supplier"). The test account
   gets `HANDOFF_CLIENT_MESSAGE`, your other account gets the alert, and further messages get
   no reply. Reply `resume` to the alert from the other account and the bot answers again.
5. **Fallback:** quit Ollama (menu-bar icon → Quit) and have them message again. They should get
   `brate radim`, and the terminal shows a warning. Reopen Ollama afterwards.
6. Make sure commands **ignore other people**: ask the friend to send you `.ping`. They get an
   auto-reply, but the command itself does nothing.
7. Make sure groups are ignored: when someone writes in a group you're in, nothing is sent.
8. Use `LOG_LEVEL=DEBUG` in `.env` for more detail.
9. Turn the delay back on (`AUTO_REPLY_DELAY_ENABLED=true`) when you're done.

If nothing happens, check that the terminal says `Logged in as ...`, that you used the right
prefix, and that the command is the **whole** message (`.ping`, not `hey .ping`).

### D. Telegram test servers (no real account)

Telegram runs separate **test servers**: a parallel Telegram with its own accounts, where
anyone can log in to a test number with a fixed code
([Telegram's docs](https://core.telegram.org/api/auth#test-accounts)). The bot can run there,
so you can try the whole thing (replies, handoff alerts, `resume`, commands) without your
real account or real clients.

- **Test numbers** look like `99966` + `2` + any 4 digits, e.g. `9996621234`. The `2` is
  the test data center the bot uses.
- **The login code** is always `22222`.
- **Accounts must be created in the official Telegram app.** Telegram doesn't let
  third-party programs (like this one) sign up new accounts, on the test servers too. The
  bot can only log in to a test account that already exists.
- **Everything there is public and temporary.** Anyone can log in to any test number, and
  Telegram wipes the test servers now and then. Don't put anything real there.

**One-time setup: create the test accounts.** You need two or three: one for the bot,
one to play the client, and optionally one for the alerts. In the official app:

- **iPhone:** tap *Settings* 10 times quickly → *Accounts* → *Login to another account* →
  *Test*. Sign up with a test number (e.g. `9996621234`, code `22222`).
- **Telegram Desktop (Windows/Linux):** hold **Shift+Alt** and right-click *Add Account* →
  *Test Server*. **macOS app:** tap the Settings icon 10 times, then **⌘-click** *Add Account*.
  Telegram's guides say new test accounts can only be created on mobile, so you may need
  the phone for the sign-up and can then log in on desktop.
- **Telegram Web:** <https://web.telegram.org/?test=1>.

**Run the bot on the test servers:**

```bash
python -m userbot settings set TELEGRAM_TEST_SERVERS true
```

Then start the bot. It asks for a phone number: give the bot's test number, code `22222`.
This test login is stored separately (`sessions/userbot-test.session`), so your real
login stays as it is. The menu, the startup log and `doctor` say **TEST servers** while it's
on. From the "client" test account, message the bot's test account and play the script. Set
`HANDOFF_NOTIFY_CHAT` to the third test account's username (test accounts can set one too),
or leave it empty to get alerts in the bot account's Saved Messages.

Back to your real account: `python -m userbot settings set TELEGRAM_TEST_SERVERS false`.
*Log out of Telegram* only ends the login of the mode you're in: with test servers on, it logs
out the test account and your real login stays.

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

  It holds `settings.env` (made from `.env.example`), `prompts/`, `sessions/`, `logs/`,
  `version.json` (which version last ran, see [Updating testers](#updating-testers)) and, once a
  chat has been handed over to you, `paused_chats.json`. The default prompts are copied in on
  first run, and replaced only by *Restore the original prompts* or a version update (which
  keeps a backup).
- **`--home DIR` or `USERBOT_HOME=DIR`** picks any other folder, e.g. to test a fresh setup
  without touching your own.

---

## Sending it to testers

```bash
python3 scripts/build_bundle.py
```

This builds `dist/userbot-<version>-windows.zip`, `-macos.zip` and `-linux.zip` (18–44 MB
each). Send each tester the zip for their system, by Google Drive, WeTransfer or Telegram.
Each zip contains:

- **A launcher to double-click:** `Start Userbot.bat`, `Start Userbot.command` or `start.sh`.
- **The tester guide:** [docs/TESTERS.md](docs/TESTERS.md), as `TESTER-GUIDE.md`.
- **The app:** code, prompts, and the exact library versions from `uv.lock`.
- **[uv](https://docs.astral.sh/uv/):** on the tester's first start it downloads Python 3.13
  and the libraries into the bundle's own `runtime/` folder. Nothing is installed
  system-wide.

Things to know:

- **Your own data never goes into a bundle.** The script only packs an explicit list of files
  and refuses to include `.env`, `sessions/` or `*.session`.
- **The default prompts testers get are the repository's `prompts/` files.**
- **Before sending a new version,** bump the version in `userbot/__init__.py` and
  `pyproject.toml` (the script checks that they match), and add what changed to
  [CHANGELOG.md](CHANGELOG.md).
- **The first build downloads the pinned uv binaries** (checked against their SHA-256) into
  `dist/.cache/`. It also refreshes `uv.lock` when `pyproject.toml` changed; commit that.
- **Building on GitHub,** single-file executables and code signing are planned separately in
  [docs/plan-github-builds.md](docs/plan-github-builds.md).

### Updating testers

Testers unzip the new version into a new folder and start it as before. Their settings,
prompts and Telegram login live in the data folder, so nothing has to be set up again, and
Ollama and the model are not downloaded again. (Python and the libraries, about 30 MB, are
downloaded once more into the new folder.)

On the first start of a newer version, the bot (`userbot/updates.py`):

1. **Updates the settings file.** Settings that are new in `.env.example` are added with their
   explanation. A setting the tester never changed gets the new default (e.g. the old 3 s
   delay becomes 180 s). Values they changed themselves are kept. The old file is saved as
   `settings.env.before-<new version>` (`.env.before-<new version>` when running from the
   repository).
2. **Updates the prompts** that changed in this version. If the tester had edited theirs, their
   copy is saved as `prompts/backup/<name>-<old version>.txt` first. (Coming from 0.1.0 there's
   no record of the shipped prompt, so any copy that differs from the new one is saved.) A
   prompt that didn't change in this version is left alone, edited or not.
3. **Shows a one-time notice:** "Updated to X (from Y)", the new entries of `CHANGELOG.md`,
   every setting that was added or changed, and which prompts were replaced and where the old
   copies are. It also reminds them to set `HANDOFF_NOTIFY_CHAT` if it was just added empty,
   and warns if their active prompt is no longer included (e.g. `busy.txt`).

`version.json` in the data folder records the version, the template's defaults and a
fingerprint of each shipped prompt, so the next update knows what the tester changed. Data
folders from 0.1.0 don't have it; for those the bot uses the 0.1.0 defaults built into
`updates.py`. Running from the repository works the same way on your `.env` (writing
`version.json` and `.env.before-<version>` to the repository folder, both gitignored), except
that the prompts are never touched there.

---

## Project structure

```
telegram-bot/
├── userbot/
│   ├── __main__.py      # Entry point: python -m userbot
│   ├── cli.py           # Commands (Typer); no command = the menu
│   ├── menu.py          # Interactive menu
│   ├── setup_wizard.py  # First-run setup: API ID/hash, Ollama + model, prompt, alert account, login
│   ├── updates.py       # Brings settings and prompts up to date after a new version
│   ├── actions.py       # What the menu and the commands do (shared)
│   ├── bot.py           # Runs the userbot; Telegram login/logout
│   ├── paths.py         # The data folder (settings, prompts, sessions, logs)
│   ├── config.py        # Reads/writes the settings file + environment variables
│   ├── ollama_setup.py  # Finds/installs/starts Ollama, recommends and downloads models
│   ├── doctor.py        # `doctor`: checks everything and suggests fixes
│   ├── ui.py            # Terminal output, logging, opening files/folders
│   ├── commands.py      # @command decorator + wiring into Telethon
│   ├── autoreply.py     # Auto-reply to incoming private messages (delay, history, photos, fallback)
│   ├── handoff.py       # [[HANDOFF]] marker, paused chats, alerts, remote resume/pause
│   ├── humanize.py      # Removes markdown and adds typos to AI replies
│   ├── llm.py           # Talks to the local model through Ollama; reloads the prompt on change
│   ├── playground.py    # Terminal chat with the AI for testing (python -m userbot chat)
│   └── handlers/
│       ├── __init__.py  # Imports handler modules so their commands register
│       ├── basic.py     # .ping, .id, .help
│       └── handoff.py   # .pause, .resume, .paused
├── prompts/
│   └── chat.txt         # Default: the Reddit promotion sales script
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
├── CHANGELOG.md         # What changed per version (shown to testers after an update)
├── CLAUDE.md            # Working notes for Claude Code (keep docs in sync, release steps)
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
   from . import basic, fun, handoff  # noqa: F401
   ```

3. Restart the userbot and send `.shout hello`.

Useful things available on `event`: `event.edit(...)`, `event.reply(...)`, `event.delete()`,
`event.chat_id`, `await event.get_reply_message()`, and `event.client` (the full
`TelegramClient`, e.g. `await event.client.send_message("me", "hi")`).

### Reacting to other people's messages (your own handlers)

The `@command` helper only listens to *your* messages. To react to incoming messages in other
ways, add a plain Telethon handler. For example, in `run_bot()` in `userbot/bot.py`, after
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
| `Missing required setting(s): API_ID, API_HASH` | Run `python -m userbot setup`, or create `.env` from `.env.example` and fill them in. |
| `ApiIdInvalidError` | `API_ID`/`API_HASH` are wrong. Copy them again from my.telegram.org. |
| `PhoneNumberInvalidError` | Use international format with `+` and the country code. |
| Login code never arrives | Look in the Telegram app (the "Telegram" service chat), not SMS. |
| `FloodWaitError` | You're rate-limited. Wait the number of seconds it says. |
| `AuthKeyDuplicatedError` / session errors | The same session file was used from two places at once. Delete the `.session` file and log in again. |
| Commands do nothing | Check the prefix, that the command is the whole message, and that it was sent from the logged-in account. |
| `LLM not ready: cannot reach Ollama` | Open the Ollama app (menu-bar llama icon), or run `python -m userbot doctor`. Check `curl http://localhost:11434/api/version`. |
| `LLM not ready: model ... is not downloaded` | `python -m userbot model pull`, or the `ollama pull ...` command it prints. |
| Replies are always `brate radim` | Look for warnings in the terminal. Also check `LLM_ENABLED` and `LLM_ALLOWED_CHATS`. |
| `No reply from ... within 60s` | The Mac is short on memory or busy. Close apps, use `qwen3.5:4b`, or raise `LLM_TIMEOUT`. |
| AI answers in the wrong language | Set `LLM_REPLY_LANGUAGE` in `.env` (e.g. `English`) and restart. See [Reply language](#reply-language). |
| AI makes up prices or promises | Make sure the answer is in the `<facts>` section of `prompts/chat.txt`. It's told to use only those. |
| Prompt changes in the repository don't show up for a tester | Testers get them with the next **version**: bump the version and add a `CHANGELOG.md` entry, then build. Without a version bump, the update doesn't run; they can use *Prompts → Restore the original prompts*. |
| A tester lost their prompt edits after an update | Their old copy is in `prompts/backup/` in the data folder (`<name>-<old version>.txt`). |
| A setting changed after an update | Only settings the tester never changed get new defaults. The previous file is `settings.env.before-<version>` next to `settings.env`. |
| Login fails with "can't create" / sign-up on test servers | The test number has no account yet. Create it once in the official app's test mode (see [D. Telegram test servers](#d-telegram-test-servers-no-real-account)), then log in. |
| Test-server login says the code is wrong | It's always `22222`. Telegram changed code lengths before; if it's rejected, try `222222`. |
| No handoff alert arrives | Check the startup log for `Handoff alerts go to ...`. If `HANDOFF_NOTIFY_CHAT` wasn't found, alerts go to your Saved Messages. Use an `@username`. Test the trigger in the playground. |
| The bot doesn't reply in one chat | It may be paused (handed over to you). Send `.paused` in Saved Messages to check, `.resume <chat id>` to continue. |
| Replies take minutes | That's `AUTO_REPLY_DELAY` / `AUTO_REPLY_DELAY_MAX` (3–10 minutes in the settings file you start with). Set `AUTO_REPLY_DELAY_ENABLED=false` while testing. |
| AI talks about a photo it can't see | The model can't read images (the log says so at startup). Use `qwen3.5`, or set `LLM_VISION=false`. |
| AI replies sound off | Edit the prompt (tone, how you write, example phrases), test in the playground, or try another model. |
| Not sure what's wrong | `python -m userbot doctor` checks settings, test servers, the prompt (and its handoff rule), the reply delay, where alerts go, Ollama, the model, memory and the login. |

## Useful links

- Telethon docs: <https://docs.telethon.dev/en/stable/>
- Telethon client method reference: <https://docs.telethon.dev/en/stable/modules/client.html>
- Event types (NewMessage, MessageEdited, ChatAction, ...): <https://docs.telethon.dev/en/stable/modules/events.html>
- Raw Telegram API reference: <https://tl.telethon.dev/>
- Ollama: <https://ollama.com> · model library: <https://ollama.com/library>
- Ollama Python client: <https://github.com/ollama/ollama-python>
