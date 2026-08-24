from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from drk_emr.common.patient_search import PatientSearchSnapshot, SearchCandidate, parse_summary_count
from drk_emr.create_patient.duplicate_check import (
    assess_candidate,
    evaluate_duplicate_snapshot,
    incoming_identity,
    normalize_dob,
    normalize_phone,
    require_clear_to_create,
    write_duplicate_check_audit,
)
from drk_emr.create_patient.fill import submit_create_patient
from drk_emr.create_patient.schema import (
    DrkAddressDraft,
    DrkContactDraft,
    DrkCreatePayloadDraft,
    DrkDemographicsDraft,
    DrkDuplicateCheckDecision,
)


def _payload(**overrides: object) -> DrkCreatePayloadDraft:
    base = DrkCreatePayloadDraft(
        demographics=DrkDemographicsDraft(
            first_name="Alva",
            last_name="Butler",
            date_of_birth="1940-10-04",
        ),
        primary_address=DrkAddressDraft(
            address_line_1="5316 FISHERSOUND LN",
            city="APOLLO BEACH",
            state="FL",
            zip_code="33572",
        ),
        contact=DrkContactDraft(primary_phone="(260) 438-4646"),
    )
    return base.model_copy(update=overrides)


def _candidate(**overrides: object) -> SearchCandidate:
    values = {
        "patient_id": "55125",
        "display_name": "Alva Butler",
        "first_name": "Alva",
        "last_name": "Butler",
        "date_of_birth": "1940-10-04T00:00:00",
        "mrn": "1087998220",
        "phone": "(260) 438-4646",
        "facility_name": "WCW Florida Home",
    }
    values.update(overrides)
    return SearchCandidate(**values)  # type: ignore[arg-type]


def _snapshot(
    *,
    result_count: int,
    candidates: list[SearchCandidate] | tuple[SearchCandidate, ...] = (),
    stable: bool = True,
    error: str | None = None,
    row_count: int | None = None,
) -> PatientSearchSnapshot:
    rows = len(candidates) if row_count is None else row_count
    return PatientSearchSnapshot(
        query="Alva Butler",
        summary_text=f"{result_count} results · matched on name",
        result_count=result_count,
        row_count=rows,
        candidates=tuple(candidates),
        stable=stable,
        error=error,
    )


def test_parse_summary_count() -> None:
    assert parse_summary_count("0 results · matched on name") == 0
    assert parse_summary_count("2 results · matched on name") == 2
    assert parse_summary_count("weird") is None


def test_normalize_helpers() -> None:
    assert normalize_dob("10/04/1940") == "1940-10-04"
    assert normalize_dob("1940-10-04T00:00:00") == "1940-10-04"
    assert normalize_phone("+1 (260) 438-4646") == "2604384646"


def test_zero_results_are_clear_to_create() -> None:
    decision = evaluate_duplicate_snapshot(_snapshot(result_count=0, row_count=0), _payload())
    assert decision.status == "clear_to_create"
    assert decision.clear_to_create is True
    require_clear_to_create(decision)


def test_exact_dob_match_is_duplicate() -> None:
    decision = evaluate_duplicate_snapshot(
        _snapshot(result_count=1, candidates=[_candidate()]),
        _payload(),
        demographics_by_id={
            "55125": {
                "fullName": "Alva Butler",
                "dateOfBirth": "1940-10-04T00:00:00",
                "mrn": "1087998220",
                "phoneNumber": "(260) 438-4646",
                "address1": "5316 FISHERSOUND LN",
                "zipCode": "33572",
            }
        },
    )
    assert decision.status == "duplicate_found"
    assert decision.clear_to_create is False
    with pytest.raises(RuntimeError, match="blocked by duplicate gate"):
        require_clear_to_create(decision)


def test_multiple_candidates_with_one_duplicate_blocks() -> None:
    other = _candidate(
        patient_id="999",
        display_name="Alva Butler",
        date_of_birth="1930-01-01T00:00:00",
        mrn="1",
        phone="5555555555",
    )
    decision = evaluate_duplicate_snapshot(
        _snapshot(result_count=2, candidates=[other, _candidate()]),
        _payload(),
        demographics_by_id={
            "999": {
                "fullName": "Alva Butler",
                "dateOfBirth": "1930-01-01T00:00:00",
                "phoneNumber": "5555555555",
                "address1": "1 Other St",
                "zipCode": "11111",
            },
            "55125": {
                "fullName": "Alva Butler",
                "dateOfBirth": "1940-10-04T00:00:00",
                "phoneNumber": "(260) 438-4646",
                "address1": "5316 FISHERSOUND LN",
                "zipCode": "33572",
            },
        },
    )
    assert decision.status == "duplicate_found"
    assert "55125" in decision.candidate_patient_ids


