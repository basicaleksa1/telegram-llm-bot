# Plan: packaging the userbot for Windows, macOS and Linux

> **Status: implemented** on branch `feature/package-app`. The macOS bundle has been tested from
> a fresh unzip (first start, setup wizard, menu, AI chat). The Windows and Linux bundles are built
> the same way but haven't been run on a real Windows/Linux machine yet. The tester guide is
> [TESTERS.md](TESTERS.md).

## Decisions

| Topic | Decision |
|---|---|
| How it's sent to testers | **A zip built on your laptop** with one command, sent however you like (Google Drive, WeTransfer, Telegram). Building on GitHub is a separate, later plan: [plan-github-builds.md](plan-github-builds.md). |
| How the LLM gets installed | **Ollama, set up automatically.** The app installs Ollama (after asking) and downloads the model with a progress bar. |
| Testers' machines | **Mixed / unknown.** The app recommends a model based on the RAM and GPU it detects. |
| Telegram API_ID / API_HASH | **Each tester makes their own.** The setup wizard walks them through it; [TESTERS.md](TESTERS.md) has the step-by-step guide. |
| Prompts | **A plain text script that's passed to the model as-is.** The wizard doesn't ask "about you" questions. Testers edit the script directly. |
| Code signing | **None for now.** Testers get past the security warning once ([TESTERS.md](TESTERS.md), step 3). |

---

## Why a zip with a launcher instead of a single .exe

A single executable (PyInstaller) has to be **built on each OS**. A Mac can't build a Windows `.exe`. Since the bundle has to come from your laptop, I'd use a different approach that gives testers the same experience.

The tester unzips a folder and double-clicks **one file**:

| OS | File to double-click |
|---|---|
| Windows | `Start Userbot.bat` |
| macOS | `Start Userbot.command` |
| Linux | `start.sh` |

