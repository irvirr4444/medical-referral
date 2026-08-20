from __future__ import annotations

from datetime import datetime, timedelta, timezone

from referral_pipeline.monitoring.config import load_monitoring_config
from referral_pipeline.monitoring.models import OperationalSnapshot, WorkflowCase
from referral_pipeline.monitoring.service import WorkflowMonitoringService
from referral_pipeline.monitoring.sqlite_store import SQLiteWorkflowStore
from referral_pipeline.workflow.attention import workflow_attention


NOW = datetime(2026, 8, 6, 1, 0, tzinfo=timezone.utc)


def _case() -> WorkflowCase:
    return WorkflowCase(
        case_id="case-1",
        source_ref="message:synthetic-referral",
        source="eml-fixture",
        patient_label="Synthetic Patient",
        current_stage=3,
        status="handoff_in_progress",
        monday_item_id="monday-1",
        drk_patient_id="321",
        created_at=NOW,
        updated_at=NOW,
    )


def _monday(*, observed_at: datetime, **changes: object) -> OperationalSnapshot:
    payload: dict[str, object] = {
        "source": "monday",
        "external_id": "monday-1",
        "observed_at": observed_at,
        "monday_item_id": "monday-1",
        "patient_label": "Synthetic Patient",
        "group": "Working pipeline",
        "sent_to_case_manager": "Yes",
        "due_date": "2026-08-05",
        "scheduled_status": "Not Scheduled",
        "scheduling_complete": "No",
        "visit_status": "Scheduled",
    }
    payload.update(changes)
    return OperationalSnapshot.model_validate(payload)


def _drk(*, observed_at: datetime, **changes: object) -> OperationalSnapshot:
    payload: dict[str, object] = {
        "source": "drk",
        "external_id": "321",
        "observed_at": observed_at,
        "referral_id": "case-1",
        "monday_item_id": "monday-1",
        "drk_patient_id": "321",
        "patient_label": "Synthetic Patient",
        "appointment_date": "2026-08-07",
        "visit_status": "Seen",
        "visit_outcome": "Seen",
        "visit_event_id": "visit-0",
        "progress_note_status": "Signed",
    }
    payload.update(changes)
    return OperationalSnapshot.model_validate(payload)


def test_stage_five_and_six_replay_round_trips_under_one_case(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "stage56-proof.sqlite")
    store.upsert_workflow_case(_case())
    service = WorkflowMonitoringService(store=store, config=load_monitoring_config())

    # Stage 5: the due referral is not scheduled after the EOD cutoff.
    first = service.process([_monday(observed_at=NOW)], now=NOW)
    assert first["scheduling"] == {"unscheduled": 1}
    assert first["exceptions_created"] == 1

    stage_five = workflow_attention(store, now=NOW, stage=5)
    assert [item["step_id"] for item in stage_five["items"]] == [
        "check-scheduling-status"
    ]
    assert stage_five["items"][0]["case_id"] == "case-1"

    # Stage 5: the CM completes all three scheduling signals.
    scheduled_at = NOW + timedelta(hours=1)
    scheduled = service.process(
        [
            _monday(
                observed_at=scheduled_at,
                scheduled_status="Scheduled",
                scheduling_complete="Yes",
                appointment_date="2026-08-07",
            )
        ],
        now=scheduled_at,
    )
    assert scheduled["scheduling"] == {"scheduled": 1}
    assert scheduled["exceptions_resolved"] == 1
    assert workflow_attention(store, now=scheduled_at, stage=5)["items"] == []

    # Stage 6: baseline a recorded visit, then observe three distinct misses.
    baseline_at = scheduled_at + timedelta(days=1)
    service.process([_drk(observed_at=baseline_at)], now=baseline_at)
    for index in range(1, 4):
        observed_at = baseline_at + timedelta(days=index)
        report = service.process(
            [
                _drk(
                    observed_at=observed_at,
                    visit_status="Not Seen",
                    visit_outcome="Not Seen",
                    visit_event_id=f"visit-{index}",
                )
            ],
            now=observed_at,
        )
        assert report["events_created"] == (2 if index == 3 else 1)

    assert store.get_counter("case-1", "consecutive_not_seen") == 3
    exceptions = store.list_exceptions(status="open")
    assert [exception.exception_type for exception in exceptions] == [
        "noncompliance_discharge_review"
    ]
    assert exceptions[0].entity_id == "case-1"

    stage_six = workflow_attention(store, now=observed_at, stage=6)
    assert [item["step_id"] for item in stage_six["items"]] == ["patient-seen"]
    assert stage_six["items"][0]["case_id"] == "case-1"

    # Verify the latest source payload and the generated event survived storage.
    latest = store.latest_snapshot("drk", "321")
    assert latest is not None
    assert latest.visit_status == "Not Seen"
    assert latest.visit_event_id == "visit-3"
    assert all(event.entity_id == "case-1" for event in store.list_events("case-1"))


def test_stage_six_replay_routes_healed_and_expired_reviews(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "stage6-clinical-proof.sqlite")
    store.upsert_workflow_case(_case())
    service = WorkflowMonitoringService(store=store, config=load_monitoring_config())

    baseline = NOW + timedelta(days=2)
    service.process([_drk(observed_at=baseline)], now=baseline)

    healed_at = baseline + timedelta(days=1)
    service.process(
        [
            _drk(
                observed_at=healed_at,
                visit_status="Healed",
                visit_outcome="Healed",
                visit_event_id="visit-healed",
                qa_hold_reason="Healed",
            )
        ],
        now=healed_at,
    )
    healed_attention = workflow_attention(store, now=healed_at, stage=6)
    assert any(item["step_id"] == "wound-healed" for item in healed_attention["items"])

    expired_at = healed_at + timedelta(days=1)
    service.process(
        [
            _drk(
                observed_at=expired_at,
                visit_status="Expired",
                visit_outcome="Expired",
                visit_event_id="visit-expired",
                discharge_reason="Expired",
            )
        ],
        now=expired_at,
    )
    expired_attention = workflow_attention(store, now=expired_at, stage=6)
    assert any(item["step_id"] == "patient-expired" for item in expired_attention["items"])

    open_types = {exception.exception_type for exception in store.list_exceptions(status="open")}
    assert open_types == {"qa_review", "discharge_approval_review"}
