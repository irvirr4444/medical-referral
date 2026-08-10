"""One fault-isolated monitoring cycle for the continuous intake worker."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from referral_pipeline.monitoring.config import DEFAULT_CONFIG_PATH, load_monitoring_config
from referral_pipeline.monitoring.drk_capture import DEFAULT_PROFILE_PATH, load_drk_capture_snapshots
from referral_pipeline.monitoring.drk_source import load_drk_snapshots
from referral_pipeline.monitoring.health import record_cycle_health
from referral_pipeline.monitoring.live_drk_source import ROTATION_CURSOR, load_live_drk_snapshots
from referral_pipeline.monitoring.monday_source import load_monday_snapshots
from referral_pipeline.monitoring.notifications import dispatch_pending_notifications, outlook_sender
from referral_pipeline.monitoring.service import WorkflowMonitoringService
from referral_pipeline.monitoring.store import create_workflow_store


logger = logging.getLogger(__name__)


def run_monitor_cycle(
    *,
    data_root: Path,
    send_alerts: bool = False,
    config_path: Path = DEFAULT_CONFIG_PATH,
    database_backend: str | None = None,
    sqlite_path: Path | None = None,
    drk_snapshot: Path | None = None,
    drk_capture_dir: Path | None = None,
    drk_capture_profile: Path = DEFAULT_PROFILE_PATH,
    live_drk: bool = False,
    drk_max_patients: int = 10,
    drk_live_profile_dir: Path | None = None,
) -> dict:
    """Read current source state and evaluate deterministic Step 4-5 rules."""
    started = time.perf_counter()
    try:
        now = datetime.now(timezone.utc)
        monday_snapshots = load_monday_snapshots(observed_at=now, live=True)
        snapshots = list(monday_snapshots)

        selected_backend = (
            database_backend or os.getenv("WORKFLOW_DATABASE_BACKEND") or "sqlite"
        ).strip().casefold()
        effective_sqlite_path = sqlite_path
        if selected_backend == "sqlite" and effective_sqlite_path is None and not os.getenv("WORKFLOW_SQLITE_PATH"):
            effective_sqlite_path = data_root / "workflow-monitor.sqlite"
        store = create_workflow_store(backend=selected_backend, sqlite_path=effective_sqlite_path)
        monitoring_config = load_monitoring_config(config_path)
        if drk_snapshot is not None:
            snapshots.extend(load_drk_snapshots(drk_snapshot, observed_at=now))
        if drk_capture_dir is not None:
            snapshots.extend(
                load_drk_capture_snapshots(
                    drk_capture_dir,
                    observed_at=now,
                    profile_path=drk_capture_profile,
                )
            )
        live_drk_report = None
        if live_drk:
            batch = load_live_drk_snapshots(
                monday_snapshots=monday_snapshots,
                store=store,
                monitoring_config=monitoring_config,
                observed_at=now,
                browser_profile_dir=(
                    drk_live_profile_dir or data_root / "drk-live-browser-profile"
                ),
                max_patients=drk_max_patients,
                capture_profile_path=drk_capture_profile,
            )
            snapshots.extend(batch.snapshots)
            if batch.next_cursor is not None:
                store.record_cursor(ROTATION_CURSOR, batch.next_cursor)
            record_cycle_health(
                store=store,
                component="drk_reader",
                result={
                    "status": "ok" if batch.status == "idle" else batch.status,
                    "elapsed_seconds": batch.elapsed_seconds,
                },
                observed_at=now,
                failure_threshold=int(os.getenv("INTAKE_HEALTH_FAILURE_THRESHOLD", "3")),
                recipients=monitoring_config.notification_recipients,
            )
            live_drk_report = {
                "status": batch.status,
                "attempted": batch.attempted,
                "captured": len(batch.snapshots),
                "failures": list(batch.failures),
                "elapsed_seconds": batch.elapsed_seconds,
            }

        service = WorkflowMonitoringService(store=store, config=monitoring_config)
        report = service.process(snapshots, now=now)
        if live_drk_report is not None:
            report["drk_live"] = live_drk_report
        store.record_cursor("monday", now.isoformat())
        if drk_snapshot is not None or drk_capture_dir is not None or live_drk:
            store.record_cursor("drk", now.isoformat())
        report["database"] = store.status_summary()
        report["notifications"] = (
            dispatch_pending_notifications(store=store, send_email=outlook_sender())
            if send_alerts
            else {"sent": 0, "mode": "outbox-only"}
        )

        report_path = data_root / "monitoring" / "last-run.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return {
            "kind": "monitor",
            "status": (
                "degraded"
                if live_drk_report is not None
                and live_drk_report["status"] not in {"ok", "idle"}
                else "ok"
            ),
            "report_path": str(report_path),
            "elapsed_seconds": round(time.perf_counter() - started, 2),
            **report,
        }
    except Exception as error:  # noqa: BLE001 - worker must survive cycle failures
        logger.exception("Workflow monitoring cycle failed")
        return {
            "kind": "monitor",
            "status": "error",
            "error": str(error),
            "elapsed_seconds": round(time.perf_counter() - started, 2),
        }
