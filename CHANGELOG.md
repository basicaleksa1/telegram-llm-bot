# Changelog

What changed in each version. The bot shows the new entries once, the first
time a tester starts a newer version.

## 0.2.0

- The AI follows a sales script for a Reddit promotion service and looks at the photos clients send.
- At the key point (no Reddit accounts and no supplier, or "are you a bot?") it stops and hands the chat to you: the client gets a short holding message and you get an alert on Telegram.
- Reply "resume" to an alert, or send .resume, to let the AI continue in that chat. .pause and .paused are new too.
- Replies wait a random 3–10 minutes and contain small typos, so they read like a person typing. AUTO_REPLY_DELAY_ENABLED=false makes replies come within seconds while testing.
- If you reply to someone yourself while the bot is waiting to answer, the bot no longer replies too.
- The setup asks which Telegram account should get the handoff alerts.
- New setting TELEGRAM_TEST_SERVERS: try the bot on Telegram's test servers with a test account.
- Updates like this one now bring your settings and prompt up to date automatically.

## 0.1.0

- First tester version: AI auto-reply with a local model, a menu, setup wizard and playground.
