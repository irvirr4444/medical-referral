"""DRK patient-intake API without eagerly loading the browser automation stack."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "DrkDuplicateCheckDecision",
    "main",
    "require_clear_to_create",
    "run_duplicate_check",
    "safe_click",
    "submit_create_patient",
]


_EXPORT_MODULES = {
    "DrkDuplicateCheckDecision": "drk_emr.create_patient.schema",
    "main": "drk_emr.create_patient.fill",
    "require_clear_to_create": "drk_emr.create_patient.duplicate_check",
    "run_duplicate_check": "drk_emr.create_patient.duplicate_check",
    "safe_click": "drk_emr.create_patient.fill",
    "submit_create_patient": "drk_emr.create_patient.fill",
}


def __getattr__(name: str) -> Any:
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value
