"""Platform feed field lists for each email humans receive."""

from __future__ import annotations

import json
from pathlib import Path

from gmail_alert.ids import ACTION_IDS, ConfirmationActionId

FeedField = tuple[str, str]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = _REPO_ROOT / "frontend" / "src" / "features" / "automation" / "fixtures"
_GONZALEZ = _FIXTURES / "canonicals" / "gonzalez-eric.json"
_BUTLER = _FIXTURES / "butlerCanonicalReferral.json"

_CM_EMAIL: dict[str, str] = {
    "Braxton Rickert": "brickert@westcoastwound.com",
    "Carla Bustillo": "cbustillo@westcoastwound.com",
    "Cole Winfield": "cwinfield@westcoastwound.com",
    "Donessa Ruiz": "druiz@westcoastwound.com",
    "Michelle Lagahit": "mlagahit@westcoastwound.com",
    "Nicole Chorvat": "nchorvat@westcoastwound.com",
}
_PROVIDER_EMAIL: dict[str, str] = {
    "Aaron Currie": "aaron_currie@hotmail.com",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _with_email(name: str, email: str | None = None) -> str:
    if email:
        return f"{name} ({email})"
    return name


def _cm(name: str) -> str:
    return _with_email(name, _CM_EMAIL.get(name))


def _provider(name: str) -> str:
    return _with_email(name, _PROVIDER_EMAIL.get(name))


def _gonzalez_intake_fields() -> tuple[FeedField, ...]:
    record = _load_json(_GONZALEZ)
    patient = record["patient"]
    name = patient["name"].get("full") or "Gonzalez, Eric"
    dob = patient.get("date_of_birth") or "—"
    phone = (patient.get("phones") or [{"number": "—"}])[0]["number"]
    address = patient.get("address") or {}
    address_line = ", ".join(
        part
        for part in (
            address.get("line_1"),
            address.get("city"),
            address.get("state"),
            address.get("postal_code"),
        )
        if part
    ) or "—"
    # Email needs a short wound line; fixture clinical.summary can be an essay.
    clinical = "Right groin unstageable pressure injury / wound cellulitis"
    insurances = record.get("insurances") or []
    if insurances:
        first = insurances[0]
        insurance = " · ".join(
            part
            for part in (
                first.get("payer_name"),
                first.get("policy_number"),
                first.get("insurance_type"),
            )
            if part
        )
    else:
        insurance = "—"
    hh = (
        ((record.get("home_health_or_hospice") or {}).get("organization") or {}).get("name")
        or "Not documented"
    )
    return (
        ("Identity", f"{name} · {dob} · {phone}"),
        ("Threshold", "Not met"),
        ("Completeness", "5/7"),
        ("Missing", "Home health or hospice agency"),
        ("Unclear", "Patient address"),
        ("Patient name", name),
        ("Date of birth", dob),
        ("Contact number", phone),
        ("Patient address", address_line),
        ("Home health or hospice agency", hh),
        ("Wound or clinical information", clinical),
        ("Insurance information", insurance),
    )


def _butler_partner_fields() -> tuple[FeedField, ...]:
    record = _load_json(_BUTLER)
    source = record.get("referral_source") or {}
    org = source.get("organization") or {}
    partner = source.get("provider_name") or org.get("contact_name") or "Referral partner"
    sent_by = (record.get("source") or {}).get("sent_by") or ""
    email = "—"
    if "<" in sent_by and ">" in sent_by:
        email = sent_by.split("<", 1)[1].rstrip(">")
    elif "@" in sent_by:
        email = sent_by
    partner_line = _with_email(partner, email if email != "—" else None)
    return (
        ("Referral partner", partner_line),
        ("Partner replied?", "Not recorded"),
    )


_FEED_BODIES: dict[ConfirmationActionId, tuple[FeedField, ...]] = {
    "confirm-intake-review": (),
    "confirm-partner-contacted": (),
    "cm-assigned": (
        ("Case manager", _cm("Cole Winfield")),
        ("Area", "Gardena / South Bay"),
        ("Wound or clinical information", "Lower extremity wound — home health referral"),
        ("Next step", "Select provider"),
        ("PDF", "Attached / available in chart"),
    ),
    "use-fallback-provider": (
        ("Patient location", "Pasadena, CA 91103"),
        ("Eligible providers in area", "Yes"),
        ("Suggested provider", _provider("Daniel Rowady")),
        ("Provider confirmed?", "No — timer passed"),
        ("Case manager", _cm("Donessa Ruiz")),
    ),
    "no-area-provider": (
        ("Patient location", "Needles, CA 92363"),
        ("Eligible providers in area", "No"),
        ("Territory", "No company provider in Needles"),
        ("Case manager", _cm("Nicole Chorvat")),
        ("Next step", "Nicole / management: fallback provider or discharge"),
    ),
    "send-referral-provider": (
        ("Patient", "Maria Alvarez"),
        ("Provider", _provider("Daniel Rowady")),
        ("Case manager", _cm("Donessa Ruiz")),
        ("Patient location", "Pasadena, CA 91103"),
        ("Wound or clinical information", "Pressure injury — home health wound care"),
        ("Packet", "Referral + clinical documents"),
        ("Next step", "Confirm availability and schedule within 24–48 hours"),
    ),
    "eod-follow-up-cm": (
        ("Provider", _provider("Charles Cho")),
        ("Case manager", _cm("Donessa Ruiz")),
        ("Provider selected", "August 11, 2026 at 11:01 PM"),
        ("Hours since provider selected", "18"),
        ("Scheduled status", "Not Scheduled"),
    ),
    "eod-escalate": (
        ("Provider", _provider("Aaron Currie")),
        ("Case manager", _cm("Braxton Rickert")),
        ("Provider selected", "August 8, 2026 at 2:15 PM"),
        ("Hours since provider selected", "51"),
        ("Scheduled status", "Not Scheduled"),
        ("CM follow-up", "Sent — still unresolved"),
    ),
    "not-seen-week-1": (
        ("Provider", _provider("Aaron Currie")),
        ("Case manager", _cm("Cole Winfield")),
        ("Visit status", "Not Seen"),
        ("Consecutive not seen", "1 week"),
        ("Last visit", "August 8, 2026 at 6:01 PM"),
    ),
    "not-seen-week-2": (
        ("Provider", _provider("Aaron Currie")),
        ("Case manager", _cm("Cole Winfield")),
        ("Visit status", "Not Seen"),
        ("Consecutive not seen", "2 weeks in a row"),
        ("Last visit", "August 10, 2026 at 6:01 PM"),
    ),
    "not-seen-week-3": (
        ("Provider", _provider("Aaron Currie")),
        ("Case manager", _cm("Nicole Chorvat")),
        ("Visit status", "Not Seen"),
        ("Consecutive not seen", "3 weeks in a row"),
        ("Last visit", "August 10, 2026 at 6:01 PM"),
        ("Next step", "Escalate for DC (noncompliance)"),
    ),
}


def feed_body_for(action_id: ConfirmationActionId) -> tuple[FeedField, ...]:
    if action_id == "confirm-intake-review":
        return _gonzalez_intake_fields()
    if action_id == "confirm-partner-contacted":
        return _butler_partner_fields()
    fields = _FEED_BODIES.get(action_id)
    if not fields:
        raise KeyError(action_id)
    return fields


def _assert_complete() -> None:
    missing = [action_id for action_id in ACTION_IDS if action_id not in _FEED_BODIES]
    if missing:
        raise RuntimeError(f"feed_bodies missing action ids: {missing!r}")


_assert_complete()
