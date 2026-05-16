"""Label schema and class definitions for copper tube surface defects."""

from __future__ import annotations

from enum import Enum


class DefectClass(str, Enum):
    OK_CLEAN = "OK_clean"
    OK_MICRO_DEFECT = "OK_micro_defect"
    OK_OIL_STAIN = "OK_oil_stain"
    NG_SCRATCH = "NG_scratch"
    NG_PIT = "NG_pit"
    NG_DENT = "NG_dent"
    NG_DENSE_MICRO_DEFECT = "NG_dense_micro_defect"
    NG_STAIN = "NG_stain"
    NG_UNKNOWN = "NG_unknown"
    BORDERLINE = "Borderline"


CLASS_ID_MAP: dict[int, str] = {
    0: "OK_clean",
    1: "OK_micro_defect",
    2: "OK_oil_stain",
    3: "NG_scratch",
    4: "NG_pit",
    5: "NG_dent",
    6: "NG_dense_micro_defect",
    7: "NG_stain",
    8: "NG_unknown",
    9: "Borderline",
}

CLASS_NAME_MAP: dict[str, int] = {v: k for k, v in CLASS_ID_MAP.items()}

OK_CLASSES: tuple[str, ...] = ("OK_clean", "OK_oil_stain")
NG_CLASSES: tuple[str, ...] = (
    "NG_scratch",
    "NG_pit",
    "NG_dent",
    "NG_dense_micro_defect",
    "NG_stain",
    "NG_unknown",
)
ACCEPTABLE_MICRO_CLASSES: tuple[str, ...] = ("OK_micro_defect",)
MAJOR_DEFECT_CLASSES = {"NG_scratch", "NG_pit", "NG_dent", "NG_stain"}
BORDERLINE_CLASS = "Borderline"


def is_ok(label: str) -> bool:
    return label in OK_CLASSES


def is_ng(label: str) -> bool:
    return label in NG_CLASSES


def is_acceptable_micro(label: str) -> bool:
    return label in ACCEPTABLE_MICRO_CLASSES


def is_borderline(label: str) -> bool:
    return label == BORDERLINE_CLASS


def class_name_to_id(name: str) -> int:
    return CLASS_NAME_MAP.get(name, -1)


def class_id_to_name(cid: int) -> str:
    return CLASS_ID_MAP.get(cid, "Unknown")


def get_label_group(label: str) -> str:
    if is_ok(label):
        return "ok"
    if is_acceptable_micro(label):
        return "acceptable_micro"
    if is_ng(label):
        return "ng"
    if is_borderline(label):
        return "borderline"
    return "unknown"
