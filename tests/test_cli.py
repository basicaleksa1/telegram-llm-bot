import pytest
from typer.testing import CliRunner

from userbot import cli
from userbot.paths import set_home
from userbot.updates import LEGACY_DEFAULTS


@pytest.fixture(autouse=True)
def reset_home():
    yield
    set_home(None)  # the CLI sets the data folder globally


def test_a_failing_update_does_not_stop_the_app(tmp_path, monkeypatch):
    def broken(home, first_run):
        raise PermissionError("read-only data folder")

    monkeypatch.setattr(cli, "apply_updates", broken)

    result = CliRunner().invoke(cli.app, ["--home", str(tmp_path), "settings", "show"])

    assert result.exit_code == 0
    assert "Couldn't bring your settings" in result.output
    assert "AUTO_REPLY_ENABLED" in result.output  # the command still ran


def test_update_notice_is_shown_once(tmp_path):
    (tmp_path / "settings.env").write_text("".join(f"{k}={v}\n" for k, v in LEGACY_DEFAULTS.items()))
    runner = CliRunner()

    first = runner.invoke(cli.app, ["--home", str(tmp_path), "settings", "show"])
    second = runner.invoke(cli.app, ["--home", str(tmp_path), "settings", "show"])

    assert "Updated to" in first.output
    assert "Updated to" not in second.output
