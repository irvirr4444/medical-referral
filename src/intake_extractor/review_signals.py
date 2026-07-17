"""Deterministic local heuristics that flag weak/suspicious candidate fields.

These signals do not patch values themselves. They only guide the reviewer
prompt and slightly relax (never remove) patch thresholds for flagged fields.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .review_targets import TARGETED_REVIEW_FIELDS


ADDRESS_LIKE_RE = re.compile(
    r"^\s*\d+\s+\S+.*(st|street|ave|avenue|rd|road|blvd|boulevard|dr|drive|ln|lane|ct|court|way)\b",
    re.IGNORECASE,
)
ADMIN_SERVICE_RE = re.compile(
    r"\b(follow[- ]?up|appointment|callback|call back|routing|cover sheet|fax cover|"
    r"please review|for your records|notification|acknowledgement|acknowledgment)\b",
    re.IGNORECASE,
)
ICD_HEAVY_RE = re.compile(r"\b[A-TV-Z][0-9][0-9A-Z](?:\.[0-9A-Z]{1,4})?\b")
DATE_LIKE_RE = re.compile(r"^\s*\d{1,2}/\d{1,2}/\d{2,4}\s*$")


@dataclass(frozen=True)
class FieldSignal:
    field: str
    reason: str
    severity: str = "review"


def collect_field_signals(candidate: dict[str, Any]) -> list[FieldSignal]:
    """Return suspicious patterns for targeted fields only."""
    signals: list[FieldSignal] = []
    for field in TARGETED_REVIEW_FIELDS:
        detector = _DETECTORS.get(field)
        if detector is None:
            continue
        signals.extend(detector(candidate.get(field), candidate))
    return signals


def suspicious_fields(candidate: dict[str, Any]) -> set[str]:
    return {signal.field for signal in collect_field_signals(candidate)}


def format_signals_for_prompt(signals: list[FieldSignal]) -> str:
    if not signals:
        return "No local suspicious-field heuristics fired. Still verify the priority fields against the PDF."
    lines = ["Local heuristics flagged these candidate fields for careful review:"]
    for signal in signals:
        lines.append(f"- {signal.field}: {signal.reason}")
    return "\n".join(lines)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    return False


def _detect_requested_services(value: Any, candidate: dict[str, Any]) -> list[FieldSignal]:
    signals: list[FieldSignal] = []
    if _is_missing(value):
        # Multi-page packets often contain recoverable orders.
        pages = candidate.get("pages_used")
        if isinstance(pages, int) and pages >= 2:
            signals.append(
                FieldSignal(
                    "requested_services",
                    "list is empty on a multi-page packet; check for explicit orders/referrals.",
                )
            )
        return signals

    if not isinstance(value, list):
        return [FieldSignal("requested_services", "value is not a list of service objects.")]

    admin_hits = 0
    unnamed = 0
    for item in value:
        if not isinstance(item, dict):
            continue
        service = str(item.get("service") or "")
        instructions = str(item.get("instructions") or "")
        haystack = f"{service} {instructions}"
        if ADMIN_SERVICE_RE.search(haystack):
            admin_hits += 1
        if not service.strip():
            unnamed += 1

    if admin_hits:
        signals.append(
            FieldSignal(
                "requested_services",
                f"{admin_hits} item(s) look like follow-up/admin content rather than ordered services.",
            )
        )
    if unnamed:
        signals.append(FieldSignal("requested_services", f"{unnamed} item(s) lack a service label."))
    if len(value) >= 12:
        signals.append(
            FieldSignal(
                "requested_services",
                "very long list; check whether med history/profile rows were included as orders.",
            )
        )
    return signals


def _detect_diagnosis_text(value: Any, _candidate: dict[str, Any]) -> list[FieldSignal]:
    if _is_missing(value):
        return [FieldSignal("diagnosis_text", "null/empty; look for assessment/reason-for-referral text.")]
    text = str(value)
    signals: list[FieldSignal] = []
    if len(text) > 280:
        signals.append(FieldSignal("diagnosis_text", "overlong; may include chart narrative beyond diagnosis."))
    code_hits = len(ICD_HEAVY_RE.findall(text))
    if code_hits >= 3:
        signals.append(
            FieldSignal(
                "diagnosis_text",
                "contains many ICD-looking tokens; prefer human-readable diagnosis wording.",
            )
        )
    return signals


def _detect_referring_provider(value: Any, candidate: dict[str, Any]) -> list[FieldSignal]:
    if _is_missing(value):
        # Only nudge when other referring contact evidence exists.
        if any(not _is_missing(candidate.get(field)) for field in ("referring_facility", "referring_phone", "referring_fax")):
            return [
                FieldSignal(
                    "referring_provider_name",
                    "null while other referring contact fields are present; confirm whether an ordering clinician is named.",
                )
            ]
        return []
    text = str(value)
    if ADDRESS_LIKE_RE.search(text):
        return [FieldSignal("referring_provider_name", "value looks like an address, not a clinician name.")]
    return []


def _detect_referring_facility(value: Any, candidate: dict[str, Any]) -> list[FieldSignal]:
    if _is_missing(value):
        if any(not _is_missing(candidate.get(field)) for field in ("referring_provider_name", "referring_phone", "referring_fax")):
            return [
                FieldSignal(
                    "referring_facility",
                    "null while other referring fields are present; check fax header/cover-sheet sender org.",
                )
            ]
        return []
    text = str(value)
    if ADDRESS_LIKE_RE.search(text):
        return [FieldSignal("referring_facility", "value looks like a street address; facility should be an organization name or null.")]
    return []


def _digits(value: Any) -> str:
    if value is None:
        return ""
    return "".join(ch for ch in str(value) if ch.isdigit())


def _detect_referring_phone(value: Any, candidate: dict[str, Any]) -> list[FieldSignal]:
    if _is_missing(value) and not _is_missing(candidate.get("referring_facility")):
        return [FieldSignal("referring_phone", "null despite referring_facility being set; check referrer contact block.")]
    phone_digits = _digits(value)
    if phone_digits and phone_digits == _digits(candidate.get("patient_phone")):
        return [FieldSignal("referring_phone", "matches patient_phone; verify this is not the wrong contact section.")]
    return []


def _detect_referring_fax(value: Any, candidate: dict[str, Any]) -> list[FieldSignal]:
    if _is_missing(value) and not _is_missing(candidate.get("referring_facility")):
        return [FieldSignal("referring_fax", "null despite referring_facility being set; check fax header/referrer block.")]
    return []


def _detect_patient_address(value: Any, _candidate: dict[str, Any]) -> list[FieldSignal]:
    if _is_missing(value):
        return [FieldSignal("patient_address", "null/empty; look for active/current or discharge destination address.")]
    return []


def _detect_referral_date(value: Any, _candidate: dict[str, Any]) -> list[FieldSignal]:
    if _is_missing(value):
        return [FieldSignal("referral_date", "null/empty; look for order/referral/signature date (not fax timestamp).")]
    if not DATE_LIKE_RE.match(str(value)):
        return [FieldSignal("referral_date", "value is not a simple date; confirm it is the clinical referral/order date.")]
    return []


_DETECTORS = {
    "requested_services": _detect_requested_services,
    "diagnosis_text": _detect_diagnosis_text,
    "referring_provider_name": _detect_referring_provider,
    "referring_facility": _detect_referring_facility,
    "referring_phone": _detect_referring_phone,
    "referring_fax": _detect_referring_fax,
    "patient_address": _detect_patient_address,
    "referral_date": _detect_referral_date,
}
