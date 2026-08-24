"""Deterministic review-email rendering from canonical destination artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Any


NOT_DOCUMENTED = "Not documented"
NO_KNOWN_ALLERGIES = "No known allergies"
CLINICAL_SUMMARY_MAX_CHARS = 320
CLINICAL_SUMMARY_MAX_SENTENCES = 2
PARTNER_CONTACT_ACTION_TITLE = "Referral Partner Follow-up"
PARTNER_CONTACT_ACTION_COPY = (
    "Please contact the referral partner to acknowledge receipt and resolve any missing or "
    "unclear information. Reply Confirmed when contact is complete, No answer when outreach "
    "was unsuccessful, or Information missing with the remaining gap. Reply with corrected "
    "referral details when changes are required."
)
REVIEW_ACTION_TITLE = "Referral Review"
REVIEW_ACTION_COPY = (
    "Please review the referral summary. Reply Confirm if the information is accurate, "
    "or reply with the corrected information."
)


@dataclass(frozen=True)
class ReviewEmail:
    subject: str
    html_body: str
    text_body: str
    content_type: str = "HTML"


@dataclass(frozen=True)
class AttentionItem:
    label: str
    detail: str


@dataclass(frozen=True)
class PatientView:
    name: str
    date_of_birth: str
    phone: str
    address: str


@dataclass(frozen=True)
class InsuranceView:
    payer_name: str
    policy_number: str
    group_number: str


@dataclass(frozen=True)
class DiagnosisView:
    code: str
    description: str


@dataclass(frozen=True)
class MedicationView:
    name: str
    strength: str
    directions: str


@dataclass(frozen=True)
class DuplicateView:
    name: str
    date_of_birth: str
    phone: str
    address: str


@dataclass(frozen=True)
class ReviewPresentation:
    patient_heading: str
    attention: list[AttentionItem]
    patient: PatientView
    referring_organization: str
    home_health_or_hospice: str
    requested_services: list[str]
    insurances: list[InsuranceView]
    diagnoses: list[DiagnosisView]
    medications: list[MedicationView]
    allergies_label: str
    allergies: list[str]
    clinical_summary: str
    duplicate: DuplicateView | None
    approval_allowed: bool
    review_id: str
    token: str
    purpose: str = "destination_write"


def render_review_email(
    *,
    review_id: str,
    token: str,
    canonical_path: str | Path,
    intake_plan_path: str | Path,
    monday_preview_path: str | Path,
    drk_draft_path: str | Path,
    write_config_path: str | Path,
    approval_allowed: bool = True,
    purpose: str = "destination_write",
) -> ReviewEmail:
    del monday_preview_path, drk_draft_path, write_config_path
    canonical = _load(canonical_path)
    intake_plan = _load(intake_plan_path)
    presentation = build_presentation(
        canonical,
        duplicate_check=intake_plan.get("monday_duplicate_check") or {},
        review_id=review_id,
        token=token,
        approval_allowed=approval_allowed,
        purpose=purpose,
    )
    return ReviewEmail(
        subject=(
            f"Referral Follow-up: {presentation.patient_heading}"
            if purpose == "partner_contact"
            else f"Referral Review: {presentation.patient_heading}"
        ),
        html_body=render_html(presentation),
        text_body=render_text(presentation),
        content_type="HTML",
    )


def build_presentation(
    canonical: dict[str, Any],
    *,
    duplicate_check: dict[str, Any] | None = None,
    review_id: str,
    token: str,
    approval_allowed: bool,
    purpose: str = "destination_write",
) -> ReviewPresentation:
    patient = canonical.get("patient") or {}
    name = patient.get("name") or {}
    address = patient.get("address") or {}
    source = canonical.get("referral_source") or {}
    source_org = source.get("organization") or {}
    hh = (canonical.get("home_health_or_hospice") or {}).get("organization") or {}
    clinical = canonical.get("clinical") or {}
    field_quality = canonical.get("field_quality") or {}
    phones = patient.get("phones") or []
    insurances = [
        InsuranceView(
            payer_name=_display(item.get("payer_name")),
            policy_number=_display(item.get("policy_number")),
            group_number=_display(item.get("group_number")),
        )
        for item in canonical.get("insurances") or []
        if isinstance(item, dict)
    ]
    diagnoses = [
        DiagnosisView(
            code=_display(item.get("code")),
            description=_display(item.get("description")),
        )
        for item in clinical.get("diagnoses") or []
        if isinstance(item, dict)
    ]
    medications = [
        MedicationView(
            name=_display(item.get("name")),
            strength=_display(item.get("strength")),
            directions=_display(item.get("directions")),
        )
        for item in clinical.get("medications") or []
        if isinstance(item, dict)
    ]
    services = [
        _join_parts(item.get("service"), item.get("frequency"), item.get("instructions"))
        for item in canonical.get("requested_services") or []
        if isinstance(item, dict)
    ]
    services = [value for value in services if value]
    allergies_label, allergies = _allergies(clinical, field_quality)
    referring = _display(source_org.get("name"))
    home_health = _display(hh.get("name"))
    requested = services or [NOT_DOCUMENTED]
    duplicate = _duplicate_view(duplicate_check or {})
    attention = _attention_items(
        referring_organization=referring,
        home_health_or_hospice=home_health,
        requested_services=requested,
        allergies_label=allergies_label,
        patient_name=_patient_name(name),
        date_of_birth=_human_date(patient.get("date_of_birth")),
        phone=_phone(phones),
        address=_address(address),
        insurances=insurances,
        duplicate=duplicate,
    )
    return ReviewPresentation(
        patient_heading=_patient_name(name),
        attention=attention,
        patient=PatientView(
            name=_patient_name(name),
            date_of_birth=_human_date(patient.get("date_of_birth")),
            phone=_phone(phones),
            address=_address(address),
        ),
        referring_organization=referring,
        home_health_or_hospice=home_health,
        requested_services=requested,
        insurances=insurances,
        diagnoses=diagnoses,
        medications=medications,
        allergies_label=allergies_label,
        allergies=allergies,
        clinical_summary=_short_clinical_summary(clinical.get("summary")),
        duplicate=duplicate,
        approval_allowed=approval_allowed,
        review_id=review_id,
        token=token,
        purpose=purpose,
    )


def render_html(presentation: ReviewPresentation) -> str:
    sections = [
        _html_title(presentation),
        _html_attention(presentation.attention),
        _html_patient(presentation),
        _html_section("Insurance", _html_insurance(presentation.insurances)),
        _html_section(
            f"Diagnoses ({len(presentation.diagnoses)})",
            _html_diagnoses(presentation.diagnoses),
        ),
        _html_section(
            f"Medications ({len(presentation.medications)})",
            _html_medications(presentation.medications),
        ),
        _html_section("Allergies", _html_allergies(presentation)),
        _html_section("Clinical summary", _html_paragraph(presentation.clinical_summary)),
        _html_action(presentation),
    ]
    body = "".join(section for section in sections if section)
    return (
        '<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f5f7fa;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background:#f5f7fa;padding:16px 0;">'
        '<tr><td align="center">'
        '<table role="presentation" width="640" cellpadding="0" cellspacing="0" '
        'style="width:640px;max-width:100%;background:#ffffff;border:1px solid #d9e2ec;'
        'border-radius:8px;font-family:Arial,Helvetica,sans-serif;color:#102a43;'
        'font-size:14px;line-height:1.5;">'
        f"{body}"
        "</table></td></tr></table></body></html>"
    )


def render_text(presentation: ReviewPresentation) -> str:
    lines = [
        f"{_message_title(presentation)}: {presentation.patient_heading}",
        "",
    ]
    if presentation.attention:
        lines.extend(["Needs attention", ""])
        for item in presentation.attention:
            lines.append(f"- {item.label}: {item.detail}")
            lines.append("")
    lines.extend(
        [
            "Patient",
            "",
            f"Name: {presentation.patient.name}",
            "",
            f"DOB: {presentation.patient.date_of_birth}",
            "",
            f"Phone: {presentation.patient.phone}",
            "",
            f"Address: {presentation.patient.address}",
            "",
            f"Referring organization: {presentation.referring_organization}",
            "",
            f"Home health/hospice: {presentation.home_health_or_hospice}",
            "",
            "Requested services:",
            "",
        ]
    )
    for service in presentation.requested_services:
        lines.append(f"- {service}")
        lines.append("")
    lines.extend(["Insurance", ""])
    if presentation.insurances:
        for item in presentation.insurances:
            policy = item.policy_number if item.policy_number != NOT_DOCUMENTED else ""
            group = f" / Group: {item.group_number}" if item.group_number != NOT_DOCUMENTED else ""
            detail = f" — Policy: {policy}{group}" if policy or group else ""
            lines.append(f"- {item.payer_name}{detail}")
            lines.append("")
    else:
        lines.extend([f"- {NOT_DOCUMENTED}", ""])
    lines.extend([f"Diagnoses ({len(presentation.diagnoses)})", ""])
    if presentation.diagnoses:
        for item in presentation.diagnoses:
            label = f"{item.code} — {item.description}" if item.code != NOT_DOCUMENTED else item.description
            lines.append(f"- {label}")
            lines.append("")
    else:
        lines.extend([f"- {NOT_DOCUMENTED}", ""])
    lines.extend([f"Medications ({len(presentation.medications)})", ""])
    if presentation.medications:
        for item in presentation.medications:
            heading = item.name if item.strength == NOT_DOCUMENTED else f"{item.name}, {item.strength}"
            lines.append(f"- {heading}")
            lines.append(f"  {item.directions}")
            lines.append("")
    else:
        lines.extend([f"- {NOT_DOCUMENTED}", ""])
    lines.extend(["Allergies", "", presentation.allergies_label, ""])
    if presentation.allergies and presentation.allergies_label not in {NO_KNOWN_ALLERGIES, NOT_DOCUMENTED}:
        for item in presentation.allergies:
            lines.append(f"- {item}")
            lines.append("")
    lines.extend(["Clinical summary", "", presentation.clinical_summary, ""])
    lines.extend(
        [
            "----------------------------------------",
            "",
            _action_title(presentation),
            "",
            _action_copy(presentation),
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _attention_items(
    *,
    referring_organization: str,
    home_health_or_hospice: str,
    requested_services: list[str],
    allergies_label: str,
    patient_name: str,
    date_of_birth: str,
    phone: str,
    address: str,
    insurances: list[InsuranceView],
    duplicate: DuplicateView | None,
) -> list[AttentionItem]:
    items: list[AttentionItem] = []
    if duplicate is not None:
        items.append(
            AttentionItem(
                label="Duplicate patient in Monday",
                detail=(
                    f"Name: {duplicate.name}; DOB: {duplicate.date_of_birth}; "
                    f"Phone: {duplicate.phone}; Address: {duplicate.address}"
                ),
            )
        )
    checks = (
        ("Patient name", patient_name),
        ("Date of birth", date_of_birth),
        ("Phone", phone),
        ("Address", address),
        ("Referring organization", referring_organization),
        ("Home health/hospice", home_health_or_hospice),
    )
    for label, value in checks:
        if value == NOT_DOCUMENTED:
            items.append(AttentionItem(label=label, detail=NOT_DOCUMENTED))
    if requested_services == [NOT_DOCUMENTED]:
        items.append(AttentionItem(label="Requested services", detail=NOT_DOCUMENTED))
    if allergies_label == NOT_DOCUMENTED:
        items.append(
            AttentionItem(
                label="Allergies",
                detail=f"{NOT_DOCUMENTED} — no NKA/NKDA statement found",
            )
        )
    if not insurances:
        items.append(AttentionItem(label="Insurance", detail=NOT_DOCUMENTED))
    return items


def _duplicate_view(duplicate_check: dict[str, Any]) -> DuplicateView | None:
    if duplicate_check.get("status") != "duplicate_found":
        return None
    candidates = duplicate_check.get("candidates") or []
    if not candidates or not isinstance(candidates[0], dict):
        return None
    fields = candidates[0].get("fields") or {}
    if not isinstance(fields, dict):
        return None
    return DuplicateView(
        name=_display(fields.get("name")),
        date_of_birth=_human_date(fields.get("dob")),
        phone=_display(fields.get("patient_phone")),
        address=_display(fields.get("patient_address")),
    )


def _allergies(clinical: dict[str, Any], field_quality: dict[str, Any]) -> tuple[str, list[str]]:
    allergies = clinical.get("allergies") or []
    quality = field_quality.get("clinical.allergies") or field_quality.get("allergies") or {}
    quality_status = str(quality.get("status") or "")
    if clinical.get("no_known_allergies_explicit") or quality_status == "explicitly_none":
        return NO_KNOWN_ALLERGIES, []
    if allergies:
        values = []
        for item in allergies:
            if not isinstance(item, dict):
                continue
            values.append(_join_parts(item.get("name"), item.get("reaction"), item.get("treatment")))
        values = [value for value in values if value]
        if values:
            return "Documented allergies", values
    if clinical.get("allergies_section_present") is False or quality_status in {"missing", "unclear", ""}:
        return NOT_DOCUMENTED, []
    return NOT_DOCUMENTED, []


def _patient_name(name: dict[str, Any]) -> str:
    first = _clean_name_part(name.get("first"))
    middle = _clean_name_part(name.get("middle"))
    last = _clean_name_part(name.get("last"))
    structured = " ".join(part for part in (first, middle, last) if part)
    if structured:
        return structured
    full = str(name.get("full") or "").strip()
    if not full:
        return NOT_DOCUMENTED
    if "," in full:
        last_part, first_part = [part.strip() for part in full.split(",", 1)]
        rebuilt = " ".join(part for part in (_clean_name_part(first_part), _clean_name_part(last_part)) if part)
        return rebuilt or full
    return full


def _clean_name_part(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.isupper() or text.islower():
        return text.title()
    return text


def _human_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return NOT_DOCUMENTED
    for parser in (date.fromisoformat, lambda raw: datetime.fromisoformat(raw).date()):
        try:
            parsed = parser(text)
            return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"
        except ValueError:
            continue
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        try:
            parsed = date(year, month, day)
            return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"
        except ValueError:
            return text
    return text


def _phone(phones: list[Any]) -> str:
    numbers = [str(item.get("number") or "").strip() for item in phones if isinstance(item, dict)]
    numbers = [number for number in numbers if number]
    return numbers[0] if numbers else NOT_DOCUMENTED


def _address(address: dict[str, Any]) -> str:
    city = _titleish(address.get("city"))
    state = str(address.get("state") or "").strip().upper()
    postal = str(address.get("postal_code") or "").strip()
    parts = [
        _titleish(address.get("line_1")),
        _titleish(address.get("line_2")),
        ", ".join(part for part in (city, state) if part),
        postal,
    ]
    value = ", ".join(part for part in parts if part)
    return value or NOT_DOCUMENTED


def _titleish(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.isupper() or text.islower():
        return text.title()
    return text


def _display(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else NOT_DOCUMENTED


def _short_clinical_summary(value: Any) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return NOT_DOCUMENTED
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if sentence.strip()
    ]
    shortened = " ".join(sentences[:CLINICAL_SUMMARY_MAX_SENTENCES])
    if len(shortened) <= CLINICAL_SUMMARY_MAX_CHARS:
        return shortened
    boundary = shortened.rfind(" ", 0, CLINICAL_SUMMARY_MAX_CHARS - 1)
    cutoff = boundary if boundary > CLINICAL_SUMMARY_MAX_CHARS // 2 else CLINICAL_SUMMARY_MAX_CHARS - 1
    return shortened[:cutoff].rstrip(" ,;:-") + "…"


def _join_parts(*values: Any) -> str:
    return " / ".join(str(value).strip() for value in values if value not in (None, ""))


def _html_title(presentation: ReviewPresentation) -> str:
    return (
        '<tr><td style="padding:20px 24px 8px 24px;">'
        f'<div style="font-size:20px;font-weight:bold;color:#102a43;">'
        f'{escape(_message_title(presentation))}: {escape(presentation.patient_heading)}</div>'
        "</td></tr>"
    )


def _message_title(presentation: ReviewPresentation) -> str:
    return "Referral Follow-up" if presentation.purpose == "partner_contact" else "Referral Review"


def _html_attention(items: list[AttentionItem]) -> str:
    if not items:
        return ""
    rows = "".join(
        '<tr><td style="padding:4px 0;color:#9b1c1c;">'
        f"<strong>{escape(item.label)}:</strong> {escape(item.detail)}"
        "</td></tr>"
        for item in items
    )
    return (
        '<tr><td style="padding:8px 24px 16px 24px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background:#fff5f5;border:1px solid #f5c2c7;border-radius:6px;">'
        '<tr><td style="padding:12px 16px;">'
        '<div style="font-weight:bold;color:#9b1c1c;margin-bottom:8px;">Needs attention</div>'
        f"<table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\">{rows}</table>"
        "</td></tr></table></td></tr>"
    )


def _html_patient(presentation: ReviewPresentation) -> str:
    details = [
        ("Name", presentation.patient.name),
        ("DOB", presentation.patient.date_of_birth),
        ("Phone", presentation.patient.phone),
        ("Address", presentation.patient.address),
        ("Referring organization", presentation.referring_organization),
        ("Home health/hospice", presentation.home_health_or_hospice),
        ("Requested services", "; ".join(presentation.requested_services)),
    ]
    rows = "".join(
        "<tr>"
        f'<td style="width:40%;padding:6px 12px 6px 0;color:#627d98;vertical-align:top;">{escape(label)}</td>'
        f'<td style="padding:6px 0;color:#102a43;vertical-align:top;"><strong>{escape(value)}</strong></td>'
        "</tr>"
        for label, value in details
    )
    return _html_section("Patient", f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table>')


def _html_insurance(items: list[InsuranceView]) -> str:
    if not items:
        return _html_paragraph(NOT_DOCUMENTED)
    rows = []
    for item in items:
        meta = []
        if item.policy_number != NOT_DOCUMENTED:
            meta.append(f"Policy: {escape(item.policy_number)}")
        if item.group_number != NOT_DOCUMENTED:
            meta.append(f"Group: {escape(item.group_number)}")
        detail = f'<div style="color:#627d98;font-size:13px;">{ " · ".join(meta)}</div>' if meta else ""
        rows.append(
            f'<div style="padding:6px 0;border-bottom:1px solid #e2e8f0;">'
            f"<strong>{escape(item.payer_name)}</strong>{detail}</div>"
        )
    return "".join(rows)


def _html_diagnoses(items: list[DiagnosisView]) -> str:
    if not items:
        return _html_paragraph(NOT_DOCUMENTED)
    bullets = []
    for item in items:
        label = (
            f"<strong>{escape(item.code)}</strong> — {escape(item.description)}"
            if item.code != NOT_DOCUMENTED
            else escape(item.description)
        )
        bullets.append(f'<li style="margin:0 0 8px 0;">{label}</li>')
    return f'<ul style="margin:0;padding-left:18px;">{"".join(bullets)}</ul>'


def _html_medications(items: list[MedicationView]) -> str:
    if not items:
        return _html_paragraph(NOT_DOCUMENTED)
    rows = [
        '<tr style="background:#f0f4f8;color:#486581;">'
        '<th align="left" style="padding:8px;border-bottom:1px solid #d9e2ec;">Medication</th>'
        '<th align="left" style="padding:8px;border-bottom:1px solid #d9e2ec;">Strength</th>'
        '<th align="left" style="padding:8px;border-bottom:1px solid #d9e2ec;">Directions</th>'
        "</tr>"
    ]
    for item in items:
        rows.append(
            "<tr>"
            f'<td style="padding:8px;border-bottom:1px solid #e2e8f0;vertical-align:top;">{escape(item.name)}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #e2e8f0;vertical-align:top;">{escape(item.strength)}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #e2e8f0;vertical-align:top;">{escape(item.directions)}</td>'
            "</tr>"
        )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;">'
        f"{''.join(rows)}</table>"
    )


def _html_allergies(presentation: ReviewPresentation) -> str:
    if presentation.allergies_label in {NO_KNOWN_ALLERGIES, NOT_DOCUMENTED}:
        return _html_paragraph(presentation.allergies_label)
    return _html_bullets(presentation.allergies)


def _html_action(_presentation: ReviewPresentation) -> str:
    content = f"<div>{escape(_action_copy(_presentation))}</div>"
    return (
        '<tr><td style="padding:8px 24px 24px 24px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background:#f0f4f8;border:1px solid #d9e2ec;border-radius:6px;">'
        '<tr><td style="padding:14px 16px;">'
        f'<div style="font-weight:bold;margin-bottom:8px;">{escape(_action_title(_presentation))}</div>'
        f"{content}</td></tr></table></td></tr>"
    )


def _action_title(presentation: ReviewPresentation) -> str:
    return (
        PARTNER_CONTACT_ACTION_TITLE
        if presentation.purpose == "partner_contact"
        else REVIEW_ACTION_TITLE
    )


def _action_copy(presentation: ReviewPresentation) -> str:
    return (
        PARTNER_CONTACT_ACTION_COPY
        if presentation.purpose == "partner_contact"
        else REVIEW_ACTION_COPY
    )


def _html_section(title: str, content: str) -> str:
    if not content:
        return ""
    return (
        '<tr><td style="padding:8px 24px 16px 24px;">'
        f'<div style="font-size:15px;font-weight:bold;color:#243b53;margin-bottom:8px;">{escape(title)}</div>'
        f"{content}</td></tr>"
    )


def _html_paragraph(value: str) -> str:
    return f'<div style="color:#102a43;">{escape(value)}</div>'


def _html_bullets(values: list[str]) -> str:
    if not values:
        return _html_paragraph(NOT_DOCUMENTED)
    items = "".join(f'<li style="margin:0 0 8px 0;">{escape(value)}</li>' for value in values)
    return f'<ul style="margin:0;padding-left:18px;">{items}</ul>'


def _load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value
