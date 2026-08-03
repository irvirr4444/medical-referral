from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .drk_pdf import (
    DEFAULT_EFFORT,
    DEFAULT_MODEL,
    DEFAULT_PDF_TRANSPORT,
    DrkPdfExtractionError,
    _call_structured_extractor,
    _native_pdf_block,
    _page_count,
    _upload_pdf_block,
    _write_json,
)
from .llm.anthropic_json import AnthropicJsonError, build_client
from .models.schema import ReferralIntake
from .monday_pdf_schema import MondayPdfIntakeContract


DEFAULT_MAX_TOKENS = 8_000

SYSTEM_PROMPT = """You extract a focused Monday.com referral intake from one medical PDF.

The source PDF is authoritative. Copy only explicitly supported facts. Never guess, complete truncated values,
or convert a patient/account ID into an MRN. Return exactly the requested structured schema.

Extract all PDF facts that correspond to intake-relevant Master Sheet data:
- patient name, date of birth, phone, email, and address
- referring agency and its documented contact name, phone, and email
- current home-health/hospice agency and its contact details, kept separate from the referring agency
- place of service
- whether a wound order is explicitly included
- concise wound/referral-relevant clinical information
- every actual insurance policy
- an explicit clinical referral/order/signature date

The sent_by field is operational metadata supplied in the request. Copy it exactly and never infer it
from a provider, facility, fax header, author, or signer.

Do not use a fax sender as the referring agency unless the PDF explicitly identifies that organization as the
referral source. Do not assume the current HH/hospice is also the referring agency. Do not turn a fax timestamp
or PDF print date into referral_or_order_date. Set wound_order_included only when presence or absence is explicit.

Do not enumerate the complete historical diagnosis list or medication list. Clinical information should be a
concise summary sufficient for Monday intake routing. Do not add medical interpretation, causal conclusions, or
risk statements that the document does not explicitly state. In particular, do not infer wound-healing,
bleeding, infection, fall, or hospitalization risk from diagnoses or medications. Preserve every actual
insurance policy, but do not create an insurance record from an empty template block. Include short page-backed
evidence for every non-null PDF field and report ambiguity in warnings."""

EXTRACTION_REQUEST = """Perform the first reading of the entire PDF.

Inspect every page because the fields may be distributed across unrelated forms. Return the focused
Monday intake contract, concise evidence, and warnings. Missing values must remain null or empty."""

VERIFICATION_REQUEST = """Independently verify the candidate Monday intake against the entire source PDF.

Correct transcription errors, unsupported inferences, missing policies, empty insurance templates, wrong agency
roles, contact details assigned to the wrong organization, conflated referral/print/fax dates, and clinical
summaries that are too broad or omit the current referral reason. Confirm the four threshold fields (name, DOB,
phone, address) especially carefully. Remove any clinical interpretation or risk statement that is not directly
printed in the source. Return one corrected final contract. Do not expand the result into a DRK-style diagnosis
or medication history."""


