"""Run accepted email PDFs through the referral intake pipeline."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path


# Monday remains a scripts directory, so expose it only at this orchestration
# boundary instead of coupling the Outlook adapter to its layout.
SRC_ROOT = Path(__file__).resolve().parents[1]
MONDAY_DIR = SRC_ROOT / "monday.com"
for import_path in (SRC_ROOT, MONDAY_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from Outlook.graph import OutlookGraphClient, OutlookGraphConfig
from Outlook.mail import materialize_attachments, read_eml_pdf_attachments
from Outlook.review_mail import OutlookReviewMailbox
from referral_pipeline.review.workflow import create_and_send_review
from referral_pipeline.service import process_inbound_pdf
from referral_pipeline.state import InboxState


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process only PDF attachments from local email fixtures or an Outlook inbox.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--eml", type=Path, nargs="+", help="Local .eml fixture(s); useful for synthetic replay.")
    source.add_argument("--outlook-poll", action="store_true", help="Read PDF attachments from OUTLOOK_MAILBOX via Microsoft Graph.")
    parser.add_argument("--max-messages", type=int, default=25, help="Maximum Outlook inbox messages to inspect.")
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


def _attachments(args: argparse.Namespace):
    if args.eml:
        return [attachment for path in args.eml for attachment in read_eml_pdf_attachments(path)]
    return OutlookGraphClient(OutlookGraphConfig.from_environment()).list_inbox_pdf_attachments(max_messages=args.max_messages)


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
    graph_client = OutlookGraphClient(OutlookGraphConfig.from_environment()) if args.outlook_poll or args.send_review else None
    summaries: list[dict] = []
    _progress(args, "Reading configured email source")
    attachments = _attachments(args)
    _progress(args, f"Found {len(attachments)} genuine PDF attachment(s)")
    for attachment, pdf_path in materialize_attachments(attachments, args.output_dir):
        if not args.force and state.is_completed(attachment):
            _progress(args, f"Skipping completed attachment: {attachment.filename}")
            summaries.append({"filename": attachment.filename, "status": "skipped_already_completed"})
            continue
        _progress(args, f"Processing attachment: {attachment.filename}")
        attachment_started = time.perf_counter()
        try:
            manifest = process_inbound_pdf(
                attachment,
                pdf_path=pdf_path,
                output_dir=pdf_path.parent,
                input_mode=args.input_mode,
                max_pages=args.max_pages,
                monday_mode=args.monday_mode,
                monday_records_file=args.monday_records_file,
                include_full_row=args.include_full_row,
                write_config_path=args.config,
                agency_mode=args.agency_mode,
                agency_records_file=args.agency_records_file,
                master_sheet_mode=args.master_sheet_mode,
                confirm_master_sheet_write=args.confirm_master_sheet_write,
                progress=(lambda message: _progress(args, message)) if args.verbose else None,
            )
            if args.send_review:
                recipient = args.review_recipient or os.getenv("REVIEW_RECIPIENT_EMAIL", "").strip()
                if not recipient:
                    raise ValueError("--send-review requires --review-recipient or REVIEW_RECIPIENT_EMAIL")
                if graph_client is None:
                    raise RuntimeError("Outlook Graph client was not initialized")
                _progress(args, f"Sending review request to {recipient}")
                manifest.update(
                    create_and_send_review(
                        manifest,
                        recipient=recipient,
                        write_config_path=args.config,
                        state_db=args.state_db,
                        mailbox=OutlookReviewMailbox(graph_client),
                    )
                )
        except Exception as error:
            elapsed_seconds = round(time.perf_counter() - attachment_started, 2)
            state.mark(attachment, status="failed")
            _progress(args, f"Failed after {elapsed_seconds:.2f}s: {attachment.filename} ({error})")
            summaries.append(
                {
                    "filename": attachment.filename,
                    "status": "failed",
                    "error": str(error),
                    "elapsed_seconds": elapsed_seconds,
                }
            )
            continue
        elapsed_seconds = round(time.perf_counter() - attachment_started, 2)
        manifest["elapsed_seconds"] = elapsed_seconds
        state.mark(attachment, status="completed")
        if manifest["created_item_id"]:
            _progress(args, f"Created Monday item: {manifest['created_item_id']}")
        else:
            _progress(
                args,
                f"Preview complete: outcome={manifest['outcome']}, blocked={manifest['master_sheet_blocked']}",
            )
        if manifest.get("review_id"):
            _progress(args, f"Review request sent: {manifest['review_id']}")
        _progress(args, f"Finished {attachment.filename} in {elapsed_seconds:.2f}s")
        summaries.append({"filename": attachment.filename, "status": "completed", **manifest})

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
                "results": summaries,
            },
            indent=2,
        )
    )
    return 1 if any(result["status"] == "failed" for result in summaries) else 0


def _progress(args: argparse.Namespace, message: str) -> None:
    if args.verbose:
        print(f"[intake] {message}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
