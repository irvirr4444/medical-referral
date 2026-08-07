from __future__ import annotations

from datetime import datetime, timedelta, timezone

from referral_pipeline.monitoring.health import health_summary, record_cycle_health
from referral_pipeline.monitoring.models import NotificationRecord
from referral_pipeline.monitoring.notifications import dispatch_pending_notifications
from referral_pipeline.monitoring.sqlite_store import SQLiteWorkflowStore


NOW = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)


def test_health_escalates_after_threshold_and_queues_one_transition_alert(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")

    first = record_cycle_health(
        store=store,
        component="poll",
        result={"status": "error", "elapsed_seconds": 1.2},
        observed_at=NOW,
        failure_threshold=2,
        recipients=("operator@example.com",),
    )
    second = record_cycle_health(
        store=store,
        component="poll",
        result={"status": "error", "elapsed_seconds": 1.3},
        observed_at=NOW + timedelta(minutes=1),
        failure_threshold=2,
        recipients=("operator@example.com",),
    )
    record_cycle_health(
        store=store,
        component="poll",
        result={"status": "error", "elapsed_seconds": 1.4},
        observed_at=NOW + timedelta(minutes=2),
        failure_threshold=2,
        recipients=("operator@example.com",),
    )

    assert first.status == "degraded"
    assert second.status == "failed"
    assert second.error_code == "poll_error"
    assert len(store.pending_notifications()) == 1


def test_health_recovery_resets_failures_and_staleness_is_reported(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    record_cycle_health(
        store=store,
        component="approvals",
        result={"status": "failed"},
        observed_at=NOW,
        failure_threshold=1,
        recipients=("operator@example.com",),
    )
    recovered = record_cycle_health(
        store=store,
        component="approvals",
        result={"status": "ok", "elapsed_seconds": 0.5},
        observed_at=NOW + timedelta(minutes=1),
        failure_threshold=1,
        recipients=("operator@example.com",),
    )

    assert recovered.status == "healthy"
    assert recovered.consecutive_failures == 0
    assert len(store.pending_notifications()) == 2
    report = health_summary(
        store,
        now=NOW + timedelta(hours=3),
        stale_after_seconds=3600,
    )
    assert report["overall_status"] == "failed"
    assert report["components"][0]["effective_status"] == "stale"


def test_health_dispatch_does_not_send_unrelated_workflow_alerts(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    store.enqueue_notification(
        NotificationRecord(
            notification_key="workflow-alert",
            exception_key="scheduling:item-1",
            recipient="operator@example.com",
            subject="Workflow review",
            body="Synthetic workflow alert",
            created_at=NOW,
        )
    )
    record_cycle_health(
        store=store,
        component="monitor",
        result={"status": "error"},
        observed_at=NOW,
        failure_threshold=1,
        recipients=("operator@example.com",),
    )
    sent = []

    report = dispatch_pending_notifications(
        store=store,
        send_email=lambda recipient, subject, body: sent.append((recipient, subject, body)),
        exception_key_prefix="health:",
    )

    assert report["sent"] == 1
    assert len(sent) == 1
    assert sent[0][1].startswith("[WCW HEALTH]")
    assert [item.notification_key for item in store.pending_notifications()] == ["workflow-alert"]
