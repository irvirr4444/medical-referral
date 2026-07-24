from __future__ import annotations

import re
from typing import Any

from ..models.schema import ReferralIntake


GENERIC_SERVICE_RE = re.compile(
    r"\b(referral|home health|physical therapy|skilled nursing|dme|durable medical equipment|uncoded)\b",
    re.IGNORECASE,
)
SPECIFIC_SERVICE_RE = re.compile(
    r"\b(wound care|dme|durable medical equipment|supplies|medication|test|imaging|wheelchair|prosthesis|lab)\b",
    re.IGNORECASE,
)
ADMIN_SERVICE_RE = re.compile(
    r"\b(follow[- ]?up|appointment|callback|call back|routing|cover sheet|fax cover|"
    r"please review|for your records|notification|acknowledgement|acknowledgment|social work)\b",
    re.IGNORECASE,
)
PUNCT_RE = re.compile(r"[^a-z0-9]+")
ABBREVIATED_FACILITY_RE = re.compile(r"\b[A-Z]{3,}\b")


def should_repair_requested_services(referral: ReferralIntake) -> bool:
    if (referral.pages_used or 0) <= 1:
        return False

    services = referral.requested_services or []
    if not services:
        return True

    names = [item.service or "" for item in services]
    generic_count = sum(1 for service in names if GENERIC_SERVICE_RE.search(service))
    specific_count = sum(1 for service in names if SPECIFIC_SERVICE_RE.search(service))

    if len(services) == 1:
        return generic_count == 1 and specific_count == 0

    return False


def should_repair_contacts(referral: ReferralIntake) -> bool:
    missing = sum(
        1
        for value in (
            referral.referring_provider_name,
            referral.referring_facility,
            referral.referring_phone,
            referral.referring_fax,
        )
        if not value
    )
    return missing >= 3


def should_repair_header_fields(referral: ReferralIntake) -> bool:
    return (
        should_repair_contacts(referral)
        or _looks_abbreviated_facility(referral.referring_facility)
        or _looks_ambiguous_phone(referral.patient_phone)
    )


def merge_repair_payload(primary: ReferralIntake, repair_payload: dict[str, Any]) -> ReferralIntake:
    merged = primary.model_dump(mode="json")

    for field in (
        "patient_mrn",
        "patient_address",
        "referring_provider_name",
        "referring_facility",
        "referring_phone",
        "referring_fax",
    ):
        if not merged.get(field) and repair_payload.get(field):
            merged[field] = repair_payload[field]

    merged["requested_services"] = _merge_requested_services(
        merged.get("requested_services") or [],
        repair_payload.get("requested_services") or [],
    )

    if not merged.get("notes") and repair_payload.get("notes"):
        merged["notes"] = repair_payload["notes"]

    return ReferralIntake.model_validate(merged)


def merge_contact_repair_payload(primary: ReferralIntake, repair_payload: dict[str, Any]) -> ReferralIntake:
    merged = primary.model_dump(mode="json")

    for field in (
        "patient_mrn",
        "patient_address",
        "referring_provider_name",
        "referring_facility",
        "referring_phone",
        "referring_fax",
    ):
        if not merged.get(field) and repair_payload.get(field):
            merged[field] = repair_payload[field]

    return ReferralIntake.model_validate(merged)


def merge_requested_services_payload(primary: ReferralIntake, repair_payload: dict[str, Any]) -> ReferralIntake:
    merged = primary.model_dump(mode="json")
    primary_services = merged.get("requested_services") or []
    repair_services = repair_payload.get("requested_services") or []
    candidate_services = _merge_requested_services(primary_services, repair_services)
    if _should_accept_requested_services_candidate(primary_services, candidate_services):
        merged["requested_services"] = candidate_services
    return ReferralIntake.model_validate(merged)


def merge_header_payload(primary: ReferralIntake, header_payload: dict[str, Any]) -> ReferralIntake:
    merged = primary.model_dump(mode="json")

    if not merged.get("patient_name") and header_payload.get("patient_name"):
        merged["patient_name"] = header_payload["patient_name"]
    if (_looks_ambiguous_phone(merged.get("patient_phone")) or not merged.get("patient_phone")) and header_payload.get(
        "patient_phone"
    ):
        merged["patient_phone"] = header_payload["patient_phone"]

    if header_payload.get("referring_facility"):
        merged["referring_facility"] = header_payload["referring_facility"]
    if header_payload.get("referring_phone"):
        merged["referring_phone"] = header_payload["referring_phone"]
    if header_payload.get("referring_fax"):
        merged["referring_fax"] = header_payload["referring_fax"]
    if not merged.get("referring_provider_name") and header_payload.get("referring_provider_name"):
        merged["referring_provider_name"] = header_payload["referring_provider_name"]

    return ReferralIntake.model_validate(merged)


def _merge_requested_services(primary: list[dict[str, Any]], repair: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not repair:
        return primary

    merged: dict[str, dict[str, Any]] = {}
    for item in primary + repair:
        key = _service_key(item.get("service"))
        if key is None:
            continue
        existing = merged.get(key)
        if existing is None or _service_richness(item) > _service_richness(existing):
            merged[key] = item

    merged_values = list(merged.values())
    if len(merged_values) < len(primary):
        return primary
    if len(merged_values) > len(primary):
        return merged_values
    if _service_list_richness(merged_values) > _service_list_richness(primary):
        return merged_values
    return primary


def _service_key(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(PUNCT_RE.sub(" ", str(value).lower()).split())
    return normalized or None


def _service_richness(item: dict[str, Any]) -> int:
    return sum(len(str(item.get(field) or "")) for field in ("service", "frequency", "instructions"))


def _service_list_richness(items: list[dict[str, Any]]) -> int:
    return sum(_service_richness(item) for item in items)


def _should_accept_requested_services_candidate(primary: list[dict[str, Any]], candidate: list[dict[str, Any]]) -> bool:
    if candidate == primary:
        return False
    if not candidate:
        return False

    if len(candidate) > len(primary) + 2:
        return False
    if _admin_service_hits(candidate) > _admin_service_hits(primary):
        return False
    if _generic_only_service_count(candidate) > _generic_only_service_count(primary) and _specific_service_count(
        candidate
    ) <= _specific_service_count(primary):
        return False
    if _service_list_richness(candidate) <= _service_list_richness(primary):
        return False
    return True


def _admin_service_hits(items: list[dict[str, Any]]) -> int:
    hits = 0
    for item in items:
        haystack = f"{item.get('service') or ''} {item.get('instructions') or ''}"
        if ADMIN_SERVICE_RE.search(haystack):
            hits += 1
    return hits


def _specific_service_count(items: list[dict[str, Any]]) -> int:
    return sum(1 for item in items if SPECIFIC_SERVICE_RE.search(str(item.get("service") or "")))


def _generic_only_service_count(items: list[dict[str, Any]]) -> int:
    total = 0
    for item in items:
        service = str(item.get("service") or "")
        if GENERIC_SERVICE_RE.search(service) and not SPECIFIC_SERVICE_RE.search(service):
            total += 1
    return total


def _looks_abbreviated_facility(value: str | None) -> bool:
    if not value:
        return True
    return bool(ABBREVIATED_FACILITY_RE.search(value))


def _looks_ambiguous_phone(value: str | None) -> bool:
    if not value:
        return True
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return len(digits) > 10

