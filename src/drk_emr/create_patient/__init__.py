"""Fill Patient Intake form with JSON/synthetic data (never creates the patient)."""

from drk_emr.create_patient.duplicate_check import require_clear_to_create, run_duplicate_check
from drk_emr.create_patient.fill import main, safe_click, submit_create_patient
from drk_emr.create_patient.schema import DrkDuplicateCheckDecision

__all__ = [
    "DrkDuplicateCheckDecision",
    "main",
    "require_clear_to_create",
    "run_duplicate_check",
    "safe_click",
    "submit_create_patient",
]
