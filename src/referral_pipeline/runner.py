"""Run accepted email PDFs through the referral intake pipeline."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any


# Monday remains a scripts directory, so expose it only at this orchestration
# boundary instead of coupling the Outlook adapter to its layout.
SRC_ROOT = Path(__file__).resolve().parents[1]
MONDAY_DIR = SRC_ROOT / "monday.com"
for import_path in (SRC_ROOT, MONDAY_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from Outlook.graph import OutlookGraphClient, OutlookGraphConfig
from Outlook.mail import InboundPdfAttachment, materialize_attachments, read_eml_pdf_attachments
from Outlook.review_mail import OutlookReviewMailbox
from referral_pipeline.retry_policy import classify_retry
from referral_pipeline.review.workflow import create_and_send_review
from referral_pipeline.service import process_inbound_pdf
from referral_pipeline.state import AttachmentJob, InboxState


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process only PDF attachments from local email fixtures or an Outlook inbox.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--eml", type=Path, nargs="+", help="Local .eml fixture(s); useful for synthetic replay.")
    source.add_argument(
        "--outlook-poll",
        action="store_true",
        help="Read PDF attachments from Outlook threads the configured mailbox has not replied to.",
    )
    source.add_argument(
        "--process-retries",
        action="store_true",
        help="Claim and process due durable retry jobs without polling Outlook.",
    )
    parser.add_argument("--max-messages", type=int, default=25, help="Maximum Outlook inbox messages to inspect.")
    parser.add_argument("--max-jobs", type=int, default=25, help="Maximum due retry jobs to claim in one run.")
    parser.add_argument("--input-mode", choices=("auto", "text", "image", "hybrid"), default="image")
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--monday-mode", choices=("disabled", "snapshot", "live-readonly"), default="disabled")
    parser.add_argument("--monday-records-file", type=Path)
    parser.add_argument("--include-full-row", action="store_true")
    parser.add_argument("--agency-mode", choices=("disabled", "snapshot", "live-readonly"), default="disabled")
    parser.add_argument("--agency-records-file", type=Path)
    parser.add_argument(
        "--config",
        type=Path,
        default=MONDAY_DIR / "master_sheet_write_config.example.json",
    )
    parser.add_argument("--master-sheet-mode", choices=("dry-run", "apply"), default="dry-run")
    parser.add_argument("--confirm-master-sheet-write", action="store_true")
    parser.add_argument("--send-review", action="store_true", help="Send an approval email after building the artifacts.")
    parser.add_argument("--review-recipient", help="Reviewer address; defaults to REVIEW_RECIPIENT_EMAIL.")
    parser.add_argument("--force", action="store_true", help="Reprocess an attachment even when its hash is already marked completed.")
    parser.add_argument("--output-dir", type=Path, default=Path("tmp") / "inbox-runs")
    parser.add_argument("--state-db", type=Path, default=Path("tmp") / "inbox-state.sqlite")
    parser.add_argument("--verbose", action="store_true", help="Print pipeline progress and enable extractor INFO logs.")
    return parser.parse_args(argv)


def _processing_options(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "input_mode": args.input_mode,
        "max_pages": args.max_pages,
        "monday_mode": args.monday_mode,
        "monday_records_file": str(args.monday_records_file) if args.monday_records_file else None,
        "include_full_row": bool(args.include_full_row),
        "agency_mode": args.agency_mode,
        "agency_records_file": str(args.agency_records_file) if args.agency_records_file else None,
        "config": str(args.config),
        "master_sheet_mode": args.master_sheet_mode,
        "confirm_master_sheet_write": bool(args.confirm_master_sheet_write),
        "send_review": bool(args.send_review),
        "review_recipient": args.review_recipient,
    }


def _attachments(args: argparse.Namespace, *, state: InboxState) -> list[InboundPdfAttachment]:
    if args.eml:
        return [attachment for path in args.eml for attachment in read_eml_pdf_attachments(path)]
    return OutlookGraphClient(OutlookGraphConfig.from_environment()).list_inbox_pdf_attachments(
        max_messages=args.max_messages,
        include_attachment=None if args.force else lambda attachment: state.get_job(attachment) is None,
    )


def _attachment_from_job(job: AttachmentJob) -> InboundPdfAttachment:
    content = b"%PDF-1.4\n"
    if job.artifact_path:
        path = Path(job.artifact_path)
        if path.is_file():
            content = path.read_bytes()
    options = job.options
    return InboundPdfAttachment(
        source=job.source,
        message_id=job.message_id,
        attachment_id=job.attachment_id,
        filename=job.filename or "referral.pdf",
        content=content,
        received_at=job.received_at,
        subject=job.subject,
        sender=str(options.get("source_sender") or "").strip() or None,
        conversation_id=str(options.get("source_conversation_id") or "").strip() or None,
    )


def _review_recipient(
    *,
    options: dict[str, Any],
    args: argparse.Namespace,
    attachment: InboundPdfAttachment,
    manifest: dict[str, Any],
) -> str:
    """Prefer an explicit override; otherwise reply to the original sender."""
    return (
        str(options.get("review_recipient") or "").strip()
        or str(getattr(args, "review_recipient", None) or "").strip()
        or str(manifest.get("source_sender") or "").strip()
        or str(getattr(attachment, "sender", None) or "").strip()
        or str(options.get("source_sender") or "").strip()
        or os.getenv("REVIEW_RECIPIENT_EMAIL", "").strip()
    )


def process_claimed_job(
    job: AttachmentJob,
    *,
    state: InboxState,
    args: argparse.Namespace,
    graph_client: OutlookGraphClient | None,
) -> dict[str, Any]:
    attachment = _attachment_from_job(job)
    options = job.options or _processing_options(args)
    pdf_path = Path(job.artifact_path) if job.artifact_path else None
    if pdf_path is None or not pdf_path.is_file():
        updated = state.mark_terminal_failure(job, error="artifact PDF missing for retry", error_kind="permanent")
        return {
            "filename": attachment.filename,
            "status": updated.status,
            "error": updated.last_error,
            "attempt_count": updated.attempt_count,
        }

    output_dir = pdf_path.parent
    attachment_started = time.perf_counter()
    try:
        _progress(args, f"Processing attachment: {attachment.filename} (attempt {job.attempt_count})")
        manifest = process_inbound_pdf(
            attachment,
            pdf_path=pdf_path,
            output_dir=output_dir,
            input_mode=str(options.get("input_mode") or args.input_mode),
            max_pages=options.get("max_pages", args.max_pages),
            monday_mode=str(options.get("monday_mode") or args.monday_mode),
            monday_records_file=options.get("monday_records_file") or args.monday_records_file,
            include_full_row=bool(options.get("include_full_row", args.include_full_row)),
            write_config_path=options.get("config") or args.config,
            agency_mode=str(options.get("agency_mode") or args.agency_mode),
            agency_records_file=options.get("agency_records_file") or args.agency_records_file,
            master_sheet_mode=str(options.get("master_sheet_mode") or args.master_sheet_mode),
            confirm_master_sheet_write=bool(
                options.get("confirm_master_sheet_write", args.confirm_master_sheet_write)
            ),
            progress=(lambda message: _progress(args, message)) if args.verbose else None,
        )
        send_review = bool(options.get("send_review", args.send_review))
        if send_review:
            recipient = _review_recipient(
                options=options,
                args=args,
                attachment=attachment,
                manifest=manifest,
            )
            if not recipient:
                raise ValueError(
                    "--send-review requires the original sender address, "
                    "--review-recipient, or REVIEW_RECIPIENT_EMAIL"
                )
            if graph_client is None:
                graph_client = OutlookGraphClient(OutlookGraphConfig.from_environment())
            _progress(args, f"Sending review request to {recipient}")
            manifest.update(
                create_and_send_review(
                    manifest,
                    recipient=recipient,
                    write_config_path=options.get("config") or args.config,
                    state_db=args.state_db,
                    mailbox=OutlookReviewMailbox(graph_client),
                )
            )
    except Exception as error:
        elapsed_seconds = round(time.perf_counter() - attachment_started, 2)
        retry = classify_retry(error)
        if retry is not None:
            updated = state.mark_retryable_failure(
                job,
                error=str(error),
                error_kind=retry.error_kind,
            )
            _progress(
                args,
                f"Deferred after {elapsed_seconds:.2f}s: {attachment.filename} "
                f"(next_attempt_at={updated.next_attempt_at})",
            )
            return {
                "filename": attachment.filename,
                "status": updated.status,
                "error": updated.last_error,
                "error_kind": updated.error_kind,
                "attempt_count": updated.attempt_count,
                "next_attempt_at": updated.next_attempt_at,
                "elapsed_seconds": elapsed_seconds,
                "artifact_path": str(pdf_path),
            }
        updated = state.mark_terminal_failure(job, error=str(error), error_kind="permanent")
        _progress(args, f"Failed after {elapsed_seconds:.2f}s: {attachment.filename} ({error})")
        return {
            "filename": attachment.filename,
            "status": updated.status,
            "error": updated.last_error,
            "error_kind": updated.error_kind,
            "attempt_count": updated.attempt_count,
            "elapsed_seconds": elapsed_seconds,
            "artifact_path": str(pdf_path),
        }

    elapsed_seconds = round(time.perf_counter() - attachment_started, 2)
    manifest["elapsed_seconds"] = elapsed_seconds
    manifest["attempt_count"] = job.attempt_count
    state.mark_completed(job)
    if manifest.get("created_item_id"):
        _progress(args, f"Created Monday item: {manifest['created_item_id']}")
    else:
        _progress(
            args,
            f"Preview complete: outcome={manifest['outcome']}, blocked={manifest['master_sheet_blocked']}",
        )
    if manifest.get("review_id"):
        _progress(args, f"Review request sent: {manifest['review_id']}")
    _progress(args, f"Finished {attachment.filename} in {elapsed_seconds:.2f}s")
    return {"filename": attachment.filename, "status": "completed", **manifest}


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    run_started = time.perf_counter()
    if args.master_sheet_mode == "apply" and not args.confirm_master_sheet_write:
        raise ValueError("--master-sheet-mode apply requires --confirm-master-sheet-write")
    if args.send_review and args.master_sheet_mode == "apply":
        raise ValueError("--send-review cannot be combined with an immediate Master Sheet apply")
    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

    state = InboxState(args.state_db)
    needs_graph = bool(args.outlook_poll or args.send_review or args.process_retries)
    graph_client = OutlookGraphClient(OutlookGraphConfig.from_environment()) if needs_graph else None
    summaries: list[dict] = []
    options = _processing_options(args)

    if args.process_retries:
        _progress(args, "Claiming due retry jobs")
        if not state.circuit_allows_work():
            _progress(args, "Anthropic circuit open; deferring retry work")
            summaries.append({"status": "circuit_open", "pending_retry_count": state.pending_retry_count()})
        else:
            jobs = state.claim_due(limit=max(args.max_jobs, 1))
            _progress(args, f"Claimed {len(jobs)} due job(s)")
            for job in jobs:
                summaries.append(process_claimed_job(job, state=state, args=args, graph_client=graph_client))
    else:
        _progress(args, "Reading configured email source")
        attachments = _attachments(args, state=state)
        _progress(args, f"Found {len(attachments)} genuine PDF attachment(s)")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for attachment, pdf_path in materialize_attachments(attachments, args.output_dir):
            job_options = dict(options)
            if attachment.sender:
                job_options["source_sender"] = attachment.sender
            if attachment.conversation_id:
                job_options["source_conversation_id"] = attachment.conversation_id
            job = state.enqueue(
                attachment,
                artifact_path=pdf_path,
                options=job_options,
                force=args.force,
            )
            if job is None:
                _progress(args, f"Skipping completed attachment: {attachment.filename}")
                summaries.append({"filename": attachment.filename, "status": "skipped_already_completed"})
                continue
            if job.status == "failed":
                _progress(
                    args,
                    f"Skipping permanent failure: {attachment.filename} "
                    f"(use failures --requeue {attachment.sha256} to retry)",
                )
                summaries.append(
                    {
                        "filename": attachment.filename,
                        "status": "skipped_already_failed",
                        "attachment_sha256": attachment.sha256,
                        "error": job.last_error,
                        "error_kind": job.error_kind,
                        "attempt_count": job.attempt_count,
                    }
                )
                continue
            claimed = state.claim_job(attachment)
            if claimed is None:
                if not state.circuit_allows_work():
                    _progress(args, f"Deferred by Anthropic circuit: {attachment.filename}")
                    summaries.append(
                        {
                            "filename": attachment.filename,
                            "status": "circuit_open",
                            "attachment_sha256": attachment.sha256,
                        }
                    )
                    continue
                current = state.get_job(attachment)
                if current and current.status == "pending_retry":
                    _progress(
                        args,
                        f"Already scheduled for retry: {attachment.filename} "
                        f"(next_attempt_at={current.next_attempt_at})",
                    )
                    summaries.append(
                        {
                            "filename": attachment.filename,
                            "status": current.status,
                            "next_attempt_at": current.next_attempt_at,
                            "attempt_count": current.attempt_count,
                            "attachment_sha256": attachment.sha256,
                        }
                    )
                    continue
                _progress(args, f"Queued but not claimed: {attachment.filename}")
                summaries.append({"filename": attachment.filename, "status": "queued"})
                continue
            summaries.append(process_claimed_job(claimed, state=state, args=args, graph_client=graph_client))

    summary_path = args.output_dir / "run-summary.json"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summaries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    total_elapsed_seconds = round(time.perf_counter() - run_started, 2)
    _progress(args, f"Run completed in {total_elapsed_seconds:.2f}s")
    print(
        json.dumps(
            {
                "attachment_count": len(summaries),
                "elapsed_seconds": total_elapsed_seconds,
                "summary": str(summary_path),
                "circuit_state": state.circuit_state(),
                "pending_retry_count": state.pending_retry_count(),
                "failed_count": state.failed_count(),
                "results": summaries,
            },
            indent=2,
        )
    )
    failed = any(result.get("status") == "failed" for result in summaries)
    return 1 if failed else 0


def _progress(args: argparse.Namespace, message: str) -> None:
    if args.verbose:
        print(f"[intake] {message}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
