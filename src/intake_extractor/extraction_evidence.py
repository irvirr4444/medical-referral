from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from pydantic import ValidationError

from .anthropic_json import AnthropicJsonError, call_model_for_json
from .schema import ReferralIntake


EVIDENCE_MODEL_MAX_TOKENS = 1800


SECTION_EVIDENCE_PROMPT = """You are reading a healthcare PDF to build an extraction guide for a downstream JSON extractor.

Return EXACTLY ONE JSON object with this schema:
{
  "sections": {
    "patient_demographics": string|null,
    "insurance_block": string|null,
    "referring_contact_block": string|null,
    "diagnosis_block": string|null,
    "requested_services_block": string|null
  },
  "exact_fields": {
    "patient_name": string|null,
    "patient_phone": string|null,
    "referring_phone": string|null,
    "referring_fax": string|null,
    "insurance_id": string|null
  },
  "notes": string[]
}

Rules:
- Use only evidence from the provided PDF pages.
- Keep section snippets concise and near-verbatim. They are grounding anchors, not full summaries.
- exact_fields are high-precision candidates. Copy characters exactly as shown when clear.
- If a character is unreadable or the field is not explicit, return null instead of guessing.
- patient_phone / referring_phone / referring_fax must be a single number only. Never combine multiple numbers into one value.
- For patient_phone: prefer the primary patient contact number in the demographics/contact block. If both home and mobile are listed, prefer the home/general patient number over mobile unless the document clearly marks another number as primary.
- referring_phone / referring_fax must come from the sender/referring block or fax header, not from patient, PCP, emergency contact, pharmacy, or inpatient unit sections.
- requested_services_block should contain only the order/request lines that represent requested services, therapies, tests, supplies, DME, or explicitly prescribed follow-up medications. Exclude general medication history/profile lists.
- notes should be short extraction cautions such as "multiple patient phone numbers listed" or "insurance ID partly blurry".
"""


class EvidenceSections(BaseModel):
    patient_demographics: str | None = None
    insurance_block: str | None = None
    referring_contact_block: str | None = None
    diagnosis_block: str | None = None
    requested_services_block: str | None = None


class EvidenceExactFields(BaseModel):
    patient_name: str | None = None
    patient_phone: str | None = None
    referring_phone: str | None = None
    referring_fax: str | None = None
    insurance_id: str | None = None


class ExtractionEvidenceGuide(BaseModel):
    sections: EvidenceSections = Field(default_factory=EvidenceSections)
    exact_fields: EvidenceExactFields = Field(default_factory=EvidenceExactFields)
    notes: list[str] = Field(default_factory=list)


def extract_evidence_guide(
    client: Any,
    *,
    model_name: str,
    user_content: list[dict[str, Any]],
) -> ExtractionEvidenceGuide:
    parsed = call_model_for_json(
        client,
        model_name=model_name,
        max_tokens=EVIDENCE_MODEL_MAX_TOKENS,
        system_prompt=SECTION_EVIDENCE_PROMPT,
        user_content=user_content,
        lead_text="Build a concise section/evidence guide from this PDF. Output JSON only.",
    )
    try:
        return ExtractionEvidenceGuide.model_validate(parsed)
    except ValidationError as exc:
        raise AnthropicJsonError(f"Evidence guide JSON did not validate: {exc.__class__.__name__}") from None


def prepend_evidence_guide(
    user_content: list[dict[str, Any]],
    guide: ExtractionEvidenceGuide | None,
    *,
    include_exact_fields: tuple[str, ...] = (
        "patient_name",
        "patient_phone",
        "referring_phone",
        "referring_fax",
        "insurance_id",
    ),
    include_section_fields: tuple[str, ...] = (
        "patient_demographics",
        "insurance_block",
        "referring_contact_block",
        "diagnosis_block",
        "requested_services_block",
    ),
    include_notes: bool = True,
    header: str | None = None,
) -> list[dict[str, Any]]:
    if guide is None or not _has_any_evidence(guide):
        return user_content
    return [
        {
            "type": "text",
            "text": render_evidence_guide(
                guide,
                include_exact_fields=include_exact_fields,
                include_section_fields=include_section_fields,
                include_notes=include_notes,
                header=header,
            ),
        }
    ] + user_content


