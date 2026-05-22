"""Base integration client interface."""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseIntegrationClient(ABC):
    client_name: str = "base"

    @abstractmethod
    def connect(self, config: dict) -> bool:
        ...

    @abstractmethod
    def disconnect(self) -> None:
        ...

    @abstractmethod
    def send_alarm(self, event: dict) -> bool:
        """Send alarm event to external system."""
        ...

    @abstractmethod
    def send_status(self, status: dict) -> bool:
        """Send status update to external system."""
        ...

    @abstractmethod
    def test_connection(self) -> bool:
        ...
