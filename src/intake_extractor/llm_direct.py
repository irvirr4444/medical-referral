from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .anthropic_json import AnthropicJsonError, build_client, call_model_for_json
from .extraction_evidence import (
    apply_evidence_guide,
    extract_evidence_guide,
    needs_exact_field_evidence,
    prepend_evidence_guide,
)
from .pdf_inputs import PDF_INPUT_MODE_CHOICES, PdfInputMode, build_pdf_input_payload, coerce_input_mode
from .pdf_payloads import vision_user_content
from .postprocess import normalize_referral
from .repair import (
    merge_contact_repair_payload,
    merge_header_payload,
    merge_requested_services_payload,
    should_repair_contacts,
    should_repair_header_fields,
    should_repair_requested_services,
)
from .schema import ReferralIntake
from .selection import DEFAULT_SELECTION_CONFIG, select_image_pages, select_text_pages

# By default, evaluate the full document. Use --max-pages to cap pages deliberately.
DEFAULT_MAX_PAGES: int | None = None

logger = logging.getLogger(__name__)

MODEL_NAME = "claude-sonnet-5"
MAX_TOKENS = 4000


DIRECT_JSON_PROMPT = """You are extracting structured referral/intake data from heterogeneous healthcare PDFs (digital forms, scanned faxes, EHR printouts).

Return EXACTLY ONE JSON object that matches the schema below.
Do NOT include any commentary, markdown, or extra keys-JSON only.
The output MUST be strict RFC 8259 JSON:
- no code fences
- no trailing commas
- no comments
- all strings must be properly JSON-escaped (quotes/newlines/etc.)

Rules:
- Do not guess. Only extract what is explicitly present.
- If a field is missing, set it to null (or [] for lists).
- Preserve source wording as closely as possible. Do not expand abbreviations, rewrite service names, or normalize brand spacing unless the document itself does.
- Keep `notes` concise (<= 500 characters). Do NOT paste long medication lists or full problem lists into notes.
- patient_dob: use "MM/DD/YYYY" only if unambiguous; otherwise copy as written.
- patient_name / patient_phone / referring_phone / referring_fax / insurance_id: high-precision fields. Copy exact characters from the matching block when clear. If conflicting or partly unreadable, return null instead of guessing.
- patient_phone / referring_phone / referring_fax: return a single number only. Never combine home/mobile/work numbers into one string.
- patient_mrn: prefer the explicit MRN when present. If MRN is blank but a chart/patient/account ID is clearly used as the patient identifier near demographics, use that instead. Do not use fax job IDs, episode IDs, or unrelated system IDs when a patient/chart identifier is present.
- diagnosis_text: if there is no dedicated diagnosis field, you may assemble it from an explicit assessment/problem list.
- icd10_codes: return a flat list of ICD-10 codes only (no ICD-9).
- referral_date: clinical referral/order date, NOT the fax transmission timestamp.
- requested_services: include only services, supplies, tests, therapies, home-health disciplines, or medications that are explicitly being requested, ordered, or prescribed as part of the referral/order packet.
- requested_services: if multiple distinct order items appear in the packet, keep them as separate list items instead of collapsing them into one summary item.
- requested_services: preserve the original service wording closely. For example, keep "eval" if that is how the form states it.
- requested_services: do NOT turn general medication history, active med lists, staffing assignments, pharmacy profiles, or unrelated discharge medication lists into requested_services unless they are explicitly ordered referral items.
- referring_provider_name: use the ordering/referring clinician only when explicit. Do NOT use PCP, attending, admitting, cover-sheet sender, or emergency contact unless the document clearly identifies that person as the referrer/orderer.
- referring_facility: use the organization sending or originating the referral/order. Inspect fax headers/footers and cover-sheet sender blocks before leaving this null. Do NOT put a street address in this field. If only an address is shown and no organization name is explicit, set referring_facility to null.
- patient_address: choose one active/current patient address only. If the packet contains crossed-out, alternate, prior, or temporary discharge addresses, keep the best active/current one here and move alternates to notes only if materially relevant. If a prior address is crossed out and a handwritten or discharge destination is presented as the current location, prefer the current location.
- notes: include only short clinically/admin relevant leftovers that do not fit other fields (allergies, emergency contact, homebound justification, alternate address context, etc.)

Schema (keys must match exactly):
{
  "patient_name": string|null,
  "patient_dob": string|null,
  "patient_sex": string|null,
  "patient_phone": string|null,
  "patient_address": string|null,
  "patient_mrn": string|null,

  "referring_provider_name": string|null,
  "referring_facility": string|null,
  "referring_phone": string|null,
  "referring_fax": string|null,

  "diagnosis_text": string|null,
  "icd10_codes": string[],

  "insurance_provider": string|null,
  "insurance_id": string|null,
  "insurance_group_number": string|null,

  "requested_services": [
    {
      "service": string|null,
      "frequency": string|null,
      "instructions": string|null
    }
  ],

  "referral_date": string|null,

  "notes": string|null,

  "source_file": string|null,
  "pages_used": number|null
}
"""


