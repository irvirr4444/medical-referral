"""ReportLab renderers modeled after the seven supplied referral families."""

from __future__ import annotations

import random
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from textwrap import wrap
from typing import Callable

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from .models import SyntheticReferral
from .vocabulary import MEDICATIONS, NOTE_FRAGMENTS


PAGE_W, PAGE_H = letter
MARGIN = 48


@dataclass(frozen=True)
class RenderStyle:
    margin: float = MARGIN
    section_font: int = 10
    swap_columns: bool = False
    abbreviate_labels: bool = False


_STYLE: ContextVar[RenderStyle] = ContextVar("synthetic_render_style", default=RenderStyle())


def render_referral(
    case: SyntheticReferral,
    output: str | Path,
    *,
    variant: int = 0,
    apply_scan_style: bool = True,
) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(f"{case.slug}:layout:{variant}")
    style = RenderStyle(
        margin=float(MARGIN + rng.choice((-14, -10, -6, 0, 6, 10, 14))),
        section_font=int(rng.choice((9, 10, 11))),
        swap_columns=bool(
            variant % 2 == 1 and case.layout in {"patient_chart", "agency_summary"}
        ),
        abbreviate_labels=bool(variant % 2 == 1 and case.layout == "wcw_handwritten"),
    )
    token = _STYLE.set(style)
    try:
        renderer = RENDERERS[case.layout]
        renderer(case, path)
        if apply_scan_style and case.scan_style == "fax":
            _flatten_with_fax_artifacts(path, seed=case.slug)
    finally:
        _STYLE.reset(token)
    return path


def _style() -> RenderStyle:
    return _STYLE.get()


def _margin() -> float:
    return _style().margin


def _canvas(path: Path) -> Canvas:
    canvas = Canvas(str(path), pagesize=letter, pageCompression=1)
    canvas.setTitle("Patient referral packet")
    canvas.setAuthor("Health Information Management")
    return canvas


def _case_choice(case: SyntheticReferral, label: str, values: tuple[str, ...]) -> str:
    return random.Random(f"{case.slug}:{label}").choice(values)


def _synthetic_banner(c: Canvas) -> None:
    """Compatibility hook; safety labeling lives in the external manifest."""


def _label(text: str) -> str:
    if not _style().abbreviate_labels:
        return text
    abbrev = {
        "Phone": "Ph",
        "Address": "Addr",
        "Patient name": "Pt name",
        "Primary insurance": "Ins",
        "Subscriber ID": "Sub ID",
        "Reason for referral": "Reason",
        "Requested service": "Service",
        "Emergency contact": "E-contact",
        "PCP / ordering provider": "Ordering",
    }
    return abbrev.get(text, text)


def _header(c: Canvas, title: str, subtitle: str | None = None) -> float:
    margin = _margin()
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, PAGE_H - 55, title)
    if subtitle:
        c.setFont("Helvetica", 9)
        c.drawString(margin, PAGE_H - 70, subtitle)
    c.setLineWidth(1)
    c.line(margin, PAGE_H - 79, PAGE_W - margin, PAGE_H - 79)
    return PAGE_H - 102


def _section(c: Canvas, y: float, title: str, *, dark: bool = False) -> float:
    margin = _margin()
    font_size = _style().section_font
    if dark:
        c.setFillColor(colors.black)
        c.rect(margin, y - 13, PAGE_W - 2 * margin, 17, fill=1, stroke=0)
        c.setFillColor(colors.white)
    else:
        c.setFillColor(colors.HexColor("#E8ECEE"))
        c.rect(margin, y - 13, PAGE_W - 2 * margin, 17, fill=1, stroke=0)
        c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", font_size)
    c.drawString(margin + 5, y - 9, title.upper())
    c.setFillColor(colors.black)
    return y - 28


