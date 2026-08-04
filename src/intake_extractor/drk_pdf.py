from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar
from urllib.parse import quote

from pydantic import BaseModel, ValidationError

from .llm.anthropic_json import AnthropicJsonError, build_client, parse_json_from_message
from .drk_pdf_schema import (
    ClinicalExtraction,
    DrkPdfExtraction,
    IdentityReferralExtraction,
    InsuranceExtraction,
)
from .pdf.payloads import extract_text


DEFAULT_MODEL = "claude-opus-5"
DEFAULT_MAX_TOKENS = 32_000
DEFAULT_EFFORT = "max"
DEFAULT_PDF_TRANSPORT = "files-api"
MAX_INLINE_PDF_BYTES = 23 * 1024 * 1024
MAX_SUPPLEMENTAL_TEXT_CHARS = 750_000
FILES_API_BETA = "files-api-2025-04-14"

CARD_NAMES = (
    "patient_information",
    "admission",
    "communications",
    "encounters",
    "diagnosis",
    "medications_allergies",
    "insurance",
    "custom_scans",
    "billing",
    "pipeline",
)

EXTRACTION_SYSTEM_PROMPT = """You are the final-source clinical document abstraction specialist for a medical intake workflow.

Read the complete PDF visually and textually. The document may be a scan, fax, form, EHR printout, handwriting, mixed packet, or have no consistent layout.

Accuracy rules:
- The PDF is the only authority. Never invent, autocomplete, or import common medical assumptions.
- Extract every explicitly present demographic, referring-source, admission, diagnosis, medication, allergy, insurance, requested-service, and clinically relevant note.
- Preserve all repeated list rows when they represent distinct records. Do not summarize away diagnoses, medications, or insurance policies.
- An empty ALLERGIES section is not the same as an explicit NKA/NKDA statement.
- Put a value in `mrn` only when the source explicitly labels it MRN. Put Patient ID, Account #, chart ID, and similar identifiers in `source_patient_id`, preserving the label separately.
- A medication history is not a requested service. Requested services require explicit order/referral intent.
- Do not infer Primary/Secondary insurance merely from display order.
- Dates should be copied faithfully. Prefer YYYY-MM-DD when the source is unambiguous.
- Preserve medication name, strength, form, directions, status, date, prescriber, days supply, quantity, and refills separately when present.
- For each non-null field and each list item, add concise evidence with a field path, one-indexed page number(s), a near-verbatim quote when text is readable, and calibrated confidence.
- Use null for absent scalar values, [] for absent lists, and null for section-presence booleans when section presence is uncertain.
- Add a warning for conflicts, illegible values, truncated content, uncertain section boundaries, or source contradictions.
"""

DOMAIN_REQUESTS = {
    "identity/referral": """Extract only document type, patient demographics and identifiers, referring source,
admission/referral facts, requested services, and other clinical notes. Inspect every page. Preserve source IDs
separately from explicit MRNs. Do not extract diagnosis, medication, allergy, or insurance lists in this pass.""",
    "clinical": """Extract every diagnosis, medication, and allergy row. Inspect every page and recount each list.
Preserve medication attributes separately. An empty allergy section is not an explicit no-known-allergies statement.
Do not extract demographics, referral, admission, or insurance in this pass.""",
    "insurance": """Extract every insurance policy and subscriber/policy-holder fact. Inspect every page.
Do not infer Primary or Secondary from display order. Do not extract other domains in this pass.""",
}

INDEPENDENT_REQUEST = """Independently extract this PDF domain from scratch into the required schema.
Do not assume another extraction exists. Prioritize exact character transcription and complete row counts.
The appended machine-extracted text is only a secondary aid; the original PDF visuals remain authoritative."""

ADJUDICATION_REQUEST = """Produce the final adjudicated extraction for this domain from the original PDF.

Two independent candidate extractions are appended. Compare them field by field and row by row against the PDF itself.
- Recover omissions.
- Remove unsupported values.
- Resolve disagreements from direct source evidence.
- Recount diagnoses, medications, allergies, and insurance records.
- Preserve the MRN versus account/patient-ID distinction.
- Do not copy candidate values unless the PDF supports them.

Return one complete corrected extraction in the required schema."""


class DrkPdfExtractionError(RuntimeError):
    pass


StructuredOutput = TypeVar("StructuredOutput", bound=BaseModel)