The launcher uses [uv](https://docs.astral.sh/uv/), a single small program included in the zip. **On first start it downloads Python 3.13 and the libraries (~30 MB download) into the folder itself.** Nothing is installed system-wide, and deleting the folder removes it all. Later starts take about a second.

- **One command on your Mac builds zips for all three OSes:** `python scripts/build_bundle.py`.
- **The zips are small (18–44 MB),** so they're easy to send.
- **Prompts are plain text files,** easy to find and edit.
- **The single-executable approach is still possible later** via GitHub's Windows, macOS and Linux build machines (see [plan-github-builds.md](plan-github-builds.md)).

The model is **not** inside the zip (it's 1–8 GB). Ollama downloads it once on first setup.

---

## What the tester experiences

1. Unzip, then double-click the launcher. Get past the OS security warning once.
2. **First start:** the launcher downloads Python and the libraries automatically, then offers the **setup wizard** (5 steps):
   1. **Telegram API ID and hash.** It explains where to get them, offers to open my.telegram.org, and checks the format.
   2. **The local AI.** It detects Ollama and starts it if it isn't running. If it's missing, it installs it after asking (Windows/macOS) or shows the one command to run (Linux). Then it detects RAM and GPU, recommends a model, and downloads it with a progress bar.
   3. **Prompt.** Choose which prompt file to use, with an option to open it in an editor right away.
   4. **Handoff alerts.** Which Telegram account gets the alert when the AI hands a chat over (added in 0.2.0).
   5. **Telegram login.** Phone, the code from the Telegram app, and the 2FA password if set.
3. **After setup, a menu.** Later starts open it directly:

```
 Telegram Userbot  0.1.0
 Data folder       ~/Library/Application Support/TelegramUserbot
 Telegram          login saved
 AI model          qwen3.5:4b ✓
 Prompt            chat.txt

 ? What do you want to do?
 » Start the bot
   Test the AI here in the terminal (playground)
   Prompts: edit / switch / create
   Settings
   AI model
   Check everything (doctor)
   Run setup again
   Open data folder
   Log out of Telegram
   Quit
```

---

## Phase 1: Make the app work outside the repo

- **New `userbot/paths.py`** resolves a **data folder** per user:

  | OS | Data folder |
  |---|---|
  | Windows | `%APPDATA%\TelegramUserbot\` |
  | macOS | `~/Library/Application Support/TelegramUserbot/` |
  | Linux | `~/.local/share/TelegramUserbot/` |

  - `USERBOT_HOME` or `--home DIR` overrides it.
  - **Dev mode:** if the repo has a `.env`, the repo itself is the data folder. Your current `.env`, `sessions/` and `prompts/` keep working unchanged.
- **Data folder layout:**

  ```
  TelegramUserbot/
  ├── settings.env        # same KEY=VALUE format as .env (created from .env.example)
  ├── prompts/            # chat.txt (+ any you add); copied on first run, replaced only by "Restore" or a version update
  ├── sessions/           # Telegram login, private
  ├── logs/userbot.log    # rotating, for bug reports. Reply text is only logged at DEBUG level
  ├── version.json        # which version last ran (added in 0.2.0, for updates)
  └── paused_chats.json   # chats the AI handed over to you (added in 0.2.0)
  ```

- **The data folder survives updates.** A tester unzips a new version, and their settings, prompts and login are still there. Since 0.2.0, the first start of a newer version also brings their settings and the shipped prompts up to date and tells them what changed (see the README, *Updating testers*).
- **The repo's `prompts/` folder stays the source of the default prompts,** so prompts you tune in the repo are what testers get.
- **Config reloads from the file each time** (no more `os.environ` caching), so changing settings from the menu takes effect on the next start.
- **Prompt hot-reload:** the prompt file is re-read when it changes. Testers edit and save, and the next reply uses the new version, both in the bot and in the playground.

## Phase 2: A friendlier command-line interface

- **Libraries:** Typer for commands, Rich for colours, tables and progress bars, questionary for arrow-key menus.
- **No arguments opens the interactive menu.** That's what the launcher does.
- **Subcommands for scripting and power users:**

  ```
  userbot start | chat | setup | doctor | login | logout | folder | --version
  userbot prompt list | use <name> | edit [name] | show | new <name> | reset
  userbot settings show | set KEY VALUE | edit
  userbot model list | recommend | use <model> | pull [model]
  ```

  Through the launcher: `./start.sh doctor`, `"Start Userbot.bat" settings show`, and so on.
- **Ctrl+C** stops the bot and returns to the menu.
- **Settings menu:** pick a setting, see its explanation and current value, and enter a new one. It's validated, and an invalid value is rejected.
- **Prompts menu:** switch the active prompt, edit it in the system editor, create a new one from a copy, open the prompts folder, or restore the defaults.
- **Playground:** `/prompt <name>` switches prompts mid-conversation, `/reset` and `/quit` work as before, and edits to the prompt apply on the next message.
- **Doctor:** a ✓ / ! / ✗ table covering settings, the prompt, Ollama, the model, memory and the Telegram login, with a fix for each problem.
- **Logout:** ends the session on Telegram's side and deletes the session file.
- **Windows:** UTF-8 console output (Serbian characters, emoji), and the window stays open on errors.

## Phase 3: Automatic Ollama and model setup (`userbot/ollama_setup.py`)

- **Detect Ollama:** via the API, then via the binary in known install locations.
- **Start Ollama if it isn't running:** open the app on macOS and Windows, or run `ollama serve` in the background on Linux.
- **Install it if missing, after asking:**
  - **Windows:** download and run the official `OllamaSetup.exe` (per-user, no admin rights).
  - **macOS:** download the official app and install it to Applications.
  - **Linux:** show the official install command and offer to run it (it asks for the tester's password).
- **Model recommendation:**

  | Machine | Model | Download |
  |---|---|---|
  | Apple Silicon with 16 GB or more, or an NVIDIA GPU with 10 GB or more | `qwen3.5:9b` | ~8 GB |
  | 12 GB or more RAM, or an NVIDIA GPU with 5 GB or more | `qwen3.5:4b` | ~4 GB |
  | 8 GB or more RAM | `qwen3.5:2b` | ~3 GB |
  | Less | `qwen3.5:0.8b` (weak, but it runs) | ~1 GB |

  The tester can pick any model, including one they've already downloaded.
- **Download with a progress bar.** Check free disk space first.

## Phase 4: The tester bundle (`scripts/build_bundle.py`)

- **Builds three zips into `dist/`:** `userbot-<version>-windows.zip`, `-macos.zip` and `-linux.zip`.
- **Each zip contains** the launcher, `TESTER-GUIDE.md`, the app code and prompts, and the uv binary for that OS. The macOS and Linux zips include both Intel and ARM builds, and the launcher picks the right one.
- **Pinned uv version** (≥ 2 weeks old), downloaded from uv's official GitHub releases and **checked against the published SHA-256**.
- **Safety:** files are taken from an explicit allowlist. The build **refuses** to include `.env`, `sessions/` or `*.session`, so your own login can never end up in a zip.
- **`uv.lock`** pins the exact library versions, so every tester gets the same ones.
- **Smoke test (done):** the macOS bundle was unzipped and run on the Mac, including the first-start download (~10 s), the setup wizard, the menu and the playground.

## Phase 5: Documentation

- **`docs/TESTERS.md`:** a step-by-step tester guide, focused on everything that has to be done online. It's also included in each zip as `TESTER-GUIDE.md`.
- **`README.md`:** the new CLI, the data folder, and how to build and send a bundle.

---

## What you have to do (online or otherwise) to send a version

1. **Update the version** in `userbot/__init__.py` and `pyproject.toml` (the build script checks they match), and add what changed to `CHANGELOG.md`: testers see those lines after updating.
2. **Build the zips:**

   ```bash
   python scripts/build_bundle.py
   ```

   The first time, it downloads the uv binaries (~90 MB, five platforms) from GitHub into `dist/.cache/`.
3. **Upload the zip(s)** to Google Drive, Dropbox or WeTransfer, or send them directly in Telegram (it allows files up to 2 GB). Send each tester the zip for their OS plus a link to the guide; the guide is also inside the zip.
4. **That's all.** No accounts, signing or GitHub setup needed for now.

Everything a tester does online is in [TESTERS.md](TESTERS.md).

---

## Not in this plan

- **Building and releasing on GitHub, single-file executables and code signing:** see [plan-github-builds.md](plan-github-builds.md).
- **Asking "about you" questions:** the prompt is a plain script that testers edit themselves.
