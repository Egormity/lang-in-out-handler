"""Prefer native desktop input and load optional X11 libraries when needed."""

from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path


def configure_platform() -> str:
    """Call before constructing QApplication; explicit test/platform overrides win.

    Native Wayland is required for reliable XP-Pen input on GNOME. Forcing
    XWayland can prevent the tablet from interacting with every app control,
    not just the canvas. GNOME's keep-above support is handled separately.
    Explicit xcb selection and real X11 sessions still load optional cursor
    libraries installed by the user-local bootstrap.
    """
    if sys.platform != "linux":
        return os.environ.get("QT_QPA_PLATFORM", "")
    platform = os.environ.get("QT_QPA_PLATFORM")
    if not platform:
        if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
            platform = "wayland"
        elif os.environ.get("DISPLAY"):
            platform = "xcb"
        if platform:
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
