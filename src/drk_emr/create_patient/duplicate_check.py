"""Fail-closed DRK patient duplicate gate.

Search first. Zero stable results clear creation. Any candidate is verified against
DOB, MRN, phone, address/ZIP, and facility before create/fill is allowed.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

from drk_emr.common.browser import (
    emr_root,
    extract_patient_id_from_url,
    login,
    login_url_for,
    make_driver,
    patient_dashboard_url,
    require_env,
    safe_log,
)
from drk_emr.common.patient_search import (
    PatientSearchSnapshot,
    SearchCandidate,
    search_patients_on_dashboard,
)
from drk_emr.create_patient.schema import (
    DrkCreatePayloadDraft,
    DrkDuplicateCandidateAssessment,
    DrkDuplicateCheckDecision,
    DrkFieldComparison,
)


DemographicsFetcher = Callable[[Any, str], dict[str, Any] | None]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_name(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    return " ".join(re.sub(r"[^A-Za-z0-9]+", " ", text).upper().split())


def normalize_dob(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if "T" in text:
        text = text.split("T", 1)[0]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) == 8:
        # Prefer ISO when year-looking prefix; otherwise US MMDDYYYY.
        if int(digits[:4]) > 1900:
            return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"
        return f"{digits[4:]}-{digits[:2]}-{digits[2:4]}"
    return None


def normalize_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits or None


def normalize_zip(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits[:5] if len(digits) >= 5 else (digits or None)


def normalize_street(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = normalize_name(value)
    return cleaned or None


def normalize_mrn(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "n/a"}:
        return None
    return re.sub(r"\s+", "", text).upper() or None


def _compare(field_name: str, incoming: str | None, candidate: str | None) -> DrkFieldComparison:
    if not incoming:
        return DrkFieldComparison(
            field_name=field_name,
            incoming_value=incoming,
            candidate_value=candidate,
            outcome="missing_incoming",
        )
    if not candidate:
        return DrkFieldComparison(
            field_name=field_name,
            incoming_value=incoming,
            candidate_value=candidate,
            outcome="missing_candidate",
        )
    return DrkFieldComparison(
        field_name=field_name,
        incoming_value=incoming,
        candidate_value=candidate,
        outcome="match" if incoming == candidate else "mismatch",
    )


def canonical_search_name(payload: DrkCreatePayloadDraft) -> str:
    demo = payload.demographics
    parts = [demo.first_name, demo.middle_name, demo.last_name, demo.suffix]
    return " ".join(part for part in parts if part and str(part).strip())


def incoming_identity(payload: DrkCreatePayloadDraft) -> dict[str, str | None]:
    demo = payload.demographics
    address = payload.primary_address
    contact = payload.contact
    return {
        "name": normalize_name(canonical_search_name(payload)),
        "dob": normalize_dob(demo.date_of_birth),
        "mrn": None,  # create draft does not currently carry a trusted MRN
        "phone": normalize_phone(contact.primary_phone) or normalize_phone(contact.secondary_phone),
        "street": normalize_street(address.address_line_1),
        "zip": normalize_zip(address.zip_code),
        "facility": normalize_name(payload.admission.facility_query),
    }


def candidate_identity(candidate: SearchCandidate, demographics: dict[str, Any] | None) -> dict[str, str | None]:
    data = demographics or {}
    full_name = data.get("fullName") or candidate.display_name
    if not full_name:
        full_name = " ".join(
            part
            for part in (
                data.get("firstName") or candidate.first_name,
                data.get("lastName") or candidate.last_name,
            )
            if part
        )
    street = data.get("address1") or data.get("fullAddress")
    return {
        "name": normalize_name(str(full_name) if full_name else None),
        "dob": normalize_dob(str(data.get("dateOfBirth") or candidate.date_of_birth or "") or None),
        "mrn": normalize_mrn(
            None if data.get("mrn") in (None, "") else str(data.get("mrn"))
        )
        or normalize_mrn(candidate.mrn),
        "phone": normalize_phone(str(data.get("phoneNumber") or "") or None)
        or normalize_phone(candidate.phone),
        "street": normalize_street(str(street) if street else None),
        "zip": normalize_zip(str(data.get("zipCode") or "") or None),
        "facility": normalize_name(
            str(data.get("facilityName") or candidate.facility_name or "") or None
        ),
    }


def assess_candidate(
    *,
    incoming: dict[str, str | None],
    candidate: SearchCandidate,
    demographics: dict[str, Any] | None,
) -> DrkDuplicateCandidateAssessment:
    if demographics is None:
        return DrkDuplicateCandidateAssessment(
            patient_id=candidate.patient_id,
            display_name=candidate.display_name,
            classification="inconclusive",
            reason="missing_candidate_demographics",
            comparisons=[],
            demographics=None,
        )

    values = candidate_identity(candidate, demographics)
    comparisons = [
        _compare("name", incoming["name"], values["name"]),
        _compare("dob", incoming["dob"], values["dob"]),
        _compare("mrn", incoming["mrn"], values["mrn"]),
        _compare("phone", incoming["phone"], values["phone"]),
        _compare("street", incoming["street"], values["street"]),
        _compare("zip", incoming["zip"], values["zip"]),
        _compare("facility", incoming["facility"], values["facility"]),
    ]
    by_field = {item.field_name: item for item in comparisons}

    dob = by_field["dob"]
    phone = by_field["phone"]
    street = by_field["street"]
    zip_code = by_field["zip"]
    mrn = by_field["mrn"]
    facility = by_field["facility"]

    location_match = street.outcome == "match" or (
        street.outcome != "mismatch" and zip_code.outcome == "match"
    )
    phone_match = phone.outcome == "match"
    mrn_match = mrn.outcome == "match"
    corroborating = phone_match or location_match or facility.outcome == "match"

    if mrn_match:
        return DrkDuplicateCandidateAssessment(
            patient_id=candidate.patient_id,
            display_name=candidate.display_name or demographics.get("fullName"),
            classification="duplicate",
            reason="trusted_mrn_match",
            comparisons=comparisons,
            demographics=demographics,
        )
    if dob.outcome == "match":
        return DrkDuplicateCandidateAssessment(
            patient_id=candidate.patient_id,
            display_name=candidate.display_name or demographics.get("fullName"),
            classification="duplicate",
            reason="name_search_hit_with_matching_dob",
            comparisons=comparisons,
            demographics=demographics,
        )
    if dob.outcome == "mismatch" and corroborating:
        return DrkDuplicateCandidateAssessment(
            patient_id=candidate.patient_id,
            display_name=candidate.display_name or demographics.get("fullName"),
            classification="suspicious",
            reason="corroborating_contact_or_location_with_different_dob",
            comparisons=comparisons,
            demographics=demographics,
        )
    if dob.outcome == "mismatch" and not corroborating:
        return DrkDuplicateCandidateAssessment(
            patient_id=candidate.patient_id,
            display_name=candidate.display_name or demographics.get("fullName"),
            classification="different_person",
            reason="different_dob_without_corroborating_identifiers",
            comparisons=comparisons,
            demographics=demographics,
        )
    return DrkDuplicateCandidateAssessment(
        patient_id=candidate.patient_id,
        display_name=candidate.display_name or demographics.get("fullName"),
        classification="inconclusive",
        reason="insufficient_identity_evidence",
        comparisons=comparisons,
        demographics=demographics,
    )


def decide_from_assessments(
    *,
    snapshot: PatientSearchSnapshot,
    assessments: list[DrkDuplicateCandidateAssessment],
) -> DrkDuplicateCheckDecision:
    checked_at = utc_now_iso()
    candidate_ids = [item.patient_id for item in assessments] or [
        item.patient_id for item in snapshot.candidates
    ]

    if snapshot.error:
        return DrkDuplicateCheckDecision(
            status="manual_review_required",
            searched_name=snapshot.query,
            result_count=snapshot.result_count,
            row_count=snapshot.row_count,
            summary_text=snapshot.summary_text,
            candidate_patient_ids=candidate_ids,
            assessments=assessments,
            reason=snapshot.error,
            clear_to_create=False,
            checked_at_utc=checked_at,
            error=snapshot.error,
        )

    if not snapshot.stable:
        return DrkDuplicateCheckDecision(
            status="manual_review_required",
            searched_name=snapshot.query,
            result_count=snapshot.result_count,
            row_count=snapshot.row_count,
            summary_text=snapshot.summary_text,
            candidate_patient_ids=candidate_ids,
            assessments=assessments,
            reason="search_results_unstable",
            clear_to_create=False,
            checked_at_utc=checked_at,
            error="search_results_unstable",
        )

    if snapshot.result_count == 0 and snapshot.row_count == 0 and not snapshot.candidates:
        return DrkDuplicateCheckDecision(
            status="clear_to_create",
            searched_name=snapshot.query,
            result_count=0,
            row_count=0,
            summary_text=snapshot.summary_text,
            candidate_patient_ids=[],
            assessments=[],
            reason="stable_zero_search_results",
            clear_to_create=True,
            checked_at_utc=checked_at,
        )

    if any(item.classification == "duplicate" for item in assessments):
        return DrkDuplicateCheckDecision(
            status="duplicate_found",
            searched_name=snapshot.query,
            result_count=snapshot.result_count,
            row_count=snapshot.row_count,
            summary_text=snapshot.summary_text,
            candidate_patient_ids=candidate_ids,
            assessments=assessments,
            reason="matching_patient_already_exists",
            clear_to_create=False,
            checked_at_utc=checked_at,
        )

    if any(item.classification in {"suspicious", "inconclusive"} for item in assessments):
        return DrkDuplicateCheckDecision(
            status="manual_review_required",
            searched_name=snapshot.query,
            result_count=snapshot.result_count,
            row_count=snapshot.row_count,
            summary_text=snapshot.summary_text,
            candidate_patient_ids=candidate_ids,
            assessments=assessments,
            reason="ambiguous_or_conflicting_candidate_evidence",
            clear_to_create=False,
            checked_at_utc=checked_at,
        )

    if assessments and all(item.classification == "different_person" for item in assessments):
        return DrkDuplicateCheckDecision(
            status="clear_to_create",
            searched_name=snapshot.query,
            result_count=snapshot.result_count,
            row_count=snapshot.row_count,
            summary_text=snapshot.summary_text,
            candidate_patient_ids=candidate_ids,
            assessments=assessments,
            reason="all_candidates_have_different_dob_without_corroboration",
            clear_to_create=True,
            checked_at_utc=checked_at,
        )

    return DrkDuplicateCheckDecision(
        status="manual_review_required",
        searched_name=snapshot.query,
        result_count=snapshot.result_count,
        row_count=snapshot.row_count,
        summary_text=snapshot.summary_text,
        candidate_patient_ids=candidate_ids,
        assessments=assessments,
        reason="unable_to_classify_search_results",
        clear_to_create=False,
        checked_at_utc=checked_at,
        error="unable_to_classify_search_results",
    )


def fetch_patient_demographics(driver: Any, patient_id: str) -> dict[str, Any] | None:
    """Open the patient dashboard and read GetPatientDemographics JSON for one ID."""
    root = emr_root(driver.current_url)
    dashboard = patient_dashboard_url(root, patient_id)
    marker = f"/PatientDashboard/GetPatientDemographics/{patient_id}"
    before = len(getattr(driver, "requests", []))
    driver.get(dashboard)
    WebDriverWait(driver, 25).until(lambda d: extract_patient_id_from_url(d.current_url) == str(patient_id))
    # Prefer network capture; fall back to a direct same-session fetch via browser JS.
    deadline = datetime.now(timezone.utc).timestamp() + 12
    while datetime.now(timezone.utc).timestamp() < deadline:
        for request in list(getattr(driver, "requests", []))[before:]:
            url = getattr(request, "url", "") or ""
            if marker.lower() not in url.lower():
                continue
            response = getattr(request, "response", None)
            if response is None:
                continue
            try:
                from drk_emr.common.patient_search import _decode_response_body

                payload = json.loads(_decode_response_body(response).decode("utf-8", errors="replace"))
            except Exception:
                continue
            data = payload.get("data") if isinstance(payload, dict) else None
            if isinstance(data, dict):
                return data
        import time

        time.sleep(0.2)

    # Cookie-authenticated XHR fallback through the open browser context.
    try:
        payload = driver.execute_async_script(
            """
            const patientId = arguments[0];
            const done = arguments[arguments.length - 1];
            fetch(`/PatientDashboard/GetPatientDemographics/${patientId}`, {
              credentials: 'same-origin',
              headers: { 'Accept': 'application/json' }
            })
              .then((response) => response.json())
              .then((body) => done(body))
              .catch((error) => done({ success: false, error: String(error) }));
            """,
            str(patient_id),
        )
    except Exception:
        return None
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            return data
    return None


def evaluate_duplicate_snapshot(
    snapshot: PatientSearchSnapshot,
    payload: DrkCreatePayloadDraft,
    *,
    demographics_by_id: dict[str, dict[str, Any] | None] | None = None,
    fetch_demographics: DemographicsFetcher | None = None,
    driver: Any | None = None,
) -> DrkDuplicateCheckDecision:
    """Pure-ish evaluator used by both live browser runs and unit tests."""
    if snapshot.error or not snapshot.stable:
        return decide_from_assessments(snapshot=snapshot, assessments=[])

    if snapshot.result_count == 0 and snapshot.row_count == 0 and not snapshot.candidates:
        return decide_from_assessments(snapshot=snapshot, assessments=[])

    if (
        snapshot.result_count is not None
        and snapshot.result_count > 0
        and snapshot.candidates
        and snapshot.result_count != len(snapshot.candidates)
    ):
        return DrkDuplicateCheckDecision(
            status="manual_review_required",
            searched_name=snapshot.query,
            result_count=snapshot.result_count,
            row_count=snapshot.row_count,
            summary_text=snapshot.summary_text,
            candidate_patient_ids=[item.patient_id for item in snapshot.candidates],
            assessments=[],
            reason="search_count_candidate_mismatch",
            clear_to_create=False,
            checked_at_utc=utc_now_iso(),
            error="search_count_candidate_mismatch",
        )

    incoming = incoming_identity(payload)
    if not incoming["name"] or not incoming["dob"]:
        return DrkDuplicateCheckDecision(
            status="manual_review_required",
            searched_name=snapshot.query,
            result_count=snapshot.result_count,
            row_count=snapshot.row_count,
            summary_text=snapshot.summary_text,
            candidate_patient_ids=[item.patient_id for item in snapshot.candidates],
            assessments=[],
            reason="incoming_name_or_dob_missing",
            clear_to_create=False,
            checked_at_utc=utc_now_iso(),
            error="incoming_name_or_dob_missing",
        )

    assessments: list[DrkDuplicateCandidateAssessment] = []
    for candidate in snapshot.candidates:
        demographics = None
        if demographics_by_id is not None and candidate.patient_id in demographics_by_id:
            demographics = demographics_by_id[candidate.patient_id]
        elif fetch_demographics is not None and driver is not None and candidate.patient_id:
            demographics = fetch_demographics(driver, candidate.patient_id)
        else:
            # Search table NAME/DOB/MRN/PHONE is enough to score a row without an API id.
            demographics = {
                "id": int(candidate.patient_id) if candidate.patient_id.isdigit() else candidate.patient_id,
                "fullName": candidate.display_name,
                "firstName": candidate.first_name,
                "lastName": candidate.last_name,
                "dateOfBirth": candidate.date_of_birth,
                "mrn": candidate.mrn,
                "phoneNumber": candidate.phone,
                "facilityName": candidate.facility_name,
            }
        assessments.append(
            assess_candidate(incoming=incoming, candidate=candidate, demographics=demographics)
        )
    return decide_from_assessments(snapshot=snapshot, assessments=assessments)


def require_clear_to_create(decision: DrkDuplicateCheckDecision) -> None:
    """Hard gate for fill/create orchestration."""
    if decision.status != "clear_to_create" or not decision.clear_to_create:
        raise RuntimeError(
            "DRK create/fill blocked by duplicate gate: "
            f"status={decision.status} reason={decision.reason}"
        )


def write_duplicate_check_audit(path: str | Path, decision: DrkDuplicateCheckDecision) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(decision.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    temporary.replace(output)
    os.chmod(output, 0o600)
    return output


def run_duplicate_check(
    driver: Any,
    payload: DrkCreatePayloadDraft,
    *,
    fetch_demographics: DemographicsFetcher = fetch_patient_demographics,
    return_to_dashboard: bool = True,
) -> DrkDuplicateCheckDecision:
    """Search for the patient on the dashboard and classify any candidates."""
    query = canonical_search_name(payload)
    snapshot = search_patients_on_dashboard(driver, query)
    decision = evaluate_duplicate_snapshot(
        snapshot,
        payload,
        fetch_demographics=fetch_demographics,
        driver=driver,
    )
    if return_to_dashboard:
        root = emr_root(driver.current_url)
        driver.get(f"{root}/Dashboard")
        WebDriverWait(driver, 20).until(ec.presence_of_element_located((By.ID, "dashPatientSearch")))
    safe_log(
        f"DRK duplicate gate status={decision.status} clear_to_create={decision.clear_to_create} "
        f"reason={decision.reason}"
    )
    return decision


def check_duplicates_for_payload(
    payload: DrkCreatePayloadDraft,
    *,
    output_path: str | Path | None = None,
    profile_dir: str | Path | None = None,
) -> DrkDuplicateCheckDecision:
    """Login, run the dashboard duplicate gate, and optionally write an audit file."""
    import shutil

    from dotenv import load_dotenv

    load_dotenv()
    emr_url = require_env("EMR_URL")
    username = require_env("EMR_USERNAME")
    password = require_env("EMR_PASSWORD")

    cleanup_profile = False
    if profile_dir is None:
        profile_dir = Path("output") / "drk-duplicate-check" / "_chrome_profile"
        cleanup_profile = True
    profile = Path(profile_dir)
    if profile.exists():
        shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    os.chmod(profile, 0o700)

    driver = None
    try:
        driver = make_driver(profile)
        login(driver, login_url_for(emr_url), username, password)
        decision = run_duplicate_check(driver, payload)
        if output_path is not None:
            write_duplicate_check_audit(output_path, decision)
        return decision
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
        if cleanup_profile and profile.exists():
            shutil.rmtree(profile, ignore_errors=True)