def test_all_dob_mismatches_without_corroboration_clear() -> None:
    decision = evaluate_duplicate_snapshot(
        _snapshot(
            result_count=1,
            candidates=[
                _candidate(
                    patient_id="77",
                    date_of_birth="1933-02-02T00:00:00",
                    phone="1112223333",
                    mrn="77",
                )
            ],
        ),
        _payload(),
        demographics_by_id={
            "77": {
                "fullName": "Alva Butler",
                "dateOfBirth": "1933-02-02T00:00:00",
                "phoneNumber": "1112223333",
                "address1": "9 Nowhere Ave",
                "zipCode": "00000",
                "mrn": "77",
            }
        },
    )
    assert decision.status == "clear_to_create"
    assert decision.clear_to_create is True


def test_phone_match_with_different_dob_is_manual_review() -> None:
    decision = evaluate_duplicate_snapshot(
        _snapshot(
            result_count=1,
            candidates=[_candidate(date_of_birth="1939-01-01T00:00:00")],
        ),
        _payload(),
        demographics_by_id={
            "55125": {
                "fullName": "Alva Butler",
                "dateOfBirth": "1939-01-01T00:00:00",
                "phoneNumber": "(260) 438-4646",
                "address1": "Different Street",
                "zipCode": "99999",
            }
        },
    )
    assert decision.status == "manual_review_required"
    assert decision.clear_to_create is False


def test_missing_demographics_fail_closed() -> None:
    decision = evaluate_duplicate_snapshot(
        _snapshot(result_count=1, candidates=[_candidate()]),
        _payload(),
        demographics_by_id={"55125": None},
    )
    assert decision.status == "manual_review_required"
    assert decision.assessments[0].classification == "inconclusive"


def test_unstable_or_timeout_fail_closed() -> None:
    unstable = evaluate_duplicate_snapshot(
        _snapshot(result_count=1, candidates=[_candidate()], stable=False),
        _payload(),
    )
    assert unstable.status == "manual_review_required"
    assert unstable.error == "search_results_unstable"

    timed_out = evaluate_duplicate_snapshot(
        _snapshot(result_count=1, candidates=[], error="search_results_unstable", stable=False),
        _payload(),
    )
    assert timed_out.status == "manual_review_required"


def test_mrn_match_is_duplicate_even_without_dob() -> None:
    assessment = assess_candidate(
        incoming={
            "name": "ALVA BUTLER",
            "dob": None,
            "mrn": "1087998220",
            "phone": None,
            "street": None,
            "zip": None,
            "facility": None,
        },
        candidate=_candidate(),
        demographics={"fullName": "Alva Butler", "mrn": "1087998220", "dateOfBirth": None},
    )
    assert assessment.classification == "duplicate"
    assert assessment.reason == "trusted_mrn_match"


def test_submit_create_patient_requires_clear_and_confirmation() -> None:
    blocked = DrkDuplicateCheckDecision(
        status="duplicate_found",
        reason="matching_patient_already_exists",
        clear_to_create=False,
    )
    with pytest.raises(RuntimeError, match="blocked by duplicate gate"):
        submit_create_patient(object(), duplicate_decision=blocked, confirm_create_patient=True)

    clear = DrkDuplicateCheckDecision(
        status="clear_to_create",
        reason="stable_zero_search_results",
        clear_to_create=True,
    )
    with pytest.raises(RuntimeError, match="confirm_create_patient=True"):
        submit_create_patient(object(), duplicate_decision=clear, confirm_create_patient=False)
    with pytest.raises(RuntimeError, match="intentionally unimplemented"):
        submit_create_patient(object(), duplicate_decision=clear, confirm_create_patient=True)


def test_write_duplicate_check_audit_uses_restricted_permissions(tmp_path: Path) -> None:
    decision = evaluate_duplicate_snapshot(_snapshot(result_count=0, row_count=0), _payload())
    path = write_duplicate_check_audit(tmp_path / "drk-duplicate-check.json", decision)
    assert path.is_file()
    if os.name != "nt":
        # Windows ACLs are not represented as POSIX 0600 mode bits by pathlib.
        assert (path.stat().st_mode & 0o777) == 0o600
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] == "clear_to_create"


def test_incoming_identity_reads_draft_fields() -> None:
    values = incoming_identity(_payload())
    assert values["name"] == "ALVA BUTLER"
    assert values["dob"] == "1940-10-04"
    assert values["phone"] == "2604384646"
    assert values["zip"] == "33572"
