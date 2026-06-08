"""Copper Vision exception hierarchy.

所有项目异常的根基类为 `CopperVisionError`。新代码应使用具体异常子类，
避免裸 `except Exception: pass`。

Usage::

    from core.exceptions import StorageError, ConfigError

    raise StorageError(f"Failed to query schema_version: {err}")
"""


class CopperVisionError(Exception):
    """Base exception for all Copper Vision errors."""


# ── Storage ──
class StorageError(CopperVisionError):
    """Database or storage operation failed."""


class SchemaVersionError(StorageError):
    """Schema version table does not exist yet (expected during migrations)."""


# ── Configuration ──
class ConfigError(CopperVisionError):
    """Configuration loading or validation failed."""


class BackupError(CopperVisionError):
    """Backup or restore operation failed."""


class BackupMetaLoadError(BackupError):
    """Failed to load backup metadata from disk."""


# ── Inference ──
class InferenceError(CopperVisionError):
    """Model inference failed."""


class ModelLoadError(InferenceError):
    """Model loading or initialization failed."""


class RunnerCreationError(InferenceError):
    """Failed to create a model runner instance."""


# ── Camera ──
class CameraError(CopperVisionError):
    """Camera operation failed."""


class CameraDiscoveryError(CameraError):
    """Camera discovery or enumeration failed."""


# ── Dataset / Training ──
class DatasetError(CopperVisionError):
    """Dataset build or validation failed."""


class TrainingError(CopperVisionError):
    """Model training failed."""


# ── Deployment ──
class DeploymentError(CopperVisionError):
    """Deployment package generation failed."""


# ── Validation ──
class ValidationError(CopperVisionError):
    """Data validation failed."""
