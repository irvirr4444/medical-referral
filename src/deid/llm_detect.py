"""LLM secondary PHI detection ("Identify").

The regex/harvest machinery in deidentify_patient_docs.py only removes PHI it
already knows about. This pass sends each document's extracted text to Claude
and asks for any remaining identifier mentions - relatives, employers,
caregivers, stray addresses, odd date formats - which are then fed into the
same surrogate machinery so replacements stay consistent bundle-wide.

Detections are cached in the patient's key file keyed by sha256(text), so
reruns don't re-bill the API.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Callable

import pymupdf

DEFAULT_MODEL = "claude-sonnet-5"
MAX_TEXT_CHARS = 150_000  # per document; larger docs are truncated with a flag

# LLM entity type -> surrogate category understood by the caller's factory
TYPE_TO_CATEGORY = {
    "PATIENT_NAME": "person",
    "RELATIVE_NAME": "person",
    "STAFF_NAME": "person",
    "PROVIDER_NAME": "provider",     # dropped when providers are kept
    "FACILITY": "org",               # dropped when facilities are kept
    "EMPLOYER": "org",
    "ADDRESS": "street",
    "STREET": "street",
    "CITY": "city",
    "ZIP": "zip",
    "DATE": "date",
    "PHONE": "phone",
    "FAX": "phone",
    "EMAIL": "email",
    "SSN": "ssn",
    "MRN": "id",
    "HEALTH_PLAN_ID": "id",
    "ACCOUNT_NUMBER": "id",
    "LICENSE_NUMBER": "id",
    "VEHICLE_ID": "id",
    "DEVICE_ID": "id",
    "URL": "url",
    "IP_ADDRESS": "ip",
    "UNIQUE_ID": "id",
}

SYSTEM_PROMPT = """\
You are a HIPAA Safe Harbor de-identification detector for medical documents.
Find every mention of the 18 Safe Harbor identifier categories that relates to
the PATIENT (or the patient's relatives, employers, caregivers, or household
members) in the text you are given, plus healthcare organization names.

Return STRICT JSON only, in this shape:
{"entities": [{"type": "<TYPE>", "value": "<verbatim substring from the text>"}]}

Allowed TYPE values:
PATIENT_NAME, RELATIVE_NAME, STAFF_NAME, PROVIDER_NAME, FACILITY, EMPLOYER,
ADDRESS, STREET, CITY, ZIP, DATE, PHONE, FAX, EMAIL, SSN, MRN, HEALTH_PLAN_ID,
ACCOUNT_NUMBER, LICENSE_NUMBER, VEHICLE_ID, DEVICE_ID, URL, IP_ADDRESS, UNIQUE_ID

Rules:
- "value" must be copied VERBATIM from the text (exact characters), one entity
  per distinct string. Do not invent, normalize, or merge values.
- Label licensed clinicians treating the patient as PROVIDER_NAME, other
  healthcare workers or office staff as STAFF_NAME, family/friends/caregivers
  as RELATIVE_NAME.
- Label hospitals/clinics/companies as FACILITY; the patient's employer as EMPLOYER.
- Include partial mentions (a bare first or last name of the patient or a
  relative counts).
- Do NOT include: bare years, ages under 90, medication names, diagnoses,
  CPT/ICD codes, insurer names of national payers (Medicare, Medicaid, BCBS),
  US state names, or generic words.
