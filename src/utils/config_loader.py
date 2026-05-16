"""YAML configuration loader with caching."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ConfigLoader:
    """Loads and caches YAML configuration files."""

    def __init__(self, config_dir: str | Path = "configs") -> None:
        self.config_dir = Path(config_dir)
        self._cache: dict[str, dict[str, Any]] = {}

    def load(self, name: str) -> dict[str, Any]:
        """Load a YAML config file by name (without .yaml extension)."""
        if name in self._cache:
            return self._cache[name]

        file_path = self.config_dir / f"{name}.yaml"
        if not file_path.exists():
            raise FileNotFoundError(f"Config file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        self._cache[name] = data
        return data

    def reload(self, name: str) -> dict[str, Any]:
        """Force reload a config file."""
        self._cache.pop(name, None)
        return self.load(name)

    def get(self, name: str, *keys: str, default: Any = None) -> Any:
        """Load config and traverse nested keys. Returns default if any key is missing."""
        data = self.load(name)
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key)
            else:
                return default
            if data is None:
                return default
        return data


_config_loader: ConfigLoader | None = None


def get_config_loader(config_dir: str | Path = "configs") -> ConfigLoader:
    """Get or create the singleton ConfigLoader."""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader(config_dir)
    return _config_loader
