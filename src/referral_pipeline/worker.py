"""Continuous Outlook intake, retry, and approval worker for Render."""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from Outlook.graph import OutlookGraphClient, OutlookGraphConfig
from Outlook.review_mail import OutlookReviewMailbox
from referral_pipeline.monitoring.config import DEFAULT_CONFIG_PATH
from referral_pipeline.monitoring.drk_capture import DEFAULT_PROFILE_PATH
from referral_pipeline.monitoring.health import WorkerHealthReporter, create_worker_health_reporter
from referral_pipeline.monitoring.worker_cycle import run_monitor_cycle
from referral_pipeline.review.workflow import ApprovalProcessor
from referral_pipeline.runner import main as run_inbound_main


logger = logging.getLogger(__name__)

DEFAULT_DATA_ROOT = Path(os.getenv("INTAKE_DATA_ROOT", "/var/data/intake"))
DEFAULT_POLL_INTERVAL_SECONDS = int(os.getenv("INTAKE_POLL_INTERVAL_SECONDS", "600"))
DEFAULT_RETRY_INTERVAL_SECONDS = int(os.getenv("INTAKE_RETRY_INTERVAL_SECONDS", "300"))
DEFAULT_APPROVAL_INTERVAL_SECONDS = int(os.getenv("INTAKE_APPROVAL_INTERVAL_SECONDS", "60"))
DEFAULT_MONITOR_INTERVAL_SECONDS = int(os.getenv("INTAKE_MONITOR_INTERVAL_SECONDS", "3600"))
DEFAULT_MAX_MESSAGES = int(os.getenv("INTAKE_MAX_MESSAGES", "25"))
DEFAULT_MAX_RETRY_JOBS = int(os.getenv("INTAKE_MAX_RETRY_JOBS", "10"))
DEFAULT_MAX_APPROVAL_MESSAGES = int(os.getenv("INTAKE_MAX_APPROVAL_MESSAGES", "100"))


def _env_flag(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Outlook discovery, durable retries, and approval polling.",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help="Durable root for SQLite state, PDFs, and run artifacts (Render disk mount).",
    )
    parser.add_argument("--poll-interval-seconds", type=int, default=DEFAULT_POLL_INTERVAL_SECONDS)
    parser.add_argument("--retry-interval-seconds", type=int, default=DEFAULT_RETRY_INTERVAL_SECONDS)
    parser.add_argument("--approval-interval-seconds", type=int, default=DEFAULT_APPROVAL_INTERVAL_SECONDS)
    parser.add_argument("--monitor-interval-seconds", type=int, default=DEFAULT_MONITOR_INTERVAL_SECONDS)
    parser.add_argument("--max-messages", type=int, default=DEFAULT_MAX_MESSAGES)
    parser.add_argument("--max-jobs", type=int, default=DEFAULT_MAX_RETRY_JOBS)
    parser.add_argument("--max-approval-messages", type=int, default=DEFAULT_MAX_APPROVAL_MESSAGES)
    parser.add_argument(
        "--execute-approvals",
        action="store_true",
        default=_env_flag("INTAKE_EXECUTE_APPROVALS"),
        help="Apply confirmed Monday previews; disabled unless explicitly enabled.",
    )
    parser.add_argument(
        "--monitor",
        action=argparse.BooleanOptionalAction,
        default=_env_flag("INTAKE_MONITOR_ENABLED"),
        help="Run read-only Monday/DRK monitoring; disabled by default.",
    )
    parser.add_argument(
        "--monitor-send-alerts",
        action=argparse.BooleanOptionalAction,
        default=_env_flag("INTAKE_MONITOR_SEND_ALERTS"),
        help="Send queued monitoring alerts; outbox-only by default.",
    )
    parser.add_argument(
        "--monitor-config",
        type=Path,
        default=Path(os.getenv("INTAKE_MONITOR_CONFIG", str(DEFAULT_CONFIG_PATH))),
    )
    parser.add_argument("--monitor-database-backend", choices=("sqlite", "supabase"))
    parser.add_argument("--monitor-sqlite-path", type=Path)
    parser.add_argument(
        "--health",
        action=argparse.BooleanOptionalAction,
        default=_env_flag("INTAKE_HEALTH_ENABLED", default=True),
        help="Persist PHI-free component health; enabled by default.",
    )
    parser.add_argument(
        "--health-send-alerts",
        action=argparse.BooleanOptionalAction,
        default=_env_flag("INTAKE_HEALTH_SEND_ALERTS"),
        help="Send queued health transition alerts; disabled by default.",
    )
    parser.add_argument(
        "--health-failure-threshold",
        type=int,
        default=int(os.getenv("INTAKE_HEALTH_FAILURE_THRESHOLD", "3")),
    )
    parser.add_argument("--drk-snapshot", type=Path, help="Optional normalized DRK read-only snapshot.")
    parser.add_argument(
        "--drk-capture-dir",
        type=Path,
        help="Optional DRK Selenium capture root to normalize during monitoring.",
    )
    parser.add_argument("--drk-capture-profile", type=Path, default=DEFAULT_PROFILE_PATH)
    parser.add_argument(
        "--live-drk",
        action=argparse.BooleanOptionalAction,
        default=_env_flag("INTAKE_LIVE_DRK_ENABLED"),
        help="Continuously read bounded active-patient batches from DRK; disabled by default.",
    )
    parser.add_argument(
        "--drk-max-patients",
        type=int,
        default=int(os.getenv("INTAKE_DRK_MAX_PATIENTS_PER_CYCLE", "10")),
    )
    parser.add_argument("--drk-live-profile-dir", type=Path)
    parser.add_argument("--once", action="store_true", help="Run each enabled cycle once, then exit.")
    parser.add_argument("--skip-poll", action="store_true", help="Do not run Outlook referral discovery.")
    parser.add_argument("--skip-retries", action="store_true", help="Do not drain due retry jobs.")
    parser.add_argument("--skip-approvals", action="store_true", help="Do not poll review confirmations.")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    configured_drk_sources = sum(
        (args.drk_snapshot is not None, args.drk_capture_dir is not None, args.live_drk)
    )
    if configured_drk_sources > 1:
        parser.error("choose only one DRK source: snapshot, capture directory, or live DRK")
    if args.live_drk and not args.monitor:
        parser.error("--live-drk requires --monitor")
    return args


