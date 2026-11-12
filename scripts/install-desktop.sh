#!/usr/bin/env bash
# Install the current checkout as a user-local application. No sudo required.
set -euo pipefail
APP_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -x "$APP_ROOT/.venv/bin/lang-in-out" ]]; then
    printf '%s\n' 'Run uv sync --python 3.12 in the project first.' >&2
    exit 1
fi
"$APP_ROOT/scripts/bootstrap-linux.sh"
python3 - "$APP_ROOT" <<'PY'
import os
from pathlib import Path
import shlex
import shutil
import sys

root = Path(sys.argv[1])
bin_dir = Path.home() / '.local/bin'
data = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
applications = data / 'applications'
icons = data / 'icons/hicolor/scalable/apps'
for directory in (bin_dir, applications, icons):
    directory.mkdir(parents=True, exist_ok=True)
launcher = bin_dir / 'lang-in-out'
launcher.write_text('#!/bin/sh\nexec ' + shlex.quote(str(root / '.venv/bin/lang-in-out')) + ' "$@"\n')
launcher.chmod(0o755)
shutil.copyfile(root / 'assets/lang-in-out.svg', icons / 'lang-in-out.svg')
executable = '"' + str(launcher).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$') + '"'
desktop = f'''[Desktop Entry]
Type=Application
Name=Lang In/Out
Comment=Dictation, live captions, translation, and AI speech
Exec={executable}
Icon=lang-in-out
Terminal=false
Categories=AudioVideo;Utility;Accessibility;
StartupWMClass=lang-in-out
Actions=Dictation;Captions;

[Desktop Action Dictation]
Name=Toggle dictation
Exec={executable} --action input

[Desktop Action Captions]
Name=Toggle live captions
Exec={executable} --action output
'''
(applications / 'lang-in-out.desktop').write_text(desktop)
print(f'Installed {applications / "lang-in-out.desktop"}')
PY
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${XDG_DATA_HOME:-$HOME/.local/share}/applications"
fi
