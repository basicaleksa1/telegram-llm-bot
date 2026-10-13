import json

import pytest
from dotenv import dotenv_values

from userbot import __version__, updates
from userbot.paths import DEFAULT_PROMPTS_DIR, Home, ensure_home
from userbot.updates import LEGACY_DEFAULTS, apply_updates, changelog_since, show_notice, version_tuple

NEW_PROMPT = (DEFAULT_PROMPTS_DIR / "chat.txt").read_text()


def legacy_home(tmp_path, **changes):
    """A data folder as 0.1.0 left it: its settings file, prompts, and no version.json."""
    home = Home(tmp_path / "data")
    home.prompts_dir.mkdir(parents=True)
    values = {**LEGACY_DEFAULTS, "API_ID": "123", "API_HASH": "abc", **changes}
    home.settings_file.write_text("".join(f"{key}={value}\n" for key, value in values.items()))
    (home.prompts_dir / "chat.txt").write_text("Old chat prompt for {name}.")
    (home.prompts_dir / "busy.txt").write_text("Busy {name}.")
    return home


def settings(home):
    return dotenv_values(home.settings_file)


# --- Fresh installs and repeated starts ------------------------------------------


def test_fresh_install_gets_no_notice_but_records_the_version(tmp_path):
    home = Home(tmp_path / "data")
    ensure_home(home)

    assert apply_updates(home, first_run=True) is None
    assert json.loads((home.root / "version.json").read_text())["version"] == __version__


def test_second_start_of_the_same_version_does_nothing(tmp_path):
    home = legacy_home(tmp_path)
    assert apply_updates(home, first_run=False) is not None

    assert apply_updates(home, first_run=False) is None


def test_older_app_on_a_newer_data_folder_changes_nothing(tmp_path):
    home = legacy_home(tmp_path)
    (home.root / "version.json").write_text(json.dumps({"version": "99.0.0"}))
    before = home.settings_file.read_text()

    assert apply_updates(home, first_run=False) is None
    assert home.settings_file.read_text() == before


# --- Settings -------------------------------------------------------------------


def test_new_settings_are_added_with_their_template_values(tmp_path):
    home = legacy_home(tmp_path)

    notice = apply_updates(home, first_run=False)

    values = settings(home)
    assert values["AUTO_REPLY_DELAY_MAX"] == "600"
    assert values["LLM_TYPO_RATE"] == "0.03"
    assert values["HANDOFF_CLIENT_MESSAGE"].startswith("okay let me check")
    assert ("AUTO_REPLY_DELAY_MAX", "600") in notice.settings_added
    assert "Added by the" in home.settings_file.read_text()  # with the template's explanations


def test_unchanged_old_defaults_get_the_new_default(tmp_path):
    home = legacy_home(tmp_path)

    notice = apply_updates(home, first_run=False)

    assert settings(home)["AUTO_REPLY_DELAY"] == "180"
    assert ("AUTO_REPLY_DELAY", "3", "180") in notice.settings_changed


def test_values_the_tester_changed_are_kept(tmp_path):
    home = legacy_home(tmp_path, AUTO_REPLY_DELAY="10", LLM_MODEL="qwen3.5:4b", AUTO_REPLY_TEXT="zauzet sam")

    notice = apply_updates(home, first_run=False)

    values = settings(home)
    assert values["AUTO_REPLY_DELAY"] == "10"
    assert values["LLM_MODEL"] == "qwen3.5:4b"
    assert values["AUTO_REPLY_TEXT"] == "zauzet sam"
    assert values["API_ID"] == "123"
    assert all(key != "AUTO_REPLY_DELAY" for key, _, _ in notice.settings_changed)


def test_settings_are_backed_up_before_changing(tmp_path):
    home = legacy_home(tmp_path)
    before = home.settings_file.read_text()

    notice = apply_updates(home, first_run=False)

    assert notice.settings_backup.read_text() == before
    assert notice.settings_backup.name == f"settings.env.before-{__version__}"


def test_updated_settings_still_load(tmp_path):
    from userbot.config import load_config

    home = legacy_home(tmp_path)
    apply_updates(home, first_run=False)

    config = load_config(home=home)
    assert config.auto_reply_delay == 180
    assert config.auto_reply_delay_max == 600


