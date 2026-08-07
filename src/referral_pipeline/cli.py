"""Operator-friendly CLI for the referral pipeline and guarded Monday writes."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


# `monday.com` is a scripts directory rather than an importable package. Keep its
# path handling at the cross-system orchestration boundary.
SRC_ROOT = Path(__file__).resolve().parents[1]
MONDAY_DIR = SRC_ROOT / "monday.com"
for import_path in (SRC_ROOT, MONDAY_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from master_sheet_writer import apply_master_sheet_create  # noqa: E402
from Outlook.graph import OutlookGraphClient, OutlookGraphConfig  # noqa: E402
from Outlook.review_mail import OutlookReviewMailbox  # noqa: E402
from referral_pipeline.review.workflow import ApprovalProcessor  # noqa: E402
from referral_pipeline.review.workflow import create_and_send_review  # noqa: E402
from referral_pipeline.runner import main as run_inbound_main  # noqa: E402
from referral_pipeline.state import InboxState  # noqa: E402
from referral_pipeline.monitoring.cli import add_monitoring_commands, run_monitoring_command  # noqa: E402


DEFAULT_OUTPUT_ROOT = Path("tmp") / "inbox-runs"
LATEST_POINTER_NAME = "latest.json"
# Temporary test toggle. Change to True when Monday duplicate checks should run.
MONDAY_DUPLICATE_CHECK_ENABLED = False


class IntakeCLIError(RuntimeError):
    pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Outlook-to-Monday referral intake flow with safe defaults.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    outlook = commands.add_parser(
        "outlook",
        help="Process PDF attachments from the configured Outlook mailbox.",
    )
    write_mode = outlook.add_mutually_exclusive_group()
    write_mode.add_argument("--dry-run", action="store_true", help="Build and save a preview only (default).")
    write_mode.add_argument("--apply", action="store_true", help="Create an unblocked Master Sheet item immediately.")
    outlook.add_argument("--confirm-master-sheet-write", action="store_true")
    outlook.add_argument(
        "--max-messages",
        type=int,
        default=25,
        help="Maximum eligible new referral emails to process (newest first).",
    )
    outlook.add_argument("--input-mode", choices=("auto", "text", "image", "hybrid"), default="image")
    outlook.add_argument("--max-pages", type=int)
    outlook.add_argument(
        "--monday-mode",
        choices=("disabled", "snapshot", "live-readonly"),
        default="live-readonly" if MONDAY_DUPLICATE_CHECK_ENABLED else "disabled",
        help="Monday duplicate lookup mode; disabled by the in-code test toggle by default.",
    )
    outlook.add_argument("--monday-records-file", type=Path)
    outlook.add_argument("--agency-mode", choices=("disabled", "snapshot", "live-readonly"), default="live-readonly")
    outlook.add_argument("--agency-records-file", type=Path)
    outlook.add_argument("--include-full-row", action="store_true")
    outlook.add_argument("--config", type=Path)
    outlook.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    outlook.add_argument("--state-db", type=Path)
    outlook.add_argument("--force", action="store_true", help="Reprocess eligible PDFs even when already recorded.")
    outlook.add_argument("--quiet", action="store_true", help="Suppress progress logs while retaining the final summary.")
    outlook.add_argument("--send-review", action="store_true", help="Email the generated review summary instead of writing immediately.")
    outlook.add_argument(
        "--review-recipient",
        help="Authorized internal reviewer email; defaults to REVIEW_RECIPIENT_EMAIL.",
    )

    apply = commands.add_parser(
        "apply",
        help="Apply the exact preview from the latest successful dry run.",
    )
    source = apply.add_mutually_exclusive_group()
    source.add_argument("--preview", type=Path, help="Apply a specific master-sheet-preview.json file.")
    source.add_argument("--run", type=Path, help="Apply the only preview inside a specific run directory.")
    apply.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    apply.add_argument("--confirm-master-sheet-write", action="store_true", required=True)

    approvals = commands.add_parser(
        "approvals",
        help="Read review replies and optionally execute exact confirmed Monday previews.",
    )
    approvals.add_argument("--execute", action="store_true", help="Apply confirmed Monday previews and create DRK handoffs.")
    approvals.add_argument("--max-messages", type=int, default=25)
    approvals.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    approvals.add_argument("--state-db", type=Path)

    review_send = commands.add_parser(
        "review-send",
        help="Send a review from an existing completed extraction without rerunning the LLM.",
    )
    review_send.add_argument("--run", type=Path, required=True, help="Existing timestamped intake run directory.")
    review_send.add_argument(
        "--review-recipient",
        help="Authorized internal reviewer email; defaults to REVIEW_RECIPIENT_EMAIL.",
    )
    review_send.add_argument(
        "--config",
        type=Path,
        default=MONDAY_DIR / "master_sheet_write_config.example.json",
    )
    review_send.add_argument("--state-db", type=Path)

    retries = commands.add_parser(
        "retries",
        help="Process due durable retry jobs (scheduler-friendly one-shot).",
    )
    retries.add_argument("--max-jobs", type=int, default=10)
    retries.add_argument("--input-mode", choices=("auto", "text", "image", "hybrid"), default="image")
    retries.add_argument("--max-pages", type=int)
    retries.add_argument(
        "--monday-mode",
        choices=("disabled", "snapshot", "live-readonly"),
        default="live-readonly" if MONDAY_DUPLICATE_CHECK_ENABLED else "disabled",
        help="Monday duplicate lookup mode; disabled by the in-code test toggle by default.",
    )
    retries.add_argument("--monday-records-file", type=Path)
    retries.add_argument("--agency-mode", choices=("disabled", "snapshot", "live-readonly"), default="live-readonly")
    retries.add_argument("--agency-records-file", type=Path)
    retries.add_argument("--include-full-row", action="store_true")
    retries.add_argument("--config", type=Path)
    retries.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    retries.add_argument("--state-db", type=Path)
    retries.add_argument("--quiet", action="store_true")
    retries.add_argument("--send-review", action="store_true", default=True)
    retries.add_argument("--no-send-review", action="store_false", dest="send_review")
    retries.add_argument("--review-recipient", help="Reviewer email; defaults to REVIEW_RECIPIENT_EMAIL.")

    failures = commands.add_parser(
        "failures",
        help="List permanent intake failures and optionally requeue one by sha256.",
    )
    failures.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    failures.add_argument("--state-db", type=Path)
    failures.add_argument("--limit", type=int, default=50, help="Maximum failed jobs to list.")
    failures.add_argument(
        "--requeue",
        metavar="SHA256",
        help="Move one permanent failure back onto the discovery queue for a deliberate retry.",
    )

    add_monitoring_commands(commands)

    return parser


def _new_run_dir(output_root: Path) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    stem = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = output_root / stem
    suffix = 2
    while candidate.exists():
        candidate = output_root / f"{stem}-{suffix}"
        suffix += 1
    return candidate


def _run_outlook(args: argparse.Namespace) -> int:
    if args.apply and not args.confirm_master_sheet_write:
        raise IntakeCLIError("--apply requires --confirm-master-sheet-write")
    if args.apply and args.send_review:
        raise IntakeCLIError("--send-review cannot be combined with --apply")
    if args.max_messages < 1:
        raise IntakeCLIError("--max-messages must be at least 1")

    output_root = args.output_root.resolve()
    run_dir = _new_run_dir(output_root)
    state_db = (args.state_db or output_root / "state.sqlite").resolve()
    mode = "apply" if args.apply else "dry-run"

    delegated = [
        "--outlook-poll",
        "--max-messages",
        str(args.max_messages),
        "--input-mode",
        args.input_mode,
        "--monday-mode",
        args.monday_mode,
        "--agency-mode",
        args.agency_mode,
        "--output-dir",
        str(run_dir),
        "--state-db",
        str(state_db),
        "--master-sheet-mode",
        mode,
    ]
    if args.max_pages is not None:
        delegated.extend(("--max-pages", str(args.max_pages)))
    if args.monday_records_file is not None:
        delegated.extend(("--monday-records-file", str(args.monday_records_file)))
    if args.agency_records_file is not None:
        delegated.extend(("--agency-records-file", str(args.agency_records_file)))
    if args.include_full_row:
        delegated.append("--include-full-row")
    if args.config is not None:
        delegated.extend(("--config", str(args.config)))
    if args.force:
        delegated.append("--force")
    if not args.quiet:
        delegated.append("--verbose")
    if args.confirm_master_sheet_write:
        delegated.append("--confirm-master-sheet-write")
    if args.send_review:
        delegated.append("--send-review")
    if args.review_recipient:
        delegated.extend(("--review-recipient", args.review_recipient))

    print(f"[intake] source: Outlook ({args.max_messages} newest message{'s' if args.max_messages != 1 else ''})")
    print(f"[intake] mode: {mode}")
    print(f"[intake] run directory: {run_dir}")
    exit_code = run_inbound_main(delegated)

    pointer = _record_latest_run(output_root, run_dir)
    _print_run_result(pointer, output_root=output_root)
    return exit_code


def _record_latest_run(output_root: Path, run_dir: Path) -> dict[str, Any]:
    summary_path = run_dir / "run-summary.json"
    pointer: dict[str, Any] = {
        "version": 1,
        "status": "not_ready",
        "run_dir": str(run_dir.resolve()),
        "summary_path": str(summary_path.resolve()),
    }
    try:
        results = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pointer["reason"] = f"run summary could not be read: {error}"
        return _write_pointer(output_root, pointer)

    if not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], dict):
        pointer["reason"] = "the simple apply flow requires exactly one attachment result"
        return _write_pointer(output_root, pointer)

    result = results[0]
    pointer.update(
        {
            "filename": result.get("filename"),
            "attachment_sha256": result.get("attachment_sha256"),
            "created_item_id": result.get("created_item_id"),
            "review_id": result.get("review_id"),
            "review_status": result.get("review_status"),
            "elapsed_seconds": result.get("elapsed_seconds"),
        }
    )
    if result.get("status") != "completed":
        status = str(result.get("status") or "attachment did not complete")
        pointer["reason"] = status
        if status == "pending_retry":
            pointer["status"] = "pending_retry"
            pointer["next_attempt_at"] = result.get("next_attempt_at")
        elif status == "circuit_open":
            pointer["status"] = "circuit_open"
        return _write_pointer(output_root, pointer)

    preview_value = result.get("preview_path")
    if not isinstance(preview_value, str) or not preview_value:
        pointer["reason"] = "completed result did not contain a preview path"
        return _write_pointer(output_root, pointer)

    preview_path = _absolute_path(preview_value)
    pointer["preview_path"] = str(preview_path)
    try:
        preview = _load_json_object(preview_path, label="Master Sheet preview")
    except IntakeCLIError as error:
        pointer["reason"] = str(error)
        return _write_pointer(output_root, pointer)

    pointer["item_name"] = preview.get("item_name")
    if result.get("review_status") == "awaiting_confirmation":
        pointer["status"] = "awaiting_confirmation"
    elif result.get("review_status") == "needs_correction":
        pointer["status"] = "needs_correction"
        blockers = result.get("master_sheet_blockers") or preview.get("blockers") or []
        pointer["reason"] = "; ".join(str(blocker) for blocker in blockers) or "review is blocked"
    elif result.get("created_item_id"):
        pointer["status"] = "applied"
    elif result.get("master_sheet_blocked") or preview.get("blocked"):
        blockers = result.get("master_sheet_blockers") or preview.get("blockers") or []
        pointer["reason"] = "; ".join(str(blocker) for blocker in blockers) or "preview is blocked"
    else:
        pointer["status"] = "ready"
    return _write_pointer(output_root, pointer)


def _write_pointer(output_root: Path, pointer: dict[str, Any]) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / LATEST_POINTER_NAME).write_text(
        json.dumps(pointer, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return pointer


def _print_run_result(pointer: dict[str, Any], *, output_root: Path) -> None:
    status = pointer["status"]
    print(f"[intake] status: {status}")
    if pointer.get("item_name"):
        print(f"[intake] patient: {pointer['item_name']}")
    if pointer.get("elapsed_seconds") is not None:
        print(f"[intake] attachment time: {float(pointer['elapsed_seconds']):.2f}s")
    if status == "ready":
        print("[intake] no Monday item was created")
        print("[intake] next: python run_pipeline.py apply --confirm-master-sheet-write")
    elif status == "awaiting_confirmation":
        print(f"[intake] review request: {pointer.get('review_id')}")
        print("[intake] next: reply to the review email, then run python run_pipeline.py approvals --execute")
    elif status == "needs_correction":
        print(f"[intake] review request: {pointer.get('review_id')}")
        print(f"[intake] correction required: {pointer.get('reason', 'review is blocked')}")
    elif status == "pending_retry":
        print(f"[intake] deferred for retry: {pointer.get('next_attempt_at') or 'soon'}")
        print("[intake] next: python run_pipeline.py retries")
    elif status == "circuit_open":
        print("[intake] Anthropic circuit open; work deferred")
        print("[intake] next: python run_pipeline.py retries")
    elif status == "applied":
        print(f"[intake] created Monday item: {pointer.get('created_item_id')}")
    else:
        print(f"[intake] not ready to apply: {pointer.get('reason', 'unknown reason')}")
    print(f"[intake] latest run metadata: {output_root / LATEST_POINTER_NAME}")


def _apply_preview(args: argparse.Namespace) -> int:
    preview_path, pointer = _select_preview(args)
    preview = _load_json_object(preview_path, label="Master Sheet preview")
    if preview.get("blocked"):
        blockers = preview.get("blockers") or []
        raise IntakeCLIError(f"preview is blocked: {'; '.join(str(value) for value in blockers)}")
    if preview.get("operation") != "create_item":
        raise IntakeCLIError("preview is not a Master Sheet create_item operation")

    result_path = preview_path.parent / "master-sheet-apply-result.json"
    if result_path.exists():
        raise IntakeCLIError(f"this preview already has an apply result: {result_path}")

    print(f"[intake] applying preview: {preview_path}")
    print(f"[intake] patient: {preview.get('item_name') or 'unknown'}")
    result = apply_master_sheet_create({**preview, "mode": "apply"})
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    created_item_id = result["item"]["id"]

    if pointer is not None:
        pointer["status"] = "applied"
        pointer["created_item_id"] = created_item_id
        pointer["apply_result_path"] = str(result_path.resolve())
        _write_pointer(args.output_root.resolve(), pointer)

    print(
        json.dumps(
            {
                "status": "applied",
                "item_name": preview.get("item_name"),
                "created_item_id": created_item_id,
                "apply_result": str(result_path),
            },
            indent=2,
        )
    )
    return 0


def _run_approvals(args: argparse.Namespace) -> int:
    if args.max_messages < 1:
        raise IntakeCLIError("--max-messages must be at least 1")
    state_db = (args.state_db or args.output_root / "state.sqlite").resolve()
    mailbox = OutlookReviewMailbox(OutlookGraphClient(OutlookGraphConfig.from_environment()))
    print(f"[review] checking {args.max_messages} recent inbox messages")
    print(f"[review] execution: {'enabled' if args.execute else 'disabled'}")
    result = ApprovalProcessor(state_db=state_db, mailbox=mailbox).poll(
        max_messages=args.max_messages,
        execute=args.execute,
    )
    print(json.dumps(result, indent=2))
    return 1 if any(item.get("status") == "failed" for item in result["executed"]) else 0


def _run_retries(args: argparse.Namespace) -> int:
    if args.max_jobs < 1:
        raise IntakeCLIError("--max-jobs must be at least 1")
    output_root = args.output_root.resolve()
    run_dir = _new_run_dir(output_root)
    state_db = (args.state_db or output_root / "state.sqlite").resolve()
    delegated = [
        "--process-retries",
        "--max-jobs",
        str(args.max_jobs),
        "--input-mode",
        args.input_mode,
        "--monday-mode",
        args.monday_mode,
        "--agency-mode",
        args.agency_mode,
        "--output-dir",
        str(run_dir),
        "--state-db",
        str(state_db),
        "--master-sheet-mode",
        "dry-run",
    ]
    if args.max_pages is not None:
        delegated.extend(("--max-pages", str(args.max_pages)))
    if args.monday_records_file is not None:
        delegated.extend(("--monday-records-file", str(args.monday_records_file)))
    if args.agency_records_file is not None:
        delegated.extend(("--agency-records-file", str(args.agency_records_file)))
    if args.include_full_row:
        delegated.append("--include-full-row")
    if args.config is not None:
        delegated.extend(("--config", str(args.config)))
    if not args.quiet:
        delegated.append("--verbose")
    if args.send_review:
        delegated.append("--send-review")
    if args.review_recipient:
        delegated.extend(("--review-recipient", args.review_recipient))

    print(f"[intake] source: durable retry queue (max {args.max_jobs})")
    print(f"[intake] run directory: {run_dir}")
    exit_code = run_inbound_main(delegated)
    pointer = _record_latest_run(output_root, run_dir)
    _print_run_result(pointer, output_root=output_root)
    return exit_code


def _resend_review(args: argparse.Namespace) -> int:
    run_dir = args.run.resolve()
    manifests = list(run_dir.rglob("manifest.json"))
    if len(manifests) != 1:
        raise IntakeCLIError(f"--run must contain exactly one manifest; found {len(manifests)}")
    manifest = _load_json_object(manifests[0], label="intake manifest")
    graph_client = OutlookGraphClient(OutlookGraphConfig.from_environment())
    recipient = (
        (args.review_recipient or "").strip()
        or os.getenv("REVIEW_RECIPIENT_EMAIL", "").strip()
    )
    if not recipient:
        raise IntakeCLIError(
            "review-send requires --review-recipient or REVIEW_RECIPIENT_EMAIL"
        )
    state_db = (args.state_db or run_dir.parent / "state.sqlite").resolve()

    print(f"[review] reusing extraction: {run_dir}")
    print(f"[review] sending to: {recipient}")
    result = create_and_send_review(
        manifest,
        recipient=recipient,
        write_config_path=args.config,
        state_db=state_db,
        mailbox=OutlookReviewMailbox(graph_client),
    )
    print(json.dumps(result, indent=2))
    return 0


def _run_failures(args: argparse.Namespace) -> int:
    if args.limit < 1:
        raise IntakeCLIError("--limit must be at least 1")
    output_root = args.output_root.resolve()
    state_db = (args.state_db or output_root / "state.sqlite").resolve()
    state = InboxState(state_db)

    if args.requeue:
        try:
            job = state.requeue_failed(sha256=args.requeue)
        except KeyError as error:
            raise IntakeCLIError(str(error)) from error
        print(
            json.dumps(
                {
                    "status": "requeued",
                    "sha256": job.sha256,
                    "filename": job.filename,
                    "subject": job.subject,
                    "next": "python run_pipeline.py outlook --send-review  or  python run_pipeline.py retries",
                },
                indent=2,
            )
        )
        return 0

    jobs = state.list_failed(limit=args.limit)
    payload = {
        "failed_count": state.failed_count(),
        "listed": len(jobs),
        "state_db": str(state_db),
        "failures": [
            {
                "filename": job.filename,
                "subject": job.subject,
                "received_at": job.received_at,
                "sha256": job.sha256,
                "attempt_count": job.attempt_count,
                "error_kind": job.error_kind,
                "last_error": job.last_error,
                "updated_at": job.updated_at,
            }
            for job in jobs
        ],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 1 if jobs else 0


def _select_preview(args: argparse.Namespace) -> tuple[Path, dict[str, Any] | None]:
    if args.preview is not None:
        return args.preview.resolve(), None
    if args.run is not None:
        matches = list(args.run.resolve().rglob("master-sheet-preview.json"))
        if len(matches) != 1:
            raise IntakeCLIError(f"--run must contain exactly one preview; found {len(matches)}")
        return matches[0], None

    pointer_path = args.output_root.resolve() / LATEST_POINTER_NAME
    pointer = _load_json_object(pointer_path, label="latest run metadata")
    if pointer.get("status") != "ready":
        raise IntakeCLIError(
            f"latest run is not ready to apply: {pointer.get('reason') or pointer.get('status') or 'unknown status'}"
        )
    preview_value = pointer.get("preview_path")
    if not isinstance(preview_value, str) or not preview_value:
        raise IntakeCLIError("latest run metadata does not contain a preview path")
    return _absolute_path(preview_value), pointer


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise IntakeCLIError(f"{label} could not be read: {path}") from error
    except json.JSONDecodeError as error:
        raise IntakeCLIError(f"{label} is not valid JSON: {path}") from error
    if not isinstance(value, dict):
        raise IntakeCLIError(f"{label} must be a JSON object: {path}")
    return value


def _absolute_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "outlook":
            return _run_outlook(args)
        if args.command == "apply":
            return _apply_preview(args)
        if args.command == "approvals":
            return _run_approvals(args)
        if args.command == "retries":
            return _run_retries(args)
        if args.command == "failures":
            return _run_failures(args)
        if args.command in {"monitor", "monitor-status", "health"}:
            return run_monitoring_command(args)
        return _resend_review(args)
    except (IntakeCLIError, ValueError) as error:
        print(f"intake: error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
