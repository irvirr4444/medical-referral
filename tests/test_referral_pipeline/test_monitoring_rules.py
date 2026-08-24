from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from referral_pipeline.monitoring.config import load_monitoring_config
from referral_pipeline.monitoring.models import OperationalSnapshot
from referral_pipeline.monitoring.scheduling import evaluate_scheduling
from referral_pipeline.monitoring.visits import evaluate_visit_transition


NOW = datetime(2026, 8, 6, 1, 0, tzinfo=timezone.utc)  # 18:00 previous day in Los Angeles


def _snapshot(**changes: object) -> OperationalSnapshot:
    payload = {
        "source": "monday",
        "external_id": "item-1",
        "observed_at": NOW,
        "monday_item_id": "item-1",
        "patient_label": "Synthetic Patient",
        "group": "Working pipeline",
        "sent_to_case_manager": "Yes",
        "due_date": "2026-08-05",
        "scheduled_status": "Not Scheduled",
        "scheduling_complete": "No",
    }
    payload.update(changes)
    return OperationalSnapshot.model_validate(payload)


def test_end_of_day_marks_due_unscheduled_referral() -> None:
    decision = evaluate_scheduling(_snapshot(), config=load_monitoring_config(), now=NOW)

    assert decision.status == "unscheduled"
    assert decision.exception_required is True


def test_scheduling_requires_all_three_completion_signals() -> None:
    config = load_monitoring_config()
    complete = evaluate_scheduling(
        _snapshot(scheduled_status="Scheduled", scheduling_complete="Yes", appointment_date="2026-08-07"),
        config=config,
        now=NOW,
    )
    conflict = evaluate_scheduling(
        _snapshot(scheduled_status="Scheduled", scheduling_complete="No", appointment_date=None),
        config=config,
        now=NOW,
    )

    assert complete.status == "scheduled"
    assert conflict.status == "indeterminate"
    assert conflict.exception_required is True


def test_visit_transition_counts_only_explicit_not_seen() -> None:
    config = load_monitoring_config()
    previous = _snapshot(visit_status="Scheduled")
    current = _snapshot(visit_status="Not Seen")

    transition = evaluate_visit_transition(
        previous,
        current,
        config=config,
        consecutive_not_seen=2,
    )

    assert transition.consecutive_not_seen == 3
    assert transition.review_required is True
    assert "noncompliance_discharge_review_required" in transition.event_types


def test_visit_transition_recognizes_master_sheet_not_seen_label() -> None:
    config = load_monitoring_config()
    transition = evaluate_visit_transition(
        _snapshot(visit_status="Scheduled"),
        _snapshot(visit_status="ATTEMPTED TO SEE THE PATIENT BUT NOT SEEN"),
        config=config,
        consecutive_not_seen=0,
    )

    assert transition.consecutive_not_seen == 1
    assert transition.event_types == ("visit_not_seen",)


def test_seen_resets_counter_and_hold_return_is_detected() -> None:
    config = load_monitoring_config()
    previous = _snapshot(visit_status="On Holds List")
    current = _snapshot(visit_status="Seen")

    transition = evaluate_visit_transition(
        previous,
        current,
        config=config,
        consecutive_not_seen=2,
    )

    assert transition.consecutive_not_seen == 0
    assert transition.event_types == ("visit_seen", "patient_returned_from_hold")


def test_new_visit_id_counts_repeated_explicit_not_seen_outcome() -> None:
    config = load_monitoring_config()
    transition = evaluate_visit_transition(
        _snapshot(visit_status="Not Seen", visit_event_id="visit-2"),
        _snapshot(visit_status="Not Seen", visit_event_id="visit-3"),
        config=config,
        consecutive_not_seen=2,
    )

    assert transition.consecutive_not_seen == 3
    assert transition.review_required is True


def test_recorded_healed_status_creates_review_event_without_inference() -> None:
    config = replace(load_monitoring_config(), healed_statuses=frozenset({"healed"}))
    transition = evaluate_visit_transition(
        _snapshot(qa_hold_reason="Not on Hold"),
        _snapshot(qa_hold_reason="Healed"),
        config=config,
        consecutive_not_seen=0,
    )

    assert "recorded_healed_status" in transition.event_types


def test_operational_config_can_be_overridden_without_editing_tracked_json(monkeypatch) -> None:
    monkeypatch.setenv("WCW_END_OF_DAY", "18:30")
    monkeypatch.setenv("WORKFLOW_NOTIFICATION_RECIPIENTS", "one@example.com, two@example.com")

    config = load_monitoring_config()

    assert config.end_of_day == "18:30"
    assert config.notification_recipients == ("one@example.com", "two@example.com")
