"""Shared orchestration for an accepted PDF attachment through Monday preview/write."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, Protocol


# Monday is still a scripts directory rather than an importable package. Keep
# that compatibility detail inside the orchestration layer.
SRC_ROOT = Path(__file__).resolve().parents[1]
MONDAY_DIR = SRC_ROOT / "monday.com"
if str(MONDAY_DIR) not in sys.path:
    sys.path.insert(0, str(MONDAY_DIR))

from intake_duplicate_check import check_duplicates_disabled, check_duplicates_from_snapshot, check_duplicates_live
from intake_plan import build_intake_plan
from intake_extractor.aligned_intake import (
    to_drk_create_draft_from_canonical,
    to_master_sheet_referral,
    to_master_sheet_referral_from_canonical,
)
from intake_extractor.canonical_referral import CanonicalReferral, extract_referral_pdf, render_inbox_text
from intake_extractor.drk_pdf_schema import DrkPdfExtraction
from intake_extractor.monday_pdf import to_referral_intake
from intake_extractor.monday_pdf_schema import MondayPdfIntakeContract
from intake_extractor.models.schema import ReferralIntake
from master_sheet_agency_lookup import find_agency_matches_from_snapshot, find_agency_matches_live
from master_sheet_writer import (
    apply_master_sheet_create,
    build_master_sheet_create_preview,
    load_master_sheet_write_config,
)

Extractor = Callable[..., Any]


class InboundPdfAttachment(Protocol):
    source: str
    message_id: str
    attachment_id: str
    sha256: str
    received_at: str
    subject: str
    filename: str


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
    sent_by: str | None = None,
    extractor: Extractor | None = None,
    progress: Callable[[str], None] | None = None,
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
    if extractor is None:
        result = extract_referral_pdf(
            pdf,
            email_id=attachment.message_id,
            attachment_id=attachment.attachment_id,
            sent_by=sent_by,
            pdf_transport="files-api",
            progress=progress,
        )
    else:
        # Retain the injection seam for legacy extractors and isolated unit tests.
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
        "sent_by": sent_by,
    }

    config = load_master_sheet_write_config(write_config_path)
    agency_matches = _agency_matches(
        referral.referring_facility,
        mode=agency_mode,
        records_file=agency_records_file,
        accounts_board_id=config.accounts_board_id,
    )
    current_hh_matches = _agency_matches(
        referral.current_home_health_or_hospice,
        mode=agency_mode,
        records_file=agency_records_file,
        accounts_board_id=config.accounts_board_id,
    )
    preview = build_master_sheet_create_preview(
        plan,
        config=config,
        agency_matches=agency_matches,
        current_hh_matches=current_hh_matches,
    )
    preview["mode"] = master_sheet_mode

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    plan_path = output / "intake-plan.json"
    preview_path = output / "master-sheet-preview.json"
    canonical_path = output / "canonical-referral.json"
    inbox_path = output / "inbox-intake.txt"
    drk_draft_path = output / "drk-create-draft.json"
    monday_contract_path = output / "monday-intake.json"
    if isinstance(result, CanonicalReferral):
        canonical_path.write_text(
            json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        inbox_path.write_text(render_inbox_text(result), encoding="utf-8")
        drk_draft_path.write_text(
            json.dumps(
                to_drk_create_draft_from_canonical(result).model_dump(mode="json"),
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
    if isinstance(result, MondayPdfIntakeContract):
        monday_contract_path.write_text(
            json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
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
        "canonical_referral_path": str(canonical_path) if isinstance(result, CanonicalReferral) else None,
        "inbox_text_path": str(inbox_path) if isinstance(result, CanonicalReferral) else None,
        "drk_draft_path": str(drk_draft_path) if isinstance(result, CanonicalReferral) else None,
        "monday_contract_path": str(monday_contract_path) if isinstance(result, MondayPdfIntakeContract) else None,
        "outcome": plan["outcome"],
        "duplicate_status": plan["monday_duplicate_check"]["status"],
        "master_sheet_blocked": preview["blocked"],
        "master_sheet_blockers": preview["blockers"],
        "created_item_id": None if applied is None else applied["item"]["id"],
        "source_message_id": attachment.message_id,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _referral_from_extraction(result: Any) -> ReferralIntake:
    referral = getattr(result, "referral", result)
    if isinstance(referral, CanonicalReferral):
        return to_master_sheet_referral_from_canonical(referral)
    if isinstance(referral, MondayPdfIntakeContract):
        return to_referral_intake(referral)
    if isinstance(referral, DrkPdfExtraction):
        return to_master_sheet_referral(referral)
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
    facility: str | None,
    *,
    mode: str,
    records_file: str | Path | None,
    accounts_board_id: str | None,
) -> list[dict[str, str]]:
    if not facility or mode == "disabled":
        return []
    if mode == "snapshot":
        if records_file is None:
            raise ValueError("agency_records_file is required when agency_mode is snapshot")
        return find_agency_matches_from_snapshot(facility, records_file=records_file)
    if mode == "live-readonly":
        if not accounts_board_id:
            raise ValueError("The write config needs an Accounts board ID for live agency lookup")
        return find_agency_matches_live(facility, board_id=accounts_board_id)
    raise ValueError("agency_mode must be disabled, snapshot, or live-readonly")
