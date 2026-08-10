"""Persistent, PHI-free component health and transition alerts."""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from referral_pipeline.monitoring.config import load_monitoring_config
from referral_pipeline.monitoring.models import ComponentHealth, NotificationRecord
from referral_pipeline.monitoring.notifications import dispatch_pending_notifications, outlook_sender
from referral_pipeline.monitoring.store import WorkflowStore
from referral_pipeline.monitoring.store import create_workflow_store


logger = logging.getLogger(__name__)


class WorkerHealthReporter:
    """Fault-isolated health recorder used by the continuous worker."""

    def __init__(
        self,
        *,
        store: WorkflowStore,
        recipients: tuple[str, ...],
        failure_threshold: int,
        send_alerts: bool,
    ) -> None:
        self.store = store
        self.recipients = recipients
        self.failure_threshold = failure_threshold
        self.send_alerts = send_alerts

    def record(self, result: dict) -> None:
        try:
            record_cycle_health(
                store=self.store,
                component=str(result.get("kind") or "worker"),
                result=result,
                observed_at=datetime.now(timezone.utc),
                failure_threshold=self.failure_threshold,
                recipients=self.recipients,
            )
            if self.send_alerts:
                dispatch_pending_notifications(
                    store=self.store,
                    send_email=outlook_sender(),
                    exception_key_prefix="health:",
                )
        except Exception:  # noqa: BLE001 - health reporting cannot stop intake
            logger.exception("Unable to persist worker health result")


def create_worker_health_reporter(
    *,
    data_root: Path,
    database_backend: str | None,
    sqlite_path: Path | None,
    config_path: Path,
    failure_threshold: int,
    send_alerts: bool,
) -> WorkerHealthReporter:
    selected_backend = (
        database_backend or os.getenv("WORKFLOW_DATABASE_BACKEND") or "sqlite"
    ).strip().casefold()
    effective_sqlite_path = sqlite_path
    if selected_backend == "sqlite" and effective_sqlite_path is None:
        effective_sqlite_path = data_root / "workflow-monitor.sqlite"
    store = create_workflow_store(
        backend=selected_backend,
        sqlite_path=effective_sqlite_path,
    )
    return WorkerHealthReporter(
        store=store,
        recipients=load_monitoring_config(config_path).notification_recipients,
        failure_threshold=failure_threshold,
        send_alerts=send_alerts,
    )


def record_cycle_health(
    *,
    store: WorkflowStore,
    component: str,
    result: dict,
    observed_at: datetime,
    failure_threshold: int = 3,
    recipients: Iterable[str] = (),
) -> ComponentHealth:
    """Persist one worker result and queue alerts on failure/recovery transitions."""
    if failure_threshold < 1:
        raise ValueError("failure_threshold must be at least 1")
    previous = store.component_health(component)
    succeeded = result.get("status") == "ok"
    failures = 0 if succeeded else (previous.consecutive_failures if previous else 0) + 1
    status = "healthy" if succeeded else "failed" if failures >= failure_threshold else "degraded"
    record = ComponentHealth(
        component=component,
        status=status,
        last_attempt_at=observed_at,
        last_success_at=(
            observed_at if succeeded else previous.last_success_at if previous else None
        ),
        consecutive_failures=failures,
        duration_seconds=_duration(result.get("elapsed_seconds")),
        error_code=None if succeeded else f"{component}_{result.get('status', 'error')}",
    )
    store.upsert_component_health(record)

    previous_status = previous.status if previous else None
    transition = None
    if status == "failed" and previous_status != "failed":
        transition = "failed"
    elif succeeded and previous_status in {"degraded", "failed"}:
        transition = "recovered"
    if transition:
        for recipient in recipients:
            _queue_health_notification(
                store=store,
                recipient=recipient,
                record=record,
                transition=transition,
                created_at=observed_at,
            )
    return record


def health_summary(
    store: WorkflowStore,
    *,
    now: datetime,
    stale_after_seconds: int,
) -> dict[str, object]:
    if stale_after_seconds < 1:
        raise ValueError("stale_after_seconds must be at least 1")
    stale_before = now - timedelta(seconds=stale_after_seconds)
    components = []
    for record in store.list_component_health():
        stale = record.last_attempt_at < stale_before
        effective_status = "stale" if stale else record.status
        components.append(
            {
                **record.model_dump(mode="json"),
                "effective_status": effective_status,
                "stale": stale,
            }
        )
    statuses = {item["effective_status"] for item in components}
    overall = (
        "no_data"
        if not components
        else "failed"
        if statuses & {"failed", "stale"}
        else "degraded"
        if "degraded" in statuses
        else "healthy"
    )
    return {"overall_status": overall, "components": components}


def _queue_health_notification(
    *,
    store: WorkflowStore,
    recipient: str,
    record: ComponentHealth,
    transition: str,
    created_at: datetime,
) -> None:
    event_key = f"health:{record.component}:{transition}:{created_at.isoformat()}"
    notification_key = hashlib.sha256(
        f"{event_key}|{recipient.casefold()}".encode("utf-8")
    ).hexdigest()
    if transition == "failed":
        subject = f"[WCW HEALTH] {record.component} failed repeatedly"
        body = (
            f"Component: {record.component}\n"
            f"Status: failed\n"
            f"Consecutive failures: {record.consecutive_failures}\n"
            f"Last successful run: {record.last_success_at or 'Not recorded'}\n"
            f"Error code: {record.error_code or 'Not recorded'}\n\n"
            "No patient information is included in this operational alert."
        )
    else:
        subject = f"[WCW HEALTH] {record.component} recovered"
        body = (
            f"Component: {record.component}\n"
            f"Status: healthy\n"
            f"Recovered at: {record.last_attempt_at.isoformat()}\n\n"
            "No patient information is included in this operational alert."
        )
    store.enqueue_notification(
        NotificationRecord(
            notification_key=notification_key,
            exception_key=f"health:{record.component}",
            recipient=recipient,
            subject=subject,
            body=body,
            created_at=created_at,
        )
    )


def _duration(value: object) -> float | None:
    try:
        return None if value is None else max(float(value), 0.0)
    except (TypeError, ValueError):
        return None
