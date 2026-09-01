from __future__ import annotations

from intake_extractor.schema import ReferralIntake
from referral_pipeline.intake_plan import DuplicateCheck, build_intake_plan, referral_missing_fields


def _complete_referral(**changes: object) -> ReferralIntake:
    payload = {
        "patient_name": "Example, Patient",
        "patient_dob": "01/02/1980",
        "patient_phone": "555-555-0100",
        "patient_address": "1 Example Street",
        "referring_facility": "Example Home Health",
        "diagnosis_text": "Chronic wound",
        "insurance_provider": "Example Insurance",
    }
    payload.update(changes)
    return ReferralIntake.model_validate(payload)


def test_threshold_gap_routes_to_intake_manager() -> None:
    referral = _complete_referral(patient_phone=None, patient_address=None)

    threshold_missing, supporting_missing = referral_missing_fields(referral)
    plan = build_intake_plan(referral, duplicate_check=DuplicateCheck(mode="disabled", status="not_checked"))

    assert threshold_missing == ["patient_phone", "patient_address"]
    assert supporting_missing == []
    assert plan["outcome"] == "blocked_missing_threshold"
    assert plan["proposed_actions"][-1]["type"] == "route_missing_information_to_intake_manager"
    assert plan["proposed_actions"][-1]["owner"] == "information-box manager"
    assert plan["write_safety"]["monday_writes_enabled"] is False


def test_duplicate_requires_review_even_when_complete() -> None:
    referral = _complete_referral()
    check = DuplicateCheck(mode="snapshot", status="duplicate_found", candidates=({"id": "1"},))

    plan = build_intake_plan(referral, duplicate_check=check)

    assert plan["outcome"] == "manual_review_required"
    assert plan["review_reasons"] == ["possible_duplicate"]
    assert any(action["type"] == "review_duplicate_candidate" for action in plan["proposed_actions"])


def test_supporting_gaps_remain_blocked_with_intake_manager() -> None:
    referral = _complete_referral(referring_facility=None, diagnosis_text=None, insurance_provider=None)

    plan = build_intake_plan(referral, duplicate_check=DuplicateCheck(mode="snapshot", status="no_candidates_found"))

    assert plan["outcome"] == "manual_review_required"
    assert plan["validation"]["supporting_missing"] == [
        "referring_facility",
        "clinical_information",
        "insurance_information",
    ]
    assert plan["proposed_actions"][-1]["type"] == "route_missing_information_to_intake_manager"
    assert plan["proposed_actions"][-1]["owner"] == "information-box manager"


def test_explicitly_none_counts_as_complete_for_seven_field_gate() -> None:
    referral = _complete_referral(referring_facility=None, insurance_provider=None)
    statuses = {
        "patient_name": "present",
        "patient_dob": "present",
        "patient_phone": "present",
        "patient_address": "present",
        "referring_facility": "explicitly_none",
        "clinical_information": "present",
        "insurance_information": "explicitly_none",
    }

    plan = build_intake_plan(
        referral,
        duplicate_check=DuplicateCheck(mode="snapshot", status="no_candidates_found"),
        field_status=statuses,
    )

    assert plan["outcome"] == "ready_for_human_approval"
    assert plan["validation"]["supporting_missing"] == []
