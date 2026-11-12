#!/usr/bin/env bash
# On Debian/Ubuntu, extract optional Qt cursor libraries into the venv, without sudo.
set -euo pipefail
APP_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$APP_ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
    printf '%s\n' 'Run uv sync --python 3.12 first.' >&2
    exit 1
fi
if "$PYTHON" -c 'import ctypes; ctypes.CDLL("libxcb-cursor.so.0")' 2>/dev/null; then
    exit 0
fi
LOCAL_LIBS="$APP_ROOT/.venv/lib/lang-in-out-system"
if [[ -f "$LOCAL_LIBS/libxcb-cursor.so.0" ]]; then
    exit 0
fi
if ! command -v apt-get >/dev/null || ! command -v dpkg-deb >/dev/null; then
    printf '%s\n' 'Install your distribution package for libxcb-cursor to enable the floating window.' >&2
    exit 1
fi
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf -- "$TEMP_DIR"' EXIT
mkdir -p "$LOCAL_LIBS"
(
    cd -- "$TEMP_DIR"
    apt-get download libxcb-cursor0 libxcb-image0 libxcb-render-util0 libxcb-util1
    for package in ./*.deb; do
        dpkg-deb --extract "$package" extracted
    done
)
"$PYTHON" - "$TEMP_DIR/extracted" "$LOCAL_LIBS" <<'PY'
from pathlib import Path
import shutil
import sys

source, destination = map(Path, sys.argv[1:])
for library in source.rglob('libxcb-*.so.*'):
    shutil.copyfile(library, destination / library.name)
print('Installed optional Qt libraries inside the virtual environment.')
PY
