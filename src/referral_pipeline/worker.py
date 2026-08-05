"""Continuous Outlook poll + retry worker for durable Render deployments."""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from referral_pipeline.runner import main as run_inbound_main


logger = logging.getLogger(__name__)

DEFAULT_DATA_ROOT = Path(os.getenv("INTAKE_DATA_ROOT", "/var/data/intake"))
DEFAULT_POLL_INTERVAL_SECONDS = int(os.getenv("INTAKE_POLL_INTERVAL_SECONDS", "600"))
DEFAULT_RETRY_INTERVAL_SECONDS = int(os.getenv("INTAKE_RETRY_INTERVAL_SECONDS", "300"))
DEFAULT_MAX_MESSAGES = int(os.getenv("INTAKE_MAX_MESSAGES", "25"))
DEFAULT_MAX_RETRY_JOBS = int(os.getenv("INTAKE_MAX_RETRY_JOBS", "10"))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Outlook discovery and durable retries in a continuous loop.",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help="Durable root for SQLite state, PDFs, and run artifacts (Render disk mount).",
    )
    parser.add_argument("--poll-interval-seconds", type=int, default=DEFAULT_POLL_INTERVAL_SECONDS)
    parser.add_argument("--retry-interval-seconds", type=int, default=DEFAULT_RETRY_INTERVAL_SECONDS)
    parser.add_argument("--max-messages", type=int, default=DEFAULT_MAX_MESSAGES)
    parser.add_argument("--max-jobs", type=int, default=DEFAULT_MAX_RETRY_JOBS)
    parser.add_argument("--once", action="store_true", help="Run one poll cycle and one retry cycle, then exit.")
    parser.add_argument("--skip-poll", action="store_true", help="Only run the retry drain path.")
    parser.add_argument("--skip-retries", action="store_true", help="Only run the Outlook discovery path.")
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
    output_root = data_root / "inbox-runs"
    state_db = data_root / "state.sqlite"
    run_dir = _new_run_dir(output_root)
    argv = [
        "--outlook-poll",
        "--max-messages",
        str(max_messages),
        "--output-dir",
        str(run_dir),
        "--state-db",
        str(state_db),
        "--master-sheet-mode",
        "dry-run",
        "--send-review",
        "--monday-mode",
        "disabled",
        "--agency-mode",
        "live-readonly",
    ]
    if not quiet:
        argv.append("--verbose")
    started = time.perf_counter()
    try:
        exit_code = run_main(argv)
        return {
            "kind": "poll",
            "status": "ok" if exit_code == 0 else "failed",
            "exit_code": exit_code,
            "run_dir": str(run_dir),
            "elapsed_seconds": round(time.perf_counter() - started, 2),
        }
    except Exception as error:  # noqa: BLE001 - worker must survive cycle failures
        logger.exception("Outlook poll cycle failed")
        return {
            "kind": "poll",
            "status": "error",
            "error": str(error),
            "run_dir": str(run_dir),
            "elapsed_seconds": round(time.perf_counter() - started, 2),
        }


def run_retry_cycle(
    *,
    data_root: Path,
    max_jobs: int,
    quiet: bool = False,
    run_main: Callable[[list[str]], int] = run_inbound_main,
) -> dict:
    """One durable retry drain cycle; failures are logged and returned, not raised."""
    output_root = data_root / "inbox-runs"
    state_db = data_root / "state.sqlite"
    run_dir = _new_run_dir(output_root)
    argv = [
        "--process-retries",
        "--max-jobs",
        str(max_jobs),
        "--output-dir",
        str(run_dir),
        "--state-db",
        str(state_db),
        "--master-sheet-mode",
        "dry-run",
        "--send-review",
        "--monday-mode",
        "disabled",
        "--agency-mode",
        "live-readonly",
    ]
    if not quiet:
        argv.append("--verbose")
    started = time.perf_counter()
    try:
        exit_code = run_main(argv)
        return {
            "kind": "retries",
            "status": "ok" if exit_code == 0 else "failed",
            "exit_code": exit_code,
            "run_dir": str(run_dir),
            "elapsed_seconds": round(time.perf_counter() - started, 2),
        }
    except Exception as error:  # noqa: BLE001 - worker must survive cycle failures
        logger.exception("Retry cycle failed")
        return {
            "kind": "retries",
            "status": "error",
            "error": str(error),
            "run_dir": str(run_dir),
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
) -> list[dict]:
    """Run poll and retry cycles on independent intervals until stopped or `--once`."""
    if poll_interval_seconds < 1:
        raise ValueError("poll_interval_seconds must be at least 1")
    if retry_interval_seconds < 1:
        raise ValueError("retry_interval_seconds must be at least 1")

    data_root.mkdir(parents=True, exist_ok=True)
    (data_root / "inbox-runs").mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    now = clock()
    next_poll_at = now if not skip_poll else float("inf")
    next_retry_at = now if not skip_retries else float("inf")

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
            print(json.dumps(result, indent=2), flush=True)
            next_retry_at = clock() + retry_interval_seconds

        if once:
            break

        now = clock()
        wake_in = min(next_poll_at - now, next_retry_at - now)
        sleep_fn(max(wake_in, 1.0))

    return results


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if not args.quiet else logging.WARNING,
        format="%(levelname)s:%(name)s:%(message)s",
    )
    logger.info(
        "Starting intake worker data_root=%s poll=%ss retry=%ss max_messages=%s",
        args.data_root,
        args.poll_interval_seconds,
        args.retry_interval_seconds,
        args.max_messages,
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
        quiet=args.quiet,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
