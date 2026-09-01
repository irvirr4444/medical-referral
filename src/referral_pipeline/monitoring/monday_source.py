"""Read-only Monday Master Sheet projection for operational monitoring."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from referral_pipeline.integrations.monday.reader import fetch_items, item_values, load_export_items
from referral_pipeline.monitoring.models import OperationalSnapshot


def load_monday_snapshots(
    *,
    observed_at: datetime,
    records_file: str | Path | None = None,
    live: bool = False,
    page_size: int = 250,
) -> list[OperationalSnapshot]:
    if live == (records_file is not None):
        raise ValueError("choose exactly one Monday source: live or records_file")
    if live:
        _, items = fetch_items(page_size=page_size)
    else:
        _, items = load_export_items(Path(records_file))
    return [monday_item_to_snapshot(item, observed_at=observed_at) for item in items]


def monday_item_to_snapshot(item: dict[str, Any], *, observed_at: datetime) -> OperationalSnapshot:
    values = item_values(item)
    item_id = str(item.get("id") or "").strip()
    if not item_id:
        raise ValueError("Monday item is missing its ID")
    return OperationalSnapshot(
        source="monday",
        external_id=item_id,
        observed_at=observed_at,
        patient_label=values.get("name") or None,
        monday_item_id=item_id,
        group=str((item.get("group") or {}).get("title") or "") or None,
        case_manager=values.get("case_manager") or None,
        provider=values.get("provider") or None,
        sent_to_case_manager=values.get("sent_to_cm") or None,
        referral_sent_to_provider=values.get("referral_sent_to_provider") or None,
        due_date=values.get("due_date") or None,
        appointment_date=values.get("appointment_date") or None,
        scheduling_complete=values.get("scheduling_complete") or None,
        scheduled_status=values.get("scheduled_status") or None,
        visit_status=values.get("visit_status") or None,
        qa_hold_reason=values.get("qa_hold_reason") or None,
        discharge_reason=values.get("discharge_reason") or None,
        source_updated_at=str(item.get("updated_at") or "") or None,
        details={
            "dob": values.get("dob") or None,
            "referral_received": values.get("referral_received") or None,
        },
    )