def _new_run_dir(output_root: Path) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    stem = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    candidate = output_root / stem
    suffix = 2
    while candidate.exists():
        candidate = output_root / f"{stem}-{suffix}"
        suffix += 1
    return candidate


def run_poll_cycle(
    *,
    data_root: Path,
    max_messages: int,
    quiet: bool = False,
    run_main: Callable[[list[str]], int] = run_inbound_main,
) -> dict:
    """One Outlook discovery cycle; failures are logged and returned, not raised."""
    argv = [
        "--outlook-poll",
        "--max-messages",
        str(max_messages),
        "--master-sheet-mode",
        "dry-run",
        "--send-review",
        "--monday-mode",
        "live-readonly",
        "--agency-mode",
        "live-readonly",
    ]
    if not quiet:
        argv.append("--verbose")
    return _run_intake_cycle(kind="poll", data_root=data_root, argv=argv, run_main=run_main)


def run_retry_cycle(
    *,
    data_root: Path,
    max_jobs: int,
    quiet: bool = False,
    run_main: Callable[[list[str]], int] = run_inbound_main,
) -> dict:
    """One durable retry drain cycle; failures are logged and returned, not raised."""
    argv = [
        "--process-retries",
        "--max-jobs",
        str(max_jobs),
        "--master-sheet-mode",
        "dry-run",
        "--send-review",
        "--monday-mode",
        "live-readonly",
        "--agency-mode",
        "live-readonly",
    ]
    if not quiet:
        argv.append("--verbose")
    return _run_intake_cycle(kind="retries", data_root=data_root, argv=argv, run_main=run_main)


def _run_intake_cycle(
    *,
    kind: str,
    data_root: Path,
    argv: list[str],
    run_main: Callable[[list[str]], int],
) -> dict:
    run_dir = _new_run_dir(data_root / "inbox-runs")
    argv.extend(("--output-dir", str(run_dir), "--state-db", str(data_root / "state.sqlite")))
    started = time.perf_counter()
    try:
        exit_code = run_main(argv)
        return {
            "kind": kind,
            "status": "ok" if exit_code == 0 else "failed",
            "exit_code": exit_code,
            "run_dir": str(run_dir),
            "elapsed_seconds": round(time.perf_counter() - started, 2),
        }
    except Exception as error:  # noqa: BLE001 - worker must survive cycle failures
        logger.exception("%s cycle failed", kind)
        return {
            "kind": kind,
            "status": "error",
            "error": str(error),
            "run_dir": str(run_dir),
            "elapsed_seconds": round(time.perf_counter() - started, 2),
        }


