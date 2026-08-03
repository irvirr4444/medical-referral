"""Shared orchestration for an accepted PDF attachment through Monday preview/write."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from inbound_mail import InboundPdfAttachment
from intake_duplicate_check import check_duplicates_disabled, check_duplicates_from_snapshot, check_duplicates_live
from intake_plan import build_intake_plan
from intake_extractor.llm_direct import extract_direct_from_pdf
from intake_extractor.schema import ReferralIntake
from master_sheet_agency_lookup import find_agency_matches_from_snapshot, find_agency_matches_live
from master_sheet_writer import (
    apply_master_sheet_create,
    build_master_sheet_create_preview,
    load_master_sheet_write_config,
)

Extractor = Callable[..., Any]


def process_inbound_pdf(
    attachment: InboundPdfAttachment,
    *,
    pdf_path: str | Path,
    output_dir: str | Path,
    input_mode: str = "image",
    max_pages: int | None = None,
    monday_mode: str = "disabled",
    monday_records_file: str | Path | None = None,
    include_full_row: bool = False,
    write_config_path: str | Path,
    agency_mode: str = "disabled",
    agency_records_file: str | Path | None = None,
    master_sheet_mode: str = "dry-run",
    confirm_master_sheet_write: bool = False,
    extractor: Extractor = extract_direct_from_pdf,
) -> dict[str, Any]:
    """Extract, plan, duplicate-check, and preview or apply a Master Sheet create.

    `master_sheet_mode` defaults to dry-run. An apply request additionally requires
    explicit confirmation so an inbox poll cannot accidentally create items.
    """
    if master_sheet_mode not in {"dry-run", "apply"}:
        raise ValueError("master_sheet_mode must be 'dry-run' or 'apply'")
    if master_sheet_mode == "apply" and not confirm_master_sheet_write:
        raise ValueError("Applying a Master Sheet write requires explicit confirmation.")

    pdf = Path(pdf_path)
    result = extractor(pdf, input_mode=input_mode, max_pages=max_pages)
    referral = _referral_from_extraction(result)
    duplicate = _duplicate_check(
        referral,
        mode=monday_mode,
        records_file=monday_records_file,
        include_full_row=include_full_row,
    )
    plan = build_intake_plan(referral, duplicate_check=duplicate)
    plan["source"] = {
        "kind": "inbound_email_pdf",
        "path": str(pdf),
        "mail_source": attachment.source,
        "message_id": attachment.message_id,
        "attachment_id": attachment.attachment_id,
        "attachment_sha256": attachment.sha256,
        "received_at": attachment.received_at,
        "subject": attachment.subject,
    }

    config = load_master_sheet_write_config(write_config_path)
    agency_matches = _agency_matches(
        referral,
        mode=agency_mode,
        records_file=agency_records_file,
        accounts_board_id=config.accounts_board_id,
    )
    preview = build_master_sheet_create_preview(
        plan,
        config=config,
        agency_matches=agency_matches,
    )
    preview["mode"] = master_sheet_mode

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    plan_path = output / "intake-plan.json"
    preview_path = output / "master-sheet-preview.json"
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    preview_path.write_text(json.dumps(preview, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    applied: dict[str, Any] | None = None
    if master_sheet_mode == "apply":
        applied = apply_master_sheet_create(preview)
        (output / "master-sheet-apply-result.json").write_text(
            json.dumps(applied, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    manifest = {
        "attachment_sha256": attachment.sha256,
        "filename": attachment.filename,
        "plan_path": str(plan_path),
        "preview_path": str(preview_path),
        "outcome": plan["outcome"],
        "duplicate_status": plan["monday_duplicate_check"]["status"],
        "master_sheet_blocked": preview["blocked"],
        "master_sheet_blockers": preview["blockers"],
        "created_item_id": None if applied is None else applied["item"]["id"],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _referral_from_extraction(result: Any) -> ReferralIntake:
    referral = getattr(result, "referral", result)
    if isinstance(referral, ReferralIntake):
        return referral
    if isinstance(referral, dict):
        return ReferralIntake.model_validate(referral)
    raise TypeError("The extractor did not return a ReferralIntake or an object with .referral.")


def _duplicate_check(
    referral: ReferralIntake,
    *,
    mode: str,
    records_file: str | Path | None,
    include_full_row: bool,
):
    if mode == "disabled":
        return check_duplicates_disabled()
    if mode == "snapshot":
        if records_file is None:
            raise ValueError("monday_records_file is required when monday_mode is snapshot")
        return check_duplicates_from_snapshot(referral, records_file=records_file, include_full_row=include_full_row)
    if mode == "live-readonly":
        return check_duplicates_live(referral, include_full_row=include_full_row)
    raise ValueError("monday_mode must be disabled, snapshot, or live-readonly")


def _agency_matches(
    referral: ReferralIntake,
    *,
    mode: str,
    records_file: str | Path | None,
    accounts_board_id: str | None,
) -> list[dict[str, str]]:
    if not referral.referring_facility or mode == "disabled":
        return []
    if mode == "snapshot":
        if records_file is None:
            raise ValueError("agency_records_file is required when agency_mode is snapshot")
        return find_agency_matches_from_snapshot(referral.referring_facility, records_file=records_file)
    if mode == "live-readonly":
        if not accounts_board_id:
            raise ValueError("The write config needs an Accounts board ID for live agency lookup")
        return find_agency_matches_live(referral.referring_facility, board_id=accounts_board_id)
    raise ValueError("agency_mode must be disabled, snapshot, or live-readonly")
