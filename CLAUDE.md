# Notes for Claude

Telegram userbot (Telethon) that auto-replies with a local LLM (Ollama), shipped to testers
as zips built by `scripts/build_bundle.py`.

## Always update the docs with the code

Every change that affects behaviour, settings, commands, the menu, the setup, the prompt or
packaging must update the docs **in the same change**. Not as a follow-up, and without being
asked. Before calling a change done, search the docs for anything it makes wrong (old step
counts, old defaults, removed files, "doesn't do X" sentences) and fix those too.

Where things are documented:

| Doc | Audience | Update it when |
|---|---|---|
| `README.md` | the developer | almost always: features, settings table, how to test, troubleshooting, project structure |
| `docs/TESTERS.md` | testers (shipped in the zip as `TESTER-GUIDE.md`) | anything a tester sees: setup steps, menu, settings worth knowing, updating, troubleshooting. Plain language, no code |
| `.env.example` | template for new settings files, with a comment per setting | adding, removing or changing a setting or its default |
| `CHANGELOG.md` | shown to testers once after they update | every change a tester would notice, under the upcoming version |
| `prompts/chat.txt` | the AI | when the code expects something from the prompt (e.g. the `[[HANDOFF]]` marker) |
| `docs/packaging-plan.md`, `docs/plan-github-builds.md` | record of past/future plans | only to correct facts that are now wrong |

Also keep in sync: `EDITABLE_SETTINGS` help texts in `userbot/config.py` (shown in the
Settings menu) and in-app texts in `setup_wizard.py`, `menu.py` and `doctor.py`.

After editing docs, check that intra-doc links (`](#anchor)`) still point at existing headings.

## Settings and versions

- A new setting needs: a `Config` field + parsing in `config.py`, an `EDITABLE_SETTINGS`
  entry, an entry with a comment in `.env.example`, a row in the README settings table, tests
  in `tests/test_config.py`.
- Testers' data folders are updated by `userbot/updates.py` on the first start of a newer
  version: new settings from `.env.example` are added, untouched defaults updated, changed
  shipped prompts replaced (with a backup). That only happens when the version number goes up.
- To release a version: bump `userbot/__init__.py` and `pyproject.toml` (they must match),
  add a `CHANGELOG.md` section, refresh `uv.lock`, then build.

## Checks

```bash
.venv/bin/python -m pytest -q
```

Tests are offline (fakes for Telegram and Ollama). Add tests with every change.