def test_later_update_uses_the_recorded_defaults(tmp_path, monkeypatch):
    home = legacy_home(tmp_path)
    apply_updates(home, first_run=False)
    # Pretend the next version changes the typo default; the tester never touched it.
    monkeypatch.setattr(updates, "__version__", "0.3.0")
    defaults = {**updates.template_defaults(), "LLM_TYPO_RATE": "0.05"}
    monkeypatch.setattr(updates, "template_defaults", lambda: defaults)

    notice = apply_updates(home, first_run=False)

    assert ("LLM_TYPO_RATE", "0.03", "0.05") in notice.settings_changed


# --- Prompts --------------------------------------------------------------------


def test_old_prompt_is_replaced_and_kept_as_a_backup(tmp_path):
    home = legacy_home(tmp_path)

    notice = apply_updates(home, first_run=False)

    assert (home.prompts_dir / "chat.txt").read_text() == NEW_PROMPT
    [(name, backup)] = notice.prompts_updated
    assert name == "chat.txt"
    assert backup.read_text() == "Old chat prompt for {name}."
    assert backup.parent == home.prompts_dir / "backup"


def test_prompt_that_is_already_current_is_left_alone(tmp_path):
    home = legacy_home(tmp_path)
    (home.prompts_dir / "chat.txt").write_text(NEW_PROMPT)

    notice = apply_updates(home, first_run=False)

    assert notice.prompts_updated == []
    assert not (home.prompts_dir / "backup").exists()


def test_prompt_edited_after_an_update_is_not_overwritten_when_unchanged_upstream(tmp_path, monkeypatch):
    home = legacy_home(tmp_path)
    apply_updates(home, first_run=False)
    (home.prompts_dir / "chat.txt").write_text("My own edits.")
    monkeypatch.setattr(updates, "__version__", "0.3.0")

    notice = apply_updates(home, first_run=False)

    assert notice.prompts_updated == []
    assert (home.prompts_dir / "chat.txt").read_text() == "My own edits."


def test_unedited_prompt_is_updated_without_a_backup(tmp_path, monkeypatch):
    home = legacy_home(tmp_path)
    apply_updates(home, first_run=False)  # chat.txt is now exactly the shipped version
    monkeypatch.setattr(updates, "__version__", "0.3.0")
    monkeypatch.setattr(updates, "shipped_prompt_hashes", lambda: {"chat.txt": "a-newer-version"})

    notice = apply_updates(home, first_run=False)

    assert notice.prompts_updated == [("chat.txt", None)]


def test_retired_active_prompt_is_mentioned(tmp_path):
    home = legacy_home(tmp_path, LLM_SYSTEM_PROMPT_FILE="prompts/busy.txt")

    notice = apply_updates(home, first_run=False)

    assert notice.retired_prompt == "busy.txt"
    assert (home.prompts_dir / "busy.txt").exists()  # their copy is kept


def test_own_prompt_is_not_called_retired(tmp_path):
    home = legacy_home(tmp_path, LLM_SYSTEM_PROMPT_FILE="prompts/work.txt")

    assert apply_updates(home, first_run=False).retired_prompt is None


def test_repository_prompts_are_never_touched(tmp_path, monkeypatch):
    home = legacy_home(tmp_path)
    monkeypatch.setattr(updates, "DEFAULT_PROMPTS_DIR", home.prompts_dir)

    notice = apply_updates(home, first_run=False)

    assert notice.prompts_updated == []


# --- What's new and the notice ----------------------------------------------------


def test_changelog_lists_only_newer_versions():
    items = changelog_since("0.1.0")

    assert items
    assert not any("First tester version" in item for item in items)


def test_changelog_is_empty_when_nothing_is_newer():
    assert changelog_since(__version__) == []


@pytest.mark.parametrize("a, b", [("0.1.0", "0.2.0"), ("0.9.0", "0.10.0"), ("1.0", "1.0.1")])
def test_versions_compare_as_numbers(a, b):
    assert version_tuple(a) < version_tuple(b)


def test_notice_mentions_settings_prompt_and_backups(tmp_path, capsys):
    home = legacy_home(tmp_path, LLM_SYSTEM_PROMPT_FILE="prompts/busy.txt")

    show_notice(apply_updates(home, first_run=False), home)

    out = capsys.readouterr().out
    assert f"Updated to {__version__}" in out
    assert "AUTO_REPLY_DELAY" in out and "3 → 180" in out
    assert "chat.txt is now the new version" in out
    assert "backup" in out
    assert "busy.txt" in out