def _native_pdf_block(pdf_path: Path) -> dict[str, Any]:
    size = pdf_path.stat().st_size
    if size > MAX_INLINE_PDF_BYTES:
        raise DrkPdfExtractionError(
            f"{pdf_path.name} is {size / 1024 / 1024:.1f} MB; inline base64 would exceed the "
            "Anthropic 32 MB request limit. Split or optimize the PDF before extraction."
        )
    encoded = base64.standard_b64encode(pdf_path.read_bytes()).decode("ascii")
    return {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": encoded,
        },
    }


def _upload_pdf_block(client: Any, pdf_path: Path) -> tuple[dict[str, Any], str]:
    try:
        with pdf_path.open("rb") as pdf_file:
            uploaded = client.beta.files.upload(file=(pdf_path.name, pdf_file, "application/pdf"))
    except Exception as exc:
        raise DrkPdfExtractionError(f"Anthropic Files API upload failed: {exc}") from exc
    file_id = getattr(uploaded, "id", None)
    if not file_id:
        raise DrkPdfExtractionError("Anthropic Files API upload returned no file ID")
    return {
        "type": "document",
        "source": {"type": "file", "file_id": file_id},
    }, str(file_id)


def _uses_files_api(content: list[dict[str, Any]]) -> bool:
    return any(
        block.get("type") == "document"
        and isinstance(block.get("source"), dict)
        and block["source"].get("type") == "file"
        for block in content
    )


def _page_count(pdf_path: Path) -> int:
    import pdfplumber

    with pdfplumber.open(str(pdf_path)) as pdf:
        return len(pdf.pages)


def _supplemental_text(pdf_path: Path) -> tuple[str | None, bool]:
    try:
        pages = extract_text(pdf_path).pages
    except Exception:
        return None, False
    chunks = [f"--- PAGE {page.page_number} ---\n{page.text}" for page in pages if page.text.strip()]
    if not chunks:
        return None, False
    text = "\n\n".join(chunks)
    if len(text) <= MAX_SUPPLEMENTAL_TEXT_CHARS:
        return text, False
    return text[:MAX_SUPPLEMENTAL_TEXT_CHARS], True


