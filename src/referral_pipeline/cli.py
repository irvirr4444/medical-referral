"""Operator-friendly CLI for the referral pipeline and guarded Monday writes."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


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
from referral_pipeline.monitoring.store import (  # noqa: E402
    create_live_workflow_store,
    workflow_reads_existing_remote,
)
from referral_pipeline.api.server import main as run_intake_api  # noqa: E402
from referral_pipeline.local_launcher import run_from_cli_args  # noqa: E402
from referral_pipeline.stage_one.email_preview import render_stage_one_email_preview  # noqa: E402
from referral_pipeline.stage_one.preflight import run_stage_one_preflight  # noqa: E402


LATEST_POINTER_NAME = "latest.json"
# Temporary test toggle. Change to True when Monday duplicate checks should run.
MONDAY_DUPLICATE_CHECK_ENABLED = False


class IntakeCLIError(RuntimeError):
    pass


def _build_parser() -> argparse.ArgumentParser:
    load_dotenv()
    default_data_root = Path(os.getenv("INTAKE_DATA_ROOT", "tmp/intake-service"))
    default_output_root = default_data_root / "inbox-runs"
    default_state_db = default_data_root / "state.sqlite"
    default_workflow_sqlite_path = default_data_root / "workflow-monitor.sqlite"
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

    inbox_api = commands.add_parser(
        "inbox-api",
        help="Serve the read-only testing-infobox feed for the frontend.",
    )
    inbox_api.add_argument("--host", default="127.0.0.1")
    inbox_api.add_argument("--port", type=int, default=8787)
    inbox_api.add_argument(
        "--max-messages",
        type=int,
        default=1,
        help="Newest PDF emails exposed and processed per live test cycle.",
    )
    inbox_api.add_argument("--cache-ttl-seconds", type=int, default=30)
    inbox_api.add_argument("--workflow-database-backend", choices=("sqlite", "supabase"))
    inbox_api.add_argument(
        "--workflow-sqlite-path",
        type=Path,
        default=default_workflow_sqlite_path,
    )
    inbox_api.add_argument(
        "--data-root",
        type=Path,
        default=default_data_root,
    )
    inbox_api.add_argument("--poll-interval-seconds", type=int, default=60)
    inbox_api.add_argument("--retry-interval-seconds", type=int, default=60)
    inbox_api.add_argument("--approval-interval-seconds", type=int, default=30)
    inbox_api.add_argument("--max-retry-jobs", type=int, default=10)
    inbox_api.add_argument("--max-approval-messages", type=int, default=100)
    inbox_api.add_argument("--review-recipient", default=os.getenv("REVIEW_RECIPIENT_EMAIL"))
    inbox_api.add_argument("--partner-acknowledgement", action="store_true")
    inbox_api.add_argument("--stage-one-drk-check", action="store_true")
    inbox_api.add_argument("--start-monitor", action="store_true")

    start = commands.add_parser(
        "start",
        help="Start the local inbox API and Vite frontend for development and demo.",
    )
    start.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the UI in the default browser.",
    )
    start.add_argument(
        "--stage-one-drk-check",
        action="store_true",
        help="Enable Stage 1 DRK duplicate checking for this run only.",
    )
    start.add_argument(
        "--partner-acknowledgement",
        action="store_true",
        help="Send partner acknowledgement emails for this run only.",
    )
    start.add_argument(
        "--workflow-database-backend",
        choices=("sqlite", "supabase"),
        help="Workflow store for this run. Defaults to the existing routing policy.",
    )
    start.add_argument(
        "--data-root",
        type=Path,
        help="Intake data root. Defaults to INTAKE_DATA_ROOT, or tmp/intake-service if unset.",
    )
    start.add_argument("--api-port", type=int, default=8787, help="Inbox API port (default 8787).")
    start.add_argument(
        "--frontend-port",
        type=int,
        default=5173,
        help="Vite UI port (default 5173).",
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
    outlook.add_argument("--output-root", type=Path, default=default_output_root)
    outlook.add_argument("--state-db", type=Path, default=default_state_db)
    outlook.add_argument("--force", action="store_true", help="Reprocess eligible PDFs even when already recorded.")
    outlook.add_argument("--quiet", action="store_true", help="Suppress progress logs while retaining the final summary.")
    outlook.add_argument(
        "--send-review",
        action="store_true",
        help="Email the referral summary and request confirmation of partner outreach.",
    )
    outlook.add_argument(
        "--send-partner-acknowledgement",
        action="store_true",
        help="Reply once to the referral source after the Stage 1 checks finish.",
    )
    outlook.add_argument(
        "--drk-duplicate-check",
        action="store_true",
        help="Run the read-only DRK duplicate check after extraction.",
    )
    outlook.add_argument("--workflow-database-backend", choices=("sqlite", "supabase"))
    outlook.add_argument(
        "--workflow-sqlite-path",
        type=Path,
        default=default_workflow_sqlite_path,
    )
    outlook.add_argument(
        "--review-recipient",
        help="Internal reviewer responsible for confirming referral-partner outreach.",
    )

    apply = commands.add_parser(
        "apply",
        help="Apply the exact preview from the latest successful dry run.",
    )
    source = apply.add_mutually_exclusive_group()
    source.add_argument("--preview", type=Path, help="Apply a specific master-sheet-preview.json file.")
    source.add_argument("--run", type=Path, help="Apply the only preview inside a specific run directory.")
    apply.add_argument("--output-root", type=Path, default=default_output_root)
    apply.add_argument("--confirm-master-sheet-write", action="store_true", required=True)

    approvals = commands.add_parser(
        "approvals",
        help="Read review replies and optionally dry-run or execute confirmed Monday creates.",
    )
    mode = approvals.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate confirmed Supabase JSON and destination drafts without writing Monday or DRK.",
    )
    mode.add_argument(
        "--execute",
        action="store_true",
        help="Create the Monday item once for each confirmed review; DRK remains a pending draft.",
    )
    approvals.add_argument("--max-messages", type=int, default=25)
    approvals.add_argument("--output-root", type=Path, default=default_output_root)
    approvals.add_argument("--state-db", type=Path, default=default_state_db)
    approvals.add_argument("--workflow-database-backend", choices=("sqlite", "supabase"))
    approvals.add_argument(
        "--workflow-sqlite-path",
        type=Path,
        default=default_workflow_sqlite_path,
    )

    review_send = commands.add_parser(
        "review-send",
        help="Send a review from an existing completed extraction without rerunning the LLM.",
    )
    review_send.add_argument("--run", type=Path, required=True, help="Existing timestamped intake run directory.")
    review_send.add_argument(
        "--review-recipient",
        help="Internal reviewer email; defaults to REVIEW_RECIPIENT_EMAIL.",
    )
    review_send.add_argument(
        "--config",
        type=Path,
        default=MONDAY_DIR / "master_sheet_write_config.example.json",
    )
    review_send.add_argument("--state-db", type=Path)

    doctor = commands.add_parser(
        "stage-one-doctor",
        help="Validate Stage 1 configuration without changing Outlook, Monday, DRK, or Supabase.",
    )
    doctor.add_argument(
        "--live",
        action="store_true",
        help="Also run read-only Outlook, Monday, and Supabase connectivity checks.",
    )

    email_preview = commands.add_parser(
        "stage-one-email-preview",
        help="Render Stage 1 internal and partner emails without sending them.",
    )
    email_preview.add_argument("--run", type=Path, required=True)
    email_preview.add_argument(
        "--review-recipient",
        default=os.getenv("REVIEW_RECIPIENT_EMAIL"),
        help="Internal intake-team reviewer; defaults to REVIEW_RECIPIENT_EMAIL.",
    )
    email_preview.add_argument(
        "--config",
        type=Path,
        default=MONDAY_DIR / "master_sheet_write_config.example.json",
    )

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
    retries.add_argument("--output-root", type=Path, default=default_output_root)
    retries.add_argument("--state-db", type=Path, default=default_state_db)
    retries.add_argument("--workflow-database-backend", choices=("sqlite", "supabase"))
    retries.add_argument(
        "--workflow-sqlite-path",
        type=Path,
        default=default_workflow_sqlite_path,
    )
    retries.add_argument("--quiet", action="store_true")
    retries.add_argument("--send-review", action="store_true", default=True)
    retries.add_argument("--no-send-review", action="store_false", dest="send_review")
    retries.add_argument("--review-recipient", help="Reviewer email; defaults to REVIEW_RECIPIENT_EMAIL.")
    retries.add_argument(
        "--retry-step",
        choices=("all", "extraction", "monday", "drk", "acknowledgement", "workflow"),
        default="all",
    )
    retries.add_argument(
        "--refresh-config",
        action="store_true",
        help="Replace stored job options with the current retries flags before processing.",
    )
    retries.add_argument("--send-partner-acknowledgement", action="store_true")
    retries.add_argument("--drk-duplicate-check", action="store_true")

    failures = commands.add_parser(
        "failures",
        help="List permanent intake failures and optionally requeue one by sha256.",
    )
    failures.add_argument("--output-root", type=Path, default=default_output_root)
    failures.add_argument("--state-db", type=Path, default=default_state_db)
    failures.add_argument("--limit", type=int, default=50, help="Maximum failed jobs to list.")
    failures.add_argument(
        "--requeue",
        metavar="SHA256",
        help="Move one permanent failure back onto the discovery queue for a deliberate retry.",
    )
    failures.add_argument(
        "--refresh-config",
        action="store_true",
        help="When requeuing, replace stored job options with current intake defaults.",
    )

    handoff_preview = commands.add_parser(
        "handoff-preview",
        help="Preview one Stage 3 operation without consuming it or writing externally.",
    )
    handoff_preview.add_argument("--case-id", required=True)
    handoff_preview.add_argument(
        "--operation-type",
        required=True,
        choices=("notify-assigned-case-manager", "create-monday-record", "prefill-drk-chart"),
    )
    handoff_preview.add_argument("--output-root", type=Path, default=default_output_root)
    handoff_preview.add_argument("--workflow-database-backend", choices=("sqlite", "supabase"))
    handoff_preview.add_argument("--workflow-sqlite-path", type=Path, default=default_workflow_sqlite_path)

    handoff_execute = commands.add_parser(
        "handoff-execute",
        help="Execute one Stage 3 operation after explicit confirmation. Monday requires --confirm-monday-write.",
    )
    handoff_execute.add_argument("--case-id", required=True)
    handoff_execute.add_argument(
        "--operation-type",
        required=True,
        choices=("notify-assigned-case-manager", "create-monday-record", "prefill-drk-chart"),
    )
    handoff_execute.add_argument("--confirm", action="store_true", required=True)
    handoff_execute.add_argument(
        "--confirm-monday-write",
        action="store_true",
        help="Required for create-monday-record. Default remains dry-run/preview.",
    )
    handoff_execute.add_argument("--operator-retry", action="store_true")
    handoff_execute.add_argument("--output-root", type=Path, default=default_output_root)
    handoff_execute.add_argument("--workflow-database-backend", choices=("sqlite", "supabase"))
    handoff_execute.add_argument("--workflow-sqlite-path", type=Path, default=default_workflow_sqlite_path)

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
    if args.send_partner_acknowledgement:
        delegated.append("--send-partner-acknowledgement")
    if args.drk_duplicate_check:
        delegated.append("--drk-duplicate-check")
    if args.workflow_database_backend:
        delegated.extend(("--workflow-database-backend", args.workflow_database_backend))
    if args.workflow_sqlite_path is not None:
        delegated.extend(
            ("--workflow-sqlite-path", str(args.workflow_sqlite_path.resolve()))
        )

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
            "review_purpose": result.get("review_purpose"),
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
        if pointer.get("review_purpose") == "partner_contact":
            print("[intake] next: contact the referral partner, then reply Confirm to the email")
            print("[intake] this confirmation completes Referral Intake step 5 only")
        else:
            print("[intake] next: reply to the review email, then check approvals")
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
    mode = "execute" if args.execute else ("dry_run" if args.dry_run else "check_only")
    print(f"[review] checking {args.max_messages} recent inbox messages")
    print(f"[review] mode: {mode}")
    print(f"[review] writes attempted: {'yes' if args.execute else 'no'}")
    workflow_backend = (
        args.workflow_database_backend
        or os.getenv("WORKFLOW_DATABASE_BACKEND")
        or "sqlite"
    ).strip().casefold()
    result = ApprovalProcessor(
        state_db=state_db,
        mailbox=mailbox,
        allow_supabase_store=workflow_reads_existing_remote(backend=workflow_backend),
        workflow_store=create_live_workflow_store(
            sqlite_path=args.workflow_sqlite_path,
            backend=workflow_backend,
        ),
    ).poll(
        max_messages=args.max_messages,
        execute=args.execute,
        dry_run=args.dry_run,
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
    if args.workflow_database_backend:
        delegated.extend(("--workflow-database-backend", args.workflow_database_backend))
    delegated.extend(
        ("--workflow-sqlite-path", str(args.workflow_sqlite_path.resolve()))
    )
    if getattr(args, "retry_step", None) and args.retry_step != "all":
        delegated.extend(("--retry-step", args.retry_step))
    if getattr(args, "refresh_config", False):
        delegated.append("--refresh-config")
    if getattr(args, "send_partner_acknowledgement", False):
        delegated.append("--send-partner-acknowledgement")
    if getattr(args, "drk_duplicate_check", False):
        delegated.append("--drk-duplicate-check")

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


def _run_stage_one_doctor(args: argparse.Namespace) -> int:
    result = run_stage_one_preflight(live=args.live)
    print(json.dumps(result, indent=2))
    return 0 if result["ready"] else 1


def _run_stage_one_email_preview(args: argparse.Namespace) -> int:
    result = render_stage_one_email_preview(
        args.run,
        reviewer=(args.review_recipient or ""),
        write_config_path=args.config,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
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
        if args.refresh_config:
            job = state.refresh_options(
                sha256=args.requeue,
                options={
                    "input_mode": "image",
                    "max_pages": None,
                    "monday_mode": "live-readonly" if MONDAY_DUPLICATE_CHECK_ENABLED else "disabled",
                    "monday_records_file": None,
                    "include_full_row": False,
                    "agency_mode": "live-readonly",
                    "agency_records_file": None,
                    "config": None,
                    "master_sheet_mode": "dry-run",
                    "confirm_master_sheet_write": False,
                    "send_review": True,
                    "send_partner_acknowledgement": False,
                    "drk_duplicate_check": False,
                    "review_recipient": os.getenv("REVIEW_RECIPIENT_EMAIL"),
                },
            )
        print(
            json.dumps(
                {
                    "status": "requeued",
                    "sha256": job.sha256,
                    "filename": job.filename,
                    "subject": job.subject,
                    "config_refreshed": bool(args.refresh_config),
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


def _run_handoff(args: argparse.Namespace, *, preview: bool) -> int:
    from referral_pipeline.workflow import WorkflowExecutionService

    backend = (
        args.workflow_database_backend
        or os.getenv("WORKFLOW_DATABASE_BACKEND")
        or "sqlite"
    ).strip().casefold()
    store = create_live_workflow_store(
        sqlite_path=args.workflow_sqlite_path,
        backend=backend,
    )
    service = WorkflowExecutionService(store)
    mailbox = None
    if args.operation_type == "notify-assigned-case-manager" and not preview:
        mailbox = OutlookReviewMailbox(OutlookGraphClient(OutlookGraphConfig.from_environment()))
    if preview:
        result = service.preview_handoff_operation(args.case_id, args.operation_type, mailbox=mailbox)
    else:
        if args.operation_type == "create-monday-record" and not args.confirm_monday_write:
            raise IntakeCLIError("create-monday-record requires --confirm-monday-write")
        result = service.execute_handoff_operation(
            args.case_id,
            args.operation_type,
            execute=True,
            confirm_monday_write=bool(args.confirm_monday_write),
            mailbox=mailbox,
            operator_retry=bool(getattr(args, "operator_retry", False)),
        )
    print(json.dumps(result, indent=2, default=str))
    status = result.get("status")
    if result.get("mode") == "preview" or status in {"ready", "succeeded", "blocked"}:
        return 0
    return 1


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
        if args.command == "start":
            return run_from_cli_args(args)
        if args.command == "inbox-api":
            api_args = [
                "--host",
                args.host,
                "--port",
                str(args.port),
                "--max-messages",
                str(args.max_messages),
                "--cache-ttl-seconds",
                str(args.cache_ttl_seconds),
            ]
            if args.workflow_database_backend:
                api_args.extend(("--workflow-database-backend", args.workflow_database_backend))
            if args.workflow_sqlite_path:
                api_args.extend(("--workflow-sqlite-path", str(args.workflow_sqlite_path.resolve())))
            api_args.extend(
                (
                    "--data-root",
                    str(args.data_root.resolve()),
                    "--poll-interval-seconds",
                    str(args.poll_interval_seconds),
                    "--retry-interval-seconds",
                    str(args.retry_interval_seconds),
                    "--approval-interval-seconds",
                    str(args.approval_interval_seconds),
                    "--max-retry-jobs",
                    str(args.max_retry_jobs),
                    "--max-approval-messages",
                    str(args.max_approval_messages),
                )
            )
            if args.partner_acknowledgement:
                api_args.append("--partner-acknowledgement")
            if args.stage_one_drk_check:
                api_args.append("--stage-one-drk-check")
            if args.start_monitor:
                api_args.append("--start-monitor")
            if args.review_recipient:
                api_args.extend(("--review-recipient", args.review_recipient))
            return run_intake_api(api_args)
        if args.command == "apply":
            return _apply_preview(args)
        if args.command == "approvals":
            return _run_approvals(args)
        if args.command == "retries":
            return _run_retries(args)
        if args.command == "failures":
            return _run_failures(args)
        if args.command == "handoff-preview":
            return _run_handoff(args, preview=True)
        if args.command == "handoff-execute":
            return _run_handoff(args, preview=False)
        if args.command == "stage-one-doctor":
            return _run_stage_one_doctor(args)
        if args.command == "stage-one-email-preview":
            return _run_stage_one_email_preview(args)
        if args.command in {"monitor", "monitor-status", "health"}:
            return run_monitoring_command(args)
        return _resend_review(args)
    except (IntakeCLIError, ValueError) as error:
        print(f"intake: error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
