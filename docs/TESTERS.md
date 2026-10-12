# Telegram Userbot: tester guide

This program logs in as **your own Telegram account**. When someone sends you a private message, an AI running **on your computer** writes a reply for you. These steps walk you through everything that has to be set up, most of it online, in the order you'll need it.

Expect about **30–60 minutes** the first time, most of it spent waiting for downloads.

---

## Overview: everything that happens online

| # | What | Where | How long | When |
|---|---|---|---|---|
| 1 | Get your Telegram **API ID and hash** | my.telegram.org | 5 min | once |
| 2 | Download the **bot zip** | link from the developer | 1 min | each new version |
| 3 | **Python and libraries** (~30 MB) | downloaded automatically on first start | 1–3 min | first start of each version |
| 4 | Install **Ollama**, the program that runs the AI | ollama.com, installed automatically or by hand | 2–10 min | once |
| 5 | Download the **AI model** (1–8 GB) | automatic, from ollama.com | 5–30 min | once per model |
| 6 | **Log in to Telegram** with a code | the Telegram app | 2 min | once |
| 7 | **End the session** when you stop testing | the Telegram app | 1 min | at the end |

After this first setup, the bot only needs internet for Telegram itself.

---

## Before you start

You need:

- **A Telegram account** and access to the Telegram app (phone or desktop) to receive login codes.
- **A computer** with:
  - Windows 10 (version 22H2 or newer) or Windows 11, 64-bit
  - or macOS 14 (Sonoma) or newer
  - or a 64-bit Linux
  - at least **8 GB of RAM** (16 GB is better)
  - about **10 GB of free disk space**
- **A stable internet connection**, ideally Wi-Fi, for the downloads.

