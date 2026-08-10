"""Normalize read-only DRK Selenium card captures for workflow monitoring."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict

from referral_pipeline.monitoring.models import OperationalSnapshot


DEFAULT_PROFILE_PATH = Path(__file__).with_name("drk_capture_profile.example.json")


class DrkCaptureProfile(BaseModel):
    """Configurable, exact-key mappings for known DRK capture cards."""

    model_config = ConfigDict(extra="forbid")

    identity_cards: tuple[str, ...]
    encounter_cards: tuple[str, ...]
    status_cards: tuple[str, ...]
    field_aliases: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class _Match:
    value: str
    card: str
    path: str


def load_drk_capture_snapshots(
    capture_dir: str | Path,
    *,
    observed_at: datetime,
    profile_path: str | Path = DEFAULT_PROFILE_PATH,
) -> list[OperationalSnapshot]:
    """Load one or more patient capture directories produced by read_patient."""
    root = Path(capture_dir)
    if not root.is_dir():
        raise ValueError(f"DRK capture directory does not exist: {root}")
    profile = load_drk_capture_profile(profile_path)
    patient_dirs = _patient_directories(root, profile)
    if not patient_dirs:
        raise ValueError(f"No DRK patient card captures found under: {root}")
    return [
        _capture_to_snapshot(patient_dir, profile=profile, observed_at=observed_at)
        for patient_dir in patient_dirs
    ]


def _patient_directories(root: Path, profile: DrkCaptureProfile) -> list[Path]:
    cards = {*profile.identity_cards, *profile.encounter_cards, *profile.status_cards}
    if any((root / f"{card}.json").is_file() for card in cards):
        return [root]
    return sorted(
        directory
        for directory in root.iterdir()
        if directory.is_dir() and any((directory / f"{card}.json").is_file() for card in cards)
    )


def _capture_to_snapshot(
    patient_dir: Path,
    *,
    profile: DrkCaptureProfile,
    observed_at: datetime,
) -> OperationalSnapshot:
    cards = {
        card: _load_card(patient_dir / f"{card}.json")
        for card in {*profile.identity_cards, *profile.encounter_cards, *profile.status_cards}
        if (patient_dir / f"{card}.json").is_file()
    }
    return normalize_drk_card_payloads(
        cards,
        profile=profile,
        observed_at=observed_at,
        context=str(patient_dir),
    )


def load_drk_capture_profile(path: str | Path = DEFAULT_PROFILE_PATH) -> DrkCaptureProfile:
    return DrkCaptureProfile.model_validate_json(
        Path(path).read_text(encoding="utf-8-sig")
    )


def normalize_drk_card_payloads(
    cards: dict[str, Any],
    *,
    profile: DrkCaptureProfile,
    observed_at: datetime,
    expected_patient_id: str | None = None,
    context: str = "in-memory DRK capture",
) -> OperationalSnapshot:
    """Normalize validated card wrappers without persisting raw DRK capture files."""
    for card_name, payload in cards.items():
        _validate_card_payload(payload, context=f"{context}:{card_name}")
    identity_nodes = _nodes_for_cards(cards, profile.identity_cards)
    patient_id = _find(identity_nodes, profile, "patient_id")
    if patient_id is None:
        raise ValueError(f"DRK capture is missing an explicit patient ID: {context}")
    if expected_patient_id is not None and patient_id.value != str(expected_patient_id).strip():
        raise ValueError(
            f"DRK capture patient ID mismatch: expected {expected_patient_id}, "
            f"observed {patient_id.value}"
        )

    patient_name = _find(identity_nodes, profile, "patient_name")
    if patient_name is None:
        first_name = _find(identity_nodes, profile, "first_name")
        last_name = _find(identity_nodes, profile, "last_name")
        combined = " ".join(
            part.value for part in (first_name, last_name) if part is not None
        ).strip()
        patient_name = _Match(combined, "patient_information", "derived:first+last") if combined else None

    encounter = _latest_encounter(
        _nodes_for_cards(cards, profile.encounter_cards),
        profile=profile,
    )
    status_nodes = _nodes_for_cards(cards, profile.status_cards)
    matches: dict[str, _Match | None] = {
        "patient_label": patient_name,
        "dob": _find(identity_nodes, profile, "dob"),
        "provider": _find(encounter, profile, "provider"),
        "appointment_date": _find(encounter, profile, "appointment_date"),
        "visit_status": _find(encounter, profile, "visit_status"),
        "visit_outcome": _find(encounter, profile, "visit_outcome"),
        "visit_event_id": _find(encounter, profile, "visit_event_id"),
        "progress_note_status": _find(encounter, profile, "progress_note_status"),
        "source_updated_at": _find(encounter, profile, "source_updated_at"),
        "qa_hold_reason": _find(status_nodes, profile, "qa_hold_reason"),
        "discharge_reason": _find(status_nodes, profile, "discharge_reason"),
    }
    monitored_fields = (
        "appointment_date",
        "visit_status",
        "visit_outcome",
        "visit_event_id",
        "progress_note_status",
        "qa_hold_reason",
        "discharge_reason",
    )
    missing = [field for field in monitored_fields if matches[field] is None]
    evidence = {
        field: {"card": match.card, "path": match.path}
        for field, match in matches.items()
        if match is not None
    }

    return OperationalSnapshot(
        source="drk",
        external_id=patient_id.value,
        patient_label=_value(matches["patient_label"]),
        drk_patient_id=patient_id.value,
        observed_at=observed_at,
        provider=_value(matches["provider"]),
        appointment_date=_value(matches["appointment_date"]),
        visit_status=_value(matches["visit_status"]),
        visit_outcome=_value(matches["visit_outcome"]),
        visit_event_id=_value(matches["visit_event_id"]),
        progress_note_status=_value(matches["progress_note_status"]),
        qa_hold_reason=_value(matches["qa_hold_reason"]),
        discharge_reason=_value(matches["discharge_reason"]),
        source_updated_at=_value(matches["source_updated_at"]),
        details={
            "dob": _value(matches["dob"]),
            "adapter": "drk_selenium_capture",
            "observed_field_sources": evidence,
            "missing_monitoring_fields": missing,
            "normalization_status": "complete" if not missing else "partial",
        },
    )


def _load_card(path: Path) -> Any:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    _validate_card_payload(payload, context=str(path))
    return payload


def _validate_card_payload(payload: Any, *, context: str) -> None:
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise ValueError(f"Invalid DRK card wrapper: {context}")


def _nodes_for_cards(cards: dict[str, Any], card_names: Iterable[str]) -> list[tuple[str, str, dict[str, Any]]]:
    nodes: list[tuple[str, str, dict[str, Any]]] = []
    for card_name in card_names:
        payload = cards.get(card_name)
        if payload is None:
            continue
        for index, record in enumerate(payload["records"]):
            if not isinstance(record, dict):
                continue
            business_data = record.get("business_data")
            nodes.extend(
                (card_name, f"records[{index}].business_data{path}", node)
                for path, node in _walk_dicts(business_data)
            )
    return nodes


def _walk_dicts(value: Any, path: str = "") -> Iterable[tuple[str, dict[str, Any]]]:
    if isinstance(value, dict):
        yield path, value
        for key, child in value.items():
            yield from _walk_dicts(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_dicts(child, f"{path}[{index}]")


def _latest_encounter(
    nodes: list[tuple[str, str, dict[str, Any]]],
    *,
    profile: DrkCaptureProfile,
) -> list[tuple[str, str, dict[str, Any]]]:
    candidates: list[tuple[float | None, tuple[str, str, dict[str, Any]]]] = []
    for node in nodes:
        wrapped = [node]
        event_id = _find(wrapped, profile, "visit_event_id")
        status = _find(wrapped, profile, "visit_status") or _find(wrapped, profile, "visit_outcome")
        date = _find(wrapped, profile, "source_updated_at") or _find(
            wrapped, profile, "appointment_date"
        )
        if event_id is None and status is None:
            continue
        candidates.append((_parse_datetime(date.value) if date else None, node))
    if not candidates:
        return []
    if len(candidates) == 1:
        return [candidates[0][1]]
    dated = [candidate for candidate in candidates if candidate[0] is not None]
    if not dated:
        raise ValueError(
            "DRK capture contains multiple encounters without a parseable date; "
            "refusing to guess which is latest"
        )
    return [max(dated, key=lambda candidate: candidate[0])[1]]


def _find(
    nodes: list[tuple[str, str, dict[str, Any]]],
    profile: DrkCaptureProfile,
    field: str,
) -> _Match | None:
    aliases = {_normalized_key(alias) for alias in profile.field_aliases.get(field, ())}
    for card, path, node in nodes:
        for key, raw_value in node.items():
            if _normalized_key(key) not in aliases:
                continue
            value = _scalar(raw_value)
            if value:
                return _Match(value=value, card=card, path=f"{path}.{key}")
    return None


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _scalar(value: Any) -> str | None:
    if value is None or isinstance(value, (dict, list)):
        return None
    text = str(value).strip()
    return text or None


def _parse_datetime(value: str) -> float | None:
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).timestamp()
    except ValueError:
        pass
    for pattern in ("%m/%d/%Y %I:%M %p", "%m/%d/%Y", "%b %d, %Y"):
        try:
            return datetime.strptime(value.strip(), pattern).replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            continue
    return None


def _value(match: _Match | None) -> str | None:
    return None if match is None else match.value
