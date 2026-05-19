"""Serial port client — skeleton."""
from __future__ import annotations

from integration.base import BaseIntegrationClient


class SerialPortClient(BaseIntegrationClient):
    client_name = "serial_port"

    def __init__(self):
        self._connected = False

    def connect(self, config: dict) -> bool:
        try:
            import serial  # noqa: F401
            self._connected = True
            return True
        except ImportError:
            raise NotImplementedError(
                "pyserial 未安装。请运行: pip install pyserial"
            )

    def disconnect(self) -> None:
        self._connected = False

    def send_alarm(self, event: dict) -> bool:
        return self._connected

    def send_status(self, status: dict) -> bool:
        return self._connected

    def test_connection(self) -> bool:
        return self._connected