def run_approval_cycle(
    *,
    data_root: Path,
    max_messages: int,
    execute: bool = False,
    processor_factory: Callable[[Path], ApprovalProcessor] | None = None,
) -> dict:
    """Poll reviewer replies and optionally apply confirmed Monday previews."""
    state_db = data_root / "state.sqlite"
    started = time.perf_counter()
    try:
        if processor_factory is None:
            client = OutlookGraphClient(OutlookGraphConfig.from_environment())
            processor = ApprovalProcessor(
                state_db=state_db,
                mailbox=OutlookReviewMailbox(client),
            )
        else:
            processor = processor_factory(state_db)
        result = processor.poll(max_messages=max_messages, execute=execute)
        failed = any(item.get("status") == "failed" for item in result["executed"])
        return {
            "kind": "approvals",
            "status": "failed" if failed else "ok",
            "execution_enabled": execute,
            "elapsed_seconds": round(time.perf_counter() - started, 2),
            **result,
        }
    except Exception as error:  # noqa: BLE001 - worker must survive cycle failures
        logger.exception("Approval poll cycle failed")
        return {
            "kind": "approvals",
            "status": "error",
            "execution_enabled": execute,
            "error": str(error),
            "elapsed_seconds": round(time.perf_counter() - started, 2),
        }