def _field(c: Canvas, x: float, y: float, label: str, value: object, *, width: float = 230) -> None:
    text = "Not provided" if value in (None, "") else str(value)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(x, y, _label(label).upper())
    c.setFont("Helvetica", 9)
    _draw_wrapped(c, text, x, y - 13, width=width, font_size=9, leading=11, max_lines=2)


def _line_field(c: Canvas, x: float, y: float, label: str, value: object, width: float) -> None:
    shown = _label(label)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x, y, f"{shown}:")
    label_width = pdfmetrics.stringWidth(f"{shown}:", "Helvetica-Bold", 8) + 6
    c.line(x + label_width, y - 2, x + width, y - 2)
    c.setFont(_hand_font(), 11)
    text = "" if value in (None, "") else str(value)
    c.drawString(x + label_width + 4, y + 1, text[:55])


def _wrapped_line_field(
    c: Canvas,
    x: float,
    y: float,
    label: str,
    value: object,
    width: float,
    *,
    max_lines: int = 2,
) -> None:
    shown = _label(label)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x, y, f"{shown}:")
    label_width = pdfmetrics.stringWidth(f"{shown}:", "Helvetica-Bold", 8) + 6
    text = "" if value in (None, "") else str(value)
    _draw_wrapped(
        c,
        text,
        x + label_width + 4,
        y + 1,
        width=width - x - label_width - 4,
        font_size=10,
        leading=12,
        max_lines=max_lines,
        font=_hand_font(),
    )
    for line in range(max_lines):
        line_y = y - 2 - line * 12
        c.line(x + label_width, line_y, x + width, line_y)


def _draw_wrapped(
    c: Canvas,
    value: str,
    x: float,
    y: float,
    *,
    width: float,
    font_size: float = 9,
    leading: float = 11,
    max_lines: int = 8,
    font: str = "Helvetica",
) -> float:
    chars = max(12, int(width / (font_size * 0.52)))
    lines = wrap(value, width=chars, break_long_words=False) or [""]
    c.setFont(font, font_size)
    for index, line in enumerate(lines[:max_lines]):
        c.drawString(x, y - index * leading, line)
    return y - min(len(lines), max_lines) * leading


def _page_number(c: Canvas, page: int, total: int, source: str = "Secure Fax Gateway") -> None:
    c.setFont("Courier", 7)
    c.drawString(30, PAGE_H - 18, f"From: {source}")
    c.drawCentredString(PAGE_W / 2, PAGE_H - 18, f"Page {page} of {total}")


def _services(case: SyntheticReferral) -> str:
    if not case.requested_services:
        return "No explicit requested service documented."
    return "; ".join(
        " - ".join(part for part in (item.service, item.frequency, item.instructions) if part)
        for item in case.requested_services
    )


def _insurance(case: SyntheticReferral) -> str:
    return " | ".join(
        part
        for part in (case.insurance_provider, case.insurance_id, case.insurance_group_number)
        if part
    ) or "Not provided"


def _draw_demographics(c: Canvas, case: SyntheticReferral, y: float) -> float:
    margin = _margin()
    y = _section(c, y, "Patient demographics")
    left = margin + 5
    right = 320
    if _style().swap_columns:
        left, right = right, left
    _field(c, left, y, "Patient", case.patient_name, width=220)
    _field(c, right, y, "DOB / Sex", f"{case.patient_dob} / {case.patient_sex}", width=210)
    y -= 44
    _field(c, margin + 5, y, "Address", case.patient_address, width=310)
    _field(c, 390, y, "Phone", case.patient_phone, width=150)
    y -= 48
    _field(c, margin + 5, y, "MRN", case.patient_mrn)
    _field(c, 320, y, "Emergency contact", case.emergency_contact, width=220)
    return y - 42


