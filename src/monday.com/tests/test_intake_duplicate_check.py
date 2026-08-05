from __future__ import annotations

import json

from intake_duplicate_check import check_duplicates_disabled, check_duplicates_from_snapshot
from intake_extractor.schema import ReferralIntake


def _item() -> dict:
    return {
        "id": "123",
        "name": "Example, Patient",
        "group": {"title": "Working pipeline"},
        "column_values": [
            {"id": "date12", "text": "Jan 2, 1980"},
            {"id": "phone", "text": "+1 (555) 555-0100"},
            {"id": "location", "text": "100 Example Street, Tampa, FL 33602"},
            {"id": "status5__1", "text": "Scheduled"},
        ],
    }


def test_disabled_check_never_returns_candidates() -> None:
    result = check_duplicates_disabled()

    assert result.mode == "disabled"
    assert result.status == "not_checked"
    assert not result.candidates


def test_snapshot_duplicate_check_requires_name_and_dob(tmp_path) -> None:
    records = tmp_path / "records.json"
    records.write_text(json.dumps({"board": {"id": "1"}, "items": [_item()]}))
    referral = ReferralIntake(
        patient_name="Patient, Example",
        patient_dob="01/02/1980",
        patient_phone="555-555-0100",
        patient_address="100 Example Street Tampa FL 33602",
    )

    result = check_duplicates_from_snapshot(referral, records_file=records)

    assert result.mode == "snapshot"
    assert result.status == "duplicate_found"
    assert result.candidates[0]["id"] == "123"
    assert result.candidates[0]["fields"]["patient_phone"] == "+1 (555) 555-0100"
    assert result.candidates[0]["fields"]["patient_address"] == "100 Example Street, Tampa, FL 33602"


def test_snapshot_duplicate_check_skips_when_dob_missing(tmp_path) -> None:
    records = tmp_path / "records.json"
    records.write_text(json.dumps({"board": {"id": "1"}, "items": [_item()]}))

    result = check_duplicates_from_snapshot(ReferralIntake(patient_name="Example, Patient"), records_file=records)

    assert result.status == "skipped_missing_identity"


def test_snapshot_duplicate_check_requires_all_four_fields_to_match(tmp_path) -> None:
    records = tmp_path / "records.json"
    records.write_text(json.dumps({"board": {"id": "1"}, "items": [_item()]}))
    referral = ReferralIntake(
        patient_name="Patient, Example",
        patient_dob="01/02/1980",
        patient_phone="555-555-9999",
        patient_address="100 Example Street, Tampa, FL 33602",
    )

    result = check_duplicates_from_snapshot(referral, records_file=records)

    assert result.status == "no_candidates_found"