def apply_evidence_guide(referral: ReferralIntake, guide: ExtractionEvidenceGuide | None) -> ReferralIntake:
    if guide is None:
        return referral

    data = referral.model_dump(mode="json")
    exact = guide.exact_fields

    if not data.get("patient_name") and exact.patient_name:
        data["patient_name"] = exact.patient_name

    if _needs_single_phone_value(data.get("patient_phone")) and exact.patient_phone:
        data["patient_phone"] = exact.patient_phone

    if _needs_single_phone_value(data.get("referring_phone")) and exact.referring_phone:
        data["referring_phone"] = exact.referring_phone

    if _needs_single_phone_value(data.get("referring_fax")) and exact.referring_fax:
        data["referring_fax"] = exact.referring_fax

    if _looks_uncertain_identifier(data.get("insurance_id")) and exact.insurance_id:
        data["insurance_id"] = exact.insurance_id

    return ReferralIntake.model_validate(data)


def needs_exact_field_evidence(referral: ReferralIntake) -> bool:
    return any(
        (
            not referral.patient_name,
            _needs_single_phone_value(referral.patient_phone),
            _needs_single_phone_value(referral.referring_phone),
            _needs_single_phone_value(referral.referring_fax),
            _looks_uncertain_identifier(referral.insurance_id),
        )
    )


def render_evidence_guide(
    guide: ExtractionEvidenceGuide,
    *,
    include_exact_fields: tuple[str, ...],
    include_section_fields: tuple[str, ...],
    include_notes: bool,
    header: str | None,
) -> str:
    lines = [
        header
        or "EVIDENCE GUIDE (extracted from the same PDF; use this only as grounded support for the targeted fields below):"
    ]
    if include_exact_fields:
        lines.append("Exact fields:")
        for field in include_exact_fields:
            value = getattr(guide.exact_fields, field, None)
            lines.append(f"- {field}: {_fmt_value(value)}")

    if include_section_fields:
        lines.append("Section anchors:")
        for field in include_section_fields:
            value = getattr(guide.sections, field, None)
            lines.append(f"- {field}: {_fmt_value(value)}")

    if include_notes and guide.notes:
        lines.append("Cautions:")
        for note in guide.notes:
            cleaned = " ".join(str(note).split())
            if cleaned:
                lines.append(f"- {cleaned}")

    lines.append("Use policy:")
    lines.append("- Verify against the PDF pages. Treat these anchors as support for the targeted fields only, not as a replacement for the source.")
    if include_exact_fields:
        lines.append(
            "- For the listed exact fields: copy exact characters from the matching block when clear; prefer the existing extracted value over a guess."
        )
    if any(field == "requested_services_block" for field in include_section_fields):
        lines.append(
            "- For requested_services: use requested_services_block as the primary boundary and exclude unrelated medication history or admin routing text."
        )
    if any(field in {"patient_demographics", "referring_contact_block"} for field in include_section_fields):
        lines.append(
            "- For contact fields: prefer the demographics block for patient phone and the sender/referrer block for referring phone/fax."
        )
    return "\n".join(lines)


def _fmt_value(value: str | None) -> str:
    if value is None:
        return "null"
    cleaned = " ".join(str(value).split())
    return cleaned or "null"


def _has_any_evidence(guide: ExtractionEvidenceGuide) -> bool:
    return any(
        value
        for value in (
            guide.exact_fields.patient_name,
            guide.exact_fields.patient_phone,
            guide.exact_fields.referring_phone,
            guide.exact_fields.referring_fax,
            guide.exact_fields.insurance_id,
            guide.sections.patient_demographics,
            guide.sections.insurance_block,
            guide.sections.referring_contact_block,
            guide.sections.diagnosis_block,
            guide.sections.requested_services_block,
            *guide.notes,
        )
    )


def _needs_single_phone_value(value: str | None) -> bool:
    if not value:
        return True
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) != 10:
        return True
    lowered = str(value).lower()
    if any(token in lowered for token in ("home", "mobile", "cell", "work", "/", ";", ",")):
        return True
    return len(set(digits)) == 1


def _looks_uncertain_identifier(value: str | None) -> bool:
    if not value:
        return True
    cleaned = str(value).strip()
    return any(ch in cleaned for ch in "#?*") or not any(ch.isdigit() for ch in cleaned)
