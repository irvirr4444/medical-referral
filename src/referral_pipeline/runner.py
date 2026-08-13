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
from referral_pipeline.failure_policy import can_notify_referral_sender
from referral_pipeline.retry_policy import classify_retry
from referral_pipeline.review.workflow import create_and_send_review
from referral_pipeline.service import process_inbound_pdf
from referral_pipeline.monitoring.store import create_workflow_store
from referral_pipeline.persistence_policy import SyntheticPersistencePolicy
from referral_pipeline.stage_one.acknowledgement import send_partner_acknowledgement
from referral_pipeline.stage_one.tracker import StageOneTracker
from referral_pipeline.state import (
    STATUS_DISCOVERED,
    STATUS_PENDING_RETRY,
    AttachmentJob,
    InboxState,
)


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
    parser.add_argument(
        "--newest-only",
        action="store_true",
        help="Inspect only the newest PDF email without draining older unprocessed mail.",
    )
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
    parser.add_argument(
        "--send-review",
        action="store_true",
        help="Send the referral summary and Stage 1 partner-contact confirmation request.",
    )
    parser.add_argument(
        "--send-partner-acknowledgement",
        action="store_true",
        help="Reply once to the referral partner after Stage 1 checks complete.",
    )
    parser.add_argument(
        "--drk-duplicate-check",
        action="store_true",
        help="Run the read-only Selenium DRK duplicate gate after extraction.",
    )
    parser.add_argument("--review-recipient", help="Reviewer address; defaults to REVIEW_RECIPIENT_EMAIL.")
    parser.add_argument("--force", action="store_true", help="Reprocess an attachment even when its hash is already marked completed.")
    parser.add_argument("--output-dir", type=Path, default=Path("tmp") / "inbox-runs")
    parser.add_argument("--state-db", type=Path, default=Path("tmp") / "inbox-state.sqlite")
    parser.add_argument("--workflow-database-backend", choices=("sqlite", "supabase"))
    parser.add_argument("--workflow-sqlite-path", type=Path)
    parser.add_argument(
        "--workflow-tracking",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Persist the Stage 1 case and timeline; enabled by default.",
    )
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
        "send_partner_acknowledgement": bool(getattr(args, "send_partner_acknowledgement", False)),
        "drk_duplicate_check": bool(getattr(args, "drk_duplicate_check", False)),
        "review_recipient": args.review_recipient,
    }


def _attachments(args: argparse.Namespace, *, state: InboxState) -> list[InboundPdfAttachment]:
    if args.eml:
        return [attachment for path in args.eml for attachment in read_eml_pdf_attachments(path)]
    state.recover_expired_leases()
    return OutlookGraphClient(OutlookGraphConfig.from_environment()).list_inbox_pdf_attachments(
        max_messages=args.max_messages,
        include_attachment=None if args.force else lambda attachment: _attachment_needs_processing(state, attachment),
        scan_past_ineligible=not args.newest_only,
    )


def _attachment_needs_processing(state: InboxState, attachment: InboundPdfAttachment) -> bool:
    """Include new and unfinished jobs while excluding completed/permanent work."""
    job = state.get_job(attachment)
    return job is None or job.status in {STATUS_DISCOVERED, STATUS_PENDING_RETRY}


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
    """Resolve only an explicitly configured internal review recipient."""
    del attachment, manifest
    return (
        str(options.get("review_recipient") or "").strip()
        or str(getattr(args, "review_recipient", None) or "").strip()
        or os.getenv("REVIEW_RECIPIENT_EMAIL", "").strip()
    )


def _source_recipient(attachment: InboundPdfAttachment, options: dict[str, Any]) -> str:
    return (
        str(getattr(attachment, "sender", None) or "").strip()
        or str(options.get("source_sender") or "").strip()
    )


