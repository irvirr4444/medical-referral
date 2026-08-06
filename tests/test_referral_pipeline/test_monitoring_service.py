from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from referral_pipeline.monitoring.config import load_monitoring_config
from referral_pipeline.monitoring.models import OperationalSnapshot
from referral_pipeline.monitoring.service import WorkflowMonitoringService
from referral_pipeline.monitoring.sqlite_store import SQLiteWorkflowStore


NOW = datetime(2026, 8, 6, 1, 0, tzinfo=timezone.utc)


def _snapshot(*, observed_at: datetime = NOW, **changes: object) -> OperationalSnapshot:
    payload = {
        "source": "monday",
        "external_id": "item-1",
        "observed_at": observed_at,
        "monday_item_id": "item-1",
        "patient_label": "Synthetic Patient",
        "group": "Working pipeline",
        "case_manager": "Example Manager",
        "sent_to_case_manager": "Yes",
        "due_date": "2026-08-05",
        "scheduled_status": "Not Scheduled",
        "scheduling_complete": "No",
        "visit_status": "Scheduled",
    }
    payload.update(changes)
    return OperationalSnapshot.model_validate(payload)


def test_monitor_creates_one_scheduling_exception_and_outbox_entry(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    config = replace(load_monitoring_config(), notification_recipients=("reviewer@example.com",))
    service = WorkflowMonitoringService(store=store, config=config)

    first = service.process([_snapshot()], now=NOW)
    second = service.process([_snapshot()], now=NOW)

    assert first["exceptions_created"] == 1
    assert first["notifications_queued"] == 1
    assert second["exceptions_created"] == 0
    assert len(store.pending_notifications()) == 1


def test_monitor_resolves_scheduling_and_creates_visit_transition(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    service = WorkflowMonitoringService(store=store, config=load_monitoring_config())
    service.process([_snapshot()], now=NOW)
    later = NOW.replace(hour=2)
    report = service.process(
        [
            _snapshot(
                observed_at=later,
                scheduled_status="Scheduled",
                scheduling_complete="Yes",
                appointment_date="2026-08-07",
                visit_status="Seen",
            )
        ],
        now=later,
    )

    assert report["exceptions_resolved"] == 1
    assert report["events_created"] == 1
    assert store.get_counter("monday:item-1", "consecutive_not_seen") == 0
