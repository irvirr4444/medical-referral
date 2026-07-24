from __future__ import annotations

import re
from typing import Any

from ..models.schema import ReferralIntake


DATE_RE = re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})\s*$")
EMBEDDED_CASE_RE = re.compile(r"(?<=[a-z])(?=[A-Z])")
MEDICATION_HINT_RE = re.compile(
    r"\b(mg|mcg|tablet|capsule|solution|ointment|spray|powder|insulin|oral|topical|refill|dispense)\b",
    re.IGNORECASE,
)
MEDICATION_SERVICE_RE = re.compile(
    r"\b(tablet|capsule|solution|ointment|spray|powder|insulin|injection|syrup|suspension)\b",
    re.IGNORECASE,
)
REFERRAL_SERVICE_HINT_RE = re.compile(
    r"\b(wound care|home health|physical therapy|occupational therapy|skilled nursing|dme|evaluation|referral|supplies|case management)\b",
    re.IGNORECASE,
)
ORG_HINT_RE = re.compile(
    r"\b(hospital|health|clinic|care|services|center|medical|home health|llc|inc|group|agency|community)\b",
    re.IGNORECASE,
)
PERSON_HINT_RE = re.compile(r"\b(md|do|np|aprn|pa|rn|physician|doctor|dr)\b", re.IGNORECASE)
ADDRESS_RE = re.compile(r"^\s*\d{2,}\s+\S+")
HOME_HEALTH_DISCIPLINE_MAP = {
    "skilled nursing": "Skilled Nursing (Home Health)",
    "physical therapy": "Physical Therapy (Home Health)",
    "occupational therapy": "Occupational Therapy (Home Health)",
    "speech therapy": "Speech Therapy (Home Health)",
    "social work": "Social Work (Home Health)",
}


def normalize_referral(referral: ReferralIntake) -> ReferralIntake:
    data = referral.model_dump(mode="json")

    for field, value in list(data.items()):
        if isinstance(value, str):
            data[field] = _clean_string(value)

    data["patient_dob"] = _normalize_date_string(data.get("patient_dob"))
    data["referral_date"] = _normalize_date_string(data.get("referral_date"))

    for phone_field in ("patient_phone", "referring_phone", "referring_fax"):
        data[phone_field] = _normalize_phone_string(data.get(phone_field))

    data["patient_address"] = _normalize_address(data.get("patient_address"))
    data["icd10_codes"] = _normalize_icd10_codes(data.get("icd10_codes") or [])
    data["requested_services"] = _normalize_requested_services(data.get("requested_services") or [])
    data["referring_provider_name"] = _split_embedded_case_words(data.get("referring_provider_name"))
    data["referring_facility"] = _split_embedded_case_words(data.get("referring_facility"))
    data["insurance_provider"] = _split_embedded_case_words(data.get("insurance_provider"))
    _normalize_referral_contacts(data)
    data["notes"] = _truncate_notes(data.get("notes"))

    return ReferralIntake.model_validate(data)


def _clean_string(value: str | None) -> str | None:
    if value is None:
        return None
    collapsed = " ".join(str(value).replace("\n", " ").split())
    return collapsed or None


def _normalize_date_string(value: str | None) -> str | None:
    cleaned = _clean_string(value)
    if cleaned is None:
        return None
    match = DATE_RE.match(cleaned)
    if not match:
        return cleaned
    month, day, year = match.groups()
    year_int = int(year)
    if len(year) == 2:
        year_int += 2000 if year_int <= 69 else 1900
    return f"{int(month):02d}/{int(day):02d}/{year_int:04d}"


