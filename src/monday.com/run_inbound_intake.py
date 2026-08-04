"""Run PDF-only local-email or Outlook inbox referrals through the intake pipeline."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from inbound_intake_pipeline import process_inbound_pdf
from inbound_mail import materialize_attachments, read_eml_pdf_attachments
from inbox_state import InboxState
from outlook_graph import OutlookGraphClient, OutlookGraphConfig


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
        default=Path(__file__).with_name("master_sheet_write_config.example.json"),
    )
    parser.add_argument("--master-sheet-mode", choices=("dry-run", "apply"), default="dry-run")
    parser.add_argument("--confirm-master-sheet-write", action="store_true")
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
    if args.master_sheet_mode == "apply" and not args.confirm_master_sheet_write:
        raise ValueError("--master-sheet-mode apply requires --confirm-master-sheet-write")
    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

    state = InboxState(args.state_db)
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
            )
        except Exception as error:
            state.mark(attachment, status="failed")
            _progress(args, f"Failed: {attachment.filename} ({error})")
            summaries.append({"filename": attachment.filename, "status": "failed", "error": str(error)})
            continue
        state.mark(attachment, status="completed")
        if manifest["created_item_id"]:
            _progress(args, f"Created Monday item: {manifest['created_item_id']}")
        else:
            _progress(
                args,
                f"Preview complete: outcome={manifest['outcome']}, blocked={manifest['master_sheet_blocked']}",
            )
        summaries.append({"filename": attachment.filename, "status": "completed", **manifest})

    summary_path = args.output_dir / "run-summary.json"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summaries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"attachment_count": len(summaries), "summary": str(summary_path), "results": summaries}, indent=2))
    return 1 if any(result["status"] == "failed" for result in summaries) else 0


def _progress(args: argparse.Namespace, message: str) -> None:
    if args.verbose:
        print(f"[intake] {message}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
