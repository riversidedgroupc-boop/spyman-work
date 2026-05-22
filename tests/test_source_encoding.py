"""Guard project text files against encoding regressions."""

from __future__ import annotations

from pathlib import Path


TEXT_SUFFIXES = {
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

SKIP_DIRS = {
    ".cache",
    ".git",
    ".mypy_cache",
    ".pytest-tmp",
    ".pytest_cache",
    ".pytest_tmp",
    ".ruff_cache",
    ".superpowers",
    ".venv",
    "__pycache__",
    "logs",
    "models",
    "MvImport",
    "outputs",
    "project_data",
}

MOJIBAKE_MARKERS = (
    "\ufffd",
    "\u9225",
    "\u922b",
    "\u923c",
    "\u9286",
    "\u951b",
    "\u5bb8\u30e4",
    "\u7459\u55da",
    "\u59ab\u20ac",
    "\u9428",
    "\u7ecb",
)


def _iter_project_text_files() -> list[Path]:
    root = Path(__file__).resolve().parents[1]
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        files.append(path)
    return files


def test_project_text_files_are_utf8() -> None:
    invalid: list[str] = []
    for path in _iter_project_text_files():
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            invalid.append(f"{path}: {exc}")

    assert invalid == []


def test_project_text_files_do_not_contain_mojibake_markers() -> None:
    corrupted: list[str] = []
    for path in _iter_project_text_files():
        text = path.read_text(encoding="utf-8")
        markers = [marker for marker in MOJIBAKE_MARKERS if marker in text]
        if markers:
            corrupted.append(f"{path}: {markers}")

    assert corrupted == []
