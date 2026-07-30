"""Read-only Monday duplicate checks used by the referral intake planner."""

from __future__ import annotations

from pathlib import Path

from intake_extractor.schema import ReferralIntake
from intake_plan import DuplicateCheck
from master_sheet_reader import (
    DEFAULT_RESULT_FIELDS,
    fetch_items_by_name_search,
    find_patients,
    load_export_items,
    select_fields,
)


def check_duplicates_disabled() -> DuplicateCheck:
    """Represent a deliberately disabled duplicate lookup."""
    return DuplicateCheck(mode="disabled", status="not_checked", reason="Monday duplicate checks were disabled for this run.")


def check_duplicates_from_snapshot(
    referral: ReferralIntake,
    *,
    records_file: str | Path,
    include_full_row: bool = False,
) -> DuplicateCheck:
    """Check a local Master Sheet export without making a network request."""
    _, items = load_export_items(records_file)
    return _match_referral(
        referral,
        items,
        mode="snapshot",
        include_full_row=include_full_row,
    )


def check_duplicates_live(
    referral: ReferralIntake,
    *,
    include_full_row: bool = False,
) -> DuplicateCheck:
    """Check current Monday data through the read-only name search endpoint."""
    if not _has_identity_for_check(referral):
        return _identity_missing_result(mode="live-readonly")
    result = fetch_items_by_name_search(name=referral.patient_name or "", max_items=None)
    return _match_referral(
        referral,
        result.items,
        mode="live-readonly",
        include_full_row=include_full_row,
    )


def _match_referral(
    referral: ReferralIntake,
    items: list[dict],
    *,
    mode: str,
    include_full_row: bool,
) -> DuplicateCheck:
    if not _has_identity_for_check(referral):
        return _identity_missing_result(mode=mode)
    matches = find_patients(items, name=referral.patient_name or "", dob=referral.patient_dob)
    candidates = tuple(_candidate_payload(item, include_full_row=include_full_row) for item in matches)
    if candidates:
        return DuplicateCheck(
            mode=mode,
            status="candidates_found",
            candidates=candidates,
            reason="Exact normalized name and DOB match; human confirmation is still required.",
        )
    return DuplicateCheck(mode=mode, status="no_candidates_found")


def _has_identity_for_check(referral: ReferralIntake) -> bool:
    return bool(referral.patient_name and referral.patient_dob)


def _identity_missing_result(*, mode: str) -> DuplicateCheck:
    return DuplicateCheck(
        mode=mode,
        status="skipped_missing_identity",
        reason="Duplicate matching requires both patient name and date of birth.",
    )


def _candidate_payload(item: dict, *, include_full_row: bool) -> dict:
    candidate = select_fields(item, DEFAULT_RESULT_FIELDS)
    if include_full_row:
        candidate["monday_item"] = item
    return candidate