def extract_monday_from_pdf(
    pdf_path: str | Path,
    *,
    sent_by: str | None = None,
    model: str | None = None,
    effort: str | None = None,
    max_tokens: int | None = None,
    pdf_transport: str | None = None,
    client: Any | None = None,
    progress: Callable[[str], None] | None = None,
) -> MondayPdfIntakeContract:
    pdf = Path(pdf_path)
    if not pdf.is_file():
        raise DrkPdfExtractionError(f"PDF not found: {pdf}")
    if pdf.suffix.lower() != ".pdf":
        raise DrkPdfExtractionError(f"Expected a PDF file: {pdf}")

    selected_model = model or os.getenv("ANTHROPIC_PDF_MODEL", DEFAULT_MODEL)
    selected_effort = effort or os.getenv("ANTHROPIC_PDF_EFFORT", DEFAULT_EFFORT)
    selected_max_tokens = max_tokens or DEFAULT_MAX_TOKENS
    selected_transport = pdf_transport or os.getenv("ANTHROPIC_PDF_TRANSPORT", DEFAULT_PDF_TRANSPORT)
    if selected_transport not in {"inline", "files-api"}:
        raise DrkPdfExtractionError("pdf_transport must be inline or files-api")
    api_client = client or build_client()
    supplied_sent_by = _clean(sent_by)

    def execute(pdf_block: dict[str, Any]) -> MondayPdfIntakeContract:
        metadata_instruction = (
            f"SENT_BY OPERATIONAL METADATA: {json.dumps(supplied_sent_by)}\n"
            "Copy this value exactly into sent_by. It is not a PDF extraction."
        )
        if progress:
            progress("Monday pass 1/2: focused PDF extraction started")
        first = _call_structured_extractor(
            api_client,
            output_format=MondayPdfIntakeContract,
            model=selected_model,
            effort=selected_effort,
            max_tokens=selected_max_tokens,
            system_prompt=SYSTEM_PROMPT,
            content=[
                pdf_block,
                {
                    "type": "text",
                    "text": f"{metadata_instruction}\n\n{EXTRACTION_REQUEST}",
                },
            ],
        ).model_copy(update={"sent_by": supplied_sent_by})
        if progress:
            progress("Monday pass 1/2: complete")
            progress("Monday pass 2/2: source verification started")
        final = _call_structured_extractor(
            api_client,
            output_format=MondayPdfIntakeContract,
            model=selected_model,
            effort=selected_effort,
            max_tokens=selected_max_tokens,
            system_prompt=SYSTEM_PROMPT,
            content=[
                pdf_block,
                {
                    "type": "text",
                    "text": (
                        f"{metadata_instruction}\n\n{VERIFICATION_REQUEST}\n\n"
                        "CANDIDATE FROM FIRST READING:\n"
                        f"{json.dumps(first.model_dump(mode='json'), ensure_ascii=False)}"
                    ),
                },
            ],
        ).model_copy(update={"sent_by": supplied_sent_by})
        if progress:
            progress("Monday pass 2/2: complete")
        return _sanitize_evidence(final, page_count=_page_count(pdf))

    if selected_transport == "inline":
        return execute(_native_pdf_block(pdf))

    if progress:
        progress("Uploading PDF once to the Anthropic Files API")
    pdf_block, uploaded_file_id = _upload_pdf_block(api_client, pdf)
    try:
        return execute(pdf_block)
    finally:
        try:
            api_client.beta.files.delete(uploaded_file_id)
            if progress:
                progress("Deleted temporary Anthropic Files API upload")
        except Exception as exc:
            raise DrkPdfExtractionError(
                f"Failed to delete temporary Anthropic file {uploaded_file_id}: {exc}"
            ) from exc


def to_referral_intake(
    contract: MondayPdfIntakeContract,
    *,
    source_file: str | None = None,
    pages_used: int | None = None,
) -> ReferralIntake:
    primary = contract.insurance_information[0] if contract.insurance_information else None
    additional = contract.insurance_information[1:]
    referring = contract.referring_agency
    current_hh = contract.current_home_health_or_hospice
    source_agency = referring if referring.name else current_hh
    notes: list[str] = []
    if additional:
        rendered = [
            " / ".join(
                part
                for part in (item.insurance_type, item.payer_name, item.policy_number, item.group_number)
                if part
            )
            for item in additional
        ]
        notes.append("Additional insurance: " + "; ".join(item for item in rendered if item))
    if primary and primary.insurance_type:
        notes.append(f"Insurance order: {primary.insurance_type}")
    if contract.patient_email:
        notes.append(f"Patient email: {contract.patient_email}")
    referring_details = " / ".join(
        part for part in (referring.name, referring.contact_name, referring.phone, referring.email) if part
    )
    if referring_details:
        notes.append(f"Referring agency details: {referring_details}")
    current_hh_details = " / ".join(
        part for part in (current_hh.name, current_hh.contact_name, current_hh.phone, current_hh.email) if part
    )
    if current_hh_details:
        notes.append(f"Current HH/Hospice details: {current_hh_details}")
    if contract.place_of_service:
        notes.append(f"Place of service: {contract.place_of_service}")
    if contract.wound_order_included is not None:
        notes.append(f"Wound order explicitly included: {'Yes' if contract.wound_order_included else 'No'}")
    if contract.sent_by:
        notes.append(f"Sent By: {contract.sent_by}")
    if contract.warnings:
        notes.append(f"Extraction review warnings: {len(contract.warnings)}; see monday-intake.json")
    return ReferralIntake(
        patient_name=contract.patient_name,
        patient_dob=contract.patient_date_of_birth,
        patient_phone=contract.patient_phone,
        patient_email=contract.patient_email,
        patient_address=contract.patient_address,
        referring_facility=source_agency.name,
        referring_phone=source_agency.phone,
        agency_contact_name=source_agency.contact_name,
        agency_email=source_agency.email,
        current_home_health_or_hospice=current_hh.name,
        place_of_service=contract.place_of_service,
        wound_order_included=contract.wound_order_included,
        diagnosis_text=contract.wound_or_clinical_information,
        insurance_provider=None if primary is None else primary.payer_name,
        insurance_id=None if primary is None else primary.policy_number,
        insurance_group_number=None if primary is None else primary.group_number,
        referral_date=contract.referral_or_order_date,
        notes=" | ".join(notes) or None,
        source_file=source_file,
        pages_used=pages_used,
    )