CONTACT_REPAIR_JSON_PROMPT = """You are reviewing the same healthcare PDF again to repair commonly missed contact and header-adjacent extraction fields.

Return EXACTLY ONE JSON object with ONLY these keys:
{
  "patient_mrn": string|null,
  "patient_address": string|null,
  "referring_provider_name": string|null,
  "referring_facility": string|null,
  "referring_phone": string|null,
  "referring_fax": string|null
}

Rules:
- Only include values directly supported by the packet.
- If still missing, use null.
- For one-page faxes, inspect the top fax header and sender block for facility name, phone, and fax.
- For patient_mrn, prefer MRN/patient ID/account number over episode IDs or fax/job IDs when the chart identifier is explicit.
- Use referring_provider_name only when an ordering/referring clinician is explicit.
- Preserve wording close to the source.
"""


REQUESTED_SERVICES_REPAIR_JSON_PROMPT = """You are re-reading the same healthcare PDF to extract only the requested/ordered services list.

Return EXACTLY ONE JSON object with ONLY this shape:
{
  "requested_services": [
    {
      "service": string|null,
      "frequency": string|null,
      "instructions": string|null
    }
  ]
}

Rules:
- Capture only explicit referral/order items: therapies, skilled nursing, wound care, DME, supplies, tests, imaging, and medications that are clearly prescribed as active follow-up items.
- Do NOT include general medication profiles, active medication histories, staffing assignments, follow-up appointments, routing/admin notes, or unrelated narrative.
- Keep distinct ordered items as separate list rows.
- Preserve source wording closely. Keep "eval" if the source says "eval".
- If an EVIDENCE GUIDE includes `requested_services_block`, use that as the primary section boundary for this field.
- If no requested/ordered services are explicit, return [].
"""


HEADER_REPAIR_JSON_PROMPT = """You are reading only the first page/header area of a scanned healthcare fax.

Return EXACTLY ONE JSON object with ONLY these keys:
{
  "patient_name": string|null,
  "patient_phone": string|null,
  "referring_provider_name": string|null,
  "referring_facility": string|null,
  "referring_phone": string|null,
  "referring_fax": string|null
}

Rules:
- Focus on the fax header, sender block, and top-of-page demographics only.
- For referring_facility / referring_phone / referring_fax, prefer the sender organization and sender contact numbers shown on the fax header or sender block.
- Do NOT use unrelated inpatient unit numbers, case manager numbers, PCP numbers, pharmacy numbers, or patient phone numbers for referring contact fields.
- Use referring_provider_name only if the first page explicitly names a clinician as the referring/ordering provider.
- If unclear, return null.
"""


@dataclass(frozen=True)
class DirectExtractionOutput:
    referral: ReferralIntake
    raw_json: dict[str, Any]


class DirectExtractionError(RuntimeError):
    pass


def _log_optional_pass_failure(pass_name: str, source_file: str, exc: Exception) -> None:
    logger.warning(
        "Optional extraction pass failed",
        extra={
            "pass_name": pass_name,
            "source_file": source_file,
            "error_type": type(exc).__name__,
            "error": str(exc),
        },
    )


def _message_text_only() -> str:
    return "Extract from the document I provide. Output JSON only."


def _message_repair_fields() -> str:
    return (
        "Review the same document again and focus only on patient_mrn, patient_address, "
        "and referring contacts. Output JSON only."
    )


def _message_repair_header() -> str:
    return "Read only the first page fax header/sender block and top demographics. Output JSON only."


def _message_repair_requested_services() -> str:
    return "Review only the requested/ordered services in this document. Output JSON only."


