"""Local single-instance commands for OS-level keyboard shortcuts."""

import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class Instance(QObject):
    action = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.name = f"lang-in-out-handler-{os.getuid()}"
        self.clients = set()
        self.server.newConnection.connect(self._accept)

    def forward(self, action="show") -> bool:
        client = QLocalSocket()
        client.connectToServer(self.name)
        if not client.waitForConnected(300):
            return False
        client.write((action + "\n").encode())
        client.waitForBytesWritten(1000)
        client.disconnectFromServer()
        return True

    def listen(self):
        if not self.server.listen(self.name):
            # Only remove a stale socket after checking no instance is listening.
            if self.forward("show"):
                raise RuntimeError("Lang In/Out is already running.")
            QLocalServer.removeServer(self.name)
            if not self.server.listen(self.name):
                raise RuntimeError("Could not start the local shortcut listener.")

    def _accept(self):
        while self.server.hasPendingConnections():
            client = self.server.nextPendingConnection()
            self.clients.add(client)
            client.readyRead.connect(lambda c=client: self._read(c))
            client.disconnected.connect(lambda c=client: self._remove(c))
            if client.bytesAvailable():
                self._read(client)

    def _read(self, client):
        while client.canReadLine():
            action = bytes(client.readLine(64)).decode(errors="replace").strip()
            if action in {"show", "input", "output", "translate", "tts", "quit"}:
                self.action.emit(action)

    def _remove(self, client):
        self.clients.discard(client)
        client.deleteLater()

