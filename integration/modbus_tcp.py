"""Modbus TCP client — skeleton."""
from __future__ import annotations

from integration.base import BaseIntegrationClient


class ModbusTcpClient(BaseIntegrationClient):
    client_name = "modbus_tcp"

    def __init__(self):
        self._connected = False

    def connect(self, config: dict) -> bool:
        try:
            import pymodbus  # noqa: F401
            self._connected = True
            return True
        except ImportError:
            raise NotImplementedError(
                "pymodbus 未安装。请运行: pip install pymodbus"
            )

    def disconnect(self) -> None:
        self._connected = False

    def send_alarm(self, event: dict) -> bool:
        return self._connected

    def send_status(self, status: dict) -> bool:
        return self._connected

    def test_connection(self) -> bool:
        return self._connected
