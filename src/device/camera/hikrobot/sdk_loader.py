"""MVS SDK DLL loader — loads MvCameraControl.dll and initializes SDK.

The DLL search path is the MvImport directory adjacent to this file.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_MV_IMPORT = Path(__file__).parent / "MvImport"
_MV_IMPORT_STR = str(_MV_IMPORT.resolve())

logger = logging.getLogger(__name__)

SDK_LOADED = False
SDK_ERROR: str | None = None


def load_sdk() -> bool:
    """Load MVS SDK DLLs and make Python bindings importable.

    Returns True if SDK is ready. On first failure, sets SDK_ERROR.
    Caller may call repeatedly; subsequent calls return cached result.
    """
    global SDK_LOADED, SDK_ERROR

    if SDK_LOADED:
        return True
    if SDK_ERROR is not None:
        return False

    if not _MV_IMPORT.is_dir():
        SDK_ERROR = f"MVS SDK MvImport directory not found: {_MV_IMPORT_STR}"
        logger.error(SDK_ERROR)
        return False

    dll_path = _MV_IMPORT / "MvCameraControl.dll"
    if not dll_path.is_file():
        SDK_ERROR = f"MvCameraControl.dll not found in {_MV_IMPORT_STR}"
        logger.error(SDK_ERROR)
        return False

    # Add to sys.path so Python bindings can be imported
    if _MV_IMPORT_STR not in sys.path:
        sys.path.insert(0, _MV_IMPORT_STR)

    # chdir so WinDLL resolves dependency DLLs
    old_cwd = os.getcwd()
    try:
        os.chdir(_MV_IMPORT_STR)

        from MvCameraControl_class import MvCamera  # noqa: F401
        from CameraParams_header import MV_CC_DEVICE_INFO_LIST, MV_CC_DEVICE_INFO  # noqa: F401
        from CameraParams_const import (  # noqa: F401
            MV_GIGE_DEVICE,
            MV_USB_DEVICE,
            MV_ACCESS_Exclusive,
        )
        from CameraParams_header import (  # noqa: F401
            MV_TRIGGER_MODE_OFF,
            MV_TRIGGER_MODE_ON,
        )
        import MvErrorDefine_const  # noqa: F401  # loads module into sys.modules

        SDK_LOADED = True
        logger.info("MVS SDK loaded successfully from %s", _MV_IMPORT_STR)
        return True
    except (ImportError, OSError) as e:
        SDK_ERROR = f"Failed to load MVS SDK: {e}"
        logger.error(SDK_ERROR)
        return False
    finally:
        try:
            os.chdir(old_cwd)
        except OSError:
            pass


def get_mv_import_path() -> str:
    """Return the absolute path to the MvImport directory."""
    return _MV_IMPORT_STR