> ⚠️ **Read this once.** While the bot runs, **the AI answers real people as you**. It is told not to make promises or share private information, but small AI models sometimes say odd things. You can limit it to a few chats (see [Settings worth knowing](#settings-worth-knowing)). Your login is stored on your computer only. Never send anyone the `sessions` folder.

---

## Step 1: Get your Telegram API ID and hash (online, once)

Telegram requires every program that logs in to an account to have an "API ID". It's free and takes a few minutes. You'll paste the two values into the bot's setup in step 4.

1. Open **<https://my.telegram.org>** in a browser (a computer is easiest).
2. Enter **your phone number** in international format, for example `+381601234567`, and click **Next**.
3. Telegram sends a **confirmation code to your Telegram app**, as a message from the "Telegram" account. **It is not an SMS.** Type it into the website and click **Sign In**.
4. Click **API development tools**.
5. Fill in the form:
   - **App title:** anything, for example `My Userbot`
   - **Short name:** 5–32 letters and numbers, no spaces, for example `myuserbot2026`
   - **URL:** leave empty
   - **Platform:** choose **Desktop**
   - **Description:** leave empty
6. Click **Create application**.
7. You now see **App api_id** (a number like `1234567`) and **App api_hash** (32 letters and numbers like `0123456789abcdef0123456789abcdef`). **Keep this page open, or copy both values somewhere safe.** You'll need them in step 4.

**If the form only says "ERROR":**
- turn off VPN and ad blockers
- try another browser or a private/incognito window
- try a different, more unusual short name
- wait an hour and try again

**If you already created an app before,** the page just shows your existing values. Use those.

> 🔒 Treat the api_id and api_hash like a password: don't post or share them.

---

## Step 2: Download and unzip the bot

1. Download the zip **for your system** from the link the developer sent you:
   - Windows: `userbot-<version>-windows.zip`
   - macOS: `userbot-<version>-macos.zip`
   - Linux: `userbot-<version>-linux.zip`
2. **Unzip it** into a normal folder, such as Documents. The result is a folder called `TelegramUserbot`.
   - **Windows:** right-click the zip → **Extract All…** → **Extract**. Don't run the bot from inside the zip without extracting it.
   - **macOS:** double-click the zip.
   - **Linux:** `unzip userbot-*-linux.zip`

---

## Step 3: Start it, and get past the security warning (once)

The bot isn't signed by Apple or Microsoft, so your computer warns you the first time. That's expected.

### Windows
1. Open the `TelegramUserbot` folder and double-click **`Start Userbot.bat`**.
2. If **"Windows protected your PC"** appears, click **More info**, then **Run anyway**.
3. If **"Open File – Security Warning"** appears, click **Run**.

### macOS
1. Open the `TelegramUserbot` folder and double-click **`Start Userbot.command`**.
2. macOS says it **can't be opened** or **can't verify the developer**. Click **Done** or **OK**, not "Move to Trash".
3. Open **System Settings → Privacy & Security** and scroll down. Next to *"Start Userbot.command" was blocked*, click **Open Anyway**. Confirm with your Mac password or Touch ID, then click **Open Anyway** again.
4. A Terminal window opens. If you're asked whether Terminal may access your Downloads or Documents folder, click **Allow**.

### Linux
In a terminal:
```bash
cd TelegramUserbot
chmod +x start.sh
./start.sh
```

### First start (online, automatic)
A text window opens and shows *"First start: downloading Python and the bot's libraries…"*. **This needs internet and takes up to a few minutes, once.** Then the setup offers to start: answer **y**.

---

## Step 4: The setup

The setup has 4 steps; the screen shows *Step 1 of 4*, *Step 2 of 4*… and they match 4.1–4.4 below. Use the **arrow keys** and **Enter** to choose, and **y/n** for yes/no questions. You can stop at any point with **Ctrl+C**. The setup can be run again later from the menu (**Run setup again**).

### 4.1 Telegram API ID and hash
Paste the **App api_id** and **App api_hash** from step 1:
- **Windows:** right-click in the window to paste.
- **macOS:** ⌘V.
- **Linux:** Ctrl+Shift+V.

### 4.2 The local AI (online, once)
This step installs Ollama and downloads an AI model.

**Ollama** is a free program that runs the AI model on your computer. Your messages never go to a cloud AI.

**The setup installs it for you if you answer *yes*:**

- **Windows:** it downloads Ollama's official installer (~1.6 GB) and opens it. Click through it (**Install**). No administrator rights are needed. Afterwards a small llama icon appears in the taskbar tray.
- **macOS:** it downloads the Ollama app (~200 MB) into **Applications** and opens it. Ollama may show a welcome window. You can close it, but **keep Ollama running** (llama icon in the menu bar). If it offers to install the "command line tool", that's optional.
- **Linux:** it shows this command and offers to run it. It asks for your computer password.
  ```bash
  curl -fsSL https://ollama.com/install.sh | sh
  ```

**Prefer to install it yourself?** Download it from **<https://ollama.com/download>**, install it, start it, then run the setup again.

> Ollama must be running whenever the bot runs. On Windows and macOS it normally starts automatically with your computer. If not, open the Ollama app. The bot also tries to start it for you.

**The AI model.** Once Ollama runs, the setup looks at your computer's memory and graphics card and **recommends a model**. Press Enter to accept it, or pick another:

| Model | Download | Suitable for |
|---|---|---|
| qwen3.5:9b | ~8 GB | Apple Silicon Mac with 16 GB+, or an NVIDIA GPU with 10 GB+. Best replies. |
| qwen3.5:4b | ~4 GB | Most computers with 12 GB+ RAM |
| qwen3.5:2b | ~3 GB | 8 GB computers. Faster, simpler replies. |
| qwen3.5:0.8b | ~1 GB | Weak computers. Basic replies. |

The download shows a progress bar and can take a while. If it gets interrupted, run it again and it **continues where it stopped**. You can switch models later in the menu under **AI model**.

### 4.3 Prompt
The **prompt** is a plain text file with instructions for the AI. It's sent to the model as-is. Two are included:
- **chat:** chats with people as you
- **busy:** says you're not around and will reply later

`{name}` in the prompt is replaced with your Telegram first name. You can edit the prompt at any time (see [Editing the prompt](#editing-the-prompt)).

> ✏️ **Before you start the bot, read the chat prompt** (answer *y* to "Open it in an editor now?").
> - Its *About {name}* lines (gender, where you live, work, interests, how you write) are **example details**. The AI tells people they're true about you, so replace them with your own, or delete what you don't want said.
> - Out of the box, **replies are always in English**. That's both the prompt and the setting `LLM_REPLY_LANGUAGE=English`; see [Settings worth knowing](#settings-worth-knowing) to change it.

### 4.4 Telegram login (online, once)
1. Enter **your phone number** in international format (`+381…`).
2. Telegram sends a **login code to your Telegram app**, as a message from "Telegram". Type it in.
3. If your account has **two-step verification**, enter that password. It isn't shown while you type.
4. Your Telegram apps show a **"new login"** notification. The session appears under **Settings → Devices** with the **App title** you chose in step 1 (e.g. *My Userbot*) on the device *Telegram Userbot*. That's this program.

**The login is saved on your computer**, so you won't be asked again.

---

## Step 5: Use it

After the setup you see the **menu**. Next time you double-click the launcher, it opens directly:

```
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

- **Test the AI here in the terminal (playground):** chat with the AI without Telegram. You play the friend who messages you. This is the best way to try out prompt changes.
  - `/prompt busy` switches to another prompt.
  - `/reset` starts over.
  - `/quit` goes back to the menu.
- **Start the bot:** the bot now answers private messages. Leave the window open; **Ctrl+C** stops the bot and returns to the menu.
  - **Quick test:** in Telegram, open **Saved Messages** and send `.ping`. It turns into `pong (… ms)`.
  - Then ask a friend to message you. After a few seconds they see "typing…" and get a reply.
- **Check everything (doctor):** if something doesn't work, start here. It lists every problem with a hint on how to fix it.

**What the bot doesn't answer:** groups, channels and bots. It only replies in private chats. Your own messages are never answered.

**The computer has to stay on and awake** while the bot runs. A sleeping laptop doesn't reply.

---

## Editing the prompt

1. Menu → **Prompts** → **Edit the active prompt**. The file opens in Notepad (Windows), TextEdit (macOS) or your text editor (Linux).
2. Change the text and **save**.
3. **That's it.** The next reply uses the new version, in the running bot and in the playground. No restart needed.

Other options in **Prompts**:
- **Switch to another prompt** (chat ↔ busy). Restart the bot afterwards if it's running.
- **Create a new prompt:** a copy of the current one under a new name, so you can experiment without losing the original.
- **Restore the original chat/busy prompts** if an edit went wrong.

Tips:
- **Write how you text,** e.g. *"lowercase, short, often says 'brate'"*. The more the prompt says about how you write, the more natural the replies.
- **Anything in the prompt may end up in a reply to anyone.** Don't put secrets in it.

---

## Settings worth knowing

Menu → **Settings**. Pick a setting, read its explanation, and enter a new value. Restart the bot afterwards.

| Setting | What it does |
|---|---|
| `LLM_ALLOWED_CHATS` | **Only these chats get AI replies.** Everyone else gets the fixed text. Good for testing with one friend first. To find a chat's ID, start the bot and send `.id` in that chat: your message turns into "Chat ID: …" (the other person sees it too; delete it afterwards). |
| `AUTO_REPLY_TEXT` | The fixed text sent when the AI is off, not allowed for that chat, or fails. Default: `brate radim`. |
| `AUTO_REPLY_DELAY` | Seconds to wait for the person to stop typing before replying once. |
| `LLM_REPLY_LANGUAGE` | Forces replies into one language. **Default: `English`.** Empty = whatever the prompt says (the chat prompt also says English; edit its LANGUAGE and FINAL REMINDER lines too). |
| `AUTO_REPLY_ENABLED` | `false` turns off all automatic replies. |

---

## When you're done testing (online)

1. Menu → **Log out of Telegram**. This ends the session on Telegram's side and deletes the saved login from your computer.
2. **Double-check in Telegram:** **Settings → Devices** (Privacy and Security → Active sessions on some apps). If the session with your App title (device *Telegram Userbot*) is still listed, tap it and choose **Terminate session**.
3. **Optional: remove everything.**
   - Delete the `TelegramUserbot` folder.
   - Delete the data folder (shown in the menu under *Data folder*):
     - Windows: `%APPDATA%\TelegramUserbot`
     - macOS: `~/Library/Application Support/TelegramUserbot`
     - Linux: `~/.local/share/TelegramUserbot`
   - Uninstall Ollama like any other app. Its models are in `~/.ollama` (Windows: `%USERPROFILE%\.ollama`).
   - Your API ID and hash can stay: they do nothing without a login, and my.telegram.org has no button to delete them.

---

## Troubleshooting

| Problem | What to do |
|---|---|
| The window closes immediately (Windows) | Make sure you **extracted** the zip (step 2), not opened it. Start `Start Userbot.bat` again and read the message. |
| "First start" download fails | Check your internet connection and start again. Company or school networks sometimes block it; try another network. |
| macOS: "can't be opened" | See step 3, macOS: **System Settings → Privacy & Security → Open Anyway**. |
| my.telegram.org says "ERROR" | See step 1: VPN/ad blocker off, other browser, other short name. |
| Login code doesn't arrive | Look **in the Telegram app** (chat named "Telegram"), not in your SMS. |
| "API ID / hash rejected" | Copy both values again from my.telegram.org, then **Run setup again**. |
| "Ollama not running" | Open the Ollama app (llama icon). **Start the bot** and the playground also try to start it. If it's not installed, **Run setup again**. |
| The model download is slow or stops | Run it again (menu → **AI model**); it continues where it stopped. |
| Replies take a long time (30 s+) | The model is too big for your computer. Menu → **AI model**, and pick a smaller one. |
| The bot always sends the fixed text | Run **Check everything**. Usually Ollama isn't running, or the model isn't downloaded. |
| "FloodWait" message | Telegram is rate-limiting. Wait the number of seconds shown. |

---

## Sending feedback or a bug report

- **Send:** what you did, what happened (a copy or screenshot of the text in the window helps), and the file **`logs/userbot.log`** from the data folder (menu → **Open data folder**). By default it doesn't contain the text of messages.
- **Never send** the `sessions` folder or the `settings.env` file. They contain your login and API keys.
