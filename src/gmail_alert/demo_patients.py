"""Demo patient on each email = the seed for that alert."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from gmail_alert.ids import ConfirmationActionId

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = _REPO_ROOT / "frontend" / "src" / "features" / "automation" / "fixtures"

_INTAKE_JSON: dict[str, Path] = {
    "butler-alva": _FIXTURES / "butlerCanonicalReferral.json",
    "gonzalez-eric": _FIXTURES / "canonicals" / "gonzalez-eric.json",
}


@dataclass(frozen=True)
class DemoPatient:
    patient_id: str
    patient_name: str
    hours_overdue: float
    date_of_birth: str | None = None
    phone: str | None = None
    clinical_summary: str | None = None
    owner_name: str | None = None
    provider_name: str | None = None
    area: str | None = None
    late_label: str | None = None


# (patient_id, patient_name, overdue_minutes or None, late_label or None)
_ACTION_SEED: dict[ConfirmationActionId, tuple[str, str, int | None, str | None]] = {
    "confirm-intake-review": ("gonzalez-eric", "Gonzalez, Eric", 22, None),
    "confirm-partner-contacted": ("butler-alva", "Butler, Alva", 74, None),
    "cm-assigned": ("marcus-feldman", "Marcus Feldman", None, None),
    "use-fallback-provider": ("maria-alvarez", "Maria Alvarez", 18, None),
    "no-area-provider": ("betty-hayes", "Betty Hayes", None, None),
    "send-referral-provider": ("maria-alvarez", "Maria Alvarez", None, None),
    "eod-follow-up-cm": ("thomas-reed", "Thomas Reed", None, "24-hour window missed"),
    "eod-escalate": ("frank-owens", "Frank Owens", None, "48-hour window missed"),
    "not-seen-week-1": ("patricia-johnson", "Patricia Johnson", None, None),
    "not-seen-week-2": ("margaret-ellis", "Margaret Ellis", None, None),
    "not-seen-week-3": ("walter-grant", "Walter Grant", None, None),
}


def _display_name(patient: dict) -> str:
    name = patient.get("name") or {}
    full = name.get("full")
    if full:
        return str(full)
    joined = " ".join(part for part in (name.get("first"), name.get("last")) if part)
    return joined or "Unknown patient"


def _intake_overlay(patient_id: str) -> dict[str, str]:
    path = _INTAKE_JSON.get(patient_id)
    if path is None or not path.exists():
        return {}
    record = json.loads(path.read_text())
    patient = record.get("patient") or {}
    phones = patient.get("phones") or []
    return {
        "patient_name": _display_name(patient),
        "date_of_birth": patient.get("date_of_birth") or "—",
        "phone": phones[0]["number"] if phones else "—",
        "clinical_summary": (record.get("clinical") or {}).get("summary") or "—",
    }


_FACTS: dict[str, dict[str, str]] = {
    "gonzalez-eric": {"owner_name": "Carla Bustillo"},
    "butler-alva": {},
    "marcus-feldman": {"owner_name": "Cole Winfield", "area": "Gardena"},
    "betty-hayes": {"owner_name": "Nicole Chorvat", "area": "Needles"},
    "maria-alvarez": {
        "owner_name": "Donessa Ruiz",
        "provider_name": "Daniel Rowady",
        "area": "Pasadena",
    },
    "thomas-reed": {
        "owner_name": "Donessa Ruiz",
        "provider_name": "Charles Cho",
        "area": "Los Angeles",
    },
    "frank-owens": {"owner_name": "Braxton Rickert", "provider_name": "Aaron Currie"},
    "patricia-johnson": {"owner_name": "Cole Winfield", "area": "Burbank"},
    "margaret-ellis": {"owner_name": "Cole Winfield", "area": "Gardena"},
    "walter-grant": {"owner_name": "Nicole Chorvat"},
}


def demo_for_action(action_id: ConfirmationActionId) -> DemoPatient:
    patient_id, patient_name, overdue_minutes, late_label = _ACTION_SEED[action_id]
    hours = (overdue_minutes / 60) if overdue_minutes is not None else 2.0
    overlay = _intake_overlay(patient_id)
    facts = _FACTS.get(patient_id, {})
    return DemoPatient(
        patient_id=patient_id,
        patient_name=overlay.get("patient_name") or patient_name,
        hours_overdue=hours,
        date_of_birth=overlay.get("date_of_birth"),
        phone=overlay.get("phone"),
        clinical_summary=overlay.get("clinical_summary"),
        owner_name=facts.get("owner_name"),
        provider_name=facts.get("provider_name"),
        area=facts.get("area"),
        late_label=late_label,
    )


def action_demo_patient_ids() -> tuple[str, ...]:
    return tuple(seed[0] for seed in _ACTION_SEED.values())
