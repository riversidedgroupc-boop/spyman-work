"""Exception hierarchy for the autofocus system.

All custom exceptions inherit from AutofocusError so they can be caught
at the appropriate level in the call stack.
"""

from __future__ import annotations


# ---- Root exception ----

class AutofocusError(Exception):
    """Base exception for all autofocus-related errors."""


# ---- Stage errors ----

class StageError(AutofocusError):
    """Base exception for stage/motion errors."""


class StageNotConnectedError(StageError):
    """Stage is not connected."""


class StageNotHomedError(StageError):
    """Stage has not been homed."""


class StageTimeoutError(StageError):
    """Stage movement timed out."""


class StageLimitError(StageError):
    """Stage position exceeds soft/hard limits."""


class StageEmergencyStopError(StageError):
    """Emergency stop was triggered on the stage."""


# ---- Camera errors ----

class CameraError(AutofocusError):
    """Base exception for camera errors."""


class CameraNotConnectedError(CameraError):
    """Camera is not connected."""


class CaptureQualityError(CameraError):
    """Captured image has quality issues (overexposed, underexposed, empty)."""


class CaptureSizeError(CameraError):
    """Captured image dimensions are inconsistent."""


# ---- Focus errors ----

class FocusFailedError(AutofocusError):
    """Autofocus failed to find a valid focus point."""


class CurveAnalysisError(FocusFailedError):
    """Focus curve analysis failed (flat curve, multi-peak, etc.)."""


class PeakNotFoundError(FocusFailedError):
    """No valid peak found in the focus score curve."""


class PeakAtBoundaryError(FocusFailedError):
    """Best focus found at search boundary — range may be insufficient."""


class VerificationFailedError(FocusFailedError):
    """Verification capture at best Z did not confirm the expected score."""


# ---- DOF errors ----

class DepthOfFieldError(AutofocusError):
    """Depth of field check issue (non-fatal)."""


class DOFWarningError(DepthOfFieldError):
    """Edge-to-center sharpness ratio below threshold — optical concern."""


# ---- Config errors ----

class ConfigError(AutofocusError):
    """Configuration is invalid or missing."""


# ---- Emergency ----

class EmergencyStopError(AutofocusError):
    """Emergency stop triggered — all motion and acquisition must halt immediately."""
