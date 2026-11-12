"""Select XWayland for desktop keep-above and load optional user-local Qt libraries."""

from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path


def configure_platform() -> str:
    """Call before constructing QApplication; explicit test/platform overrides win.

    GNOME's native Wayland protocol doesn't implement arbitrary always-on-top
    requests. XWayland exposes the window-manager hint needed by our overlay.
    Ubuntu's optional xcb-cursor package can be installed locally by bootstrap.
    """
    if sys.platform != "linux":
        return os.environ.get("QT_QPA_PLATFORM", "")
    platform = os.environ.get("QT_QPA_PLATFORM")
    if not platform and os.environ.get("DISPLAY"):
        platform = "xcb"
        os.environ["QT_QPA_PLATFORM"] = platform
    if platform != "xcb":
        return platform or "wayland"
    local = Path(sys.prefix) / "lib" / "lang-in-out-system"
    # Load dependencies before the cursor library. Global symbols resolve the
    # subsequently opened Qt plugin without a process-wide LD_LIBRARY_PATH.
    for name in (
        "libxcb-util.so.1",
        "libxcb-render-util.so.0",
        "libxcb-image.so.0",
        "libxcb-cursor.so.0",
    ):
        candidate = local / name
        if candidate.exists():
            ctypes.CDLL(str(candidate), mode=ctypes.RTLD_GLOBAL)
    try:
        ctypes.CDLL("libxcb-cursor.so.0", mode=ctypes.RTLD_GLOBAL)
    except OSError as exc:
        raise RuntimeError(
            "Qt needs libxcb-cursor0 for the floating caption window. "
            "Run scripts/bootstrap-linux.sh from this checkout (no sudo), "
            "or install your distribution's libxcb-cursor package."
        ) from exc
    return platform
