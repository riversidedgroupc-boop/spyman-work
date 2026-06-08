from __future__ import annotations

from pathlib import Path


def test_cpp_runtime_package_script_exists() -> None:
    """The packaging script exists and references expected artifacts."""
    script = Path("packaging/cpp_runtime_package.ps1")
    assert script.is_file(), f"Expected script at {script.resolve()}"
    content = script.read_text(encoding="utf-8")
    assert "cx_vision_runtime.exe" in content
    assert "cpp_runtime_contract.md" in content
    assert "runtime_config.example.json" in content