def write_monday_pdf_output(
    contract: MondayPdfIntakeContract,
    pdf_path: str | Path,
    *,
    output_dir: str | Path,
    model: str,
    effort: str,
    pdf_transport: str,
) -> Path:
    pdf = Path(pdf_path)
    pages = _page_count(pdf)
    folder = Path(output_dir) / _safe_folder_name(contract, pdf)
    _write_json(folder / "monday-intake.json", contract.model_dump(mode="json"))
    _write_json(
        folder / "referral-intake.json",
        to_referral_intake(contract, source_file=pdf.name, pages_used=pages).model_dump(mode="json"),
    )
    _write_json(
        folder / "_manifest.json",
        {
            "source_file": pdf.name,
            "source_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
            "source_size_bytes": pdf.stat().st_size,
            "source_pages": pages,
            "extractor": "Anthropic focused Monday extraction plus source verification",
            "model": model,
            "effort": effort,
            "model_calls": 2,
            "pdf_transport": pdf_transport,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "contract_file": "monday-intake.json",
            "referral_adapter_file": "referral-intake.json",
        },
    )
    return folder


def _sanitize_evidence(
    contract: MondayPdfIntakeContract,
    *,
    page_count: int,
) -> MondayPdfIntakeContract:
    valid = []
    warnings = list(contract.warnings)
    for item in contract.evidence:
        pages = sorted({page for page in item.page_numbers if 1 <= page <= page_count})
        if pages != item.page_numbers:
            warnings.append(
                f"Evidence pages for {item.field_name} were restricted to the source range 1-{page_count}."
            )
        valid.append(item.model_copy(update={"page_numbers": pages}))
    return contract.model_copy(update={"evidence": valid, "warnings": warnings})


def _safe_folder_name(contract: MondayPdfIntakeContract, pdf: Path) -> str:
    candidate = contract.patient_name or pdf.stem
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", candidate).strip("._")
    return cleaned or "unknown_referral"


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract the focused Monday intake contract with one reading and one verification."
    )
    parser.add_argument("pdf_path", type=Path)
    parser.add_argument("--sent-by", default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("output") / "pdf-monday-intake")
    parser.add_argument("--model", default=os.getenv("ANTHROPIC_PDF_MODEL", DEFAULT_MODEL))
    parser.add_argument(
        "--effort",
        choices=("low", "medium", "high", "xhigh", "max"),
        default=os.getenv("ANTHROPIC_PDF_EFFORT", DEFAULT_EFFORT),
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
    )
    parser.add_argument(
        "--pdf-transport",
        choices=("inline", "files-api"),
        default=os.getenv("ANTHROPIC_PDF_TRANSPORT", DEFAULT_PDF_TRANSPORT),
    )
    args = parser.parse_args(argv)
    try:
        contract = extract_monday_from_pdf(
            args.pdf_path,
            sent_by=args.sent_by,
            model=args.model,
            effort=args.effort,
            max_tokens=args.max_tokens,
            pdf_transport=args.pdf_transport,
            progress=lambda message: print(message, flush=True),
        )
        output = write_monday_pdf_output(
            contract,
            args.pdf_path,
            output_dir=args.output_dir,
            model=args.model,
            effort=args.effort,
            pdf_transport=args.pdf_transport,
        )
    except (AnthropicJsonError, DrkPdfExtractionError) as exc:
        parser.error(str(exc))
    print(
        json.dumps(
            {
                "output": str(output),
                "patient_name": contract.patient_name,
                "threshold_complete": all(
                    (
                        contract.patient_name,
                        contract.patient_date_of_birth,
                        contract.patient_phone,
                        contract.patient_address,
                    )
                ),
                "insurance_count": len(contract.insurance_information),
                "sent_by": contract.sent_by,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
