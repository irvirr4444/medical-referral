"""Operator commands for read-only workflow synchronization and reporting."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from referral_pipeline.monitoring.config import DEFAULT_CONFIG_PATH, load_monitoring_config
from referral_pipeline.monitoring.drk_capture import DEFAULT_PROFILE_PATH, load_drk_capture_snapshots
from referral_pipeline.monitoring.drk_source import load_drk_snapshots
from referral_pipeline.monitoring.health import health_summary, record_cycle_health
from referral_pipeline.monitoring.live_drk_source import (
    ROTATION_CURSOR,
    load_live_drk_snapshots,
)
from referral_pipeline.monitoring.monday_source import load_monday_snapshots
from referral_pipeline.monitoring.notifications import dispatch_pending_notifications, outlook_sender
from referral_pipeline.monitoring.service import WorkflowMonitoringService
from referral_pipeline.monitoring.store import create_workflow_store


def add_monitoring_commands(commands: argparse._SubParsersAction) -> None:
    monitor = commands.add_parser(
        "monitor",
        help="Synchronize read-only Monday/DRK snapshots and evaluate Steps 4-5.",
    )
    monday_source = monitor.add_mutually_exclusive_group()
    monday_source.add_argument("--live-monday", action="store_true", help="Read WCW Master Sheet through the API.")
    monday_source.add_argument("--monday-snapshot", type=Path, help="Use a local Monday export JSON.")
    drk_source = monitor.add_mutually_exclusive_group()
    drk_source.add_argument("--drk-snapshot", type=Path, help="Use a normalized read-only DRK status JSON.")
    drk_source.add_argument(
        "--drk-capture-dir",
        type=Path,
        help="Normalize one or more read-only DRK Selenium patient capture directories.",
    )
    drk_source.add_argument(
        "--live-drk",
        action="store_true",
        help="Read a bounded batch of active linked patients through live DRK Selenium.",
    )
    monitor.add_argument("--drk-capture-profile", type=Path, default=DEFAULT_PROFILE_PATH)
    monitor.add_argument(
        "--drk-live-profile-dir",
        type=Path,
        default=Path("tmp") / "drk-live-browser-profile",
    )
    monitor.add_argument("--drk-max-patients", type=int, default=10)
    monitor.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    monitor.add_argument("--database-backend", choices=("sqlite", "supabase"))
    monitor.add_argument("--sqlite-path", type=Path)
    monitor.add_argument("--page-size", type=int, default=250)
    monitor.add_argument("--at", help="Evaluation time as ISO-8601; defaults to now.")
    monitor.add_argument("--send-alerts", action="store_true", help="Send pending outbox alerts through Outlook.")
    monitor.add_argument("--output", type=Path, default=Path("tmp") / "monitoring" / "last-run.json")

    status = commands.add_parser("monitor-status", help="Show database-backed workflow monitoring counts.")
    status.add_argument("--database-backend", choices=("sqlite", "supabase"))
    status.add_argument("--sqlite-path", type=Path)

    health = commands.add_parser("health", help="Show persistent worker component health.")
    health.add_argument("--database-backend", choices=("sqlite", "supabase"))
    health.add_argument("--sqlite-path", type=Path)
    health.add_argument("--stale-after-seconds", type=int, default=7200)


def run_monitoring_command(args: argparse.Namespace) -> int:
    if args.command == "health":
        store = create_workflow_store(backend=args.database_backend, sqlite_path=args.sqlite_path)
        report = health_summary(
            store,
            now=datetime.now(timezone.utc),
            stale_after_seconds=args.stale_after_seconds,
        )
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1 if report["overall_status"] == "failed" else 0
    if args.command == "monitor-status":
        store = create_workflow_store(backend=args.database_backend, sqlite_path=args.sqlite_path)
        print(json.dumps(store.status_summary(), indent=2))
        return 0
    if (
        not args.live_monday
        and args.monday_snapshot is None
        and args.drk_snapshot is None
        and args.drk_capture_dir is None
        and not args.live_drk
    ):
        raise ValueError(
            "monitor requires --live-monday, --monday-snapshot, --drk-snapshot, "
            "--drk-capture-dir, or --live-drk"
        )
    if args.page_size < 1 or args.page_size > 500:
        raise ValueError("--page-size must be between 1 and 500")
    if args.drk_max_patients < 1:
        raise ValueError("--drk-max-patients must be at least 1")
    if args.live_drk and not (args.live_monday or args.monday_snapshot is not None):
        raise ValueError("--live-drk requires a Monday source to select active linked patients")

    now = _parse_time(args.at)
    store = create_workflow_store(backend=args.database_backend, sqlite_path=args.sqlite_path)
    monitoring_config = load_monitoring_config(args.config)
    monday_snapshots = []
    if args.live_monday or args.monday_snapshot is not None:
        monday_snapshots = load_monday_snapshots(
            observed_at=now,
            records_file=args.monday_snapshot,
            live=args.live_monday,
            page_size=args.page_size,
        )
    snapshots = list(monday_snapshots)
    if args.drk_snapshot is not None:
        snapshots.extend(load_drk_snapshots(args.drk_snapshot, observed_at=now))
    if args.drk_capture_dir is not None:
        snapshots.extend(
            load_drk_capture_snapshots(
                args.drk_capture_dir,
                observed_at=now,
                profile_path=args.drk_capture_profile,
            )
        )
    live_drk_report = None
    if args.live_drk:
        batch = load_live_drk_snapshots(
            monday_snapshots=monday_snapshots,
            store=store,
            monitoring_config=monitoring_config,
            observed_at=now,
            browser_profile_dir=args.drk_live_profile_dir,
            max_patients=args.drk_max_patients,
            capture_profile_path=args.drk_capture_profile,
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
    if args.live_monday or args.monday_snapshot is not None:
        store.record_cursor("monday", now.isoformat())
    if args.drk_snapshot is not None or args.drk_capture_dir is not None or args.live_drk:
        store.record_cursor("drk", now.isoformat())
    report["database"] = store.status_summary()
    if args.send_alerts:
        report["notifications"] = dispatch_pending_notifications(
            store=store,
            send_email=outlook_sender(),
        )
    else:
        report["notifications"] = {"sent": 0, "mode": "outbox-only"}

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({**report, "report_path": str(args.output.resolve())}, indent=2, ensure_ascii=False))
    return 0


def _parse_time(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("--at must include a timezone offset")
    return parsed
