"""Operator commands for read-only workflow synchronization and reporting."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from referral_pipeline.monitoring.config import DEFAULT_CONFIG_PATH, load_monitoring_config
from referral_pipeline.monitoring.drk_source import load_drk_snapshots
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
    monitor.add_argument("--drk-snapshot", type=Path, help="Use a normalized read-only DRK status JSON.")
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


def run_monitoring_command(args: argparse.Namespace) -> int:
    if args.command == "monitor-status":
        store = create_workflow_store(backend=args.database_backend, sqlite_path=args.sqlite_path)
        print(json.dumps(store.status_summary(), indent=2))
        return 0
    if not args.live_monday and args.monday_snapshot is None and args.drk_snapshot is None:
        raise ValueError("monitor requires --live-monday, --monday-snapshot, or --drk-snapshot")
    if args.page_size < 1 or args.page_size > 500:
        raise ValueError("--page-size must be between 1 and 500")

    now = _parse_time(args.at)
    snapshots = []
    if args.live_monday or args.monday_snapshot is not None:
        snapshots.extend(
            load_monday_snapshots(
                observed_at=now,
                records_file=args.monday_snapshot,
                live=args.live_monday,
                page_size=args.page_size,
            )
        )
    if args.drk_snapshot is not None:
        snapshots.extend(load_drk_snapshots(args.drk_snapshot, observed_at=now))

    store = create_workflow_store(backend=args.database_backend, sqlite_path=args.sqlite_path)
    service = WorkflowMonitoringService(store=store, config=load_monitoring_config(args.config))
    report = service.process(snapshots, now=now)
    if args.live_monday or args.monday_snapshot is not None:
        store.record_cursor("monday", now.isoformat())
    if args.drk_snapshot is not None:
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
