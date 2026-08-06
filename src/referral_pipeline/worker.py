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
from referral_pipeline.review.workflow import ApprovalProcessor
from referral_pipeline.runner import main as run_inbound_main


logger = logging.getLogger(__name__)

DEFAULT_DATA_ROOT = Path(os.getenv("INTAKE_DATA_ROOT", "/var/data/intake"))
DEFAULT_POLL_INTERVAL_SECONDS = int(os.getenv("INTAKE_POLL_INTERVAL_SECONDS", "600"))
DEFAULT_RETRY_INTERVAL_SECONDS = int(os.getenv("INTAKE_RETRY_INTERVAL_SECONDS", "300"))
DEFAULT_APPROVAL_INTERVAL_SECONDS = int(os.getenv("INTAKE_APPROVAL_INTERVAL_SECONDS", "60"))
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
    parser.add_argument("--max-messages", type=int, default=DEFAULT_MAX_MESSAGES)
    parser.add_argument("--max-jobs", type=int, default=DEFAULT_MAX_RETRY_JOBS)
    parser.add_argument("--max-approval-messages", type=int, default=DEFAULT_MAX_APPROVAL_MESSAGES)
    parser.add_argument(
        "--execute-approvals",
        action="store_true",
        default=_env_flag("INTAKE_EXECUTE_APPROVALS"),
        help=(
            "Deprecated for real writes. When set, the worker only validates confirmed "
            "reviews with --dry-run semantics; Monday creates require the CLI approvals --execute command."
        ),
    )
    parser.add_argument(
        "--dry-run-approvals",
        action="store_true",
        default=_env_flag("INTAKE_DRY_RUN_APPROVALS"),
        help="Validate confirmed reviews without writing Monday or DRK.",
    )
    parser.add_argument("--once", action="store_true", help="Run each enabled cycle once, then exit.")
    parser.add_argument("--skip-poll", action="store_true", help="Do not run Outlook referral discovery.")
    parser.add_argument("--skip-retries", action="store_true", help="Do not drain due retry jobs.")
    parser.add_argument("--skip-approvals", action="store_true", help="Do not poll review confirmations.")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


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
    dry_run: bool = False,
    processor_factory: Callable[[Path], ApprovalProcessor] | None = None,
) -> dict:
    """Poll reviewer replies. Workers never create Monday items."""
    state_db = data_root / "state.sqlite"
    started = time.perf_counter()
    # Real Monday writes stay on the explicit CLI `--execute` path only.
    worker_dry_run = bool(dry_run or execute)
    try:
        if processor_factory is None:
            client = OutlookGraphClient(OutlookGraphConfig.from_environment())
            processor = ApprovalProcessor(
                state_db=state_db,
                mailbox=OutlookReviewMailbox(client),
            )
        else:
            processor = processor_factory(state_db)
        result = processor.poll(
            max_messages=max_messages,
            execute=False,
            dry_run=worker_dry_run,
        )
        failed = any(item.get("status") == "failed" for item in result["executed"])
        return {
            "kind": "approvals",
            "status": "failed" if failed else "ok",
            "execution_enabled": False,
            "dry_run_enabled": worker_dry_run,
            "elapsed_seconds": round(time.perf_counter() - started, 2),
            **result,
        }
    except Exception as error:  # noqa: BLE001 - worker must survive cycle failures
        logger.exception("Approval poll cycle failed")
        return {
            "kind": "approvals",
            "status": "error",
            "execution_enabled": False,
            "dry_run_enabled": worker_dry_run,
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
    dry_run_approvals: bool = False,
    skip_approvals: bool = False,
    approval_processor_factory: Callable[[Path], ApprovalProcessor] | None = None,
) -> list[dict]:
    """Run discovery, retry, and approval cycles on independent intervals."""
    if poll_interval_seconds < 1:
        raise ValueError("poll_interval_seconds must be at least 1")
    if retry_interval_seconds < 1:
        raise ValueError("retry_interval_seconds must be at least 1")
    if approval_interval_seconds < 1:
        raise ValueError("approval_interval_seconds must be at least 1")

    data_root.mkdir(parents=True, exist_ok=True)
    (data_root / "inbox-runs").mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    now = clock()
    next_poll_at = now if not skip_poll else float("inf")
    next_retry_at = now if not skip_retries else float("inf")
    next_approval_at = now if not skip_approvals else float("inf")

    while True:
        now = clock()
        if now >= next_retry_at and not skip_retries:
            result = run_retry_cycle(
                data_root=data_root,
                max_jobs=max_jobs,
                quiet=quiet,
                run_main=run_main,
            )
            results.append(result)
            print(json.dumps(result, indent=2), flush=True)
            next_retry_at = clock() + retry_interval_seconds

        now = clock()
        if now >= next_poll_at and not skip_poll:
            result = run_poll_cycle(
                data_root=data_root,
                max_messages=max_messages,
                quiet=quiet,
                run_main=run_main,
            )
            results.append(result)
            print(json.dumps(result, indent=2), flush=True)
            next_poll_at = clock() + poll_interval_seconds

        now = clock()
        if now >= next_approval_at and not skip_approvals:
            result = run_approval_cycle(
                data_root=data_root,
                max_messages=max_approval_messages,
                execute=execute_approvals,
                dry_run=dry_run_approvals,
                processor_factory=approval_processor_factory,
            )
            results.append(result)
            print(json.dumps(result, indent=2), flush=True)
            next_approval_at = clock() + approval_interval_seconds

        if once:
            break

        now = clock()
        wake_in = min(next_poll_at - now, next_retry_at - now, next_approval_at - now)
        sleep_fn(max(wake_in, 1.0))

    return results


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if not args.quiet else logging.WARNING,
        format="%(levelname)s:%(name)s:%(message)s",
    )
    dry_run_approvals = bool(args.dry_run_approvals or args.execute_approvals)
    logger.info(
        "Starting intake worker data_root=%s poll=%ss retry=%ss approvals=%ss max_messages=%s dry_run_approvals=%s",
        args.data_root,
        args.poll_interval_seconds,
        args.retry_interval_seconds,
        args.approval_interval_seconds,
        args.max_messages,
        dry_run_approvals,
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
        execute_approvals=False,
        dry_run_approvals=dry_run_approvals,
        skip_approvals=args.skip_approvals,
        quiet=args.quiet,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