def _draw_referral(c: Canvas, case: SyntheticReferral, y: float) -> float:
    margin = _margin()
    y = _section(c, y, "Referral and clinical information")
    _field(c, margin + 5, y, "Referring facility", case.referring_facility, width=245)
    _field(c, 330, y, "Referral date", case.referral_date, width=100)
    _field(c, 450, y, "Admitted", case.admission_date, width=100)
    y -= 44
    _field(c, margin + 5, y, "Provider", case.referring_provider_name, width=220)
    _field(c, 320, y, "Facility phone / fax", f"{case.referring_phone} / {case.referring_fax}", width=230)
    y -= 44
    _field(c, margin + 5, y, "Diagnosis / wound", case.diagnosis_text, width=370)
    _field(c, 440, y, "ICD-10", ", ".join(case.icd10_codes), width=110)
    y -= 55
    _field(c, margin + 5, y, "Requested services", _services(case), width=500)
    return y - 55


def _draw_coverage(c: Canvas, case: SyntheticReferral, y: float) -> float:
    margin = _margin()
    y = _section(c, y, "Insurance coverage")
    _field(c, margin + 5, y, "Primary insurance / member / group", _insurance(case), width=500)
    return y - 42


def _render_patient_chart(case: SyntheticReferral, path: Path) -> None:
    c = _canvas(path)
    chart_title = _case_choice(case, "chart-title", ("PATIENT CHART", "PATIENT RECORD", "CLINICAL PROFILE"))
    chart_subtitle = _case_choice(case, "chart-subtitle", ("Clinical chart summary", "Referral record summary", "Patient information report"))
    y = _header(c, f"{chart_title} - {case.patient_name}", chart_subtitle)
    y = _draw_demographics(c, case, y)
    y = _draw_coverage(c, case, y)
    y = _draw_referral(c, case, y)
    _synthetic_banner(c)
    c.showPage()

    y = _header(c, "MEDICAL PROBLEM LIST", f"MRN: {case.patient_mrn}")
    problems = [
        (case.icd10_codes[0] if case.icd10_codes else "Z51.89", case.diagnosis_text or "Wound evaluation"),
        ("I10", "Essential hypertension"),
        ("E11.9", "Type 2 diabetes mellitus without complications"),
        ("R60.0", "Localized edema"),
        ("Z74.09", "Reduced mobility"),
    ]
    for code, problem in problems:
        c.setFont("Helvetica", 10)
        c.drawString(MARGIN, y, f"{code}  {problem}")
        c.drawRightString(PAGE_W - MARGIN, y, "Current")
        y -= 28
    y = _section(c, y - 5, "Current medications")
    medication_rng = random.Random(f"{case.slug}:medications")
    for medication in medication_rng.sample(MEDICATIONS, k=3):
        c.setFont("Helvetica", 9)
        c.drawString(MARGIN + 5, y, medication)
        y -= 22
    _synthetic_banner(c)
    c.showPage()

    y = _header(c, "REFERRAL ORDER", case.referring_facility)
    y = _draw_referral(c, case, y)
    y = _draw_coverage(c, case, y)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(MARGIN, y, f"Electronically signed by {case.referring_provider_name} on {case.referral_date}")
    _synthetic_banner(c)
    c.save()