def _repair_user_content(
    user_content: list[dict[str, object]],
) -> list[dict[str, object]]:
    return user_content


def _requested_services_user_content(
    user_content: list[dict[str, object]],
    evidence_guide: object | None,
) -> list[dict[str, object]]:
    if evidence_guide is None:
        return user_content
    return prepend_evidence_guide(
        user_content,
        evidence_guide,
        include_exact_fields=(),
        include_section_fields=("requested_services_block",),
        include_notes=False,
        header="REQUESTED SERVICES GUIDE (from the same PDF; use only to boundary the requested-services section):",
    )


def extract_direct_from_pdf(
    pdf_path: str | Path,
    *,
    input_mode: PdfInputMode = "auto",
    prefer_text: bool | None = None,
    max_pages: int | None = DEFAULT_MAX_PAGES,
) -> DirectExtractionOutput:
    p = Path(pdf_path)
    requested_mode = coerce_input_mode(input_mode, prefer_text=bool(prefer_text))
    payload = build_pdf_input_payload(
        p,
        input_mode=requested_mode,
        max_pages=max_pages,
        selection_config=DEFAULT_SELECTION_CONFIG,
    )
    selected_page_numbers = payload.selected_page_numbers
    pages_used = payload.pages_used
    user_content = payload.user_content

    client = build_client()
    logger.info(
        "Calling Claude direct JSON",
        extra={
            "source_file": p.name,
            "pages_used": pages_used,
            "selected_pages": selected_page_numbers,
            "input_mode": payload.resolved_mode,
        },
    )

    try:
        parsed = call_model_for_json(
            client,
            model_name=MODEL_NAME,
            max_tokens=MAX_TOKENS,
            system_prompt=DIRECT_JSON_PROMPT,
            user_content=user_content,
            lead_text=_message_text_only(),
        )
    except AnthropicJsonError as exc:
        raise DirectExtractionError(str(exc)) from None

    try:
        referral = ReferralIntake.model_validate(parsed)
    except ValidationError as e:
        raise DirectExtractionError(f"Claude JSON did not validate: {e.__class__.__name__}") from None

    referral.source_file = p.name
    referral.pages_used = pages_used
    needs_exact_evidence = needs_exact_field_evidence(referral)
    needs_services_repair = should_repair_requested_services(referral)
    evidence_guide = None
    if payload.selected_image_pages and (needs_exact_evidence or needs_services_repair):
        logger.info("Building extraction evidence guide", extra={"source_file": p.name})
        try:
            evidence_guide = extract_evidence_guide(
                client,
                model_name=MODEL_NAME,
                user_content=user_content,
            )
        except Exception as exc:
            _log_optional_pass_failure("evidence_guide", p.name, exc)
            evidence_guide = None
    if needs_exact_evidence and evidence_guide is not None:
        referral = apply_evidence_guide(referral, evidence_guide)
        referral.source_file = p.name
        referral.pages_used = pages_used
    if payload.selected_image_pages and should_repair_header_fields(referral):
        logger.info("Running header-focused repair pass", extra={"source_file": p.name})
        try:
            header_payload = call_model_for_json(
                client,
                model_name=MODEL_NAME,
                max_tokens=MAX_TOKENS,
                system_prompt=HEADER_REPAIR_JSON_PROMPT,
                user_content=vision_user_content(payload.selected_image_pages[:1]),
                lead_text=_message_repair_header(),
            )
        except Exception as exc:
            _log_optional_pass_failure("header_repair", p.name, exc)
        else:
            referral = merge_header_payload(referral, header_payload)
            referral.source_file = p.name
            referral.pages_used = pages_used
            if evidence_guide is not None and needs_exact_field_evidence(referral):
                referral = apply_evidence_guide(referral, evidence_guide)
                referral.source_file = p.name
                referral.pages_used = pages_used
    if needs_services_repair:
        logger.info("Running requested-services repair pass", extra={"source_file": p.name})
        try:
            services_payload = call_model_for_json(
                client,
                model_name=MODEL_NAME,
                max_tokens=MAX_TOKENS,
                system_prompt=REQUESTED_SERVICES_REPAIR_JSON_PROMPT,
                user_content=_requested_services_user_content(user_content, evidence_guide),
                lead_text=_message_repair_requested_services(),
            )
        except Exception as exc:
            _log_optional_pass_failure("requested_services_repair", p.name, exc)
        else:
            referral = merge_requested_services_payload(
                referral,
                {"requested_services": services_payload.get("requested_services")},
            )
            referral.source_file = p.name
            referral.pages_used = pages_used
    if should_repair_contacts(referral):
        logger.info("Running focused repair pass", extra={"source_file": p.name})
        try:
            repair_payload = call_model_for_json(
                client,
                model_name=MODEL_NAME,
                max_tokens=MAX_TOKENS,
                system_prompt=CONTACT_REPAIR_JSON_PROMPT,
                user_content=_repair_user_content(user_content),
                lead_text=_message_repair_fields(),
            )
        except Exception as exc:
            _log_optional_pass_failure("focused_repair", p.name, exc)
        else:
            referral = merge_contact_repair_payload(referral, repair_payload)
            referral.source_file = p.name
            referral.pages_used = pages_used
            if evidence_guide is not None and needs_exact_field_evidence(referral):
                referral = apply_evidence_guide(referral, evidence_guide)
                referral.source_file = p.name
                referral.pages_used = pages_used
    referral = normalize_referral(referral)
    return DirectExtractionOutput(referral=referral, raw_json=parsed)