def _is_retryable_api_error(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status == 429 or (isinstance(status, int) and status >= 500):
        return True
    if type(exc).__name__ in {"APIConnectionError", "APITimeoutError", "RateLimitError", "InternalServerError"}:
        return True
    message = str(exc).lower()
    return any(token in message for token in ("overloaded", "rate_limit", "temporarily unavailable"))


def _retry_delay_seconds(exc: Exception, attempt: int) -> float:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is not None:
        retry_after = headers.get("retry-after")
        if retry_after:
            try:
                return min(max(float(retry_after), 0.5), 60.0)
            except ValueError:
                pass
    return float(2**attempt)


def _call_structured_extractor(
    client: Any,
    *,
    output_format: type[StructuredOutput],
    model: str,
    effort: str,
    max_tokens: int,
    system_prompt: str,
    content: list[dict[str, Any]],
) -> StructuredOutput:
    schema_prompt = (
        f"{system_prompt}\n\n"
        "Return exactly one RFC 8259 JSON object matching this JSON Schema. "
        "Do not use markdown fences or add commentary:\n"
        f"{json.dumps(output_format.model_json_schema(), ensure_ascii=False)}"
    )
    last_error: Exception | None = None
    for attempt in (1, 2):
        attempt_content = list(content)
        if attempt == 2:
            attempt_content.append(
                {
                    "type": "text",
                    "text": (
                        "The prior response did not parse or validate. Re-read the source and return a fresh, complete "
                        f"JSON object matching the schema exactly. Validation error: {last_error}"
                    ),
                }
            )
        try:
            message = None
            for api_attempt in range(5):
                try:
                    stream_kwargs = {
                        "model": model,
                        "max_tokens": max_tokens,
                        "system": schema_prompt,
                        "messages": [{"role": "user", "content": attempt_content}],
                        "output_config": {"effort": effort},
                        "thinking": {"type": "adaptive"},
                    }
                    if _uses_files_api(attempt_content):
                        stream_manager = client.beta.messages.stream(
                            **stream_kwargs,
                            betas=[FILES_API_BETA],
                        )
                    else:
                        stream_manager = client.messages.stream(**stream_kwargs)
                    with stream_manager as stream:
                        message = stream.get_final_message()
                    break
                except Exception as exc:
                    if api_attempt == 4 or not _is_retryable_api_error(exc):
                        raise
                    time.sleep(_retry_delay_seconds(exc, api_attempt))
            if message is None:
                raise DrkPdfExtractionError("Anthropic returned no message")
            parsed = getattr(message, "parsed_output", None)
            if parsed is None:
                parsed = parse_json_from_message(message)
            return parsed if isinstance(parsed, output_format) else output_format.model_validate(parsed)
        except (AnthropicJsonError, ValidationError) as exc:
            last_error = exc
            continue
        except Exception as exc:
            raise DrkPdfExtractionError(f"Anthropic extraction failed: {exc}") from exc
    raise DrkPdfExtractionError(f"Anthropic output failed JSON/schema validation twice: {last_error}")


def _extract_domain(
    client: Any,
    *,
    domain_name: str,
    output_format: type[StructuredOutput],
    pdf_block: dict[str, Any],
    supplemental_text: str | None,
    model: str,
    effort: str,
    max_tokens: int,
    passes: int,
    parallel_readings: bool = True,
    progress: Callable[[str], None] | None = None,
) -> StructuredOutput:
    domain_request = DOMAIN_REQUESTS[domain_name]
    first_content = [
        pdf_block,
        {
            "type": "text",
            "text": f"DOMAIN: {domain_name}\n{domain_request}\n\nInspect every relevant row and return structured data.",
        },
    ]
    second_content: list[dict[str, Any]] = [pdf_block]
    if supplemental_text:
        second_content.append(
            {
                "type": "text",
                "text": (
                    "SECONDARY MACHINE-EXTRACTED TEXT WITH PAGE MARKERS:\n"
                    f"{supplemental_text}"
                ),
            }
        )
    second_content.append(
        {
            "type": "text",
            "text": f"DOMAIN: {domain_name}\n{domain_request}\n\n{INDEPENDENT_REQUEST}",
        }
    )

    def call(content: list[dict[str, Any]]) -> StructuredOutput:
        return _call_structured_extractor(
            client,
            output_format=output_format,
            model=model,
            effort=effort,
            max_tokens=max_tokens,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            content=content,
        )

    if progress:
        progress(f"[{domain_name}] pass 1/{passes}: native PDF extraction started")
    if passes == 1:
        first = call(first_content)
        if progress:
            progress(f"[{domain_name}] pass 1/{passes}: complete")
        return first

    if progress:
        progress(f"[{domain_name}] pass 2/{passes}: independent extraction started")
    if parallel_readings:
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix=f"drk-pdf-{domain_name}") as executor:
            first_future = executor.submit(call, first_content)
            second_future = executor.submit(call, second_content)
            first = first_future.result()
            if progress:
                progress(f"[{domain_name}] pass 1/{passes}: complete")
            second = second_future.result()
            if progress:
                progress(f"[{domain_name}] pass 2/{passes}: complete")
    else:
        first = call(first_content)
        if progress:
            progress(f"[{domain_name}] pass 1/{passes}: complete")
        second = call(second_content)
        if progress:
            progress(f"[{domain_name}] pass 2/{passes}: complete")

    adjudication_context = {
        "candidate_a": first.model_dump(mode="json"),
        "candidate_b": second.model_dump(mode="json"),
    }
    if progress:
        progress(f"[{domain_name}] pass 3/{passes}: source adjudication started")
    final = _call_structured_extractor(
        client,
        output_format=output_format,
        model=model,
        effort=effort,
        max_tokens=max_tokens,
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
        content=[
            pdf_block,
            {
                "type": "text",
                "text": (
                    f"DOMAIN: {domain_name}\n{domain_request}\n\n{ADJUDICATION_REQUEST}\n\n"
                    "CANDIDATE EXTRACTIONS:\n"
                    f"{json.dumps(adjudication_context, ensure_ascii=False)}"
                ),
            },
        ],
    )
    if progress:
        progress(f"[{domain_name}] pass 3/{passes}: complete")
    return final