def run_worker_loop(
    *,
    data_root: Path,
    poll_interval_seconds: int,
    retry_interval_seconds: int,
    max_messages: int,
    max_jobs: int,
    once: bool = False,
    skip_poll: bool = False,
    skip_retries: bool = False,
    quiet: bool = False,
    sleep_fn: Callable[[float], None] = time.sleep,
    run_main: Callable[[list[str]], int] = run_inbound_main,
    clock: Callable[[], float] = time.monotonic,
    approval_interval_seconds: int = DEFAULT_APPROVAL_INTERVAL_SECONDS,
    max_approval_messages: int = DEFAULT_MAX_APPROVAL_MESSAGES,
    execute_approvals: bool = False,
    skip_approvals: bool = False,
    approval_processor_factory: Callable[[Path], ApprovalProcessor] | None = None,
    monitor_enabled: bool = False,
    monitor_interval_seconds: int = DEFAULT_MONITOR_INTERVAL_SECONDS,
    monitor_send_alerts: bool = False,
    monitor_config_path: Path = DEFAULT_CONFIG_PATH,
    monitor_database_backend: str | None = None,
    monitor_sqlite_path: Path | None = None,
    drk_snapshot: Path | None = None,
    drk_capture_dir: Path | None = None,
    drk_capture_profile: Path = DEFAULT_PROFILE_PATH,
    live_drk: bool = False,
    drk_max_patients: int = 10,
    drk_live_profile_dir: Path | None = None,
    monitor_cycle: Callable[..., dict] = run_monitor_cycle,
    health_enabled: bool = True,
    health_send_alerts: bool = False,
    health_failure_threshold: int = 3,
    health_reporter: WorkerHealthReporter | None = None,
) -> list[dict]:
    """Run intake, approval, and optional monitoring cycles independently."""
    if poll_interval_seconds < 1:
        raise ValueError("poll_interval_seconds must be at least 1")
    if retry_interval_seconds < 1:
        raise ValueError("retry_interval_seconds must be at least 1")
    if approval_interval_seconds < 1:
        raise ValueError("approval_interval_seconds must be at least 1")
    if monitor_interval_seconds < 1:
        raise ValueError("monitor_interval_seconds must be at least 1")
    if health_failure_threshold < 1:
        raise ValueError("health_failure_threshold must be at least 1")
    if drk_max_patients < 1:
        raise ValueError("drk_max_patients must be at least 1")

    data_root.mkdir(parents=True, exist_ok=True)
    (data_root / "inbox-runs").mkdir(parents=True, exist_ok=True)

    effective_health_reporter = health_reporter
    if health_enabled and effective_health_reporter is None:
        try:
            effective_health_reporter = create_worker_health_reporter(
                data_root=data_root,
                database_backend=monitor_database_backend,
                sqlite_path=monitor_sqlite_path,
                config_path=monitor_config_path,
                failure_threshold=health_failure_threshold,
                send_alerts=health_send_alerts,
            )
        except Exception:  # noqa: BLE001 - health reporting cannot stop intake
            logger.exception("Unable to initialize worker health persistence")
            effective_health_reporter = None

    def record_health(result: dict) -> None:
        if effective_health_reporter is not None:
            effective_health_reporter.record(result)

    results: list[dict] = []
    now = clock()
    next_poll_at = now if not skip_poll else float("inf")
    next_retry_at = now if not skip_retries else float("inf")
    next_approval_at = now if not skip_approvals else float("inf")
    next_monitor_at = now if monitor_enabled else float("inf")

    while True:
        now = clock()
        if now >= next_poll_at and not skip_poll:
            result = run_poll_cycle(
                data_root=data_root,
                max_messages=max_messages,
                quiet=quiet,
                run_main=run_main,
            )
            results.append(result)
            record_health(result)
            print(json.dumps(result, indent=2), flush=True)
            next_poll_at = clock() + poll_interval_seconds

        now = clock()
        if now >= next_retry_at and not skip_retries:
            result = run_retry_cycle(
                data_root=data_root,
                max_jobs=max_jobs,
                quiet=quiet,
                run_main=run_main,
            )
            results.append(result)
            record_health(result)
            print(json.dumps(result, indent=2), flush=True)
            next_retry_at = clock() + retry_interval_seconds

        now = clock()
        if now >= next_approval_at and not skip_approvals:
            result = run_approval_cycle(
                data_root=data_root,
                max_messages=max_approval_messages,
                execute=execute_approvals,
                processor_factory=approval_processor_factory,
            )
            results.append(result)
            record_health(result)
            print(json.dumps(result, indent=2), flush=True)
            next_approval_at = clock() + approval_interval_seconds

        now = clock()
        if now >= next_monitor_at and monitor_enabled:
            result = monitor_cycle(
                data_root=data_root,
                send_alerts=monitor_send_alerts,
                config_path=monitor_config_path,
                database_backend=monitor_database_backend,
                sqlite_path=monitor_sqlite_path,
                drk_snapshot=drk_snapshot,
                drk_capture_dir=drk_capture_dir,
                drk_capture_profile=drk_capture_profile,
                live_drk=live_drk,
                drk_max_patients=drk_max_patients,
                drk_live_profile_dir=drk_live_profile_dir,
            )
            results.append(result)
            record_health(result)
            print(json.dumps(result, indent=2), flush=True)
            next_monitor_at = clock() + monitor_interval_seconds

        if once:
            break

        now = clock()
        wake_in = min(
            next_poll_at - now,
            next_retry_at - now,
            next_approval_at - now,
            next_monitor_at - now,
        )
        sleep_fn(max(wake_in, 1.0))

    return results


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if not args.quiet else logging.WARNING,
        format="%(levelname)s:%(name)s:%(message)s",
    )
    logger.info(
        "Starting intake worker data_root=%s poll=%ss retry=%ss approvals=%ss monitor=%s/%ss max_messages=%s execute_approvals=%s",
        args.data_root,
        args.poll_interval_seconds,
        args.retry_interval_seconds,
        args.approval_interval_seconds,
        args.monitor,
        args.monitor_interval_seconds,
        args.max_messages,
        args.execute_approvals,
    )
    run_worker_loop(
        data_root=args.data_root.resolve(),
        poll_interval_seconds=args.poll_interval_seconds,
        retry_interval_seconds=args.retry_interval_seconds,
        max_messages=args.max_messages,
        max_jobs=args.max_jobs,
        once=args.once,
        skip_poll=args.skip_poll,
        skip_retries=args.skip_retries,
        approval_interval_seconds=args.approval_interval_seconds,
        max_approval_messages=args.max_approval_messages,
        execute_approvals=args.execute_approvals,
        skip_approvals=args.skip_approvals,
        monitor_enabled=args.monitor,
        monitor_interval_seconds=args.monitor_interval_seconds,
        monitor_send_alerts=args.monitor_send_alerts,
        monitor_config_path=args.monitor_config,
        monitor_database_backend=args.monitor_database_backend,
        monitor_sqlite_path=args.monitor_sqlite_path,
        drk_snapshot=args.drk_snapshot,
        drk_capture_dir=args.drk_capture_dir,
        drk_capture_profile=args.drk_capture_profile,
        live_drk=args.live_drk,
        drk_max_patients=args.drk_max_patients,
        drk_live_profile_dir=args.drk_live_profile_dir,
        health_enabled=args.health,
        health_send_alerts=args.health_send_alerts,
        health_failure_threshold=args.health_failure_threshold,
        quiet=args.quiet,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
