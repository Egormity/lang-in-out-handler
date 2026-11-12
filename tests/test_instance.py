import uuid

from PySide6.QtNetwork import QLocalSocket
from shiboken6 import delete

from lang_handler.instance import Instance


def test_shortcut_connections_deliver_once_and_can_reconnect(qapp, qtbot):
    server = Instance()
    server.name = "lang-in-out-test-" + uuid.uuid4().hex
    server.listen()
    actions = []
    server.action.connect(actions.append)
    sender = Instance()
    sender.name = server.name
    for _ in range(3):
        assert sender.forward("show")
        qtbot.waitUntil(lambda: not server.clients)
        qapp.processEvents()
    qtbot.waitUntil(lambda: len(actions) == 3)
    assert actions == ["show"] * 3
    server.server.close()


def test_late_disconnect_after_qt_teardown_is_safe(qapp):
    server = Instance()
    socket = QLocalSocket()
    server.clients.add(socket)
    delete(socket)
    # The disconnected callback can be delivered after native deletion on quit.
    server._remove(socket)
    assert not server.clients