def _render_wcw_handwritten(case: SyntheticReferral, path: Path) -> None:
    c = _canvas(path)
    c.setFillColor(colors.HexColor("#0783B5"))
    c.setFont("Helvetica-Bold", 20)
    c.drawString(65, PAGE_H - 55, "WEST COAST")
    c.setFont("Helvetica", 11)
    c.drawString(67, PAGE_H - 70, "W O U N D  &  S K I N  C A R E")
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(
        PAGE_W / 2,
        PAGE_H - 93,
        _case_choice(case, "wcw-title", ("Patient Referral Form", "New Patient Referral", "Wound Care Referral Form")),
    )
    c.setFont("Helvetica", 8)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 106, "This referral form is for mobile wound-care services")
    y = PAGE_H - 135
    _line_field(c, 58, y, "Date", case.referral_date, 230)
    _line_field(c, 320, y, "Referred by", case.referring_facility, 535)
    y -= 30
    _line_field(c, 58, y, "Phone", case.referring_phone, 285)
    _line_field(c, 320, y, "Fax", case.referring_fax, 535)
    y -= 37
    c.setFont("Helvetica-Bold", 10)
    c.drawString(58, y, "REFERRAL DETAILS")
    y -= 24
    _line_field(c, 58, y, "Type of care needed", "Wound Care", 535)
    y -= 30
    _wrapped_line_field(c, 58, y, "Reason for referral", case.diagnosis_text, 535, max_lines=2)
    y -= 42
    _line_field(c, 58, y, "ICD", ", ".join(case.icd10_codes), 535)
    y -= 38
    c.setFont("Helvetica-Bold", 10)
    c.drawString(58, y, "PATIENT INFORMATION")
    y -= 24
    _line_field(c, 58, y, "Patient name", case.patient_name, 535)
    y -= 28
    _line_field(c, 58, y, "DOB", case.patient_dob, 285)
    _line_field(c, 320, y, "Sex", case.patient_sex, 535)
    y -= 28
    _line_field(c, 58, y, "Phone", case.patient_phone, 285)
    _line_field(c, 320, y, "MRN", case.patient_mrn, 535)
    y -= 28
    _line_field(c, 58, y, "Address", case.patient_address, 535)
    y -= 36
    c.setFont("Helvetica-Bold", 10)
    c.drawString(58, y, "INSURANCE INFORMATION")
    y -= 24
    _line_field(c, 58, y, "Primary insurance", case.insurance_provider, 320)
    _line_field(c, 335, y, "Subscriber ID", case.insurance_id, 535)
    y -= 28
    _wrapped_line_field(c, 58, y, "Requested service", _services(case), 535)
    y -= 46
    _line_field(c, 58, y, "PCP / ordering provider", case.referring_provider_name, 535)
    _synthetic_banner(c)
    c.save()


def _fax_cover(c: Canvas, case: SyntheticReferral, page: int, total: int, title: str) -> None:
    _page_number(c, page, total, case.referring_facility)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 95, title)
    c.setFont("Helvetica", 10)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 112, case.referring_facility)
    y = PAGE_H - 165
    for label, value in (
        ("To", _case_choice(case, "fax-to", ("West Coast Wound Intake", "WCW Intake Department", "West Coast Wound & Skin Care"))),
        ("From", case.referring_provider_name),
        ("Return fax", case.referring_fax),
        ("Date", case.referral_date),
        ("Patient", case.patient_name),
        ("DOB", case.patient_dob),
        ("Pages including cover", str(total)),
    ):
        c.setFont("Helvetica-Bold", 10)
        c.drawString(75, y, label)
        c.setFont("Helvetica", 10)
        c.drawString(190, y, str(value))
        y -= 26
    y -= 10
    _draw_wrapped(
        c,
        "CONFIDENTIAL HEALTH INFORMATION: This transmission may contain protected health information. "
        "If received in error, notify the sender and securely destroy all copies.",
        75,
        y,
        width=455,
        font_size=9,
        leading=12,
    )
    _synthetic_banner(c)


def _packet_page(c: Canvas, case: SyntheticReferral, page: int, total: int, title: str) -> None:
    _page_number(c, page, total, case.referring_facility)
    y = _header(c, title, f"Patient: {case.patient_name}   MRN: {case.patient_mrn}")
    if page == 2:
        y = _draw_demographics(c, case, y)
        _draw_coverage(c, case, y)
    elif page == 3:
        _draw_referral(c, case, y)
    else:
        y = _section(c, y, "Clinical notes")
        note_rng = random.Random(f"{case.slug}:note:{page}")
        narrative = " ".join((
            f"Patient evaluated for {case.diagnosis_text or 'wound concern'}",
            *note_rng.sample(NOTE_FRAGMENTS, k=note_rng.randint(3, 6)),
            f"Plan: {_services(case)}",
        ))
        _draw_wrapped(c, narrative, MARGIN + 5, y, width=500, font_size=10, leading=15, max_lines=12)
    _synthetic_banner(c)


