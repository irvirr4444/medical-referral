from __future__ import annotations

import json

import pdfplumber

from Outlook.mail import read_eml_pdf_attachments
from synthetic_referrals import CASES, write_synthetic_fixture_set


def test_generated_pdfs_and_emails_match_the_synthetic_contract(tmp_path) -> None:
    paths = write_synthetic_fixture_set(tmp_path)
    gold = json.loads((tmp_path / "gold_expectations.json").read_text(encoding="utf-8"))

    assert len(gold) == len(CASES) == 4
    for case in CASES:
        pdf = tmp_path / "pdfs" / f"synthetic-{case.slug}-referral.pdf"
        text = "\n".join(page.extract_text() or "" for page in pdfplumber.open(pdf).pages)
        if case.layout == "scanned_form":
            assert not text
        else:
            assert "SYNTHETIC TRAINING DOCUMENT" in text
            assert case.referral["patient_name"] in text
            assert case.referral["patient_dob"] in text

        attachments = read_eml_pdf_attachments(tmp_path / "emails" / f"synthetic-{case.slug}.eml")
        assert len(attachments) == 1
        assert attachments[0].content.startswith(b"%PDF-")
        assert attachments[0].filename == pdf.name
        assert attachments[0].received_at == "2026-07-30T15:00:00+00:00"

    assert paths["master_sheet_records"].endswith("master_sheet_records.json")


def test_local_email_reader_rejects_non_pdf_content_even_when_named_pdf(tmp_path) -> None:
    message = (
        b"From: source@example.test\nTo: inbox@example.test\nSubject: bad\n"
        b"MIME-Version: 1.0\nContent-Type: application/octet-stream; name=not-a-pdf.pdf\n"
        b"Content-Disposition: attachment; filename=not-a-pdf.pdf\n"
        b"Content-Transfer-Encoding: base64\n\naGVsbG8=\n"
    )
    path = tmp_path / "bad.eml"
    path.write_bytes(message)

    assert read_eml_pdf_attachments(path) == []
