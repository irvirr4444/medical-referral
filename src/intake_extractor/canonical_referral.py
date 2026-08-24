"""Canonical, destination-neutral extraction of one referral PDF.

This is the only module that asks an LLM to interpret a referral PDF. Monday,
DRK, inbox, and future integrations must project from ``CanonicalReferral``.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .llm.anthropic_json import AnthropicJsonError, build_client, parse_json_from_message
from .llm.reliability import (
    CapacityExhaustedError,
    ExtractionAudit,
    call_with_model_fallback,
    resolve_model_chain,
)


DEFAULT_MAX_TOKENS = 32_000
DEFAULT_MODEL = "claude-opus-5"
DEFAULT_EFFORT = "max"
DEFAULT_PDF_TRANSPORT = "files-api"
MAX_INLINE_PDF_BYTES = 23 * 1024 * 1024
FILES_API_BETA = "files-api-2025-04-14"
CLINICAL_SUMMARY_MAX_CHARS = 240
_WOUND_TERMS = (
    "pressure ulcer",
    "pressure injury",
    "wound",
    "ulcer",
    "cellulitis",
)
_FORM_CHROME_CLAUSE = re.compile(
    r"(?i)^(type of care needed|care needed|care type|service(?:s)? needed)\b"
)
FieldStatus = Literal["present", "explicitly_none", "missing", "unclear"]
Confidence = Literal["high", "medium", "low"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CanonicalExtractionError(RuntimeError):
    pass


class CanonicalExtractionAudit(StrictModel):
    primary_model: str
    models_attempted: list[str] = Field(default_factory=list)
    pass_models: list[str] = Field(default_factory=list)
    fallback_used: bool = False


class CanonicalSource(StrictModel):
    email_id: str | None = None
    attachment_id: str | None = None
    file_name: str
    pdf_sha256: str
    page_count: int | None = None
    sent_by: str | None = None
    extraction: CanonicalExtractionAudit | None = None


class CanonicalName(StrictModel):
    first: str | None = None
    middle: str | None = None
    last: str | None = None
    suffix: str | None = None
    full: str | None = None


class CanonicalAddress(StrictModel):
    line_1: str | None = None
    line_2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None


class CanonicalPhone(StrictModel):
    number: str
    type: str | None = None


class CanonicalEmergencyContact(StrictModel):
    name: CanonicalName = Field(default_factory=CanonicalName)
    relationship: str | None = None
    phone: str | None = None


class CanonicalPatient(StrictModel):
    name: CanonicalName = Field(default_factory=CanonicalName)
    date_of_birth: str | None = None
    age: int | None = None
    sex_or_gender: str | None = None
    ssn: str | None = None
    mrn: str | None = None
    source_patient_id: str | None = None
    source_patient_id_label: str | None = None
    phones: list[CanonicalPhone] = Field(default_factory=list)
    email: str | None = None
    address: CanonicalAddress = Field(default_factory=CanonicalAddress)
    emergency_contact: CanonicalEmergencyContact | None = None


class CanonicalOrganization(StrictModel):
    name: str | None = None
    contact_name: str | None = None
    phone: str | None = None
    fax: str | None = None
    email: str | None = None
    address: str | None = None


class CanonicalReferralSource(StrictModel):
    organization: CanonicalOrganization = Field(default_factory=CanonicalOrganization)
    provider_name: str | None = None
    referral_or_order_date: str | None = None


class CanonicalHomeHealthOrHospice(StrictModel):
    organization: CanonicalOrganization = Field(default_factory=CanonicalOrganization)
    hospice: bool | None = None
    palliative_care: bool | None = None


class CanonicalAdmission(StrictModel):
    admission_date: str | None = None
    facility: CanonicalOrganization = Field(default_factory=CanonicalOrganization)
    place_of_service: str | None = None
    medicare_admission: bool | None = None


class CanonicalDiagnosis(StrictModel):
    code: str | None = None
    description: str | None = None
    added_date: str | None = None
    is_primary: bool | None = None
    status: str | None = None


class CanonicalMedication(StrictModel):
    name: str | None = None
    strength: str | None = None
    dose_form: str | None = None
    directions: str | None = None
    status: str | None = None
    prescribed_date: str | None = None
    prescriber: str | None = None
    days_supply: int | None = None
    quantity: str | None = None
    refills: int | None = None


class CanonicalAllergy(StrictModel):
    name: str | None = None
    reaction: str | None = None
    treatment: str | None = None
    status: str | None = None


class CanonicalClinical(StrictModel):
    summary: str | None = Field(
        default=None,
        max_length=CLINICAL_SUMMARY_MAX_CHARS,
        description=(
            "One short wound or reason-for-referral line copied from the PDF "
            "(wound type, site, and stage). Include an ICD code only when the PDF "
            "prints it. Do not write hospital course, care team, start-of-care dates, "
            "or non-wound comorbidity lists."
        ),
    )
    wound_order_included: bool | None = None
    diagnoses: list[CanonicalDiagnosis] = Field(default_factory=list)
    medications: list[CanonicalMedication] = Field(default_factory=list)
    allergies: list[CanonicalAllergy] = Field(default_factory=list)
    diagnoses_section_present: bool | None = None
    medications_section_present: bool | None = None
    allergies_section_present: bool | None = None
    no_known_allergies_explicit: bool | None = None
    notes: list[str] = Field(default_factory=list)


class CanonicalInsurance(StrictModel):
    payer_name: str | None = None
    policy_number: str | None = None
    group_number: str | None = None
    group_name: str | None = None
    policy_holder_name: str | None = None
    insurance_type: Literal["Primary", "Secondary", "Tertiary", "Other"] | None = None
    effective_date: str | None = None
    expiration_date: str | None = None
    is_patient_policy_holder: bool | None = None
    subscriber_first_name: str | None = None
    subscriber_last_name: str | None = None
    subscriber_date_of_birth: str | None = None
    subscriber_relationship: str | None = None


class CanonicalRequestedService(StrictModel):
    service: str | None = None
    frequency: str | None = None
    instructions: str | None = None


class CanonicalFieldQuality(StrictModel):
    status: FieldStatus
    confidence: Confidence
    evidence_pages: list[int] = Field(default_factory=list)
    evidence_quote: str | None = None


class CanonicalReferral(StrictModel):
    schema_version: int = 1
    referral_id: str
    source: CanonicalSource
    document_type: str | None = None
    patient: CanonicalPatient = Field(default_factory=CanonicalPatient)
    referral_source: CanonicalReferralSource = Field(default_factory=CanonicalReferralSource)
    home_health_or_hospice: CanonicalHomeHealthOrHospice = Field(default_factory=CanonicalHomeHealthOrHospice)
    admission: CanonicalAdmission = Field(default_factory=CanonicalAdmission)
    clinical: CanonicalClinical = Field(default_factory=CanonicalClinical)
    insurances: list[CanonicalInsurance] = Field(default_factory=list)
    requested_services: list[CanonicalRequestedService] = Field(default_factory=list)
    field_quality: dict[str, CanonicalFieldQuality] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


SYSTEM_PROMPT = """You extract one complete, destination-neutral referral record from a medical PDF.

