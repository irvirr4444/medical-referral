"""Pure referral-intake decisions; this module never writes to Monday or DRK."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from intake_extractor.models.schema import ReferralIntake


THRESHOLD_FIELDS = ("patient_name", "patient_dob", "patient_phone", "patient_address")
SUPPORTING_FIELDS = ("referring_facility", "clinical_information", "insurance_information")

FIELD_LABELS = {
    "patient_name": "patient name",
    "patient_dob": "date of birth",
    "patient_phone": "contact number",
    "patient_address": "patient address",
    "referring_facility": "home health or hospice agency",
    "clinical_information": "wound or clinical information",
    "insurance_information": "insurance information",
}


@dataclass(frozen=True)
class DuplicateCheck:
    """Outcome from an optional, read-only duplicate lookup."""

    mode: str
    status: str
    candidates: tuple[dict[str, Any], ...] = ()
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "status": self.status,
            "candidate_count": len(self.candidates),
            "reason": self.reason,
            "candidates": list(self.candidates),
        }


def referral_missing_fields(referral: ReferralIntake) -> tuple[list[str], list[str]]:
    """Return workflow gaps without treating an extraction omission as an error."""
    threshold_missing = [field for field in THRESHOLD_FIELDS if not getattr(referral, field)]
    supporting_values = {
        "referring_facility": referral.referring_facility,
        "clinical_information": bool(referral.diagnosis_text or referral.icd10_codes or referral.requested_services),
        "insurance_information": bool(referral.insurance_provider or referral.insurance_id),
    }
    supporting_missing = [field for field in SUPPORTING_FIELDS if not supporting_values[field]]
    return threshold_missing, supporting_missing


def build_intake_plan(referral: ReferralIntake, *, duplicate_check: DuplicateCheck) -> dict[str, Any]:
    """Build a proposed workflow decision from one extracted referral.

    This intentionally produces recommendations only. The eventual Monday and
    DRK writers should consume an approved plan rather than duplicating rules.
    """
    threshold_missing, supporting_missing = referral_missing_fields(referral)
    actions: list[dict[str, Any]] = [
        {
            "type": "contact_referral_partner",
            "owner": "intake team",
            "status": "proposed",
            "reason": "WCW's documented workflow calls for confirmation and follow-up on every referral.",
        }
    ]
    review_reasons: list[str] = []

    if duplicate_check.status == "duplicate_found":
        actions.append(
            {
                "type": "review_duplicate_candidate",
                "owner": "intake team",
                "status": "proposed",
                "reason": "A Master Sheet item has the same normalized patient name, date of birth, phone, and address.",
                "candidate_count": len(duplicate_check.candidates),
            }
        )
        review_reasons.append("possible_duplicate")

    if threshold_missing:
        actions.append(
            {
                "type": "route_missing_threshold_to_marketer",
                "owner": "assigned marketer",
                "status": "proposed",
                "missing_fields": threshold_missing,
                "reason": "The minimum threshold is name, DOB, phone, and address.",
            }
        )
        review_reasons.append("missing_threshold_fields")
    elif supporting_missing:
        actions.append(
            {
                "type": "route_partial_referral_to_case_manager",
                "owner": "case manager",
                "status": "proposed",
                "missing_fields": supporting_missing,
                "reason": "The referral meets the scheduling threshold but has supporting information to close.",
            }
        )
        review_reasons.append("missing_supporting_fields")
    else:
        actions.append(
            {
                "type": "approve_before_record_write",
                "owner": "intake team",
                "status": "proposed",
                "reason": "All currently modeled intake fields are present; no writer is enabled in this pipeline.",
            }
        )

    if not review_reasons:
        outcome = "ready_for_human_approval"
    elif "missing_threshold_fields" in review_reasons:
        outcome = "blocked_missing_threshold"
    else:
        outcome = "manual_review_required"

    return {
        "version": 1,
        "write_safety": {
            "monday_writes_enabled": False,
            "drk_writes_enabled": False,
            "message": "This plan is advisory only and cannot change Monday or DRK.",
        },
        "referral": referral.model_dump(mode="json"),
        "validation": {
            "threshold_fields": list(THRESHOLD_FIELDS),
            "threshold_missing": threshold_missing,
            "supporting_missing": supporting_missing,
            "field_labels": FIELD_LABELS,
        },
        "monday_duplicate_check": duplicate_check.to_dict(),
        "outcome": outcome,
        "review_reasons": review_reasons,
        "proposed_actions": actions,
    }
