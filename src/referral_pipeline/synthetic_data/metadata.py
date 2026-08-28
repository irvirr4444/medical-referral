"""Lean evaluator sidecars for synthetic PDF source text and typed PHI."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from .models import SyntheticReferral


SCHEMA_VERSION = "1.0"
_EMERGENCY_CONTACT = re.compile(
    r"^(?P<name>.+?)\s*\([^)]+\),\s*(?P<phone>.+)$"
)


def sha256_bytes(value: bytes) -> str:
    """Hash helper retained for the internal dataset manifest."""

    return hashlib.sha256(value).hexdigest()


def extract_source_pages(source_pdf: str | Path) -> list[dict[str, Any]]:
    """Extract page-separated text from the clean PDF before degradation."""

    reader = PdfReader(str(source_pdf))
    return [
        {"page": page_number, "text": page.extract_text() or ""}
        for page_number, page in enumerate(reader.pages, start=1)
    ]


def _entity_candidates(case: SyntheticReferral) -> list[tuple[str, str | None]]:
    candidates: list[tuple[str, str | None]] = [
        ("PATIENT_NAME", case.patient_name),
        ("DATE_OF_BIRTH", case.patient_dob),
        ("PATIENT_PHONE_NUMBER", case.patient_phone),
        ("PATIENT_ADDRESS", case.patient_address),
        ("MEDICAL_RECORD_NUMBER", case.patient_mrn),
        ("HEALTH_PLAN_BENEFICIARY_NUMBER", case.insurance_id),
        ("HEALTH_PLAN_GROUP_NUMBER", case.insurance_group_number),
    ]
    match = _EMERGENCY_CONTACT.match(case.emergency_contact or "")
    if match:
        candidates.extend(
            (
                ("EMERGENCY_CONTACT_NAME", match.group("name")),
                ("EMERGENCY_CONTACT_PHONE_NUMBER", match.group("phone")),
            )
        )
    return candidates


def _typed_entities(
    case: SyntheticReferral,
    source_pages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for entity_type, raw_value in _entity_candidates(case):
        value = str(raw_value or "")
        key = (entity_type, value)
        if not value or key in seen:
            continue
        seen.add(key)
        occurrences: list[dict[str, int]] = []
        for page in source_pages:
            text = str(page["text"])
            start = 0
            while True:
                start = text.find(value, start)
                if start < 0:
                    break
                occurrences.append(
                    {
                        "page": int(page["page"]),
                        "char_start": start,
                        "char_end": start + len(value),
                    }
                )
                start += len(value)
        # Describe only values that are actually present in the rendered PDF.
        if occurrences:
            entities.append(
                {
                    "type": entity_type,
                    "value": value,
                    "occurrences": occurrences,
                }
            )
    return entities


def write_pdf_metadata(
    metadata_path: str | Path,
    *,
    source_pdf: str | Path,
    final_pdf: str | Path,
    case: SyntheticReferral,
) -> dict[str, Any]:
    """Write the external source-text and typed-PHI answer key."""

    metadata = Path(metadata_path)
    source_pages = extract_source_pages(source_pdf)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "document_id": case.slug,
        "pdf_filename": Path(final_pdf).name,
        "source_pages": source_pages,
        "entities": _typed_entities(case, source_pages),
    }
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return payload
