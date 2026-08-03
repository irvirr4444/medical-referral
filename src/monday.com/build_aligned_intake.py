"""Build one PDF-derived bundle for parallel Monday and DRK handoffs.

The default is preview-only. Monday creation requires two explicit flags. DRK
patient creation is intentionally not implemented here because the current DRK
automation is fill-only and cannot safely submit a patient.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from intake_duplicate_check import check_duplicates_disabled, check_duplicates_from_snapshot, check_duplicates_live
from intake_extractor.aligned_intake import AlignedIntakeBundle, build_aligned_intake_bundle
from intake_extractor.drk_pdf import extract_drk_from_pdf
from intake_extractor.drk_pdf_schema import DrkPdfExtraction
from intake_plan import build_intake_plan
from master_sheet_agency_lookup import find_agency_matches_from_snapshot, find_agency_matches_live
from master_sheet_writer import (
    apply_master_sheet_create,
    build_master_sheet_create_preview,
    load_master_sheet_write_config,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create aligned Monday and DRK drafts from one canonical PDF extraction."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--pdf", type=Path, help="Extract a PDF with the high-accuracy Anthropic pipeline.")
    source.add_argument("--extraction-json", type=Path, help="Existing drk_pdf _extraction.json.")
    parser.add_argument(
        "--source-pdf",
        type=Path,
        help="Original PDF required with --extraction-json for hashing and source provenance.",
    )
    parser.add_argument("--sent-by", help="Info-box agent/source value preserved for the Master Sheet Sent By column.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("master_sheet_write_config.example.json"),
    )
    parser.add_argument("--monday-mode", choices=("disabled", "snapshot", "live-readonly"), default="disabled")
    parser.add_argument("--monday-records-file", type=Path)
    parser.add_argument("--include-full-row", action="store_true")
    parser.add_argument("--agency-mode", choices=("disabled", "snapshot", "live-readonly"), default="disabled")
    parser.add_argument("--agency-records-file", type=Path)
    parser.add_argument(
        "--pdf-transport",
        choices=("inline", "files-api"),
        default=os.getenv("ANTHROPIC_PDF_TRANSPORT", "files-api"),
        help="PDF delivery method (default: files-api; use inline as the fallback)",
    )
    parser.add_argument("--passes", type=int, choices=(1, 3), default=3)
    parser.add_argument("--apply-master-sheet", action="store_true")
    parser.add_argument("--confirm-master-sheet-write", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path("tmp") / "aligned-intake")
    return parser.parse_args(argv)


def _load_extraction(args: argparse.Namespace) -> tuple[DrkPdfExtraction, Path]:
    if args.pdf is not None:
        extraction = extract_drk_from_pdf(
            args.pdf,
            passes=args.passes,
            pdf_transport=args.pdf_transport,
            progress=lambda message: print(message, flush=True),
        )
        return extraction, args.pdf
    if args.source_pdf is None:
        raise ValueError("--source-pdf is required with --extraction-json")
    try:
        payload = json.loads(args.extraction_json.read_text(encoding="utf-8-sig"))
        return DrkPdfExtraction.model_validate(payload), args.source_pdf
    except OSError as exc:
        raise RuntimeError(f"Could not read extraction JSON: {args.extraction_json}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Extraction JSON is invalid: {args.extraction_json}") from exc


def _duplicate_check(args: argparse.Namespace, bundle: AlignedIntakeBundle):
    referral = bundle.master_sheet_referral
    if args.monday_mode == "disabled":
        return check_duplicates_disabled()
    if args.monday_mode == "snapshot":
        if args.monday_records_file is None:
            raise ValueError("--monday-records-file is required for snapshot duplicate checking")
        return check_duplicates_from_snapshot(
            referral,
            records_file=args.monday_records_file,
            include_full_row=args.include_full_row,
        )
    return check_duplicates_live(referral, include_full_row=args.include_full_row)


def _agency_matches(args: argparse.Namespace, facility: str | None, *, accounts_board_id: str | None):
    if args.agency_mode == "disabled" or not facility:
        return []
    if args.agency_mode == "snapshot":
        if args.agency_records_file is None:
            raise ValueError("--agency-records-file is required for snapshot agency matching")
        return find_agency_matches_from_snapshot(facility, records_file=args.agency_records_file)
    if not accounts_board_id:
        raise ValueError("Master Sheet config has no Accounts board ID for live agency matching")
    return find_agency_matches_live(facility, board_id=accounts_board_id)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    os.chmod(path, 0o600)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.apply_master_sheet and not args.confirm_master_sheet_write:
        raise ValueError("--apply-master-sheet requires --confirm-master-sheet-write")

    extraction, source_pdf = _load_extraction(args)
    source_metadata = {"sent_by": args.sent_by} if args.sent_by else {}
    bundle = build_aligned_intake_bundle(
        extraction,
        source_pdf,
        source_metadata=source_metadata,
    )
    duplicate = _duplicate_check(args, bundle)
    plan = build_intake_plan(bundle.master_sheet_referral, duplicate_check=duplicate)
    plan["source"] = {
        "kind": "aligned_pdf_extraction",
        "path": str(source_pdf),
        "attachment_sha256": bundle.source.file_sha256,
        "sent_by": args.sent_by,
        "correlation_id": bundle.correlation_id,
    }
    plan["aligned_intake"] = {
        "version": bundle.version,
        "correlation_id": bundle.correlation_id,
        "drk_fill_ready": bundle.readiness.drk_fill_ready,
        "drk_blockers": bundle.readiness.drk_blockers,
    }
    if args.apply_master_sheet:
        plan["write_safety"] = {
            "monday_writes_enabled": True,
            "drk_writes_enabled": False,
            "message": "Monday create explicitly authorized; DRK remains a fill-only draft.",
        }

    config = load_master_sheet_write_config(args.config)
    agency_matches = _agency_matches(
        args,
        bundle.master_sheet_referral.referring_facility,
        accounts_board_id=config.accounts_board_id,
    )
    current_hh_matches = _agency_matches(
        args,
        bundle.master_sheet_referral.current_home_health_or_hospice,
        accounts_board_id=config.accounts_board_id,
    )
    preview = build_master_sheet_create_preview(
        plan,
        config=config,
        agency_matches=agency_matches,
        current_hh_matches=current_hh_matches,
    )
    preview["mode"] = "apply" if args.apply_master_sheet else "dry-run"
    preview["correlation_id"] = bundle.correlation_id

    output = args.output_dir / bundle.correlation_id
    bundle_path = output / "aligned-intake.json"
    plan_path = output / "intake-plan.json"
    master_preview_path = output / "master-sheet-preview.json"
    drk_draft_path = output / "drk-create-draft.json"
    _write_json(bundle_path, bundle.model_dump(mode="json"))
    _write_json(plan_path, plan)
    _write_json(master_preview_path, preview)
    _write_json(drk_draft_path, bundle.drk_create_draft.model_dump(mode="json"))

    applied = None
    if args.apply_master_sheet:
        applied = apply_master_sheet_create(preview)
        _write_json(output / "master-sheet-apply-result.json", applied)

    handoff_state = {
        "version": 1,
        "correlation_id": bundle.correlation_id,
        "source_sha256": bundle.source.file_sha256,
        "handoff_mode": "parallel_after_human_approval",
        "targets": ["monday_master_sheet", "drk_patient"],
        "monday": {
            "status": "created" if applied else "blocked" if preview["blocked"] else "preview_ready",
            "item_id": None if applied is None else applied["item"]["id"],
            "blocked": preview["blocked"],
            "blockers": preview["blockers"],
        },
        "drk": {
            "status": "draft_ready" if bundle.drk_create_draft.ready_for_fill else "blocked",
            "patient_id": None,
            "write_supported": False,
            "blockers": bundle.drk_create_draft.blockers,
            "message": "Current DRK automation is fill-only and does not submit Create Patient.",
        },
    }
    state_path = output / "handoff-state.json"
    _write_json(state_path, handoff_state)
    print(
        json.dumps(
            {
                "correlation_id": bundle.correlation_id,
                "monday_status": handoff_state["monday"]["status"],
                "monday_item_id": handoff_state["monday"]["item_id"],
                "drk_status": handoff_state["drk"]["status"],
                "bundle": str(bundle_path),
                "handoff_state": str(state_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
