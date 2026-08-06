"""Normalized DRK snapshot reader for captured/read-only DRK status exports."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from referral_pipeline.monitoring.models import OperationalSnapshot


def load_drk_snapshots(path: str | Path, *, observed_at: datetime) -> list[OperationalSnapshot]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    records = payload.get("patients") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError("DRK monitoring snapshot must be a list or contain a patients list")
    return [_drk_record_to_snapshot(record, observed_at=observed_at) for record in records]


def _drk_record_to_snapshot(record: dict[str, Any], *, observed_at: datetime) -> OperationalSnapshot:
    patient_id = _value(record, "drk_patient_id", "patient_id", "id")
    if not patient_id:
        raise ValueError("DRK monitoring record is missing patient ID")
    return OperationalSnapshot(
        source="drk",
        external_id=patient_id,
        observed_at=observed_at,
        referral_id=_value(record, "referral_id") or None,
        patient_label=_value(record, "patient_label", "patient_name", "name") or None,
        monday_item_id=_value(record, "monday_item_id") or None,
        drk_patient_id=patient_id,
        case_manager=_value(record, "case_manager") or None,
        provider=_value(record, "provider", "assigned_provider") or None,
        due_date=_value(record, "due_date") or None,
        appointment_date=_value(record, "appointment_date", "next_appointment") or None,
        visit_outcome=_value(record, "visit_outcome", "outcome") or None,
        visit_status=_value(record, "visit_status", "status") or None,
        visit_event_id=_value(record, "visit_event_id", "visit_id", "appointment_id", "visit_date") or None,
        progress_note_status=_value(record, "progress_note_status") or None,
        qa_hold_reason=_value(record, "hold_status", "qa_hold_reason") or None,
        discharge_reason=_value(record, "discharge_status", "discharge_reason") or None,
        source_updated_at=_value(record, "updated_at") or None,
        details={"dob": _value(record, "dob", "date_of_birth") or None},
    )


def _value(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""