- If there is nothing to report, return {"entities": []}.
"""


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def extract_document_text(pdf: Path) -> str:
    doc = pymupdf.open(pdf)
    chunks = []
    for page in doc:
        text = page.get_text()
        if not text.strip():
            # scan / vector line art / undecodable font: OCR the render,
            # otherwise the detector never sees the page at all
            try:
                tp = page.get_textpage_ocr(dpi=200, full=True)
                text = page.get_text(textpage=tp)
            except (RuntimeError, ValueError):
                text = ""
        chunks.append(text)
        for w in page.widgets() or []:
            if isinstance(w.field_value, str):
                chunks.append(w.field_value)
    doc.close()
    return "\n".join(c for c in chunks if c.strip())


def _call_llm(client, model: str, text: str) -> list[dict]:
    from intake_extractor.llm.anthropic_json import call_model_for_json

    lead = ("Detect PHI in the following medical document text and answer "
            "with the strict JSON object described in your instructions.\n\n"
            "<document>\n" + text + "\n</document>")
    parsed = call_model_for_json(
        client, model_name=model, max_tokens=8000,
        system_prompt=SYSTEM_PROMPT, user_content=[], lead_text=lead)
    entities = parsed.get("entities", [])
    return [e for e in entities
            if isinstance(e, dict) and e.get("type") in TYPE_TO_CATEGORY
            and isinstance(e.get("value"), str) and e["value"].strip()]


def detect_phi_for_folder(
    folder: Path,
    *,
    cache: dict,
    keep_providers: bool,
    keep_facilities: bool,
    surrogate_for: Callable[[str, str], str | None],
    model: str | None = None,
) -> tuple[dict[str, str], list[dict], list[str]]:
    """Run LLM PHI detection over every PDF in a patient folder.

    `surrogate_for(category, value)` renders the replacement for a detection
    (returns None to skip). Returns (additions to the known map,
    review items for the report, flags).
    """
    from intake_extractor.llm.anthropic_json import AnthropicJsonError, build_client

    model = model or os.getenv("ANTHROPIC_DEID_MODEL", DEFAULT_MODEL)
    additions: dict[str, str] = {}
    review: list[dict] = []
    flags: list[str] = []
    client = None

    # phase 1: gather detections for every document (cache-aware)
    per_doc: list[tuple[str, list[dict]]] = []
    for pdf in sorted(folder.rglob("*.pdf")):
        text = extract_document_text(pdf)
        if not text.strip():
            continue
        if len(text) > MAX_TEXT_CHARS:
            text = text[:MAX_TEXT_CHARS]
            flags.append(f"{pdf.name}: text truncated for LLM detection")
        digest = _sha(text)
        if digest in cache:
            entities = cache[digest]
        else:
            if client is None:
                try:
                    client = build_client()
                except AnthropicJsonError as exc:
                    flags.append(f"LLM detection skipped: {exc}")
                    return additions, review, flags
            try:
                entities = _call_llm(client, model, text)
            except Exception as exc:  # capacity, auth, parse - never block de-id
                flags.append(f"{pdf.name}: LLM detection failed ({exc}) "
                             f"- regex/harvest coverage only")
                continue
            cache[digest] = entities
        per_doc.append((pdf.name, entities))

    def norm_person(v: str) -> str:
        return " ".join(sorted(t for t in re.split(r"[,\s]+", v.lower())
                               if t and t not in ("md", "do", "np", "pa", "rn",
                                                  "arnp", "aprn", "dnp")))

    # a person labeled PROVIDER_NAME anywhere outranks a stray STAFF_NAME label,
    # so kept-provider names never leak into the replacement map
    provider_names = {norm_person(e["value"]) for _, ents in per_doc
                      for e in ents if e["type"] == "PROVIDER_NAME"}

    # phase 2: convert detections into replacement-map additions
    for doc_name, entities in per_doc:
        for ent in entities:
            etype, value = ent["type"], ent["value"].strip().strip(".,;:()[]")
            if len(value) < 4:
                # too short to auto-replace safely ("AB" would hit every
                # 'ab' fragment on OCR'd pages) - surface for review instead
                review.append({"file": doc_name, "type": etype,
                               "value_sha256": _sha(value),
                               "note": "too short to auto-replace - review"})
                continue
            if keep_providers and (etype == "PROVIDER_NAME" or (
                    etype in ("STAFF_NAME", "PATIENT_NAME", "RELATIVE_NAME")
                    and norm_person(value) in provider_names)):
                continue
            if etype == "FACILITY" and keep_facilities:
                continue
            category = TYPE_TO_CATEGORY[etype]
            if category == "phone" and re.search(r"[A-Za-z]{2,}", value):
                # Verbatim PHONE/FAX detections sometimes swallow surrounding
                # prose ("N 813-677-9629 (Phone) ext. 102 Amedisys TAN HH
                # spoke"). The format-preserving phone fake keeps every letter,
                # so any identifier in that prose would survive inside the
                # replacement. Map only the number-shaped substrings.
                for m in re.finditer(r"(?<!\d)\d[\d\s().\-]{7,17}\d(?!\d)", value):
                    num = m.group(0)
                    rep = surrogate_for("phone", num)
                    if rep and rep != num:
                        additions.setdefault(num, rep)
                continue
            replacement = surrogate_for(category, value)
            if replacement is None or replacement == value:
                review.append({"file": doc_name, "type": etype, "value_sha256":
                               _sha(value), "note": "not auto-replaced - review"})
                continue
            additions.setdefault(value, replacement)
            if category in ("person", "provider"):
                # reversed order + bare first/last mentions in prose
                if " " in value and "," not in value:
                    first, last = value.rsplit(" ", 1)
                    rf, rl = (replacement.rsplit(" ", 1) if " " in replacement
                              else ("", replacement))
                    additions.setdefault(f"{last}, {first}", f"{rl}, {rf}".strip(", "))
                toks = [t for t in re.split(r"[,\s]+", value) if len(t) >= 4]
                fk = replacement.split()
                for i, tok in enumerate(toks):
                    additions.setdefault(tok, fk[min(i, len(fk) - 1)])
            elif category == "org":
                # cover the stem: "Olive Health Florida" also as "Olive Health"
                cleaned = re.sub(r"[(\d].*$", "", value).strip(" -|,")
                if cleaned and cleaned.lower() != value.lower():
                    additions.setdefault(cleaned, replacement)
                toks = cleaned.split()
                if len(toks) >= 3:
                    additions.setdefault(" ".join(toks[:2]), replacement)
    return additions, review, flags
