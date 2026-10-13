"""Build the tester bundles: one zip per OS, ready to send.

    python scripts/build_bundle.py            # all three: windows, macos, linux
    python scripts/build_bundle.py macos      # just one

Creates dist/userbot-<version>-<os>.zip. Each zip holds a launcher to
double-click, the tester guide, the app (code, prompts, locked dependency
versions) and uv (https://docs.astral.sh/uv/), which downloads Python and the
libraries on the tester's first start. Only uses the standard library.

The first run downloads the uv binaries (pinned version, checked against the
published SHA-256) into dist/.cache/.
"""

import argparse
import hashlib
import io
import os
import platform
import re
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
CACHE = DIST / ".cache"
LAUNCHERS = ROOT / "packaging" / "launchers"
TOP = "TelegramUserbot"

# Pinned uv release; older than two weeks when chosen. Bump deliberately.
UV_VERSION = "0.12.19"
UV_URL = "https://github.com/astral-sh/uv/releases/download/{version}/{asset}"

# (target triple, archive type, name inside the bundle's runtime/bin/)
TARGETS = {
    "windows": [("x86_64-pc-windows-msvc", "zip", "uv.exe")],
    "macos": [("aarch64-apple-darwin", "tar.gz", "uv-arm64"), ("x86_64-apple-darwin", "tar.gz", "uv-x86_64")],
    "linux": [("aarch64-unknown-linux-musl", "tar.gz", "uv-arm64"), ("x86_64-unknown-linux-musl", "tar.gz", "uv-x86_64")],
}

# What goes into app/ (relative to the repository). Nothing else is copied.
APP_FILES = ["pyproject.toml", "uv.lock", ".env.example", "README.md", "CHANGELOG.md"]
APP_DIRS = ["userbot", "prompts"]
# Never ship these, whatever happens: they hold the developer's own account.
FORBIDDEN = re.compile(r"(^|/)(\.env|settings\.env|(\.env|settings\.env)\.before-.*|sessions/.*|.*\.session(-journal)?)$")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("targets", nargs="*", metavar="OS", help="windows, macos and/or linux (default: all)")
    args = parser.parse_args()
    targets = args.targets or list(TARGETS)
    if unknown := [t for t in targets if t not in TARGETS]:
        parser.error(f"unknown OS {', '.join(unknown)}; choose from {', '.join(TARGETS)}")

    version = check_version()
    lock(uv_binary(host_target()))
    app_files = collect_app_files()

    DIST.mkdir(exist_ok=True)
    for os_name in targets:
        out = DIST / f"userbot-{version}-{os_name}.zip"
        build_zip(out, os_name, app_files)
        print(f"Built {out.relative_to(ROOT)} ({out.stat().st_size / 1e6:.1f} MB)")


def check_version() -> str:
    init = (ROOT / "userbot" / "__init__.py").read_text()
    pyproject = (ROOT / "pyproject.toml").read_text()
    code_version = re.search(r'__version__ = "([^"]+)"', init).group(1)
    project_version = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE).group(1)
    if code_version != project_version:
        sys.exit(f"Version mismatch: userbot/__init__.py has {code_version}, pyproject.toml has {project_version}.")
    return code_version


def collect_app_files() -> list[Path]:
    files = [ROOT / name for name in APP_FILES]
    for folder in APP_DIRS:
        files += [
            p for p in sorted((ROOT / folder).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts and p.name != ".DS_Store"
        ]
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        if FORBIDDEN.search(rel):
            sys.exit(f"Refusing to bundle {rel}: it may contain your own login or settings.")
        if not path.exists():
            sys.exit(f"Missing {rel}.")
    return files


def host_target() -> str:
    machine = "aarch64" if platform.machine().lower() in ("arm64", "aarch64") else "x86_64"
    if sys.platform == "darwin":
        return f"{machine}-apple-darwin"
    if sys.platform == "win32":
        return "x86_64-pc-windows-msvc"
    return f"{machine}-unknown-linux-musl"


def uv_binary(target: str) -> Path:
    """Download (once) and unpack the uv binary for `target`, verifying its checksum."""
    kind = "zip" if "windows" in target else "tar.gz"
    folder = CACHE / f"uv-{UV_VERSION}" / target
    binary = folder / ("uv.exe" if kind == "zip" else "uv")
    if binary.exists():
        return binary

    asset = f"uv-{target}.{kind}"
    print(f"Downloading {asset} (uv {UV_VERSION})...")
    data = fetch(UV_URL.format(version=UV_VERSION, asset=asset))
    expected = fetch(UV_URL.format(version=UV_VERSION, asset=asset + ".sha256")).decode().split()[0]
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        sys.exit(f"Checksum mismatch for {asset}: expected {expected}, got {actual}.")

    folder.mkdir(parents=True, exist_ok=True)
    if kind == "zip":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            binary.write_bytes(archive.read("uv.exe"))
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            member = next(m for m in archive.getmembers() if m.name.endswith("/uv"))
            binary.write_bytes(archive.extractfile(member).read())
        binary.chmod(0o755)
    return binary


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def lock(uv: Path) -> None:
    """Make sure uv.lock matches pyproject.toml (the bundle installs exactly these versions)."""
    env = {**os.environ, "UV_CACHE_DIR": str(CACHE / "uv-cache"), "UV_NO_CONFIG": "1"}
    result = subprocess.run([str(uv), "lock", "--directory", str(ROOT)], env=env, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"uv lock failed:\n{result.stderr}")


def build_zip(out: Path, os_name: str, app_files: list[Path]) -> None:
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:

        def add(name: str, data: bytes, executable: bool = False) -> None:
            info = zipfile.ZipInfo(f"{TOP}/{name}", date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3  # Unix, so the permission bits below count (also when built on Windows)
            info.external_attr = ((0o755 if executable else 0o644) | 0o100000) << 16
            archive.writestr(info, data)

        for path in app_files:
            add(f"app/{path.relative_to(ROOT).as_posix()}", path.read_bytes())
        add("TESTER-GUIDE.md", (ROOT / "docs" / "TESTERS.md").read_bytes())

        launcher = (LAUNCHERS / "start.sh").read_bytes()
        if os_name == "windows":
            bat = (LAUNCHERS / "Start Userbot.bat").read_text().replace("\r\n", "\n").replace("\n", "\r\n")
            add("Start Userbot.bat", bat.encode())
        elif os_name == "macos":
            add("Start Userbot.command", launcher, executable=True)
        else:
            add("start.sh", launcher, executable=True)

        for target, _kind, name in TARGETS[os_name]:
            add(f"runtime/bin/{name}", uv_binary(target).read_bytes(), executable=True)


if __name__ == "__main__":
    main()