def extract_drk_from_pdf(
    pdf_path: str | Path,
    *,
    model: str | None = None,
    effort: str | None = None,
    max_tokens: int | None = None,
    passes: int = 3,
    client: Any | None = None,
    parallel_domains: bool = True,
    parallel_readings: bool = True,
    pdf_transport: str | None = None,
    progress: Callable[[str], None] | None = None,
) -> DrkPdfExtraction:
    """Compatibility projection; PDF interpretation is owned by canonical_referral."""
    from .aligned_intake import _legacy_projection
    from .canonical_referral import extract_referral_pdf

    canonical = extract_referral_pdf(
        pdf_path,
        model=model,
        effort=effort,
        max_tokens=max_tokens,
        client=client,
        pdf_transport=pdf_transport,
        progress=progress,
    )
    return _legacy_projection(canonical)

def _sanitize_evidence(extraction: DrkPdfExtraction, *, page_count: int) -> DrkPdfExtraction:
    data = extraction.model_dump(mode="json")
    invalid_paths: list[str] = []
    for item in data["evidence"]:
        valid_pages = sorted({page for page in item["page_numbers"] if 1 <= page <= page_count})
        if valid_pages != sorted(set(item["page_numbers"])):
            invalid_paths.append(item["field_path"])
        item["page_numbers"] = valid_pages
    if invalid_paths:
        data["warnings"].append(
            "Discarded out-of-range evidence page numbers for: " + ", ".join(sorted(set(invalid_paths)))
        )
    return DrkPdfExtraction.model_validate(data)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).split())
    return cleaned or None


def _iso_datetime(value: str | None) -> str | None:
    value = _clean(value)
    if value is None:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%dT00:00:00")
        except ValueError:
            continue
    return value


def _patient_names(extraction: DrkPdfExtraction) -> tuple[str | None, str | None, str | None]:
    patient = extraction.patient
    first = _clean(patient.first_name)
    last = _clean(patient.last_name)
    full = _clean(patient.full_name)
    if full and (not first or not last):
        if "," in full:
            family, given = [part.strip() for part in full.split(",", 1)]
            last = last or family
            first = first or (given.split()[0] if given else None)
        else:
            parts = full.split()
            first = first or (parts[0] if parts else None)
            last = last or (parts[-1] if len(parts) > 1 else None)
    if not full:
        full = " ".join(part for part in (first, _clean(patient.middle_name), last) if part) or None
    return first, last, full


def _full_address(extraction: DrkPdfExtraction) -> str | None:
    patient = extraction.patient
    locality = " ".join(part for part in (_clean(patient.city), _clean(patient.state), _clean(patient.zip_code)) if part)
    return " ".join(part for part in (_clean(patient.address1), _clean(patient.address2), locality) if part) or None


def _pdf_endpoint(pdf: Path, *, pages: str | None = None) -> dict[str, Any]:
    suffix = f"#pages={pages}" if pages else ""
    return {
        "method": "PDF_EXTRACT",
        "url": f"pdf://source/{quote(pdf.name)}{suffix}",
        "status": 200,
    }


