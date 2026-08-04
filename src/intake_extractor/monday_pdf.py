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
    _page_count,
    _write_json,
)
from .llm.anthropic_json import AnthropicJsonError
from .canonical_referral import CanonicalReferral, extract_referral_pdf
from .models.schema import ReferralIntake
from .monday_pdf_schema import (
    MondayAgencyInformation,
    MondayFieldEvidence,
    MondayInsuranceInformation,
    MondayPdfIntakeContract,
)


DEFAULT_MAX_TOKENS = 32_000


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
    """Compatibility projection; the PDF is interpreted by canonical_referral."""
    canonical = extract_referral_pdf(
        pdf_path,
        sent_by=sent_by,
        model=model,
        effort=effort,
        max_tokens=max_tokens,
        pdf_transport=pdf_transport,
        client=client,
        progress=progress,
    )
    return canonical_to_monday_contract(canonical)


def canonical_to_monday_contract(canonical: CanonicalReferral) -> MondayPdfIntakeContract:
    patient = canonical.patient
    address = patient.address
    locality = " ".join(part for part in (address.city, address.state, address.postal_code) if part)
    full_address = " ".join(part for part in (address.line_1, address.line_2, locality) if part) or None
    source = canonical.referral_source.organization
    current = canonical.home_health_or_hospice.organization
    evidence_names = {
        "patient.name": "patient_name",
        "patient.date_of_birth": "patient_date_of_birth",
        "patient.phones": "patient_phone",
        "patient.address": "patient_address",
        "home_health_or_hospice": "current_home_health_or_hospice",
        "clinical": "wound_or_clinical_information",
        "insurances": "insurance_information",
    }
    evidence = [
        MondayFieldEvidence(
            field_name=evidence_names[path],
            page_numbers=quality.evidence_pages,
            quote=quality.evidence_quote,
            confidence=quality.confidence,
        )
        for path, quality in canonical.field_quality.items()
        if path in evidence_names and quality.status in {"present", "explicitly_none"}
    ]
    return MondayPdfIntakeContract(
        patient_name=patient.name.full
        or " ".join(part for part in (patient.name.first, patient.name.middle, patient.name.last) if part)
        or None,
        patient_date_of_birth=patient.date_of_birth,
        patient_phone=patient.phones[0].number if patient.phones else None,
        patient_email=patient.email,
        patient_address=full_address,
        referring_agency=MondayAgencyInformation(
            name=source.name,
            contact_name=source.contact_name,
            phone=source.phone,
            email=source.email,
        ),
        current_home_health_or_hospice=MondayAgencyInformation(
            name=current.name,
            contact_name=current.contact_name,
            phone=current.phone,
            email=current.email,
        ),
        place_of_service=canonical.admission.place_of_service,
        wound_order_included=canonical.clinical.wound_order_included,
        wound_or_clinical_information=canonical.clinical.summary,
        insurance_information=[
            MondayInsuranceInformation(
                payer_name=item.payer_name,
                policy_number=item.policy_number,
                group_number=item.group_number,
                insurance_type=item.insurance_type,
            )
            for item in canonical.insurances
        ],
        referral_or_order_date=canonical.referral_source.referral_or_order_date,
        sent_by=canonical.source.sent_by,
        evidence=evidence,
        warnings=canonical.warnings,
    )


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
