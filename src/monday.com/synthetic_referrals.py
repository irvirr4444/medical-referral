"""Repeatable, non-PHI referral fixtures for the intake pipeline."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SyntheticReferralCase:
    slug: str
    email_subject: str
    layout: str
    referral: dict[str, Any]
    expected_outcome: str
    expected_duplicate_status: str


CASES: tuple[SyntheticReferralCase, ...] = (
    SyntheticReferralCase(
        slug="complete",
        email_subject="[TEST] New referral - Jamie Tester",
        layout="standard_form",
        referral={
            "patient_name": "TEST Jamie Tester",
            "patient_dob": "01/15/1958",
            "patient_phone": "(312) 555-0148",
            "patient_address": "1842 Example Avenue, Chicago, IL 60618",
            "referring_facility": "Lakeview Home Health",
            "referring_phone": "(312) 555-0199",
            "referral_date": "07/30/2026",
            "diagnosis_text": "Chronic non-pressure ulcer of right lower leg with delayed healing.",
            "icd10_codes": ["L97.912"],
            "insurance_provider": "ExampleCare Medicare Advantage",
            "insurance_id": "SYN-4481-002",
            "requested_services": [
                {"service": "Wound Care", "frequency": "Weekly", "instructions": "Initial evaluation and treatment plan."}
            ],
            "notes": "Synthetic fixture. No real patient information.",
        },
        expected_outcome="ready_for_human_approval",
        expected_duplicate_status="no_candidates_found",
    ),
    SyntheticReferralCase(
        slug="missing-threshold",
        email_subject="New referral - Rafael Torres",
        layout="fax_form",
        referral={
            "patient_name": "Rafael Torres",
            "patient_dob": "11/04/1966",
            "patient_phone": None,
            "patient_address": None,
            "referring_facility": "Cedar Post-Acute Center",
            "referring_phone": "(773) 555-0137",
            "referral_date": "07/30/2026",
            "diagnosis_text": "Pressure injury requiring wound assessment.",
            "insurance_provider": "Sample Health Plan",
            "insurance_id": "SYN-8830-114",
            "requested_services": [{"service": "Wound Care", "frequency": None, "instructions": "Assess wound."}],
            "notes": "Synthetic fixture intentionally omits contact details.",
        },
        expected_outcome="blocked_missing_threshold",
        expected_duplicate_status="no_candidates_found",
    ),
    SyntheticReferralCase(
        slug="partial",
        email_subject="New referral - Elena Brooks",
        layout="ehr_summary",
        referral={
            "patient_name": "Elena Brooks",
            "patient_dob": "08/22/1947",
            "patient_phone": "(847) 555-0112",
            "patient_address": "510 Fictional Road, Evanston, IL 60201",
            "referring_facility": None,
            "referring_phone": None,
            "referral_date": "07/30/2026",
            "diagnosis_text": None,
            "insurance_provider": None,
            "insurance_id": None,
            "requested_services": [],
            "notes": "Synthetic fixture intentionally omits supporting referral details.",
        },
        expected_outcome="manual_review_required",
        expected_duplicate_status="no_candidates_found",
    ),
    SyntheticReferralCase(
        slug="duplicate",
        email_subject="New referral - Morgan Patel",
        layout="scanned_form",
        referral={
            "patient_name": "Morgan Patel",
            "patient_dob": "04/28/1949",
            "patient_phone": "(708) 555-0184",
            "patient_address": "82 Training Street, Oak Park, IL 60302",
            "referring_facility": "Lakeview Home Health",
            "referring_phone": "(312) 555-0199",
            "referral_date": "07/30/2026",
            "diagnosis_text": "Lower-extremity wound follow-up requested.",
            "insurance_provider": "ExampleCare Medicare Advantage",
            "insurance_id": "SYN-2291-087",
            "requested_services": [{"service": "Wound Care", "frequency": "Weekly", "instructions": "Evaluate for ongoing treatment."}],
            "notes": "Synthetic fixture should match the synthetic Master Sheet snapshot.",
        },
        expected_outcome="manual_review_required",
        expected_duplicate_status="duplicate_found",
    ),
)


def write_synthetic_fixture_set(output_dir: str | Path) -> dict[str, str]:
    """Generate PDFs, MIME emails, gold expectations, and local Monday snapshots."""
    output = Path(output_dir)
    pdf_dir = output / "pdfs"
    email_dir = output / "emails"
    snapshot_dir = output / "monday-snapshots"
    for directory in (pdf_dir, email_dir, snapshot_dir):
        directory.mkdir(parents=True, exist_ok=True)

    for case in CASES:
        pdf_path = pdf_dir / f"synthetic-{case.slug}-referral.pdf"
        _write_referral_pdf(pdf_path, case)
        _write_email_fixture(email_dir / f"synthetic-{case.slug}.eml", case, pdf_path)

    gold_path = output / "gold_expectations.json"
    gold_path.write_text(
        json.dumps([asdict(case) for case in CASES], indent=2) + "\n",
        encoding="utf-8",
    )
    master_records = snapshot_dir / "master_sheet_records.json"
    master_records.write_text(json.dumps(_master_sheet_snapshot(), indent=2) + "\n", encoding="utf-8")
    account_records = snapshot_dir / "accounts_records.json"
    account_records.write_text(json.dumps(_accounts_snapshot(), indent=2) + "\n", encoding="utf-8")
    return {
        "pdf_dir": str(pdf_dir),
        "email_dir": str(email_dir),
        "gold_expectations": str(gold_path),
        "master_sheet_records": str(master_records),
        "accounts_records": str(account_records),
    }


def _write_referral_pdf(path: Path, case: SyntheticReferralCase) -> None:
    """Create a legible, referral-shaped PDF that exercises actual extraction fields."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    referral = case.referral
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    body.leading = 14
    document = SimpleDocTemplate(str(path), pagesize=letter, rightMargin=0.55 * inch, leftMargin=0.55 * inch)
    story = [
        Paragraph(_title_for_layout(case.layout), styles["Title"]),
        Paragraph("SYNTHETIC TRAINING DOCUMENT - NOT A REAL PATIENT", styles["Heading3"]),
        Spacer(1, 12),
        Paragraph(_intro_for_layout(case.layout, referral), body),
        Spacer(1, 10),
    ]
    services = "; ".join(
        " | ".join(str(part) for part in (service.get("service"), service.get("frequency"), service.get("instructions")) if part)
        for service in referral.get("requested_services", [])
    )
    insurance = " | ".join(str(part) for part in (referral.get("insurance_provider"), referral.get("insurance_id")) if part)
    rows = [
        ["Patient name", _display(referral.get("patient_name"))],
        ["Date of birth", _display(referral.get("patient_dob"))],
        ["Patient phone", _display(referral.get("patient_phone"))],
        ["Patient address", _display(referral.get("patient_address"))],
        ["Home health / referring agency", _display(referral.get("referring_facility"))],
        ["Agency phone", _display(referral.get("referring_phone"))],
        ["Insurance", _display(insurance)],
        ["Wound / clinical information", _display(referral.get("diagnosis_text"))],
        ["ICD-10", _display(", ".join(referral.get("icd10_codes", [])))],
        ["Requested services", _display(services)],
    ]
    table = Table([[Paragraph(f"<b>{label}</b>", body), Paragraph(value, body)] for label, value in rows], colWidths=[2.05 * inch, 5.1 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E9F3F5")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9AA9B0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([table, Spacer(1, 12), Paragraph(f"Notes: {_display(referral.get('notes'))}", body)])
    document.build(story)
    if case.layout == "scanned_form":
        _flatten_as_scanned_pdf(path)


def _write_email_fixture(path: Path, case: SyntheticReferralCase, pdf_path: Path) -> None:
    message = EmailMessage()
    message["From"] = "intake-source@example.test"
    message["To"] = "infobox@example.test"
    message["Subject"] = case.email_subject
    message["Date"] = format_datetime(datetime(2026, 7, 30, 15, 0, tzinfo=timezone.utc))
    message.set_content("Synthetic referral fixture for local pipeline testing. The attached PDF is synthetic.")
    message.add_attachment(pdf_path.read_bytes(), maintype="application", subtype="pdf", filename=pdf_path.name)
    path.write_bytes(message.as_bytes())


def _master_sheet_snapshot() -> dict[str, Any]:
    return {
        "board": {"id": "synthetic-master-sheet", "name": "Synthetic Master Sheet"},
        "items": [
            {
                "id": "synthetic-duplicate-001",
                "name": "Morgan Patel",
                "group": {"id": "topics", "title": "Working pipeline"},
                "column_values": [
                    {"id": "date12", "text": "Apr 28, 1949", "value": '{"date":"1949-04-28"}'},
                    {"id": "phone", "text": "(708) 555-0184"},
                    {"id": "location", "text": "82 Training Street, Oak Park, IL 60302"},
                    {"id": "deal_stage", "text": "In intake", "value": '{"label":"In intake"}'},
                ],
            }
        ],
    }


def _accounts_snapshot() -> dict[str, Any]:
    return {
        "board": {"id": "synthetic-accounts", "name": "Synthetic Accounts"},
        "items": [{"id": "synthetic-agency-001", "name": "Lakeview Home Health", "column_values": []}],
    }


def _display(value: object | None) -> str:
    return str(value) if value else "Not provided"


def _title_for_layout(layout: str) -> str:
    return {
        "fax_form": "FAXED REFERRAL - WOUND CARE INTAKE",
        "ehr_summary": "PATIENT REFERRAL SUMMARY",
        "scanned_form": "HOME HEALTH WOUND CARE REFERRAL",
    }.get(layout, "WEST COAST WOUND - REFERRAL INTAKE")


def _intro_for_layout(layout: str, referral: dict[str, Any]) -> str:
    date = _display(referral.get("referral_date"))
    if layout == "fax_form":
        return f"FAX TO: Intake Team &nbsp;&nbsp;&nbsp; FAX DATE: {date}"
    if layout == "ehr_summary":
        return f"Referral created: {date} &nbsp;&nbsp;&nbsp; Summary prepared for intake review"
    return f"Referral date: {date}"


def _flatten_as_scanned_pdf(path: Path) -> None:
    """Replace one fixture with an image-only PDF to exercise fax-like input handling."""
    import pypdfium2 as pdfium
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    image_path = path.with_suffix(".scan.png")
    source = pdfium.PdfDocument(str(path))
    try:
        image = source[0].render(scale=1.8).to_pil()
        image.save(image_path)
    finally:
        source.close()
    flattened = canvas.Canvas(str(path), pagesize=letter)
    flattened.drawImage(ImageReader(str(image_path)), 0, 0, width=letter[0], height=letter[1])
    flattened.save()
    image_path.unlink(missing_ok=True)
