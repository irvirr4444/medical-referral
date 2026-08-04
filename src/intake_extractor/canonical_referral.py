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
import time
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .llm.anthropic_json import AnthropicJsonError, build_client, parse_json_from_message


DEFAULT_MAX_TOKENS = 32_000
DEFAULT_MODEL = "claude-opus-5"
DEFAULT_EFFORT = "max"
DEFAULT_PDF_TRANSPORT = "files-api"
MAX_INLINE_PDF_BYTES = 23 * 1024 * 1024
FILES_API_BETA = "files-api-2025-04-14"
FieldStatus = Literal["present", "explicitly_none", "missing", "unclear"]
Confidence = Literal["high", "medium", "low"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CanonicalExtractionError(RuntimeError):
    pass


class CanonicalSource(StrictModel):
    email_id: str | None = None
    attachment_id: str | None = None
    file_name: str
    pdf_sha256: str
    page_count: int | None = None
    sent_by: str | None = None


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
    summary: str | None = None
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
- Clinical summary must describe the current referral reason without unsupported medical interpretation.
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


def _call_structured_extractor(
    client: Any,
    *,
    output_format: type[CanonicalReferral],
    model: str,
    effort: str,
    max_tokens: int,
    system_prompt: str,
    content: list[dict[str, Any]],
) -> CanonicalReferral:
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
            message = None
            for api_attempt in range(5):
                try:
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
                    break
                except Exception as exc:
                    retryable = getattr(exc, "status_code", None) in {429, 500, 502, 503, 504}
                    retryable = retryable or "overloaded" in str(exc).lower()
                    if api_attempt == 4 or not retryable:
                        raise
                    time.sleep(2**api_attempt)
            if message is None:
                raise CanonicalExtractionError("Anthropic returned no message")
            parsed = getattr(message, "parsed_output", None) or parse_json_from_message(message)
            return parsed if isinstance(parsed, output_format) else output_format.model_validate(parsed)
        except (AnthropicJsonError, ValidationError) as exc:
            last_error = exc
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
    effort: str | None = None,
    max_tokens: int | None = None,
    pdf_transport: str | None = None,
    client: Any | None = None,
    progress: Callable[[str], None] | None = None,
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
    selected_model = model or os.getenv("ANTHROPIC_PDF_MODEL", DEFAULT_MODEL)
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

    def execute(pdf_block: dict[str, Any]) -> CanonicalReferral:
        if progress:
            progress("Canonical pass 1/2: complete PDF extraction started")
        first = _call_structured_extractor(
            api_client,
            output_format=CanonicalReferral,
            model=selected_model,
            effort=selected_effort,
            max_tokens=selected_tokens,
            system_prompt=SYSTEM_PROMPT,
            content=[pdf_block, {"type": "text", "text": f"{FIRST_READING}\nSOURCE METADATA:\n{metadata}"}],
        )
        if progress:
            progress("Canonical pass 1/2: complete")
            progress("Canonical pass 2/2: source verification started")
        final = _call_structured_extractor(
            api_client,
            output_format=CanonicalReferral,
            model=selected_model,
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
        )
        if progress:
            progress("Canonical pass 2/2: complete")
        final = final.model_copy(update={"schema_version": 1, "referral_id": referral_id, "source": source})
        return _ensure_core_quality(final)

    if transport == "inline":
        return execute(_native_pdf_block(pdf))
    if progress:
        progress("Uploading PDF once to the Anthropic Files API")
    pdf_block, uploaded_id = _upload_pdf_block(api_client, pdf)
    try:
        return execute(pdf_block)
    finally:
        api_client.beta.files.delete(uploaded_id)
        if progress:
            progress("Deleted temporary Anthropic Files API upload")


def _ensure_core_quality(record: CanonicalReferral) -> CanonicalReferral:
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
