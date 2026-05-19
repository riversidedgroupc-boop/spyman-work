"""HTTP client for alarm/status reporting."""
from __future__ import annotations

import json
from integration.base import BaseIntegrationClient


class HttpClient(BaseIntegrationClient):
    client_name = "http"

    def __init__(self):
        self._url = ""
        self._connected = False

    def connect(self, config: dict) -> bool:
        self._url = config.get("url", "")
        self._connected = bool(self._url)
        return self._connected

    def disconnect(self) -> None:
        self._connected = False

    def send_alarm(self, event: dict) -> bool:
        if not self._connected:
            return False
        try:
            import urllib.request
            data = json.dumps(event).encode("utf-8")
            req = urllib.request.Request(
                f"{self._url}/alarm", data=data,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)
            return True
        except Exception:
            return False

    def send_status(self, status: dict) -> bool:
        if not self._connected:
            return False
        try:
            import urllib.request
            data = json.dumps(status).encode("utf-8")
            req = urllib.request.Request(
                f"{self._url}/status", data=data,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)
            return True
        except Exception:
            return False

    def test_connection(self) -> bool:
        return self._connected
