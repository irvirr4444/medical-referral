"""Match a first-last slug to live Monday and DRK records."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Literal

from patient_profile.slug import search_names_from_slug, slugify_patient_key
from referral_pipeline.integrations.monday.reader import (
    _name_match_key,
    find_patients,
    item_values,
    normalize_dob,
    normalize_name,
    normalize_phone,
)

SourceName = Literal["all", "monday", "drk"]

MondayFetch = Callable[[str], list[dict[str, Any]]]
DrkSearch = Callable[[str], list[dict[str, Any]]]
DrkRead = Callable[[str], dict[str, Any]]


@dataclass
class PatientLookupResult:
    status: int
    body: dict[str, Any]


@dataclass
class _Outcome:
    kind: Literal["found", "empty", "ambiguous", "error"]
    record: dict[str, Any] | None = None
    candidates: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


def is_chrome_session_error(exc: BaseException | str) -> bool:
    text = str(exc).casefold()
    return any(
        marker in text
        for marker in (
            "session not created",
            "chrome instance exited",
            "invalid session id",
            "no such session",
            "no such window",
            "target window already closed",
            "disconnected: not connected to devtools",
            "chrome not reachable",
        )
    )


def short_source_error(exc: BaseException, *, source: str = "") -> str:
    _ = source
    text = str(exc).strip() or exc.__class__.__name__
    first = text.splitlines()[0].strip()
    if is_chrome_session_error(first):
        return "DRK chart is temporarily unavailable."
    if len(first) > 240:
        return first[:237] + "..."
    return first


def comparable_dob(value: str | None) -> str:
    text = (value or "").strip()
    if "T" in text:
        text = text.split("T", 1)[0]
    return normalize_dob(text)


def monday_record(item: dict[str, Any]) -> dict[str, Any]:
    values = item_values(item)
    return {
        "item_id": str(item.get("id") or ""),
        "group": str((item.get("group") or {}).get("title") or ""),
        "name": values.get("name") or "",
        "dob": values.get("dob") or "",
        "phone": values.get("patient_phone") or "",
        "address": values.get("patient_address") or "",
        "pos": values.get("pos") or "",
        "case_manager": values.get("case_manager") or "",
        "sent_to_cm": values.get("sent_to_cm") or "",
        "referral_sent": values.get("referral_sent_to_provider") or "",
        "provider": values.get("provider") or "",
        "due_date": values.get("due_date") or "",
        "appointment": values.get("appointment_date") or "",
        "scheduled": values.get("scheduled_status") or "",
        "scheduled_complete": values.get("scheduling_complete") or "",
        "visit": values.get("visit_status") or "",
        "sent_by": values.get("sent_by") or "",
        "agency_contact": values.get("agency_contact") or "",
        "agency_phone": values.get("agency_phone") or "",
        "stage": values.get("stage") or "",
        "referral_received": values.get("referral_received") or "",
        "qa_hold_reason": values.get("qa_hold_reason") or "",
        "discharge_reason": values.get("discharge_reason") or "",
    }


def drk_profile_from_cards(
    patient_id: str,
    cards: dict[str, Any],
    *,
    observed_at: str | None = None,
) -> dict[str, Any]:
    data = _first_data(cards.get("patient_information"))
    first_name = str(data.get("firstName") or "").strip()
    last_name = str(data.get("lastName") or "").strip()
    name = str(data.get("fullName") or "").strip() or " ".join(
        part for part in (first_name, last_name) if part
    )
    address = str(data.get("fullAddress") or "").strip()
    if not address:
        address = ", ".join(
            part
            for part in (
                data.get("address1"),
                data.get("address2"),
                data.get("city"),
                data.get("state"),
                data.get("zipCode"),
            )
            if part
        )
    snapshot = _drk_snapshot_fields(cards, patient_id)
    from patient_profile.sections import drk_sections_from_cards, latest_encounter

    encounter = latest_encounter(cards)
    sections = drk_sections_from_cards(cards)
    provider = str(snapshot.get("provider") or encounter.get("providerName") or "")
    visit = str(
        snapshot.get("visit_status")
        or snapshot.get("visit_outcome")
        or encounter.get("status")
        or ""
    )
    appointment = str(snapshot.get("appointment_date") or encounter.get("encounterDate") or "")
    return {
        "patient_id": str(data.get("id") or patient_id),
        "name": name,
        "first_name": first_name,
        "last_name": last_name,
        "dob": str(data.get("dateOfBirth") or snapshot.get("dob") or ""),
        "phone": str(data.get("phoneNumber") or ""),
        "email": str(data.get("email") or ""),
        "address": address,
        "city": str(data.get("city") or ""),
        "mrn": str(data.get("mrn") or ""),
        "status": str(data.get("patientStatusDisplayName") or data.get("status") or ""),
        "facility": str(data.get("facilityName") or ""),
        "home_health": str(data.get("homeHealthCompanyName") or ""),
        "provider": provider,
        "visit": visit,
        "appointment": appointment,
        "observed_at": observed_at or "",
        "sections": sections,
    }


def _first_data(card: Any) -> dict[str, Any]:
    if not isinstance(card, dict):
        return {}
    records = card.get("records") or []
    if not records or not isinstance(records[0], dict):
        return {}
    business = records[0].get("business_data")
    if isinstance(business, dict) and isinstance(business.get("data"), dict):
        return business["data"]
    return business if isinstance(business, dict) else {}


def _drk_snapshot_fields(cards: dict[str, Any], patient_id: str) -> dict[str, str]:
    try:
        from referral_pipeline.monitoring.drk_capture import (
            load_drk_capture_profile,
            normalize_drk_card_payloads,
        )

        snapshot = normalize_drk_card_payloads(
            cards,
            profile=load_drk_capture_profile(),
            observed_at=datetime.now(timezone.utc),
            expected_patient_id=str(patient_id),
            context="live patient profile",
        )
    except Exception:  # noqa: BLE001
        return {}
    details = snapshot.details if isinstance(snapshot.details, dict) else {}
    return {
        "dob": str(details.get("dob") or ""),
        "provider": snapshot.provider or "",
        "visit_status": snapshot.visit_status or "",
        "visit_outcome": snapshot.visit_outcome or "",
        "appointment_date": snapshot.appointment_date or "",
    }


def monday_candidate(item: dict[str, Any]) -> dict[str, str]:
    values = item_values(item)
    return {
        "item_id": str(item.get("id") or ""),
        "name": values.get("name") or "",
        "dob": values.get("dob") or "",
    }


def drk_candidate(row: dict[str, Any]) -> dict[str, str]:
    name = (
        str(row.get("display_name") or "").strip()
        or " ".join(
            part
            for part in (row.get("first_name"), row.get("last_name"))
            if part
        ).strip()
    )
    return {
        "patient_id": str(row.get("patient_id") or ""),
        "name": name,
        "dob": str(row.get("date_of_birth") or ""),
        "mrn": str(row.get("mrn") or ""),
    }


def identity_sync(
    monday: dict[str, Any] | None,
    drk: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not monday or not drk:
        return None
    fields = [
        _compare_field("dob", monday.get("dob"), drk.get("dob"), comparable_dob),
        _compare_field("phone", monday.get("phone"), drk.get("phone"), normalize_phone),
        _compare_field(
            "provider",
            monday.get("provider"),
            drk.get("provider"),
            lambda value: tuple(sorted(normalize_name(value).split())),
        ),
    ]
    statuses = {item["status"] for item in fields}
    if "mismatch" in statuses:
        status = "mismatch"
    elif "match" in statuses and "missing" in statuses:
        status = "partial"
    elif "match" in statuses:
        status = "match"
    else:
        status = "partial"
    return {"status": status, "fields": fields}


def _compare_field(
    name: str,
    monday_value: Any,
    drk_value: Any,
    normalizer: Callable[[str | None], Any],
) -> dict[str, str]:
    left = str(monday_value or "").strip()
    right = str(drk_value or "").strip()
    if not left or not right:
        status = "missing"
    elif normalizer(left) == normalizer(right) and normalizer(left):
        status = "match"
    else:
        status = "mismatch"
    return {
        "field": name,
        "monday": left,
        "drk": right,
        "status": status,
    }


def match_drk_candidates(
    candidates: list[dict[str, Any]],
    *,
    name: str,
    dob: str | None = None,
) -> _Outcome:
    name_key = _name_match_key(name)
    named = [
        row
        for row in candidates
        if _name_match_key(drk_candidate(row)["name"]) == name_key
    ]
    if dob and comparable_dob(dob):
        dob_key = comparable_dob(dob)
        with_dob = [row for row in named if comparable_dob(row.get("date_of_birth")) == dob_key]
        if with_dob:
            named = with_dob
    if len(named) == 1:
        return _Outcome(kind="found", record=named[0])
    if len(named) == 0:
        return _Outcome(kind="empty")
    return _Outcome(kind="ambiguous", candidates=[drk_candidate(row) for row in named])


def lookup_patient(
    slug: str,
    *,
    source: SourceName = "all",
    monday_fetch: MondayFetch | None = None,
    drk_search: DrkSearch | None = None,
    drk_read: DrkRead | None = None,
) -> PatientLookupResult:
    resolved_slug = slugify_patient_key(slug)
    given_family, last_first = search_names_from_slug(resolved_slug)
    query = {"given_family": given_family, "last_first": last_first, "slug": resolved_slug}
    if monday_fetch is None or drk_search is None or drk_read is None:
        from patient_profile.sources import live_drk_read, live_drk_search, live_monday_fetch

        monday_fn = monday_fetch or live_monday_fetch
        search_fn = drk_search or live_drk_search
        read_fn = drk_read or live_drk_read
    else:
        monday_fn = monday_fetch
        search_fn = drk_search
        read_fn = drk_read

    monday_outcome = _Outcome(kind="empty")
    drk_outcome = _Outcome(kind="empty")
    monday_ready = threading.Event()
    monday_holder: dict[str, _Outcome] = {}

    def run_monday() -> _Outcome:
        try:
            items = monday_fn(last_first)
            matches = find_patients(items, name=last_first)
            if len(matches) == 1:
                outcome = _Outcome(kind="found", record=monday_record(matches[0]))
            elif len(matches) == 0:
                outcome = _Outcome(kind="empty")
            else:
                outcome = _Outcome(
                    kind="ambiguous",
                    candidates=[monday_candidate(item) for item in matches],
                )
        except Exception as exc:  # noqa: BLE001 — surface source failures to the client
            outcome = _Outcome(kind="error", error=short_source_error(exc, source="monday"))
        monday_holder["outcome"] = outcome
        monday_ready.set()
        return outcome

    def run_drk() -> _Outcome:
        try:
            candidates = search_fn(given_family)
        except Exception as exc:  # noqa: BLE001
            return _Outcome(kind="error", error=short_source_error(exc, source="drk"))
        dob = None
        monday_ready.wait(timeout=30)
        monday_now = monday_holder.get("outcome")
        if monday_now and monday_now.kind == "found" and monday_now.record:
            dob = monday_now.record.get("dob") or None
        picked = match_drk_candidates(candidates, name=given_family, dob=dob)
        if picked.kind != "found" or not picked.record:
            return picked
        patient_id = str(picked.record.get("patient_id") or "")
        if not patient_id:
            return _Outcome(kind="empty")
        try:
            return _Outcome(kind="found", record=read_fn(patient_id))
        except Exception as exc:  # noqa: BLE001
            return _Outcome(kind="error", error=short_source_error(exc, source="drk"))

    if source == "monday":
        monday_outcome = run_monday()
        monday_ready.set()
    elif source == "drk":
        with ThreadPoolExecutor(max_workers=2) as pool:
            monday_future = pool.submit(run_monday)
            drk_future = pool.submit(run_drk)
            monday_outcome = monday_future.result()
            drk_outcome = drk_future.result()
    else:
        with ThreadPoolExecutor(max_workers=2) as pool:
            monday_future = pool.submit(run_monday)
            drk_future = pool.submit(run_drk)
            monday_outcome = monday_future.result()
            drk_outcome = drk_future.result()

    return _combine(
        source=source,
        query=query,
        monday_outcome=monday_outcome,
        drk_outcome=drk_outcome,
    )


def _combine(
    *,
    source: SourceName,
    query: dict[str, str],
    monday_outcome: _Outcome,
    drk_outcome: _Outcome,
) -> PatientLookupResult:
    observed_at = datetime.now(timezone.utc).isoformat()
    errors: list[dict[str, str]] = []
    if monday_outcome.kind == "error" and monday_outcome.error:
        errors.append({"source": "monday", "message": monday_outcome.error})
    if drk_outcome.kind == "error" and drk_outcome.error:
        errors.append({"source": "drk", "message": drk_outcome.error})

    monday = monday_outcome.record if monday_outcome.kind == "found" else None
    drk = drk_outcome.record if drk_outcome.kind == "found" else None

    body: dict[str, Any] = {
        "slug": query["slug"],
        "query": query,
        "observed_at": observed_at,
        "monday": monday,
        "drk": drk,
        "match": identity_sync(monday, drk),
        "errors": errors,
    }

    if source == "monday":
        return _single_source_result("monday", monday_outcome, body)
    if source == "drk":
        return _single_source_result("drk", drk_outcome, body)

    if monday_outcome.kind == "ambiguous" or drk_outcome.kind == "ambiguous":
        body["error"] = "ambiguous"
        body["candidates"] = {
            "monday": monday_outcome.candidates,
            "drk": drk_outcome.candidates,
        }
        body["monday"] = None
        body["drk"] = None
        body["match"] = None
        return PatientLookupResult(status=409, body=body)

    if monday_outcome.kind == "empty" and drk_outcome.kind == "empty" and not errors:
        body["error"] = "not_found"
        return PatientLookupResult(status=404, body=body)

    if errors and (monday or drk):
        return PatientLookupResult(status=502, body=body)
    if errors and not monday and not drk:
        body["error"] = "source_failed"
        return PatientLookupResult(status=502, body=body)
    if not monday and not drk:
        body["error"] = "not_found"
        return PatientLookupResult(status=404, body=body)
    return PatientLookupResult(status=200, body=body)


def _single_source_result(
    source: str,
    outcome: _Outcome,
    body: dict[str, Any],
) -> PatientLookupResult:
    if outcome.kind == "ambiguous":
        body["error"] = "ambiguous"
        body["candidates"] = {source: outcome.candidates}
        body["monday"] = body["monday"] if source != "monday" else None
        body["drk"] = body["drk"] if source != "drk" else None
        if source == "monday":
            body["monday"] = None
        if source == "drk":
            body["drk"] = None
            body["match"] = None
        return PatientLookupResult(status=409, body=body)
    if outcome.kind == "empty":
        body["error"] = "not_found"
        return PatientLookupResult(status=404, body=body)
    if outcome.kind == "error":
        body["error"] = "source_failed"
        return PatientLookupResult(status=502, body=body)
    return PatientLookupResult(status=200, body=body)
