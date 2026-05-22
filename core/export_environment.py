"""Export environment detection — GPU, CUDA, TensorRT capability probe."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExportEnvironment:
    """Snapshot of the current machine's model-export capabilities."""

    gpu_name: str = ""
    cuda_available: bool = False
    cuda_version: str = ""
    torch_version: str = ""
    ultralytics_version: str = ""
    tensorrt_available: bool = False
    tensorrt_version: str = ""
    device_capability: str = ""

    def to_dict(self) -> dict:
        return {
            "gpu_name": self.gpu_name,
            "cuda_available": self.cuda_available,
            "cuda_version": self.cuda_version,
            "torch_version": self.torch_version,
            "ultralytics_version": self.ultralytics_version,
            "tensorrt_available": self.tensorrt_available,
            "tensorrt_version": self.tensorrt_version,
            "device_capability": self.device_capability,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ExportEnvironment:
        return cls(
            gpu_name=d.get("gpu_name", ""),
            cuda_available=bool(d.get("cuda_available", False)),
            cuda_version=d.get("cuda_version", ""),
            torch_version=d.get("torch_version", ""),
            ultralytics_version=d.get("ultralytics_version", ""),
            tensorrt_available=bool(d.get("tensorrt_available", False)),
            tensorrt_version=d.get("tensorrt_version", ""),
            device_capability=d.get("device_capability", ""),
        )


def detect_export_environment() -> ExportEnvironment:
    """Detect the current machine's export capabilities.

    Must NOT crash if TensorRT is not installed.
    Must NOT crash if torch is not installed.
    All ImportErrors must be caught; set *_available=False and *_version="" on failure.
    """
    env = ExportEnvironment()

    # --- torch ---
    try:
        import torch

        env.torch_version = torch.__version__
        env.cuda_available = torch.cuda.is_available()
        if env.cuda_available:
            env.cuda_version = torch.version.cuda or ""
            try:
                env.gpu_name = torch.cuda.get_device_name(0)
            except Exception:
                env.gpu_name = ""
            try:
                major, minor = torch.cuda.get_device_capability(0)
                env.device_capability = f"{major}.{minor}"
            except Exception:
                env.device_capability = ""
    except ImportError:
        pass

    # --- ultralytics ---
    try:
        import ultralytics

        env.ultralytics_version = ultralytics.__version__
    except ImportError:
        pass

    # --- tensorrt ---
    try:
        import tensorrt

        env.tensorrt_available = True
        env.tensorrt_version = tensorrt.__version__
    except ImportError:
        pass

    return env
