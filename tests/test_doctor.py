import asyncio

import pytest

from userbot import doctor, ollama_setup
from userbot.doctor import FAIL, OK, WARN, run_checks
from userbot.handoff import PausedChats
from userbot.paths import Home


@pytest.fixture
def home(tmp_path, monkeypatch):
    async def not_running(host, timeout=3.0):
        return False

    # Keep the checks offline and independent of this machine.
    monkeypatch.setattr(ollama_setup, "is_running", not_running)
    monkeypatch.setattr(ollama_setup, "find_ollama", lambda: None)
    monkeypatch.setattr(
        ollama_setup, "detect_hardware", lambda: ollama_setup.Hardware(ram_gb=16, apple_silicon=True, nvidia_vram_gb=None)
    )
    home = Home(tmp_path)
    home.prompts_dir.mkdir()
    (home.prompts_dir / "chat.txt").write_text("You are {name}. [[HANDOFF]] when stuck.")
    return home


def checks_for(home, settings=""):
    home.settings_file.write_text("API_ID=1\nAPI_HASH=abc\n" + settings)
    return {c.name: c for c in asyncio.run(run_checks(home, online=False))}


def test_prompt_with_handoff_rule_has_no_warning(home):
    checks = checks_for(home)

    assert checks["Prompt"].status == OK
    assert "Handoff rule" not in checks


def test_prompt_without_handoff_rule_warns(home):
    (home.prompts_dir / "chat.txt").write_text("You are {name}.")

    assert checks_for(home)["Handoff rule"].status == WARN


def test_reply_delay_off_warns(home):
    check = checks_for(home, "AUTO_REPLY_DELAY_ENABLED=false\n")["Reply delay"]

    assert check.status == WARN
    assert "true" in check.fix


def test_reply_delay_range_is_shown(home):
    check = checks_for(home, "AUTO_REPLY_DELAY=180\nAUTO_REPLY_DELAY_MAX=600\n")["Reply delay"]

    assert check.status == OK
    assert "180-600" in check.detail


def test_handoff_target_and_paused_chats_are_shown(home):
    PausedChats(home.root / "paused_chats.json").pause(42)

    check = checks_for(home, "HANDOFF_NOTIFY_CHAT=@my_alt_account\n")["Handoff"]

    assert "@my_alt_account" in check.detail
    assert "1 chat(s) paused" in check.detail


def test_missing_ollama_fails(home):
    assert checks_for(home)["Ollama"].status == FAIL


def test_login_check_without_saved_login_warns(home):
    assert checks_for(home)["Telegram login"].status == WARN


def test_print_checks_does_not_crash(home, capsys):
    doctor.print_checks(list(checks_for(home).values()))


def test_test_servers_are_flagged(home):
    check = checks_for(home, "TELEGRAM_TEST_SERVERS=true\n")["Telegram servers"]

    assert check.status == WARN
    assert "false" in check.fix


def test_real_servers_are_not_mentioned(home):
    assert "Telegram servers" not in checks_for(home)
