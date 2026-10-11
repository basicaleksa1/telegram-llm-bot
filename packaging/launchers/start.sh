#!/bin/sh
# Starts Telegram Userbot (macOS and Linux).
#
# The first start downloads Python and the libraries the bot needs (about
# 100 MB) into the runtime/ folder next to this file. Nothing is installed
# system-wide: deleting this folder removes it all. Your settings, prompts and
# Telegram login are kept separately (see "Open data folder" in the menu).
#
# Any arguments are passed on, e.g.:  ./start.sh doctor   ./start.sh --help
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

# macOS marks downloaded files as "quarantined" and would block the bundled
# programs one by one. You already allowed this launcher, so allow the rest.
if [ "$(uname -s)" = "Darwin" ]; then
    xattr -dr com.apple.quarantine "$DIR" 2>/dev/null || true
fi

case "$(uname -m)" in
    arm64 | aarch64) ARCH=arm64 ;;
    x86_64 | amd64) ARCH=x86_64 ;;
    *) echo "Sorry, this computer's processor ($(uname -m)) isn't supported."; exit 1 ;;
esac
UV="$DIR/runtime/bin/uv-$ARCH"
chmod +x "$UV" 2>/dev/null || true

export UV_PYTHON_INSTALL_DIR="$DIR/runtime/python"
export UV_CACHE_DIR="$DIR/runtime/cache"
export UV_PROJECT_ENVIRONMENT="$DIR/runtime/venv"
export UV_PYTHON_PREFERENCE=only-managed
export UV_NO_CONFIG=1
export PYTHONUTF8=1

if [ ! -d "$DIR/runtime/venv" ]; then
    echo "First start: downloading Python and the bot's libraries (about 100 MB, once)..."
fi

exec "$UV" run --frozen --no-dev --python 3.13 --directory "$DIR/app" python -m userbot "$@"
