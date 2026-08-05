from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from intake_extractor.canonical_referral import (
    CanonicalAddress,
    CanonicalName,
    CanonicalPatient,
    CanonicalPhone,
    CanonicalReferral,
    CanonicalSource,
)

from referral_pipeline import service as inbound_pipeline


def test_inbound_pipeline_defaults_to_canonical_extractor(tmp_path, monkeypatch) -> None:
    pdf = tmp_path / "referral.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    config = tmp_path / "master-sheet-config.json"
    config.write_text(
        json.dumps(
            {
                "board_id": 5815942462,
                "group_id": "topics",
                "stage_label": "In intake",
                "phone_country_code": "US",
                "columns": {
                    "patient_dob": "date12",
                    "patient_phone": "phone",
                    "patient_email": "email2",
                    "stage": "deal_stage",
                    "comments": "text00__1",
                },
            }
        ),
        encoding="utf-8",
    )
    contract = CanonicalReferral(
        referral_id="ref_test",
        source=CanonicalSource(file_name=pdf.name, pdf_sha256="abc123"),
        patient=CanonicalPatient(
            name=CanonicalName(full="Jane Doe", first="Jane", last="Doe"),
            date_of_birth="1950-01-02",
            phones=[CanonicalPhone(number="555-555-0100")],
            email="jane@example.com",
            address=CanonicalAddress(line_1="1 Main St"),
        ),
    )
    calls: list[tuple[Path, str | None, str | None, str | None, str | None]] = []

    def fake_extract(path: Path, **kwargs):
        calls.append(
            (
                path,
                kwargs.get("email_id"),
                kwargs.get("attachment_id"),
                kwargs.get("sent_by"),
                kwargs.get("pdf_transport"),
            )
        )
        return contract

    monkeypatch.setattr(inbound_pipeline, "extract_referral_pdf", fake_extract)
    attachment = SimpleNamespace(
        source="email",
        message_id="message-1",
        attachment_id="attachment-1",
        sha256="abc123",
        received_at="2026-08-03T12:00:00Z",
        subject="Referral",
        filename=pdf.name,
    )

    manifest = inbound_pipeline.process_inbound_pdf(
        attachment,
        pdf_path=pdf,
        output_dir=tmp_path / "output",
        write_config_path=config,
        sent_by="Intake User",
    )

    assert calls == [(pdf, "message-1", "attachment-1", "Intake User", "files-api")]
    assert manifest["canonical_referral_path"] == str(tmp_path / "output" / "canonical-referral.json")
    assert Path(manifest["inbox_text_path"]).is_file()
    assert Path(manifest["drk_draft_path"]).is_file()
    preview = json.loads((tmp_path / "output" / "master-sheet-preview.json").read_text(encoding="utf-8"))
    assert preview["column_values"]["email2"] == {
        "email": "jane@example.com",
        "text": "jane@example.com",
    }
