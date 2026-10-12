"""Finding, installing and starting Ollama, and choosing/downloading a model.

Ollama (https://ollama.com) runs the AI model locally. It handles the GPU on
Windows, macOS and Linux, so the userbot only has to make sure it's installed,
running, and has the model.
"""

import asyncio
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import httpx
import psutil
from ollama import AsyncClient, ResponseError

DOWNLOAD_PAGE = "https://ollama.com/download"
WINDOWS_INSTALLER_URL = "https://ollama.com/download/OllamaSetup.exe"
MACOS_APP_URL = "https://ollama.com/download/Ollama-darwin.zip"
LINUX_INSTALL_COMMAND = "curl -fsSL https://ollama.com/install.sh | sh"


@dataclass(frozen=True)
class ModelOption:
    name: str
    download_gb: float
    description: str


# Best first. Download sizes from ollama.com/library/qwen3.5.
MODELS = [
    ModelOption("qwen3.5:9b", 7.6, "best replies; needs Apple Silicon with 16 GB+ or an NVIDIA GPU with 10 GB+"),
    ModelOption("qwen3.5:4b", 4.0, "good replies; fine on most machines with 12 GB+ RAM"),
    ModelOption("qwen3.5:2b", 3.1, "faster, simpler replies; for 8 GB machines"),
    ModelOption("qwen3.5:0.8b", 1.2, "very small; runs almost anywhere, replies are basic"),
]


@dataclass(frozen=True)
class Hardware:
    ram_gb: float
    apple_silicon: bool
    nvidia_vram_gb: float | None  # None = no NVIDIA GPU found

    def describe(self) -> str:
        parts = [f"{self.ram_gb:.0f} GB RAM"]
        if self.apple_silicon:
            parts.append("Apple Silicon")
        if self.nvidia_vram_gb is not None:
            parts.append(f"NVIDIA GPU with {self.nvidia_vram_gb:.0f} GB")
        return ", ".join(parts)


def detect_hardware() -> Hardware:
    ram_gb = psutil.virtual_memory().total / 1024**3
    apple_silicon = sys.platform == "darwin" and platform.machine() == "arm64"
    return Hardware(ram_gb=ram_gb, apple_silicon=apple_silicon, nvidia_vram_gb=_nvidia_vram_gb())


