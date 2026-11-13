"""Real Qt tablet events exercise contact recovery, hover, and mouse fallback."""

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QInputDevice, QMouseEvent, QPointingDevice, QTabletEvent
from PySide6.QtWidgets import QApplication

from lang_handler.ui.drawing_canvas import DrawingCanvas


def canvas(qtbot):
    widget = DrawingCanvas()
    widget.resize(500, 300)
    qtbot.addWidget(widget)
    widget.show()
    return widget


def pen_device(pointer=QPointingDevice.PointerType.Pen):
    return QPointingDevice(
        "XP-Pen test device",
        991,
        QInputDevice.DeviceType.Stylus,
        pointer,
        QInputDevice.Capability.Position | QInputDevice.Capability.Pressure,
        1,
        3,
    )


def tablet(
    widget,
    device,
    kind,
    pressure=0,
    button=Qt.MouseButton.NoButton,
    buttons=Qt.MouseButton.NoButton,
    point=(30, 30),
):
    position = QPointF(*point)
    event = QTabletEvent(
        kind,
        device,
        position,
        position,
        pressure,
        0,
        0,
        0,
        0,
        0,
        Qt.KeyboardModifier.NoModifier,
        button,
        buttons,
    )
    QApplication.sendEvent(widget, event)
    return event


def mouse(widget, kind, button, buttons, point=(30, 30)):
    position = QPointF(*point)
    event = QMouseEvent(kind, position, position, button, buttons, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(widget, event)


def test_pressure_move_recovers_missing_press_and_zero_pressure_finishes(qtbot):
    widget, device = canvas(qtbot), pen_device()
    assert widget.hasTabletTracking()
    tablet(widget, device, QEvent.Type.TabletMove, pressure=0.2)
    assert widget.is_drawing
    assert len(widget.strokes) == 1
    tablet(widget, device, QEvent.Type.TabletMove, pressure=0.5, point=(100, 50))
    tablet(widget, device, QEvent.Type.TabletMove, pressure=0, point=(120, 60))
    assert not widget.is_drawing
    assert len(widget.strokes[0][1]) >= 3
    assert widget.snapshot().startswith(b"\x89PNG")


def test_hover_is_ignored_for_mouse_fallback_without_ink(qtbot):
    widget, device = canvas(qtbot), pen_device(QPointingDevice.PointerType.Cursor)
    event = tablet(widget, device, QEvent.Type.TabletMove)
    assert widget.is_blank
    assert not event.isAccepted()
    mouse(
        widget, QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton
    )
    mouse(
        widget, QEvent.Type.MouseMove, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, (70, 50)
    )
    mouse(
        widget,
        QEvent.Type.MouseButtonRelease,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        (100, 60),
    )
    assert len(widget.strokes) == 1
    assert not widget.is_drawing


def test_tip_press_release_and_duplicated_mouse_do_not_duplicate_strokes(qtbot):
    widget, device = canvas(qtbot), pen_device()
    tablet(
        widget,
        device,
        QEvent.Type.TabletPress,
        0.5,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
    )
    mouse(
        widget, QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton
    )
    tablet(
        widget,
        device,
        QEvent.Type.TabletMove,
        0.6,
        buttons=Qt.MouseButton.LeftButton,
        point=(80, 50),
    )
    tablet(widget, device, QEvent.Type.TabletRelease, 0, Qt.MouseButton.LeftButton, point=(100, 60))
    mouse(
        widget,
        QEvent.Type.MouseButtonRelease,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        (100, 60),
    )
    assert len(widget.strokes) == 1
    assert not widget.is_drawing


def test_stylus_side_button_hover_does_not_draw(qtbot):
    widget, device = canvas(qtbot), pen_device()
    event = tablet(
        widget,
        device,
        QEvent.Type.TabletPress,
        0,
        Qt.MouseButton.RightButton,
        Qt.MouseButton.RightButton,
    )
    assert widget.is_blank
    assert not event.isAccepted()


def test_side_button_release_keeps_tip_stroke_active(qtbot):
    widget, device = canvas(qtbot), pen_device()
    tablet(
        widget,
        device,
        QEvent.Type.TabletPress,
        0.5,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
    )
    tablet(
        widget,
        device,
        QEvent.Type.TabletRelease,
        0.5,
        Qt.MouseButton.RightButton,
        Qt.MouseButton.LeftButton,
        (80, 50),
    )
    assert widget.is_drawing
    assert len(widget.strokes) == 1
    tablet(widget, device, QEvent.Type.TabletRelease, 0, Qt.MouseButton.LeftButton)
    assert not widget.is_drawing


def test_leave_finishes_stroke_and_contact_reentry_starts_another(qtbot):
    widget, device = canvas(qtbot), pen_device()
    tablet(widget, device, QEvent.Type.TabletMove, 0.5)
    revision = widget.revision
    QApplication.sendEvent(widget, QEvent(QEvent.Type.Leave))
    assert not widget.is_drawing
    assert widget.revision > revision
    tablet(widget, device, QEvent.Type.TabletMove, 0.5, point=(100, 100))
    assert widget.is_drawing
    assert len(widget.strokes) == 2


def test_proximity_leave_finishes_stroke_even_without_release(qtbot):
    widget, device = canvas(qtbot), pen_device()
    tablet(widget, device, QEvent.Type.TabletMove, 0.5)
    QApplication.sendEvent(QApplication.instance(), QEvent(QEvent.Type.TabletLeaveProximity))
    assert not widget.is_drawing


def test_regular_mouse_and_undo_clear_remain_available(qtbot):
    widget = canvas(qtbot)
    mouse(widget, QEvent.Type.MouseMove, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton)
    assert widget.is_drawing
    mouse(
        widget, QEvent.Type.MouseButtonRelease, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton
    )
    assert not widget.is_drawing
    widget.undo()
    assert widget.is_blank
    widget.begin_stroke(QPointF(30, 30))
    widget.clear()
    assert widget.is_blank
    assert not widget.is_drawing


def test_wayland_session_does_not_force_xwayland_for_keep_above(monkeypatch):
    from lang_handler import qt_platform

    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr(
        qt_platform.ctypes,
        "CDLL",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected X11 dependency")),
    )
    assert qt_platform.configure_platform() == "wayland"
    assert qt_platform.os.environ["QT_QPA_PLATFORM"] == "wayland"


def test_explicit_xcb_override_remains_available(monkeypatch, tmp_path):
    from lang_handler import qt_platform

    monkeypatch.setenv("QT_QPA_PLATFORM", "xcb")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setattr(qt_platform.sys, "prefix", str(tmp_path))
    libraries = []
    monkeypatch.setattr(qt_platform.ctypes, "CDLL", lambda name, **kwargs: libraries.append(name))
    assert qt_platform.configure_platform() == "xcb"
    assert libraries == ["libxcb-cursor.so.0"]