def _card(card: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    return {"card": card, "record_count": len(records), "records": records}


def build_drk_cards(
    extraction: DrkPdfExtraction,
    pdf_path: str | Path,
    *,
    page_count: int | None = None,
) -> dict[str, dict[str, Any]]:
    pdf = Path(pdf_path)
    pages = page_count if page_count is not None else _page_count(pdf)
    page_ref = f"1-{pages}" if pages > 1 else "1"
    endpoint = _pdf_endpoint(pdf, pages=page_ref)
    patient = extraction.patient
    first_name, last_name, full_name = _patient_names(extraction)
    facility_name = _clean(extraction.admission.facility_name)

    demographics = {
        "id": None,
        "firstName": first_name,
        "middleName": _clean(patient.middle_name),
        "lastName": last_name,
        "fullName": full_name,
        "mrn": _clean(patient.mrn),
        "sourcePatientId": _clean(patient.source_patient_id),
        "sourcePatientIdLabel": _clean(patient.source_patient_id_label),
        "status": None,
        "dateOfBirth": _iso_datetime(patient.date_of_birth),
        "age": patient.age,
        "gender": _clean(patient.gender),
        "genderIdentityId": None,
        "address1": _clean(patient.address1),
        "address2": _clean(patient.address2),
        "city": _clean(patient.city),
        "state": _clean(patient.state),
        "zipCode": _clean(patient.zip_code),
        "fullAddress": _full_address(extraction),
        "phoneNumber": _clean(patient.phone_number),
        "secondaryPhoneNumber": _clean(patient.secondary_phone_number),
        "email": _clean(patient.email),
        "emergencyContactName": _clean(patient.emergency_contact_name),
        "emergencyContactPhone": _clean(patient.emergency_contact_phone),
        "relationshipId": None,
        "facilityName": facility_name,
        "homeHealthCompanyName": _clean(extraction.admission.home_health_company),
        "lastVisit": None,
        "patientStatus": None,
        "patientStatusDisplayName": None,
        "statusChangeDate": None,
        "statusChangeReason": None,
        "statusBadgeClass": None,
        "placeOfServiceCode": None,
        "placeOfServiceDescription": _clean(extraction.admission.place_of_service),
        "hasEmail": bool(_clean(patient.email)),
        "hasAddress2": bool(_clean(patient.address2)),
        "hasEmergencyContact": bool(_clean(patient.emergency_contact_name) or _clean(patient.emergency_contact_phone)),
        "hasFacility": bool(facility_name),
        "hasHomeHealth": bool(_clean(extraction.admission.home_health_company)),
        "hasPlaceOfService": bool(_clean(extraction.admission.place_of_service)),
    }

    referrer = extraction.referring_source
    admission = extraction.admission
    referral_has_data = any(
        (
            referrer.provider_name,
            referrer.facility_name,
            referrer.phone,
            referrer.fax,
            referrer.address,
            referrer.referral_date,
        )
    )
    admission_has_data = referral_has_data or any(
        (
            admission.admission_date,
            admission.facility_name,
            admission.facility_phone,
            admission.facility_fax,
            admission.home_health_company,
            admission.place_of_service,
            admission.medicare_admission,
            admission.palliative_admission,
            admission.hospice,
        )
    )
    admission_records: list[dict[str, Any]] = []
    if admission_has_data:
        referral = None
        if referral_has_data:
            referral = {
                "id": None,
                "patientId": None,
                "patientName": full_name,
                "referralDate": _iso_datetime(referrer.referral_date),
                "referringProviderName": _clean(referrer.provider_name),
                "referringFacilityName": _clean(referrer.facility_name),
                "referringPhone": _clean(referrer.phone),
                "referringFax": _clean(referrer.fax),
                "referringAddress": _clean(referrer.address),
                "notes": None,
            }
        admission_records.append(
            {
                "endpoint": endpoint,
                "business_data": {
                    "success": True,
                    "data": {
                        "patientId": None,
                        "isCurrentlyAdmitted": None,
                        "currentFacilityId": None,
                        "currentFacilityName": facility_name,
                        "currentFacilityPhone": _clean(admission.facility_phone),
                        "currentFacilityFax": _clean(admission.facility_fax),
                        "currentAdmissionDate": _iso_datetime(admission.admission_date),
                        "currentMedicareAdmission": admission.medicare_admission,
                        "isPalliative": admission.palliative_admission,
                        "isHospice": admission.hospice,
                        "homeHealthCompany": _clean(admission.home_health_company),
                        "placeOfServiceDescription": _clean(admission.place_of_service),
                        "admissionHistory": [],
                        "referral": referral,
                    },
                },
            }
        )

    diagnosis_records: list[dict[str, Any]] = []
    if extraction.diagnoses_section_present is True or extraction.diagnoses:
        diagnoses = [
            {
                "code": _clean(item.code),
                "description": _clean(item.description),
                "added": _iso_datetime(item.added_date),
                "is_primary": item.is_primary,
                "status": _clean(item.status),
            }
            for item in extraction.diagnoses
            if item.code or item.description
        ]
        diagnosis_records.append(
            {
                "endpoint": endpoint,
                "business_data": {
                    "source": "PDF extraction",
                    "count": len(diagnoses),
                    "diagnoses": diagnoses,
                },
            }
        )

    medication_allergy_records: list[dict[str, Any]] = []
    if extraction.allergies_section_present is True or extraction.allergies or extraction.no_known_allergies_explicit:
        allergy_items = [
            {
                "id": None,
                "allergenId": None,
                "name": _clean(item.name),
                "reaction": _clean(item.reaction),
                "treatment": _clean(item.treatment),
                "reactionType": "Allergy",
                "statusType": _clean(item.status),
            }
            for item in extraction.allergies
            if item.name or item.reaction
        ]
        medication_allergy_records.append(
            {
                "endpoint": endpoint,
                "business_data": {
                    "success": True,
                    "data": {
                        "items": allergy_items,
                        "noKnownAllergy": extraction.no_known_allergies_explicit,
                        "hasNoKnownAllergies": extraction.no_known_allergies_explicit is True,
                    },
                },
            }
        )
    if extraction.medications_section_present is True or extraction.medications:
        medication_items = [
            {
                "id": None,
                "name": _clean(item.name),
                "strength": _clean(item.strength),
                "doseForm": _clean(item.dose_form),
                "directions": _clean(item.directions),
                "status": _clean(item.status),
                "prescribedDate": _iso_datetime(item.prescribed_date),
                "prescriber": _clean(item.prescriber),
                "daysSupply": item.days_supply,
                "quantity": _clean(item.quantity),
                "refills": item.refills,
            }
            for item in extraction.medications
            if item.name or item.directions
        ]
        medication_allergy_records.append(
            {
                "endpoint": endpoint,
                "business_data": {
                    "success": True,
                    "data": {
                        "items": medication_items,
                        "pageResult": {
                            "currentPage": 1,
                            "totalPages": 1 if medication_items else 0,
                            "pageSize": len(medication_items),
                            "totalCount": len(medication_items),
                            "hasPrevious": False,
                            "hasNext": False,
                        },
                    },
                },
            }
        )

    insurance_records: list[dict[str, Any]] = []
    if extraction.insurance_section_present is True or extraction.insurances:
        insurance_items = [
            {
                "id": None,
                "payerName": _clean(item.payer_name),
                "policyNumber": _clean(item.policy_number),
                "groupNumber": _clean(item.group_number),
                "groupName": _clean(item.group_name),
                "subscriberId": None,
                "subscriberName": _clean(item.policy_holder_name),
                "effectiveDate": _iso_datetime(item.effective_date),
                "expirationDate": _iso_datetime(item.expiration_date),
                "type": item.insurance_type,
                "isPrimary": True if item.insurance_type == "Primary" else False if item.insurance_type else None,
                "status": None,
                "isActive": None,
                "copay": None,
                "deductible": None,
                "percentCoverage": None,
                "deductibleMet": None,
                "isPatientPolicyHolder": item.is_patient_policy_holder,
                "verifiedWith": None,
                "insurancePayerId": None,
                "subscriberFirstName": _clean(item.subscriber_first_name),
                "subscriberLastName": _clean(item.subscriber_last_name),
                "subscriberDateOfBirth": _iso_datetime(item.subscriber_date_of_birth),
                "subscriberRelationship": _clean(item.subscriber_relationship),
            }
            for item in extraction.insurances
            if item.payer_name or item.policy_number
        ]
        insurance_records.append(
            {
                "endpoint": endpoint,
                "business_data": {"success": True, "data": insurance_items},
            }
        )

    source_scan = {
        "id": None,
        "fileName": pdf.name,
        "fileType": "pdf",
        "fileUrl": None,
        "uploadDate": None,
        "uploadedBy": "PDF intake extractor",
        "description": f"Source intake document: {pdf.name}",
        "category": "Source Intake",
        "fileSize": pdf.stat().st_size,
        "fileSizeFormatted": f"{pdf.stat().st_size / 1024:.1f} KB",
    }

    cards = {
        "patient_information": _card(
            "patient_information",
            [{"endpoint": endpoint, "business_data": {"success": True, "data": demographics}}],
        ),
        "admission": _card("admission", admission_records),
        "communications": _card("communications", []),
        "encounters": _card("encounters", []),
        "diagnosis": _card("diagnosis", diagnosis_records),
        "medications_allergies": _card("medications_allergies", medication_allergy_records),
        "insurance": _card("insurance", insurance_records),
        "custom_scans": _card(
            "custom_scans",
            [
                {
                    "endpoint": endpoint,
                    "business_data": {
                        "success": True,
                        "data": {
                            "scans": [source_scan],
                            "totalCount": 1,
                            "hasMore": False,
                            "currentPage": 1,
                            "pageSize": 1,
                        },
                    },
                }
            ],
        ),
        "billing": _card("billing", []),
        "pipeline": _card("pipeline", []),
    }
    return cards


def _safe_patient_folder_name(extraction: DrkPdfExtraction, pdf: Path) -> str:
    first_name, last_name, full_name = _patient_names(extraction)
    raw = " ".join(part for part in (first_name, last_name) if part) or full_name or pdf.stem
    cleaned = re.sub(r"[^\w\s\-]+", "", raw, flags=re.UNICODE)
    cleaned = re.sub(r"[\s\-]+", "_", cleaned).strip("_")
    return cleaned or "unknown_patient"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    os.chmod(temp, 0o600)
    temp.replace(path)
    os.chmod(path, 0o600)


def write_drk_pdf_output(
    extraction: DrkPdfExtraction,
    pdf_path: str | Path,
    *,
    output_dir: str | Path,
    model: str,
    effort: str,
    passes: int,
    pdf_transport: str = DEFAULT_PDF_TRANSPORT,
) -> Path:
    pdf = Path(pdf_path)
    pages = _page_count(pdf)
    patient_dir = Path(output_dir) / _safe_patient_folder_name(extraction, pdf)
    cards = build_drk_cards(extraction, pdf, page_count=pages)
    for card_name in CARD_NAMES:
        _write_json(patient_dir / f"{card_name}.json", cards[card_name])

    _write_json(patient_dir / "_extraction.json", extraction.model_dump(mode="json"))
    _write_json(
        patient_dir / "_manifest.json",
        {
            "source_file": pdf.name,
            "source_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
            "source_size_bytes": pdf.stat().st_size,
            "source_pages": pages,
            "extractor": (
                "Anthropic native PDF / independent dual extraction / source adjudication"
                if passes == 3
                else "Anthropic native PDF / domain extraction"
            ),
            "model": model,
            "effort": effort,
            "passes": passes,
            "pdf_transport": pdf_transport,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "card_files": [f"{name}.json" for name in CARD_NAMES],
            "evidence_file": "_extraction.json",
        },
    )
    return patient_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract an unstructured medical PDF into DRK-compatible card JSON using Anthropic native PDF vision."
    )
    parser.add_argument("pdf_path", help="Path to one PDF")
    parser.add_argument("--output-dir", default="output/pdf-drk-profile")
    parser.add_argument("--model", default=os.getenv("ANTHROPIC_PDF_MODEL", DEFAULT_MODEL))
    parser.add_argument(
        "--effort",
        choices=("low", "medium", "high", "xhigh", "max"),
        default=os.getenv("ANTHROPIC_PDF_EFFORT", DEFAULT_EFFORT),
    )
    parser.add_argument("--max-tokens", type=int, default=int(os.getenv("ANTHROPIC_PDF_MAX_TOKENS", DEFAULT_MAX_TOKENS)))
    parser.add_argument(
        "--passes",
        type=int,
        choices=(1, 3),
        default=3,
        help="1 = one native-PDF pass; 3 = two independent passes plus source adjudication (default)",
    )
    parser.add_argument(
        "--sequential-domains",
        action="store_true",
        help="Disable the default three-domain concurrency (useful when API rate limits are very low)",
    )
    parser.add_argument(
        "--sequential-readings",
        action="store_true",
        help="Disable concurrent independent readings within each domain",
    )
    parser.add_argument(
        "--pdf-transport",
        choices=("inline", "files-api"),
        default=os.getenv("ANTHROPIC_PDF_TRANSPORT", DEFAULT_PDF_TRANSPORT),
        help="PDF delivery method (default: files-api; inline remains available as a fallback)",
    )
    args = parser.parse_args(argv)

    try:
        extraction = extract_drk_from_pdf(
            args.pdf_path,
            model=args.model,
            effort=args.effort,
            max_tokens=args.max_tokens,
            passes=args.passes,
            parallel_domains=not args.sequential_domains,
            parallel_readings=not args.sequential_readings,
            pdf_transport=args.pdf_transport,
            progress=lambda message: print(message, flush=True),
        )
        patient_dir = write_drk_pdf_output(
            extraction,
            args.pdf_path,
            output_dir=args.output_dir,
            model=args.model,
            effort=args.effort,
            passes=args.passes,
            pdf_transport=args.pdf_transport,
        )
    except (AnthropicJsonError, DrkPdfExtractionError) as exc:
        parser.error(str(exc))

    print(f"Wrote DRK-compatible PDF extraction to {patient_dir}")
    print(
        "Counts: "
        f"diagnoses={len(extraction.diagnoses)}, "
        f"medications={len(extraction.medications)}, "
        f"allergies={len(extraction.allergies)}, "
        f"insurances={len(extraction.insurances)}"
    )
    if extraction.warnings:
        print(f"Warnings: {len(extraction.warnings)} (see _extraction.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
