"""Linux desktop entry point and resident application lifecycle."""

import argparse
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Lang In/Out — OpenAI language tools for Linux")
    parser.add_argument("--action", choices=["show", "input", "output", "translate", "tts", "drawing", "quit"])
    parser.add_argument("--no-shortcuts", action="store_true", help="Do not register desktop shortcuts")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args()
    if args.version:
        from . import __version__
        print(__version__)
        return 0

    # Native Wayland preserves tablet input; pinning is handled by the window host.
    # Respect explicit platform selection (including offscreen UI tests).
    from .qt_platform import configure_platform
    configure_platform()
    os.environ.setdefault("QT_LINUX_ACCESSIBILITY_ALWAYS_ON", "1")
    from PySide6.QtCore import QEvent, QObject, QTimer
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

    from .audio import enumerate_sources
    from .controller import Controller
    from .credentials import Credentials
    from .instance import Instance
    from .storage import Store
    from .ui.main_window import MainWindow
    from .ui.overlay import CaptionOverlay

    application = QApplication([sys.argv[0]])
    application.setApplicationName("lang-in-out")
    application.setDesktopFileName("lang-in-out")
    application.setApplicationDisplayName("Lang In/Out")
    application.setOrganizationName("Egormity")
    instance = Instance(application)
    if instance.forward(args.action or "show"):
        return 0
    if args.action == "quit":
        return 0
    instance.listen()
    store = Store()
    credentials = Credentials()
    try:
        key_present = bool(credentials.get())
    except (OSError, RuntimeError, ValueError) as exc:
        QMessageBox.critical(None, "Credential storage", str(exc))
        return 1
    settings = store.load_settings()
    window = MainWindow(settings, key_present)
    overlay = CaptionOverlay(settings)
    controller = Controller(window, overlay, store, credentials)
    icon_path = Path(__file__).resolve().parents[2] / "assets" / "lang-in-out.svg"
    if not icon_path.exists():
        icon_path = Path(__file__).resolve().parent / "assets" / "lang-in-out.svg"
    icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon.fromTheme("audio-input-microphone")
    application.setWindowIcon(icon)
    window.setWindowIcon(icon)
    tray = QSystemTrayIcon(icon, application)
    tray.setToolTip("Lang In/Out")
    menu = QMenu()
    menu.addAction("Open Lang In/Out", lambda: controller.action("show"))
    menu.addSeparator()
    for name, mode in [("Toggle voice input", "input"), ("Toggle live captions", "output"),
                       ("Translate clipboard", "translate"), ("Speak clipboard", "tts")]:
        menu.addAction(name, lambda m=mode: controller.action(m))
    menu.addAction("Show captions", controller.show_overlay)
    menu.addAction("Floating handwriting", lambda: controller.action("drawing"))
    menu.addSeparator()
    menu.addAction("Quit", application.quit)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: controller.action("show")
                           if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
    has_tray = QSystemTrayIcon.isSystemTrayAvailable()
    if has_tray:
        tray.show()
        application.setQuitOnLastWindowClosed(False)

    class CloseToTray(QObject):
        def eventFilter(self, watched, event):
            if watched is window and event.type() == QEvent.Type.Close and has_tray:
                window.hide()
                event.ignore()
                tray.showMessage("Lang In/Out", "Still running. Use your shortcuts or the tray menu.",
                                 QSystemTrayIcon.MessageIcon.Information, 2000)
                return True
            return False

    close_filter = CloseToTray(application)
    window.installEventFilter(close_filter)
    instance.action.connect(lambda action: application.quit() if action == "quit"
                             else controller.action(action))

    def shutdown():
        controller.shutdown()
        instance.server.close()
        # Workers only return results to the main loop; no database writes occur there.
        store.close()

    application.aboutToQuit.connect(shutdown)
    if not args.action or args.action == "show":
        window.show()
    if not args.no_shortcuts:
        QTimer.singleShot(0, controller.apply_shortcuts)
    if hasattr(window, "set_sources"):
        controller.jobs.submit(lambda cancel, progress: enumerate_sources(), window.set_sources,
                               controller.fail)
    if args.action and args.action != "show":
        QTimer.singleShot(100, lambda: controller.action(args.action))
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())