The PDF is the only authority. Inspect every page and extract every explicitly supported demographic,
referral-source, home-health/hospice, admission, clinical, diagnosis, medication, allergy, insurance,
requested-service, and order fact. Never tailor the result to Monday.com or DRK and never omit a fact
because a destination lacks a dedicated field.

Accuracy rules:
- Never guess, autocomplete, or turn a patient/account ID into an MRN.
- Keep the referring organization separate from the patient's current home-health/hospice organization.
- Preserve all distinct diagnoses, medications, allergies, insurance policies, and requested services.
- Do not infer insurance order from display order.
- An empty section means missing unless the PDF explicitly says none/NKA/NKDA.
- Dates should be ISO YYYY-MM-DD when unambiguous; otherwise preserve the source text.
- Clinical summary is one short wound or reason-for-referral line copied from the PDF (wound type, site, and stage). Include an ICD code only when the PDF prints it. Do not write hospital course, care team, start-of-care dates, or a comorbidity dump.
- field_quality keys are dot paths. Use present, explicitly_none, missing, or unclear. Include direct
  one-indexed evidence pages for present/explicitly_none values and calibrated confidence.
- At minimum assess: patient.name, patient.date_of_birth, patient.phones, patient.address,
  home_health_or_hospice, clinical, and insurances.
