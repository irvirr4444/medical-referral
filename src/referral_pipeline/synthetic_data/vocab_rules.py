"""Shared vocabulary quality rules for synthetic referral banks.

Used by offline expansion, the validate CLI, and tests. Runtime PDF generation
does not call Anthropic; these rules keep committed banks honest.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).with_name("vocabulary_data.json")

LEAK_RE = re.compile(
    r"\b(synthetic|training|example|fictional|fake|lorem|ipsum|placeholder|not a real)\b",
    re.IGNORECASE,
)
ICD_RE = re.compile(r"^[A-TV-Z][0-9][0-9A-Z](?:\.[0-9A-Z]{1,4})?$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z'\- ]{1,40}$")

WITHDRAWN_MEDS = (
    "ranitidine",
    "cisapride",
    "troglitazone",
    "cerivastatin",
    "phenformin",
    "astemizole",
    "terfenadine",
)

SIZE_FLOORS = {
    "first_names": 200,
    "last_names": 200,
    "facilities": 80,
    "insurers": 40,
    "medications": 60,
    "note_fragments": 200,
    "diagnoses": 200,
    "service_instructions": 80,
    "service_frequencies": 12,
    "street_names": 120,
    "cities": 80,
}

MAX_ICD_TUPLE_SHARE = 0.03
MAX_DIAGNOSIS_BIGRAM_SHARE = 0.08


def load_vocabulary_data(path: Path | None = None) -> dict[str, Any]:
    target = path or DATA_PATH
    return json.loads(target.read_text(encoding="utf-8"))


def diagnosis_family_errors(text: str, codes: list[str]) -> list[str]:
    """Return human-readable family mismatches for one diagnosis."""

    errors: list[str] = []
    if not text or not codes:
        return ["missing text or codes"]
    for code in codes:
        if not ICD_RE.match(code):
            errors.append(f"bad ICD format: {code}")
    if errors:
        return errors

    t = text.casefold()
    has = lambda prefix: any(c.startswith(prefix) for c in codes)
    has_l97 = has("L97")

    if "pressure" in t or re.search(r"\bstage\s*[1-4iv]+\b", t) or "deep tissue" in t:
        if not has("L89"):
            errors.append("pressure injury requires L89*")
    if "diabetic" in t or "neuropathic ulcer" in t:
        if not (has("E11") or has("E10")):
            errors.append("diabetic/neuropathic ulcer requires E10*/E11*")
        if "ulcer" in t and not has_l97:
            errors.append("diabetic/neuropathic ulcer requires site L97*")
    if "venous" in t:
        if not (has("I83") or has("I87")):
            errors.append("venous diagnosis requires I83*/I87*")
        if "ulcer" in t and not has_l97:
            errors.append("venous ulcer requires site L97*")
    if "arterial" in t:
        if not has("I70"):
            errors.append("arterial diagnosis requires I70*")
        if "ulcer" in t and not has_l97:
            errors.append("arterial ulcer requires site L97*")
    if "skin tear" in t and not any(c.startswith("S") for c in codes):
        errors.append("skin tear requires S*")
    if any(token in t for token in ("dehisc", "surgical wound", "postoperative wound", "post-operative")):
        if not has("T81"):
            errors.append("surgical/dehiscence wound requires T81*")
    return errors


def walk_strings(obj: Any, path: str = ""):
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            yield from walk_strings(item, f"{path}[{index}]")
    elif isinstance(obj, dict):
        for key, item in obj.items():
            child = f"{path}.{key}" if path else key
            yield from walk_strings(item, child)


def validate_vocabulary_payload(payload: dict[str, Any]) -> list[str]:
    """Return a list of blocking quality failures (empty means pass)."""

    failures: list[str] = []

    for key, floor in SIZE_FLOORS.items():
        value = payload.get(key) or []
        if len(value) < floor:
            failures.append(f"{key}: {len(value)} < floor {floor}")

    for path, text in walk_strings(payload):
        if LEAK_RE.search(text):
            failures.append(f"leak word at {path}: {text[:80]}")

    for med in payload.get("medications") or []:
        if not isinstance(med, str):
            continue
        lowered = med.casefold()
        for banned in WITHDRAWN_MEDS:
            if banned in lowered:
                failures.append(f"withdrawn medication: {med}")

    diagnoses = payload.get("diagnoses") or []
    icd_counter: Counter[tuple[str, ...]] = Counter()
    bigram_counter: Counter[str] = Counter()
    for item in diagnoses:
        if not isinstance(item, dict):
            failures.append("diagnosis entry is not an object")
            continue
        text = item.get("text") or ""
        codes = item.get("icd10") or []
        if not isinstance(codes, list):
            failures.append(f"diagnosis codes not a list: {text[:60]}")
            continue
        code_list = [str(code) for code in codes]
        for err in diagnosis_family_errors(str(text), code_list):
            failures.append(f"ICD family ({err}): {text[:90]}")
        icd_counter[tuple(code_list)] += 1
        words = str(text).split()
        if len(words) >= 2:
            bigram_counter[f"{words[0]} {words[1]}".casefold()] += 1

    total = len(diagnoses) or 1
    for key, count in icd_counter.items():
        share = count / total
        if share > MAX_ICD_TUPLE_SHARE + 1e-9:
            failures.append(
                f"ICD tuple share {share:.1%} > {MAX_ICD_TUPLE_SHARE:.0%}: {key} ({count}/{total})"
            )
    for key, count in bigram_counter.items():
        share = count / total
        if share > MAX_DIAGNOSIS_BIGRAM_SHARE + 1e-9:
            failures.append(
                f"diagnosis bigram share {share:.1%} > {MAX_DIAGNOSIS_BIGRAM_SHARE:.0%}: {key!r} ({count}/{total})"
            )

    for name in payload.get("first_names") or []:
        if not isinstance(name, str) or not NAME_RE.match(name):
            failures.append(f"bad first name: {name!r}")
    for name in payload.get("last_names") or []:
        if not isinstance(name, str) or not NAME_RE.match(name):
            failures.append(f"bad last name: {name!r}")

    for city in payload.get("cities") or []:
        if not isinstance(city, dict) or not all(city.get(k) for k in ("city", "state", "zip")):
            failures.append(f"bad city entry: {city!r}")

    return failures


def failing_diagnoses(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in payload.get("diagnoses") or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "")
        codes = [str(c) for c in (item.get("icd10") or [])]
        if diagnosis_family_errors(text, codes):
            out.append(item)
    return out