def _nvidia_vram_gb() -> float | None:
    smi = shutil.which("nvidia-smi")
    if not smi:
        return None
    try:
        out = subprocess.run(
            [smi, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout
        return max(float(line) for line in out.split() if line.strip()) / 1024
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def recommend_model(hw: Hardware) -> str:
    vram = hw.nvidia_vram_gb or 0
    if (hw.apple_silicon and hw.ram_gb >= 15) or vram >= 10:
        return "qwen3.5:9b"
    if hw.ram_gb >= 11.5 or vram >= 5:
        return "qwen3.5:4b"
    if hw.ram_gb >= 7.5:
        return "qwen3.5:2b"
    return "qwen3.5:0.8b"


def free_disk_gb() -> float:
    models_dir = Path(os.environ.get("OLLAMA_MODELS") or Path.home())
    while not models_dir.exists():
        models_dir = models_dir.parent
    return shutil.disk_usage(models_dir).free / 1024**3


# --- Is Ollama there and running? ---------------------------------------------


async def is_running(host: str, timeout: float = 3.0) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout) as http:
            return (await http.get(f"{host.rstrip('/')}/api/version")).status_code == 200
    except httpx.HTTPError:
        return False


async def wait_until_running(host: str, seconds: float = 45) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if await is_running(host):
            return True
        await asyncio.sleep(1)
    return False


def _candidates() -> list[Path]:
    if sys.platform == "win32":
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return [local / "Programs" / "Ollama" / "ollama.exe"]
    if sys.platform == "darwin":
        return [
            Path("/Applications/Ollama.app/Contents/Resources/ollama"),
            Path.home() / "Applications/Ollama.app/Contents/Resources/ollama",
            Path("/opt/homebrew/bin/ollama"),
            Path("/usr/local/bin/ollama"),
        ]
    return [Path("/usr/local/bin/ollama"), Path("/usr/bin/ollama"), Path.home() / ".local/bin/ollama"]


def find_ollama() -> Path | None:
    """The ollama program, if it's installed."""
    on_path = shutil.which("ollama")
    if on_path:
        return Path(on_path)
    return next((p for p in _candidates() if p.exists()), None)


def _macos_app() -> Path | None:
    for app in (Path("/Applications/Ollama.app"), Path.home() / "Applications/Ollama.app"):
        if app.exists():
            return app
    return None


def start_ollama(binary: Path, logs_dir: Path) -> None:
    """Start Ollama in the background (the app on macOS/Windows, `ollama serve` otherwise)."""
    if sys.platform == "darwin" and (app := _macos_app()):
        subprocess.run(["open", "-g", str(app)], check=False)
        return
    if sys.platform == "win32":
        tray_app = binary.with_name("ollama app.exe")
        if tray_app.exists():
            subprocess.Popen([str(tray_app)], creationflags=subprocess.DETACHED_PROCESS)  # type: ignore[attr-defined]
            return
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = open(logs_dir / "ollama.log", "ab")  # noqa: SIM115  (handed to the child process)
    kwargs: dict = {"stdout": log_file, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen([str(binary), "serve"], **kwargs)


# --- Installing Ollama ----------------------------------------------------------


def can_install_automatically() -> bool:
    return sys.platform in ("win32", "darwin")


async def download(url: str, target: Path, on_progress) -> None:
    """Download `url` to `target`, calling on_progress(done_bytes, total_bytes)."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(30, read=120)) as http:
        async with http.stream("GET", url) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            done = 0
            with open(target, "wb") as out:
                async for chunk in response.aiter_bytes(1 << 20):
                    out.write(chunk)
                    done += len(chunk)
                    on_progress(done, total)


async def install_ollama(on_progress) -> None:
    """Download and run the official installer (Windows) or install the app (macOS)."""
    with tempfile.TemporaryDirectory(prefix="ollama-setup-") as tmp:
        if sys.platform == "win32":
            installer = Path(tmp) / "OllamaSetup.exe"
            await download(WINDOWS_INSTALLER_URL, installer, on_progress)
            # The installer is interactive: the user clicks through it. No admin rights needed.
            await asyncio.to_thread(subprocess.run, [str(installer)], check=True)
        elif sys.platform == "darwin":
            archive = Path(tmp) / "Ollama-darwin.zip"
            await download(MACOS_APP_URL, archive, on_progress)
            target = Path("/Applications")
            if not os.access(target, os.W_OK):
                target = Path.home() / "Applications"
                target.mkdir(exist_ok=True)
            await asyncio.to_thread(subprocess.run, ["ditto", "-x", "-k", str(archive), str(target)], check=True)
            subprocess.run(["open", str(target / "Ollama.app")], check=False)
        else:
            raise RuntimeError(f"Run this in a terminal to install Ollama: {LINUX_INSTALL_COMMAND}")


def run_linux_installer() -> bool:
    """Run Ollama's official Linux install script (asks for the user's sudo password)."""
    if not shutil.which("curl"):
        return False
    return subprocess.run(["sh", "-c", LINUX_INSTALL_COMMAND], check=False).returncode == 0


# --- Models ---------------------------------------------------------------------


async def installed_models(host: str) -> list[str]:
    response = await AsyncClient(host=host).list()
    return sorted(m.model for m in response.models if m.model)


async def has_model(host: str, model: str) -> bool:
    try:
        await AsyncClient(host=host).show(model)
        return True
    except ResponseError:
        return False


@dataclass
class PullProgress:
    status: str
    completed: int
    total: int


async def pull_model(host: str, model: str) -> AsyncIterator[PullProgress]:
    """Download a model, yielding overall progress (summed over all its parts)."""
    totals: dict[str, int] = {}
    done: dict[str, int] = {}
    stream = await AsyncClient(host=host).pull(model, stream=True)
    async for part in stream:
        if part.digest and part.total:
            totals[part.digest] = part.total
            done[part.digest] = part.completed or 0
        yield PullProgress(status=part.status or "", completed=sum(done.values()), total=sum(totals.values()))
