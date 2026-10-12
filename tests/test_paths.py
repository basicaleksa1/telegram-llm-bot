from userbot import paths
from userbot.paths import DEFAULT_PROMPTS_DIR, Home, ensure_home, resolve_home, restore_default_prompts


def test_override_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("USERBOT_HOME", str(tmp_path / "from-env"))

    assert resolve_home(tmp_path / "chosen").root == tmp_path / "chosen"
    assert resolve_home().root == tmp_path / "from-env"


def test_repository_with_env_file_is_the_data_folder(tmp_path, monkeypatch):
    monkeypatch.delenv("USERBOT_HOME", raising=False)
    monkeypatch.setattr(paths, "PROJECT_ROOT", tmp_path)
    (tmp_path / ".env").write_text("API_ID=1\n")

    assert resolve_home().root == tmp_path


def test_without_env_file_the_user_data_folder_is_used(tmp_path, monkeypatch):
    monkeypatch.delenv("USERBOT_HOME", raising=False)
    monkeypatch.setattr(paths, "PROJECT_ROOT", tmp_path)

    assert resolve_home().root.name == "TelegramUserbot"


def test_ensure_home_creates_folders_settings_and_prompts(tmp_path):
    home = Home(tmp_path / "data")

    ensure_home(home)

    assert home.settings_file.name == "settings.env"
    assert "API_ID=" in home.settings_file.read_text()
    assert {p.name for p in home.prompts_dir.glob("*.txt")} >= {"chat.txt", "busy.txt"}
    assert home.sessions_dir.is_dir() and home.logs_dir.is_dir()


def test_ensure_home_never_overwrites_user_files(tmp_path):
    home = Home(tmp_path)
    home.prompts_dir.mkdir()
    (home.prompts_dir / "chat.txt").write_text("my edited prompt")
    home.settings_file.write_text("API_ID=42\n")

    ensure_home(home)

    assert (home.prompts_dir / "chat.txt").read_text() == "my edited prompt"
    assert home.settings_file.read_text() == "API_ID=42\n"


def test_restore_default_prompts_overwrites_only_shipped_ones(tmp_path):
    home = Home(tmp_path)
    ensure_home(home)
    (home.prompts_dir / "chat.txt").write_text("edited")
    (home.prompts_dir / "work.txt").write_text("mine")

    restored = restore_default_prompts(home)

    assert "chat.txt" in restored
    assert (home.prompts_dir / "chat.txt").read_text() == (DEFAULT_PROMPTS_DIR / "chat.txt").read_text()
    assert (home.prompts_dir / "work.txt").read_text() == "mine"


def test_relative_paths_resolve_against_the_data_folder(tmp_path):
    home = Home(tmp_path)

    assert home.resolve("prompts/x.txt") == tmp_path / "prompts/x.txt"
    assert home.resolve(tmp_path / "abs.txt") == tmp_path / "abs.txt"