def _render_hospital_fax(case: SyntheticReferral, path: Path) -> None:
    _render_packet(
        case,
        path,
        _case_choice(case, "hospital-cover", ("Hospital Referral Fax", "Patient Transfer Referral", "Clinical Referral Packet")),
        4,
    )


def _render_discharge_packet(case: SyntheticReferral, path: Path) -> None:
    _render_packet(
        case,
        path,
        _case_choice(case, "discharge-cover", ("Discharge Planning Fax Cover Sheet", "Post-Acute Referral Packet", "Discharge Referral Cover Sheet")),
        5,
    )


def _render_packet(case: SyntheticReferral, path: Path, title: str, pages: int) -> None:
    c = _canvas(path)
    _fax_cover(c, case, 1, pages, title)
    for page in range(2, pages + 1):
        c.showPage()
        _packet_page(c, case, page, pages, "Patient Referral Packet")
    c.save()


def _render_hospital_facesheet(case: SyntheticReferral, path: Path) -> None:
    c = _canvas(path)
    _page_number(c, 1, 3, case.referring_facility)
    c.setLineWidth(1)
    c.rect(55, PAGE_H - 160, PAGE_W - 110, 105, fill=0)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(65, PAGE_H - 77, case.referring_facility.upper()[:48])
    c.setFont("Helvetica", 8)
    c.drawString(65, PAGE_H - 93, "Health Information Management - Patient Access")
    _field(c, 390, PAGE_H - 80, "Admit date", case.admission_date, width=150)
    _field(c, 390, PAGE_H - 113, "MRN", case.patient_mrn, width=150)
    y = PAGE_H - 180
    y = _draw_demographics(c, case, y)
    y = _draw_coverage(c, case, y)
    _draw_referral(c, case, y)
    _synthetic_banner(c)
    c.showPage()
    _packet_page(c, case, 2, 3, "Encounter Summary")
    c.showPage()
    _packet_page(c, case, 3, 3, "Wound Care Order")
    c.save()


def _render_home_health_fax(case: SyntheticReferral, path: Path) -> None:
    c = _canvas(path)
    _page_number(c, 1, 3, case.referring_facility)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, PAGE_H - 72, case.referring_facility)
    c.setFont("Helvetica", 9)
    c.drawString(50, PAGE_H - 88, f"Phone {case.referring_phone}  Fax {case.referring_fax}")
    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, PAGE_H - 145, _case_choice(case, "home-health-title", ("FAX", "REFERRAL", "PATIENT INTAKE")))
    y = PAGE_H - 190
    for label, value in (
        ("From", case.referring_provider_name),
        ("Return Fax", case.referring_fax),
        ("Attention To", "West Coast Wound Care"),
        ("Regarding", case.patient_name),
        ("DOB", case.patient_dob),
    ):
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, f"{label}:")
        c.setFont("Helvetica", 10)
        c.drawString(145, y, str(value))
        y -= 24
    y -= 15
    _draw_wrapped(c, f"Please evaluate patient. {case.diagnosis_text or ''} {_services(case)}", 50, y, width=500, font_size=11, leading=15)
    _synthetic_banner(c)
    c.showPage()
    _packet_page(c, case, 2, 3, "Home Health Patient Summary")
    c.showPage()
    _packet_page(c, case, 3, 3, "Physician Order")
    c.save()