def process_claimed_job(
    job: AttachmentJob,
    *,
    state: InboxState,
    args: argparse.Namespace,
    graph_client: OutlookGraphClient | None,
    tracker: StageOneTracker | None = None,
) -> dict[str, Any]:
    attachment = _attachment_from_job(job)
    workflow_case = tracker.discover(attachment) if tracker is not None else None
    if tracker is not None and workflow_case is not None:
        workflow_case = tracker.processing_started(workflow_case)
    options = job.options or _processing_options(args)
    pdf_path = Path(job.artifact_path) if job.artifact_path else None
    if pdf_path is None or not pdf_path.is_file():
        return _handle_terminal_failure(
            job,
            attachment=attachment,
            state=state,
            args=args,
            graph_client=graph_client,
            error=RuntimeError("artifact PDF missing for retry"),
            elapsed_seconds=0.0,
        )

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
        if tracker is not None and workflow_case is not None:
            workflow_case = tracker.extraction_completed(workflow_case, manifest)

        if bool(options.get("drk_duplicate_check", getattr(args, "drk_duplicate_check", False))):
            _progress(args, "Checking DRK for an existing chart")
            decision = _run_drk_duplicate_check(manifest)
            manifest["drk_duplicate_status"] = decision.get("status")
            if tracker is not None and workflow_case is not None:
                tracker.drk_checked(workflow_case, decision)

        if bool(
            options.get(
                "send_partner_acknowledgement",
                getattr(args, "send_partner_acknowledgement", False),
            )
        ):
            if tracker is None or workflow_case is None:
                raise RuntimeError("partner acknowledgement requires workflow tracking")
            recipient = str(getattr(attachment, "sender", None) or "").strip()
            if not recipient:
                raise ValueError("partner acknowledgement requires the original sender address")
            if graph_client is None:
                graph_client = OutlookGraphClient(OutlookGraphConfig.from_environment())
            _progress(args, f"Sending referral acknowledgement to {recipient}")
            manifest["partner_acknowledgement"] = send_partner_acknowledgement(
                case=workflow_case,
                manifest=manifest,
                recipient=recipient,
                source_message_id=attachment.message_id,
                mailbox=OutlookReviewMailbox(graph_client),
                store=tracker.store,
                tracker=tracker,
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
                    "--send-review requires an internal --review-recipient "
                    "or REVIEW_RECIPIENT_EMAIL"
                )
            if graph_client is None:
                graph_client = OutlookGraphClient(OutlookGraphConfig.from_environment())
            _progress(args, f"Sending review request to {recipient}")
            review_result = create_and_send_review(
                manifest,
                recipient=recipient,
                write_config_path=options.get("config") or args.config,
                state_db=args.state_db,
                mailbox=OutlookReviewMailbox(graph_client),
                purpose="partner_contact",
                workflow_case_id=(workflow_case.case_id if workflow_case is not None else None),
            )
            manifest.update(review_result)
            if tracker is not None and workflow_case is not None:
                workflow_case = tracker.contact_confirmation_requested(
                    workflow_case,
                    recipient=recipient,
                    review_id=str(review_result["review_id"]),
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
            if (
                updated.status == STATUS_PENDING_RETRY
                and tracker is not None
                and workflow_case is not None
            ):
                current_case = tracker.store.workflow_case(workflow_case.case_id)
                if current_case is None or current_case.status != "completed":
                    tracker.retry_scheduled(
                        current_case or workflow_case,
                        error_kind=retry.error_kind,
                        attempt_count=updated.attempt_count,
                    )
            elif tracker is not None and workflow_case is not None:
                current_case = tracker.store.workflow_case(workflow_case.case_id)
                if current_case is None or current_case.status != "completed":
                    tracker.failed(
                        current_case or workflow_case,
                        event_type="stage_one_failed",
                        error_code=type(error).__name__,
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
        if tracker is not None and workflow_case is not None:
            current_case = tracker.store.workflow_case(workflow_case.case_id)
            if current_case is None or current_case.status != "completed":
                tracker.failed(
                    current_case or workflow_case,
                    event_type="stage_one_failed",
                    error_code=type(error).__name__,
                )
        return _handle_terminal_failure(
            job,
            attachment=attachment,
            state=state,
            args=args,
            graph_client=graph_client,
            error=error,
            elapsed_seconds=elapsed_seconds,
            artifact_path=pdf_path,
        )

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


def _handle_terminal_failure(
    job: AttachmentJob,
    *,
    attachment: InboundPdfAttachment,
    state: InboxState,
    args: argparse.Namespace,
    graph_client: OutlookGraphClient | None,
    error: Exception,
    elapsed_seconds: float,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    """Record a terminal failure and notify only for sender-actionable problems."""
    options = job.options or _processing_options(args)
    notification_error: Exception | None = None
    failure_reply_sent = False
    if bool(options.get("send_review", args.send_review)) and can_notify_referral_sender(error):
        recipient = _source_recipient(attachment, options)
        try:
            if not recipient:
                raise ValueError("original sender address is unavailable")
            client = graph_client or OutlookGraphClient(OutlookGraphConfig.from_environment())
            OutlookReviewMailbox(client).send_reply(
                source_message_id=attachment.message_id,
                recipient=recipient,
                content_type="HTML",
                html_body=(
                    "<p>We could not process the submitted referral document.</p>"
                    "<p>Please verify that the attached PDF opens correctly and resend it. "
                    "If the issue continues, contact the referral team.</p>"
                ),
                text_body=(
                    "We could not process the submitted referral document.\n\n"
                    "Please verify that the attached PDF opens correctly and resend it. "
                    "If the issue continues, contact the referral team."
                ),
            )
            failure_reply_sent = True
        except Exception as reply_error:  # noqa: BLE001 - preserve the job until a reply can be sent
            notification_error = reply_error

    if notification_error is not None:
        updated = state.mark_retryable_failure(
            job,
            error=f"{error}; failure reply also failed: {notification_error}",
            error_kind="failure_reply",
        )
    else:
        updated = state.mark_terminal_failure(job, error=str(error), error_kind="permanent")
    _progress(args, f"Failed after {elapsed_seconds:.2f}s: {attachment.filename} ({error})")
    result: dict[str, Any] = {
        "filename": attachment.filename,
        "status": updated.status,
        "error": updated.last_error,
        "error_kind": updated.error_kind,
        "attempt_count": updated.attempt_count,
        "elapsed_seconds": elapsed_seconds,
        "failure_reply_sent": failure_reply_sent,
    }
    if artifact_path is not None:
        result["artifact_path"] = str(artifact_path)
    return result


def _requested_workflow_backend(args: argparse.Namespace) -> str:
    return (
        args.workflow_database_backend or os.getenv("WORKFLOW_DATABASE_BACKEND") or "sqlite"
    ).strip().casefold()


def _workflow_tracker(
    args: argparse.Namespace,
    *,
    backend: str | None = None,
) -> StageOneTracker:
    return StageOneTracker(
        create_workflow_store(
            backend=backend or _requested_workflow_backend(args),
            sqlite_path=args.workflow_sqlite_path,
        )
    )


def _tracker_for_job(
    args: argparse.Namespace,
    job: AttachmentJob,
    policy: SyntheticPersistencePolicy,
) -> StageOneTracker | None:
    if not args.workflow_tracking:
        return None
    persisted_backend = str(job.options.get("workflow_database_backend") or "").strip()
    backend = persisted_backend or policy.stage_one_backend(
        _requested_workflow_backend(args),
        job.sha256,
    )
    return _workflow_tracker(args, backend=backend)


def _run_drk_duplicate_check(manifest: dict[str, Any]) -> dict[str, Any]:
    from drk_emr.create_patient.duplicate_check import check_duplicates_for_payload
    from drk_emr.create_patient.schema import DrkCreateDraftEnvelope

    draft_path = manifest.get("drk_draft_path")
    if not draft_path:
        raise RuntimeError("DRK duplicate check requires a canonical DRK draft")
    path = Path(draft_path)
    draft = DrkCreateDraftEnvelope.model_validate_json(path.read_text(encoding="utf-8"))
    decision = check_duplicates_for_payload(
        draft.payload,
        output_path=path.parent / "drk-duplicate-check.json",
    )
    return decision.model_dump(mode="json")


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
    persistence_policy = SyntheticPersistencePolicy.from_environment()
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
            max_jobs = max(args.max_jobs, 1)
            processed_jobs = 0
            while processed_jobs < max_jobs:
                jobs = state.claim_due(limit=1)
                if not jobs:
                    break
                processed_jobs += 1
                _progress(args, f"Claimed due job {processed_jobs}/{max_jobs}")
                summaries.append(
                    process_claimed_job(
                        jobs[0],
                        state=state,
                        args=args,
                        graph_client=graph_client,
                        tracker=_tracker_for_job(args, jobs[0], persistence_policy),
                    )
                )
            _progress(args, f"Processed {processed_jobs} due job(s)")
    else:
        _progress(args, "Reading configured email source")
        attachments = _attachments(args, state=state)
        _progress(args, f"Found {len(attachments)} genuine PDF attachment(s)")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for attachment, pdf_path in materialize_attachments(attachments, args.output_dir):
            workflow_backend = persistence_policy.stage_one_backend(
                _requested_workflow_backend(args),
                attachment.sha256,
            )
            tracker = (
                _workflow_tracker(args, backend=workflow_backend)
                if args.workflow_tracking
                else None
            )
            if workflow_backend == "sqlite" and _requested_workflow_backend(args) == "supabase":
                _progress(
                    args,
                    f"Keeping non-allowlisted referral local: {attachment.filename}",
                )
            if tracker is not None:
                tracker.discover(attachment)
            job_options = dict(options)
            job_options["workflow_database_backend"] = workflow_backend
            job_options["synthetic_persistence_allowed"] = persistence_policy.permits(
                attachment.sha256
            )
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
            summaries.append(
                process_claimed_job(
                    claimed, state=state, args=args, graph_client=graph_client, tracker=tracker
                )
            )

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
