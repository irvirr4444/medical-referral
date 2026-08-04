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
from intake_extractor.canonical_referral import CanonicalReferral, extract_referral_pdf
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
    source.add_argument("--canonical-json", type=Path, help="Existing canonical-referral.json.")
    parser.add_argument(
        "--source-pdf",
        type=Path,
        help="Original PDF required with --canonical-json for hashing and source provenance.",
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
    parser.add_argument("--apply-master-sheet", action="store_true")
    parser.add_argument("--confirm-master-sheet-write", action="store_true")
    parser.add_argument(
        "--drk-duplicate-json",
        type=Path,
        help="Optional drk-duplicate-check.json decision to include in handoff state.",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("tmp") / "aligned-intake")
    return parser.parse_args(argv)


def _load_extraction(args: argparse.Namespace) -> tuple[CanonicalReferral, Path]:
    if args.pdf is not None:
        extraction = extract_referral_pdf(
            args.pdf,
            sent_by=args.sent_by,
            pdf_transport=args.pdf_transport,
            progress=lambda message: print(message, flush=True),
        )
        return extraction, args.pdf
    if args.source_pdf is None:
        raise ValueError("--source-pdf is required with --canonical-json")
    try:
        payload = json.loads(args.canonical_json.read_text(encoding="utf-8-sig"))
        return CanonicalReferral.model_validate(payload), args.source_pdf
    except OSError as exc:
        raise RuntimeError(f"Could not read canonical JSON: {args.canonical_json}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Canonical JSON is invalid: {args.canonical_json}") from exc


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


def _load_drk_duplicate_decision(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "status": "not_checked",
            "clear_to_create": False,
            "reason": "DRK duplicate gate was not run for this aligned preview.",
            "candidate_patient_ids": [],
        }
    try:
        from drk_emr.create_patient.schema import DrkDuplicateCheckDecision

        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        decision = DrkDuplicateCheckDecision.model_validate(payload)
        return decision.model_dump(mode="json")
    except OSError as exc:
        raise RuntimeError(f"Could not read DRK duplicate JSON: {path}") from exc
    except Exception as exc:
        raise RuntimeError(f"Invalid DRK duplicate JSON: {path}") from exc


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.apply_master_sheet and not args.confirm_master_sheet_write:
        raise ValueError("--apply-master-sheet requires --confirm-master-sheet-write")

    canonical, source_pdf = _load_extraction(args)
    source_metadata = {"sent_by": args.sent_by} if args.sent_by else {}
    bundle = build_aligned_intake_bundle(
        canonical,
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
    canonical_path = output / "canonical-referral.json"
    plan_path = output / "intake-plan.json"
    master_preview_path = output / "master-sheet-preview.json"
    drk_draft_path = output / "drk-create-draft.json"
    drk_duplicate = _load_drk_duplicate_decision(args.drk_duplicate_json)
    drk_duplicate_path = output / "drk-duplicate-check.json"
    _write_json(canonical_path, bundle.canonical_referral.model_dump(mode="json"))
    _write_json(bundle_path, bundle.model_dump(mode="json"))
    _write_json(plan_path, plan)
    _write_json(master_preview_path, preview)
    _write_json(drk_draft_path, bundle.drk_create_draft.model_dump(mode="json"))
    _write_json(drk_duplicate_path, drk_duplicate)

    applied = None
    if args.apply_master_sheet:
        applied = apply_master_sheet_create(preview)
        _write_json(output / "master-sheet-apply-result.json", applied)

    drk_blockers = list(bundle.drk_create_draft.blockers)
    if drk_duplicate.get("status") == "duplicate_found":
        drk_blockers.append("drk_duplicate_found")
    elif drk_duplicate.get("status") == "manual_review_required":
        drk_blockers.append("drk_duplicate_manual_review_required")
    elif drk_duplicate.get("status") == "not_checked":
        drk_blockers.append("drk_duplicate_not_checked")
    elif not drk_duplicate.get("clear_to_create"):
        drk_blockers.append("drk_duplicate_not_clear_to_create")

    if drk_duplicate.get("status") == "clear_to_create" and bundle.drk_create_draft.ready_for_fill:
        drk_status = "clear_to_create"
    elif bundle.drk_create_draft.ready_for_fill and drk_duplicate.get("status") == "not_checked":
        drk_status = "draft_ready_duplicate_not_checked"
    elif drk_duplicate.get("status") == "duplicate_found":
        drk_status = "blocked_duplicate"
    elif drk_duplicate.get("status") == "manual_review_required":
        drk_status = "blocked_manual_review"
    else:
        drk_status = "blocked"

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
            "status": drk_status,
            "patient_id": None,
            "write_supported": False,
            "clear_to_create": bool(drk_duplicate.get("clear_to_create")),
            "duplicate_check": drk_duplicate,
            "blockers": drk_blockers,
            "message": (
                "DRK fill requires a fresh clear_to_create duplicate decision; "
                "Create Patient submit remains disabled."
            ),
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