def _render_agency_summary(case: SyntheticReferral, path: Path) -> None:
    c = _canvas(path)
    _page_number(c, 1, 2, case.referring_facility)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(55, PAGE_H - 55, f"{case.patient_name} ({case.patient_mrn})")
    c.drawRightString(PAGE_W - 55, PAGE_H - 55, case.referring_facility)
    y = PAGE_H - 85
    y = _section(c, y, "Patient Information", dark=True)
    _field(c, 55, y, "Medicare / Member", case.insurance_id, width=210)
    _field(c, 300, y, "Date of Birth / Sex", f"{case.patient_dob} / {case.patient_sex}", width=220)
    y -= 46
    _field(c, 55, y, "Address", case.patient_address, width=300)
    _field(c, 390, y, "Phone", case.patient_phone, width=150)
    y -= 52
    y = _section(c, y, "Insurance", dark=True)
    _field(c, 55, y, "Primary insurance", _insurance(case), width=500)
    y -= 45
    y = _section(c, y, "Current Episode", dark=True)
    _field(c, 55, y, "Primary diagnosis", case.diagnosis_text, width=370)
    _field(c, 450, y, "ICD-10", ", ".join(case.icd10_codes), width=100)
    y -= 60
    _field(c, 55, y, "Primary clinician", case.referring_provider_name, width=230)
    _field(c, 330, y, "Requested service", _services(case), width=220)
    y -= 58
    y = _section(c, y, "Emergency Contact", dark=True)
    _field(c, 55, y, "Contact", case.emergency_contact, width=500)
    y -= 45
    y = _section(c, y, "Primary Physician", dark=True)
    _field(c, 55, y, "Provider", case.referring_provider_name, width=200)
    _field(c, 280, y, "Phone", case.referring_phone, width=130)
    _field(c, 430, y, "Fax", case.referring_fax, width=130)
    _synthetic_banner(c)
    c.showPage()
    _packet_page(c, case, 2, 2, "Episode Clinical Note")
    c.save()


def _hand_font() -> str:
    name = "SyntheticHand"
    if name in pdfmetrics.getRegisteredFontNames():
        return name
    candidates = (
        Path("C:/Windows/Fonts/segoepr.ttf"),
        Path("C:/Windows/Fonts/comic.ttf"),
    )
    for path in candidates:
        if path.is_file():
            try:
                pdfmetrics.registerFont(TTFont(name, str(path)))
                return name
            except Exception:
                continue
    return "Helvetica-Oblique"


def _flatten_with_fax_artifacts(path: Path, *, seed: str) -> None:
    """Rasterize, grayscale, and lightly degrade a PDF without changing its text content."""
    import pypdfium2 as pdfium
    from PIL import Image, ImageEnhance, ImageFilter
    from reportlab.lib.utils import ImageReader

    rng = random.Random(seed)
    source = pdfium.PdfDocument(str(path))
    pages = []
    try:
        for page in source:
            image = page.render(scale=1.65).to_pil().convert("L")
            image = ImageEnhance.Contrast(image).enhance(1.12)
            if rng.random() < 0.7:
                image = image.filter(ImageFilter.GaussianBlur(radius=0.25))
            pixels = image.load()
            for _ in range(int(image.width * image.height * 0.00035)):
                x = rng.randrange(image.width)
                y = rng.randrange(image.height)
                pixels[x, y] = rng.choice((0, 35, 210, 240))
            pages.append(image)
    finally:
        source.close()

    temporary = path.with_suffix(".fax.pdf")
    c = Canvas(str(temporary), pagesize=letter, pageCompression=1)
    for image in pages:
        c.drawImage(ImageReader(image), 0, 0, width=PAGE_W, height=PAGE_H)
        c.showPage()
    c.save()
    temporary.replace(path)


RENDERERS: dict[str, Callable[[SyntheticReferral, Path], None]] = {
    "patient_chart": _render_patient_chart,
    "wcw_handwritten": _render_wcw_handwritten,
    "hospital_fax": _render_hospital_fax,
    "hospital_facesheet": _render_hospital_facesheet,
    "home_health_fax": _render_home_health_fax,
    "discharge_packet": _render_discharge_packet,
    "agency_summary": _render_agency_summary,
}
