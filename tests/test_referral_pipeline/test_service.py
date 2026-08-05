from __future__ import annotations

from pathlib import Path

from Outlook.mail import InboundPdfAttachment
from referral_pipeline.service import process_inbound_pdf
from synthetic_referrals import CASES, write_synthetic_fixture_set


def test_pipeline_builds_unblocked_preview_for_complete_synthetic_referral(tmp_path) -> None:
    write_synthetic_fixture_set(tmp_path / "fixtures")
    case = next(case for case in CASES if case.slug == "complete")
    pdf = tmp_path / "fixtures" / "pdfs" / "synthetic-complete-referral.pdf"
    attachment = InboundPdfAttachment(
        source="test",
        message_id="message-1",
        attachment_id="attachment-1",
        filename=pdf.name,
        content=pdf.read_bytes(),
    )
    config = Path(__file__).resolve().parents[2] / "src" / "monday.com" / "master_sheet_write_config.example.json"

    manifest = process_inbound_pdf(
        attachment,
        pdf_path=pdf,
        output_dir=tmp_path / "run",
        monday_mode="snapshot",
        monday_records_file=tmp_path / "fixtures" / "monday-snapshots" / "master_sheet_records.json",
        write_config_path=config,
        agency_mode="snapshot",
        agency_records_file=tmp_path / "fixtures" / "monday-snapshots" / "accounts_records.json",
        extractor=lambda *_args, **_kwargs: case.referral,
    )

    assert manifest["outcome"] == "ready_for_human_approval"
    assert manifest["duplicate_status"] == "no_candidates_found"
    assert manifest["master_sheet_blocked"] is False
    assert (tmp_path / "run" / "intake-plan.json").is_file()
    assert (tmp_path / "run" / "master-sheet-preview.json").is_file()


def test_pipeline_blocks_synthetic_duplicate_before_any_write(tmp_path) -> None:
    write_synthetic_fixture_set(tmp_path / "fixtures")
    case = next(case for case in CASES if case.slug == "duplicate")
    pdf = tmp_path / "fixtures" / "pdfs" / "synthetic-duplicate-referral.pdf"
    attachment = InboundPdfAttachment("test", "message-2", "attachment-2", pdf.name, pdf.read_bytes())
    config = Path(__file__).resolve().parents[2] / "src" / "monday.com" / "master_sheet_write_config.example.json"

    manifest = process_inbound_pdf(
        attachment,
        pdf_path=pdf,
        output_dir=tmp_path / "run",
        monday_mode="snapshot",
        monday_records_file=tmp_path / "fixtures" / "monday-snapshots" / "master_sheet_records.json",
        write_config_path=config,
        extractor=lambda *_args, **_kwargs: case.referral,
    )

    assert manifest["duplicate_status"] == "candidates_found"
    assert manifest["master_sheet_blocked"] is True
    assert "duplicate_check_is_candidates_found" in manifest["master_sheet_blockers"]