- Use warnings for contradictions, illegibility, truncation, or ambiguity.
"""

FIRST_READING = """Read the entire PDF once and return the complete canonical referral record.
The source metadata and referral ID supplied below are operational values, not facts to infer."""

VERIFICATION = """Independently verify the candidate against the entire PDF. Correct transcription errors,
unsupported inferences, omissions, organization-role conflation, missing list rows, and field-quality states.
Return one corrected complete canonical record. Do not summarize away data."""


def _native_pdf_block(pdf: Path) -> dict[str, Any]:
    if pdf.stat().st_size > MAX_INLINE_PDF_BYTES:
        raise CanonicalExtractionError("PDF is too large for inline transport; use the default Files API.")
    return {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": base64.standard_b64encode(pdf.read_bytes()).decode("ascii"),
        },
    }


def _upload_pdf_block(client: Any, pdf: Path) -> tuple[dict[str, Any], str]:
    try:
        with pdf.open("rb") as handle:
            uploaded = client.beta.files.upload(file=(pdf.name, handle, "application/pdf"))
    except Exception as exc:
        raise CanonicalExtractionError(f"Anthropic Files API upload failed: {exc}") from exc
    file_id = getattr(uploaded, "id", None)
    if not file_id:
        raise CanonicalExtractionError("Anthropic Files API upload returned no file ID")
    return {"type": "document", "source": {"type": "file", "file_id": str(file_id)}}, str(file_id)


def _page_count(pdf: Path) -> int:
    import pdfplumber

    with pdfplumber.open(str(pdf)) as document:
        return len(document.pages)


def _validate_structured_output(
    output_format: type[CanonicalReferral],
    parsed: Any,
) -> CanonicalReferral:
    """Drop schema-unknown LLM keys while preserving strict validation.

    Anthropic can occasionally emit a plausible but unsupported key despite
    receiving the JSON Schema. Unknown keys should not invalidate otherwise
    valid patient data, but all errors involving known fields remain fatal.
    """
    if isinstance(parsed, output_format):
        return parsed
    try:
        return output_format.model_validate(parsed)
    except ValidationError as error:
        if not isinstance(parsed, dict):
            raise
        cleaned = deepcopy(parsed)
        removed: list[str] = []
        for issue in error.errors():
            if issue.get("type") != "extra_forbidden":
                continue
            location = tuple(issue.get("loc") or ())
            if location and _remove_unknown_path(cleaned, location):
                removed.append(".".join(str(part) for part in location))
        if not removed:
            raise
        validated = output_format.model_validate(cleaned)
        validated.warnings.extend(
            f"Ignored unsupported extractor field: {path}" for path in sorted(set(removed))
        )
        return validated


def _remove_unknown_path(payload: Any, location: tuple[Any, ...]) -> bool:
    current = payload
    for part in location[:-1]:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and isinstance(part, int) and 0 <= part < len(current):
            current = current[part]
        else:
            return False
    final = location[-1]
    if isinstance(current, dict) and final in current:
        del current[final]
        return True
    if isinstance(current, list) and isinstance(final, int) and 0 <= final < len(current):
        del current[final]
        return True
    return False


def _call_structured_extractor(
    client: Any,
    *,
    output_format: type[CanonicalReferral],
    models: Sequence[str],
    effort: str,
    max_tokens: int,
    system_prompt: str,
    content: list[dict[str, Any]],
    progress: Callable[[str], None] | None = None,
    sleep: Callable[[float], None] | None = None,
    random_source: Callable[[], float] | None = None,
) -> tuple[CanonicalReferral, str]:
    schema_prompt = (
        f"{system_prompt}\n\nReturn exactly one RFC 8259 JSON object matching this JSON Schema. "
        f"Do not add markdown or commentary:\n{json.dumps(output_format.model_json_schema(), ensure_ascii=False)}"
    )
    last_error: Exception | None = None
    for validation_attempt in range(2):
        attempt_content = list(content)
        if validation_attempt:
            attempt_content.append(
                {"type": "text", "text": f"Return fresh valid JSON. Previous validation error: {last_error}"}
            )
        try:

            def _invoke(model: str) -> CanonicalReferral:
                kwargs = {
                    "model": model,
                    "max_tokens": max_tokens,
                    "system": schema_prompt,
                    "messages": [{"role": "user", "content": attempt_content}],
                    "output_config": {"effort": effort},
                    "thinking": {"type": "adaptive"},
                }
                uses_file = content[0].get("source", {}).get("type") == "file"
                manager = (
                    client.beta.messages.stream(**kwargs, betas=[FILES_API_BETA])
                    if uses_file
                    else client.messages.stream(**kwargs)
                )
                with manager as stream:
                    message = stream.get_final_message()
                if message is None:
                    raise CanonicalExtractionError("Anthropic returned no message")
                parsed = getattr(message, "parsed_output", None) or parse_json_from_message(message)
                return _validate_structured_output(output_format, parsed)

            result, audit = call_with_model_fallback(
                _invoke,
                models=models,
                progress=progress,
                sleep=sleep or __import__("time").sleep,
                random_source=random_source,
            )
            return result, audit.model
        except (AnthropicJsonError, ValidationError) as exc:
            last_error = exc
        except CapacityExhaustedError as exc:
            raise CanonicalExtractionError(str(exc)) from exc
        except Exception as exc:
            raise CanonicalExtractionError(f"Anthropic extraction failed: {exc}") from exc
    raise CanonicalExtractionError(f"Anthropic output failed JSON/schema validation twice: {last_error}")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    os.chmod(path, 0o600)


def extract_referral_pdf(
    pdf_path: str | Path,
    *,
    email_id: str | None = None,
    attachment_id: str | None = None,
    sent_by: str | None = None,
    model: str | None = None,
    fallback_models: Sequence[str] | None = None,
    effort: str | None = None,
    max_tokens: int | None = None,
    pdf_transport: str | None = None,
    client: Any | None = None,
    progress: Callable[[str], None] | None = None,
    sleep: Callable[[float], None] | None = None,
    random_source: Callable[[], float] | None = None,
) -> CanonicalReferral:
    """Interpret a PDF exactly twice: initial extraction, then source verification."""
    pdf = Path(pdf_path)
    if not pdf.is_file():
        raise CanonicalExtractionError(f"PDF not found: {pdf}")
    if pdf.suffix.lower() != ".pdf":
        raise CanonicalExtractionError(f"Expected a PDF file: {pdf}")
    transport = pdf_transport or os.getenv("ANTHROPIC_PDF_TRANSPORT", DEFAULT_PDF_TRANSPORT)
    if transport not in {"inline", "files-api"}:
        raise CanonicalExtractionError("pdf_transport must be inline or files-api")
    models = resolve_model_chain(primary=model, fallbacks=fallback_models)
    selected_effort = effort or os.getenv("ANTHROPIC_PDF_EFFORT", DEFAULT_EFFORT)
    selected_tokens = max_tokens or int(os.getenv("ANTHROPIC_PDF_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))
    api_client = client or build_client()
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    source = CanonicalSource(
        email_id=email_id,
        attachment_id=attachment_id,
        file_name=pdf.name,
        pdf_sha256=digest,
        page_count=_page_count(pdf),
        sent_by=sent_by,
    )
    referral_id = f"ref_{digest[:24]}"
    metadata = json.dumps({"referral_id": referral_id, "source": source.model_dump(mode="json")})
    audit = ExtractionAudit()
    sleeper = sleep if sleep is not None else __import__("time").sleep

    def execute(pdf_block: dict[str, Any]) -> CanonicalReferral:
        if progress:
            progress("Canonical pass 1/2: complete PDF extraction started")
        first, first_model = _call_structured_extractor(
            api_client,
            output_format=CanonicalReferral,
            models=models,
            effort=selected_effort,
            max_tokens=selected_tokens,
            system_prompt=SYSTEM_PROMPT,
            content=[pdf_block, {"type": "text", "text": f"{FIRST_READING}\nSOURCE METADATA:\n{metadata}"}],
            progress=progress,
            sleep=sleeper,
            random_source=random_source,
        )
        audit.record_pass(first_model, primary_model=models[0])
        if progress:
            progress(f"Canonical pass 1/2: complete (model={first_model})")
            progress("Canonical pass 2/2: source verification started")
        final, final_model = _call_structured_extractor(
            api_client,
            output_format=CanonicalReferral,
            models=models,
            effort=selected_effort,
            max_tokens=selected_tokens,
            system_prompt=SYSTEM_PROMPT,
            content=[
                pdf_block,
                {
                    "type": "text",
                    "text": (
                        f"{VERIFICATION}\nSOURCE METADATA:\n{metadata}\n"
                        f"CANDIDATE FROM FIRST READING:\n{json.dumps(first.model_dump(mode='json'), ensure_ascii=False)}"
                    ),
                },
            ],
            progress=progress,
            sleep=sleeper,
            random_source=random_source,
        )
        audit.record_pass(final_model, primary_model=models[0])
        if progress:
            progress(f"Canonical pass 2/2: complete (model={final_model})")
        source_with_audit = source.model_copy(
            update={
                "extraction": CanonicalExtractionAudit(
                    primary_model=models[0],
                    models_attempted=list(audit.models_attempted),
                    pass_models=list(audit.pass_models),
                    fallback_used=audit.fallback_used,
                )
            }
        )
        final = final.model_copy(update={"schema_version": 1, "referral_id": referral_id, "source": source_with_audit})
        return _ensure_core_quality(final)

    if transport == "inline":
        return execute(_native_pdf_block(pdf))
    if progress:
        progress("Uploading PDF once to the Anthropic Files API")
    pdf_block, uploaded_id = _upload_pdf_block(api_client, pdf)
    try:
        return execute(pdf_block)
    finally:
        try:
            api_client.beta.files.delete(uploaded_id)
        except Exception as cleanup_error:
            if progress:
                progress(f"Failed to delete temporary Anthropic upload: {cleanup_error}")
        else:
            if progress:
                progress("Deleted temporary Anthropic Files API upload")

def _contains_wound_term(text: str) -> bool:
    haystack = text.lower()
    return any(re.search(rf"\b{re.escape(term)}\b", haystack) for term in _WOUND_TERMS)


def _is_wound_diagnosis(item: CanonicalDiagnosis) -> bool:
    haystack = " ".join(part for part in (item.code, item.description) if part)
    return bool(haystack) and _contains_wound_term(haystack)


def _render_wound_line(item: CanonicalDiagnosis) -> str | None:
    code = (item.code or "").strip() or None
    description = (item.description or "").strip() or None
    if code and description:
        return f"{code} {description}"
    return description or code


def _is_narrative(text: str) -> bool:
    cleaned = " ".join(text.split())
    if not cleaned:
        return False
    if len(cleaned) > CLINICAL_SUMMARY_MAX_CHARS:
        return True
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()]
    return len(sentences) > 1


def _truncate_reason(text: str) -> str | None:
    cleaned = " ".join(text.split())
    if not cleaned:
        return None
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()]
    shortened = sentences[0] if sentences else cleaned
    if len(shortened) <= CLINICAL_SUMMARY_MAX_CHARS:
        return shortened
    boundary = shortened.rfind(" ", 0, CLINICAL_SUMMARY_MAX_CHARS)
    cutoff = boundary if boundary > CLINICAL_SUMMARY_MAX_CHARS // 2 else CLINICAL_SUMMARY_MAX_CHARS
    return shortened[:cutoff].rstrip(" ,;:-") or None


def _join_limited(parts: Sequence[str]) -> str | None:
    cleaned = [part.strip() for part in parts if part and part.strip()]
    if not cleaned:
        return None
    result = "; ".join(cleaned)
    if len(result) <= CLINICAL_SUMMARY_MAX_CHARS:
        return result
    kept: list[str] = []
    for part in cleaned:
        candidate = "; ".join([*kept, part])
        if len(candidate) > CLINICAL_SUMMARY_MAX_CHARS:
            break
        kept.append(part)
    if kept:
        return "; ".join(kept)
    return _truncate_reason(cleaned[0])


def _clause_key(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower().rstrip(".;:")


def _is_form_chrome_clause(text: str, service_names: Sequence[str]) -> bool:
    cleaned = text.strip()
    if _FORM_CHROME_CLAUSE.match(cleaned):
        return True
    key = _clause_key(cleaned)
    return any(key == _clause_key(name) for name in service_names if name)


def _normalize_reason_line(
    text: str | None,
    *,
    service_names: Sequence[str] = (),
) -> str | None:
    """Drop form-label repeats so one wound/reason clause remains."""
    cleaned = " ".join((text or "").split()) or None
    if not cleaned:
        return None
    clauses = [part.strip(" -") for part in re.split(r"\s*;\s*", cleaned) if part.strip()]
    kept: list[str] = []
    for clause in clauses:
        if _is_form_chrome_clause(clause, service_names):
            continue
        key = _clause_key(clause)
        if not key or any(key == _clause_key(item) for item in kept):
            continue
        if any(key != _clause_key(item) and key in _clause_key(item) for item in kept):
            continue
        kept = [item for item in kept if not (_clause_key(item) != key and _clause_key(item) in key)]
        kept.append(clause)
    return _join_limited(kept)


def _requested_service_reason(requested_services: Sequence[CanonicalRequestedService]) -> str | None:
    service_names = [item.service for item in requested_services if item.service]
    for item in requested_services:
        text = _normalize_reason_line(item.instructions, service_names=service_names)
        if text:
            return text if not _is_narrative(text) else _truncate_reason(text)
    for item in requested_services:
        text = _normalize_reason_line(item.service)
        if text:
            return text if not _is_narrative(text) else _truncate_reason(text)
    return None


def intake_clinical_summary(
    clinical: CanonicalClinical,
    requested_services: Sequence[CanonicalRequestedService] | None = None,
) -> str | None:
    """Compose the seventh intake field: a short PDF-grounded wound/reason line."""
    services = requested_services or []
    service_names = [item.service for item in services if item.service]
    summary = _normalize_reason_line(
        " ".join((clinical.summary or "").split()) or None,
        service_names=service_names,
    )
    wound_items = [item for item in clinical.diagnoses if _is_wound_diagnosis(item)]
    wound_items.sort(key=lambda item: (not bool(item.is_primary), item.description or "", item.code or ""))
    wound_lines = [line for line in (_render_wound_line(item) for item in wound_items) if line]
    if (
        summary
        and len(summary) <= CLINICAL_SUMMARY_MAX_CHARS
        and not _is_narrative(summary)
        and (_contains_wound_term(summary) or not wound_lines)
    ):
        return summary
    if wound_lines:
        return _join_limited(wound_lines)
    service_reason = _requested_service_reason(services)
    if service_reason:
        return service_reason
    if summary:
        return _truncate_reason(summary)
    return None


def _apply_intake_clinical_summary(record: CanonicalReferral) -> CanonicalReferral:
    original = record.clinical.summary
    composed = intake_clinical_summary(record.clinical, record.requested_services)
    if composed == original:
        return record
    notes = list(record.clinical.notes)
    original_text = (original or "").strip()
    if (
        original_text
        and original_text != (composed or "")
        and original_text not in notes
        and (_is_narrative(original_text) or len(original_text) > CLINICAL_SUMMARY_MAX_CHARS)
    ):
        notes.append(original_text)
    clinical = record.clinical.model_copy(update={"summary": composed, "notes": notes})
    return record.model_copy(update={"clinical": clinical})


def _ensure_core_quality(record: CanonicalReferral) -> CanonicalReferral:
    record = _apply_intake_clinical_summary(record)
    quality = dict(record.field_quality)
    warnings = list(record.warnings)
    values = {
        "patient.name": record.patient.name.full or record.patient.name.first or record.patient.name.last,
        "patient.date_of_birth": record.patient.date_of_birth,
        "patient.phones": record.patient.phones,
        "patient.address": record.patient.address.line_1,
        "home_health_or_hospice": record.home_health_or_hospice.organization.name,
        "clinical": record.clinical.summary or record.clinical.diagnoses or record.clinical.notes,
        "insurances": record.insurances,
    }
    for path, value in values.items():
        current = quality.get(path)
        if current is None:
            quality[path] = CanonicalFieldQuality(
                status="present" if value else "missing",
                confidence="high" if value else "medium",
            )
            continue
        inconsistent = (current.status == "present" and not value) or (
            current.status == "explicitly_none" and bool(value)
        )
        if inconsistent:
            warnings.append(f"Field quality for {path} contradicted the extracted value; marked unclear.")
            quality[path] = current.model_copy(update={"status": "unclear", "confidence": "low"})
    return record.model_copy(update={"field_quality": quality, "warnings": warnings})


def write_canonical_referral(record: CanonicalReferral, output_dir: str | Path) -> Path:
    from .aligned_intake import (
        to_drk_create_draft_from_canonical,
        to_master_sheet_referral_from_canonical,
    )

    folder = Path(output_dir) / record.referral_id
    destination = folder / "canonical-referral.json"
    _write_json(destination, record.model_dump(mode="json"))
    _write_json(
        folder / "monday-referral.json",
        to_master_sheet_referral_from_canonical(record).model_dump(mode="json"),
    )
    _write_json(
        folder / "drk-create-draft.json",
        to_drk_create_draft_from_canonical(record).model_dump(mode="json"),
    )
    inbox_path = folder / "inbox-intake.txt"
    inbox_path.write_text(render_inbox_text(record), encoding="utf-8")
    os.chmod(inbox_path, 0o600)
    return destination


def render_inbox_text(record: CanonicalReferral) -> str:
    patient = record.patient
    name = patient.name.full or " ".join(
        part for part in (patient.name.first, patient.name.middle, patient.name.last) if part
    )
    address = " ".join(
        part
        for part in (
            patient.address.line_1,
            patient.address.line_2,
            patient.address.city,
            patient.address.state,
            patient.address.postal_code,
        )
        if part
    )
    phone = patient.phones[0].number if patient.phones else None
    insurance = "; ".join(
        " / ".join(part for part in (item.payer_name, item.policy_number, item.group_number) if part)
        for item in record.insurances
    )
    services = "; ".join(
        " / ".join(part for part in (item.service, item.frequency, item.instructions) if part)
        for item in record.requested_services
    )
    rows = (
        ("Referral ID", record.referral_id),
        ("Patient", name),
        ("DOB", patient.date_of_birth),
        ("Phone", phone),
        ("Address", address),
        ("Referring source", record.referral_source.organization.name),
        ("Current HH/Hospice", record.home_health_or_hospice.organization.name),
        ("Clinical", record.clinical.summary),
        ("Insurance", insurance),
        ("Requested services", services),
    )
    return "\n".join(f"{label}: {value or 'Not documented'}" for label, value in rows) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract one PDF into the canonical referral record (two Anthropic calls).")
    parser.add_argument("pdf_path", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("output") / "canonical-referrals")
    parser.add_argument("--email-id")
    parser.add_argument("--attachment-id")
    parser.add_argument("--sent-by")
    parser.add_argument("--model", default=os.getenv("ANTHROPIC_PDF_MODEL", DEFAULT_MODEL))
    parser.add_argument("--effort", default=os.getenv("ANTHROPIC_PDF_EFFORT", DEFAULT_EFFORT))
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--pdf-transport", choices=("files-api", "inline"), default=DEFAULT_PDF_TRANSPORT)
    args = parser.parse_args(argv)
    try:
        record = extract_referral_pdf(
            args.pdf_path,
            email_id=args.email_id,
            attachment_id=args.attachment_id,
            sent_by=args.sent_by,
            model=args.model,
            effort=args.effort,
            max_tokens=args.max_tokens,
            pdf_transport=args.pdf_transport,
            progress=lambda message: print(message, flush=True),
        )
        output = write_canonical_referral(record, args.output_dir)
    except (AnthropicJsonError, CanonicalExtractionError) as exc:
        parser.error(str(exc))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