def write_direct_output(out: DirectExtractionOutput, out_path: str | Path) -> None:
    Path(out_path).write_text(json.dumps(out.referral.model_dump(mode="json"), indent=2, sort_keys=True))


def extract_folder_to_expected(
    input_dir: str | Path,
    *,
    out_dir: str | Path = "out/benchmarks",
    input_mode: PdfInputMode = "auto",
    max_pages: int | None = DEFAULT_MAX_PAGES,
) -> None:
    in_dir = Path(input_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    pdfs = sorted([path for path in in_dir.iterdir() if path.suffix.lower() == ".pdf"])
    ok = 0
    combined_path = out / "_combined.expected.jsonl"
    with combined_path.open("w", encoding="utf-8") as combined:
        for pdf in pdfs:
            try:
                result = extract_direct_from_pdf(pdf, input_mode=input_mode, prefer_text=None, max_pages=max_pages)
                out_path = out / f"{pdf.stem}.expected.json"
                write_direct_output(result, out_path)
                combined.write(json.dumps(result.referral.model_dump(mode="json"), sort_keys=True) + "\n")
                ok += 1
                print(f"OK  | {pdf.name} | pages_used={result.referral.pages_used}")
            except Exception as exc:
                print(f"FAIL| {pdf.name} | err={type(exc).__name__}")
    print(f"Expected generation complete: {ok}/{len(pdfs)} succeeded. Outputs in {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Direct Claude JSON extraction (no tool forcing).")
    parser.add_argument("pdf_path", type=str, help="Path to a single PDF")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
        help="Optional: cap pages sent (default: send the full document)",
    )
    parser.add_argument(
        "--prefer-text",
        action="store_true",
        help="Force text extraction (otherwise auto-detect via pdffonts)",
    )
    parser.add_argument(
        "--input-mode",
        choices=PDF_INPUT_MODE_CHOICES,
        default="auto",
        help="PDF input mode: auto, text, image, or hybrid (text + rendered page images)",
    )
    parser.add_argument(
        "--write-out",
        type=str,
        default=None,
        help="Optional: also write JSON to this directory as <pdf_stem>.json",
    )
    args = parser.parse_args()

    pdf = Path(args.pdf_path)
    if not pdf.exists():
        raise SystemExit(f"File not found: {pdf}")
    if pdf.is_dir():
        raise SystemExit(f"Expected a PDF file, got a directory: {pdf}")

    if args.prefer_text and args.input_mode != "auto":
        raise SystemExit("Use either --prefer-text or --input-mode, not both.")

    result = extract_direct_from_pdf(
        pdf,
        input_mode=args.input_mode,
        prefer_text=(True if args.prefer_text else None),
        max_pages=args.max_pages,
    )
    print(json.dumps(result.referral.model_dump(mode="json"), indent=2, sort_keys=True))

    if args.write_out:
        out_dir = Path(args.write_out)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / (pdf.stem + ".json")
        write_direct_output(result, out_path)
        logger.info("Wrote output JSON", extra={"path": str(out_path)})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
