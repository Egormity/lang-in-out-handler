#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
"$APP_ROOT/.venv/bin/lang-in-out" --action quit
"$APP_ROOT/.venv/bin/python" - <<'PY'
import os
from pathlib import Path
from lang_handler.shortcuts import GlobalShortcuts

GlobalShortcuts().unregister()
data = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
for path in [Path.home() / '.local/bin/lang-in-out', data / 'applications/lang-in-out.desktop',
             data / 'icons/hicolor/scalable/apps/lang-in-out.svg']:
    path.unlink(missing_ok=True)
print('Desktop integration removed. Personal settings, history, and credentials retained.')
PY

