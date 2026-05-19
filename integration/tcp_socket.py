"""TCP socket client for PLC communication."""
from __future__ import annotations

import socket
import json
from integration.base import BaseIntegrationClient


class TcpSocketClient(BaseIntegrationClient):
    client_name = "tcp_socket"

    def __init__(self):
        self._host = ""
        self._port = 0
        self._sock: socket.socket | None = None
        self._connected = False

    def connect(self, config: dict) -> bool:
        self._host = config.get("host", "127.0.0.1")
        self._port = int(config.get("port", 502))
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(3)
            self._sock.connect((self._host, self._port))
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    def disconnect(self) -> None:
        self._connected = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def send_alarm(self, event: dict) -> bool:
        if not self._connected or not self._sock:
            return False
        try:
            msg = json.dumps(event).encode("utf-8")
            self._sock.sendall(msg)
            return True
        except Exception:
            return False

    def send_status(self, status: dict) -> bool:
        return self.send_alarm(status)

    def test_connection(self) -> bool:
        return self._connected
