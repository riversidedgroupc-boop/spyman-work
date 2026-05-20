"""Camera adapter framework — folder watcher, Hikvision MVS, Basler Pylon, etc."""
from __future__ import annotations

from camera_adapters.base import BaseCameraAdapter
from camera_adapters.folder_watcher import FolderWatcherCameraAdapter


_ADAPTER_REGISTRY: dict[str, type[BaseCameraAdapter]] = {}


def _init_registry() -> None:
    """Lazy-register built-in adapters."""
    if _ADAPTER_REGISTRY:
        return
    _ADAPTER_REGISTRY["folder_watcher"] = FolderWatcherCameraAdapter
    try:
        from camera_adapters.hikvision_mvs import HikvisionMVSAdapter
        _ADAPTER_REGISTRY["hikvision_mvs"] = HikvisionMVSAdapter
    except ImportError:
        pass
    try:
        from camera_adapters.basler_pylon import BaslerPylonAdapter
        _ADAPTER_REGISTRY["basler_pylon"] = BaslerPylonAdapter
    except ImportError:
        pass


def register_adapter(adapter_type: str, adapter_cls: type[BaseCameraAdapter]) -> None:
    """Register a custom camera adapter class."""
    _ADAPTER_REGISTRY[adapter_type] = adapter_cls


def create_adapter(adapter_type: str) -> BaseCameraAdapter:
    """Factory: create a camera adapter instance by type string."""
    _init_registry()
    cls = _ADAPTER_REGISTRY.get(adapter_type)
    if cls is None:
        raise ValueError(
            f"Unknown camera adapter type: {adapter_type}. "
            f"Available: {list(_ADAPTER_REGISTRY)}"
        )
    return cls()


def available_adapter_types() -> list[str]:
    """Return list of registered adapter type names."""
    _init_registry()
    return sorted([*_ADAPTER_REGISTRY, "line_scan", "hikrobot_line_scan"])