def _normalize_phone_string(value: str | None) -> str | None:
    cleaned = _clean_string(value)
    if cleaned is None:
        return None
    digits = "".join(ch for ch in cleaned if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return cleaned


def _normalize_address(value: str | None) -> str | None:
    cleaned = _clean_string(value)
    if cleaned is None:
        return None
    cleaned = re.sub(r"\s*,\s*", ", ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\b(\d{5})(\d{4})\b", r"\1-\2", cleaned)
    cleaned = re.sub(r",?\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)\b", r", \1 \2", cleaned)
    return cleaned


def _normalize_icd10_codes(codes: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for code in codes:
        cleaned = _clean_string(code)
        if cleaned is None:
            continue
        canonical = re.sub(r"[^A-Z0-9.]", "", cleaned.upper())
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        normalized.append(canonical)
    return normalized


def _normalize_requested_services(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str | None, str | None]] = set()

    for item in items:
        service = _normalize_service_label(_clean_string(item.get("service")), _clean_string(item.get("instructions")))
        frequency = _clean_string(item.get("frequency"))
        instructions = _clean_string(item.get("instructions"))
        if service is None and frequency is None and instructions is None:
            continue
        key = (_norm_key(service), _norm_key(frequency), _norm_key(instructions))
        if key in seen:
            continue
        seen.add(key)
        normalized.append({"service": service, "frequency": frequency, "instructions": instructions})

    if _looks_like_medication_profile(normalized):
        return []

    return _postprocess_service_items(normalized)


def _normalize_referral_contacts(data: dict[str, Any]) -> None:
    provider = data.get("referring_provider_name")
    facility = data.get("referring_facility")
    notes = data.get("notes")

    if provider and _looks_like_org(provider) and not facility:
        data["referring_facility"] = provider
        data["referring_provider_name"] = None
        provider = None
        facility = data["referring_facility"]

    if facility and _looks_like_person(facility) and not provider:
        data["referring_provider_name"] = facility
        data["referring_facility"] = None
        provider = data["referring_provider_name"]
        facility = None

    if facility and _looks_like_address(facility) and provider:
        data["referring_facility"] = None
        data["notes"] = _merge_notes(notes, f"Referring address listed separately: {facility}.")


def _looks_like_medication_profile(items: list[dict[str, Any]]) -> bool:
    if len(items) < 8:
        return False
    medication_like = 0
    referral_like = 0
    for item in items:
        service = item.get("service") or ""
        instructions = item.get("instructions") or ""
        haystack = f"{service} {instructions}"
        if MEDICATION_HINT_RE.search(haystack):
            medication_like += 1
        if REFERRAL_SERVICE_HINT_RE.search(haystack):
            referral_like += 1
    return medication_like / max(len(items), 1) >= 0.8 and referral_like == 0


def _normalize_service_label(service: str | None, instructions: str | None) -> str | None:
    if service is None:
        return None

    normalized = _split_embedded_case_words(service)
    lowered = normalized.lower()

    if ("dme" in lowered or "durable medical equipment" in lowered) and "wheelchair" in lowered:
        return "Durable Medical Equipment - Wheelchair"

    instruction_text = instructions or ""
    service_haystack = f"{normalized} {instruction_text}".strip()
    if MEDICATION_SERVICE_RE.search(normalized) or (
        MEDICATION_HINT_RE.search(service_haystack)
        and not REFERRAL_SERVICE_HINT_RE.search(normalized)
        and not lowered.startswith("medication ")
    ):
        normalized = re.sub(r"^(topical|oral)\s+", "", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\s+oral$", "", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\s{2,}", " ", normalized).strip()
        return f"Medication - {normalized}"

    return normalized


def _postprocess_service_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if _has_dme_supply_line_items(items):
        return [_collapse_dme_supply_items(items)]

    home_health_context = any("home health" in (_norm_key(item.get("service")) or "") for item in items)
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str | None, str | None]] = set()
    for item in items:
        service = _canonicalize_service(item.get("service"), home_health_context=home_health_context)
        frequency = item.get("frequency")
        instructions = item.get("instructions")
        key = (_norm_key(service), _norm_key(frequency), _norm_key(instructions))
        if key in seen:
            continue
        seen.add(key)
        deduped.append({"service": service, "frequency": frequency, "instructions": instructions})
    return deduped


def _canonicalize_service(service: str | None, *, home_health_context: bool) -> str | None:
    key = _norm_key(service) or ""
    if key == "wheelchair":
        return "Durable Medical Equipment - Wheelchair"
    if "home health" in key:
        for discipline, canonical in HOME_HEALTH_DISCIPLINE_MAP.items():
            if discipline in key:
                return canonical
    if home_health_context and key in HOME_HEALTH_DISCIPLINE_MAP:
        return HOME_HEALTH_DISCIPLINE_MAP[key]
    return service


def _has_dme_supply_line_items(items: list[dict[str, Any]]) -> bool:
    supply_items = 0
    for item in items:
        key = _norm_key(item.get("service")) or ""
        if key.startswith("dme wound care supplies "):
            supply_items += 1
    return supply_items >= 2


def _collapse_dme_supply_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    instructions: list[str] = []
    frequencies: list[str] = []
    context = None
    for item in items:
        key = _norm_key(item.get("service")) or ""
        if key.startswith("dme wound care supplies "):
            suffix = str(item.get("service")).split(" - ", 1)[-1]
            freq = _clean_string(item.get("frequency"))
            frequencies.append(freq or "")
            instructions.append(f"{suffix} - {freq}" if freq else suffix)
            context = context or _clean_string(item.get("instructions"))
    merged_instructions = "; ".join(part for part in instructions if part)
    if context:
        merged_instructions = f"{context}. {merged_instructions}" if merged_instructions else context
    return {
        "service": "DME Wound Care Supplies",
        "frequency": "For one month" if any("monthly" in freq.lower() for freq in frequencies if freq) else None,
        "instructions": merged_instructions or None,
    }


def _looks_like_org(value: str) -> bool:
    return bool(ORG_HINT_RE.search(value))


def _looks_like_person(value: str) -> bool:
    if PERSON_HINT_RE.search(value):
        return True
    tokens = value.replace(",", " ").split()
    alpha_tokens = [token for token in tokens if token.isalpha()]
    return 1 < len(alpha_tokens) <= 4 and not _looks_like_org(value) and not _looks_like_address(value)


def _looks_like_address(value: str) -> bool:
    return bool(ADDRESS_RE.match(value))


def _split_embedded_case_words(value: str | None) -> str | None:
    cleaned = _clean_string(value)
    if cleaned is None:
        return None
    return EMBEDDED_CASE_RE.sub(" ", cleaned)


def _merge_notes(existing: str | None, addition: str) -> str:
    if not existing:
        return addition
    if addition in existing:
        return existing
    return f"{existing} {addition}"


def _truncate_notes(value: str | None, *, limit: int = 500) -> str | None:
    cleaned = _clean_string(value)
    if cleaned is None:
        return None
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 3].rstrip() + "..."


def _norm_key(value: str | None) -> str | None:
    return None if value is None else re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

