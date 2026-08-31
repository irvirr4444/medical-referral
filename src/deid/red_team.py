"""Adversarial re-identification audit ("Monitor").

Feeds the de-identified bundle (PDF text, form fields, sidecar JSONs) to
Claude with a red-team prompt asking it to identify the real patient and to
list any strings it believes are REAL leaked identifiers rather than
surrogates. Every suspect is checked against the real values recorded in the
re-identification key file; any confirmed hit fails the audit.

Usage:
    PYTHONPATH=src python -m deid.red_team \
        --bundle "patient_docs_deid/<fake name>" --key deid_keys/<slug>.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import pymupdf

DEFAULT_MODEL = "claude-sonnet-5"
MAX_CHARS = 120_000

SYSTEM_PROMPT = """\
You are a privacy red-teamer auditing a supposedly de-identified medical
record bundle. The bundle should contain ONLY fabricated surrogate
identifiers. Your job is to catch any REAL protected health information that
leaked through.

Analyze the text for: real patient names (including relatives/caregivers),
real street addresses/cities/ZIPs, full dates that look authentic, phone/fax
numbers, emails, SSNs, medical record numbers, insurance IDs, account or
record numbers, and any string that looks like an authentic identifier rather
than a consistent surrogate. Consider internal inconsistencies (a name or
date that appears only once and does not match the rest of the bundle is
suspicious).

Return STRICT JSON only:
{"suspected_identifiers": [{"type": "<category>", "value": "<verbatim string>",
                            "reason": "<why you think it is real>"}],
 "patient_identity_guess": "<your best guess of the real patient's name, or null>"}
"""


def bundle_text(bundle: Path, limit: int = MAX_CHARS) -> str:
    chunks: list[str] = []
    for pdf in sorted(bundle.rglob("*.pdf")):
        doc = pymupdf.open(pdf)
        chunks.append(f"\n===== {pdf.name} =====\n")
        for page in doc:
            chunks.append(page.get_text())
            for w in page.widgets() or []:
                if isinstance(w.field_value, str):
                    chunks.append(w.field_value)
        doc.close()
    for j in sorted(bundle.glob("*.json")):
        if j.name == "_deid_report.json":
            continue
        chunks.append(f"\n===== {j.name} =====\n")
        chunks.append(j.read_text()[: limit // 4])
    return "".join(chunks)[:limit]


def real_value_patterns(key: dict) -> list[tuple[str, re.Pattern]]:
    values = set(key.get("values_replaced", {}))
    values.add(key.get("patient", ""))
    patterns = []
    for v in values:
        v = v.strip()
        if len(v) < 4:
            continue
        pat = re.escape(v)
        if v[:1].isalnum():
            pat = r"(?<![A-Za-z0-9])" + pat
        if v[-1:].isalnum():
            pat = pat + r"(?![A-Za-z0-9])"
        patterns.append((v, re.compile(pat, re.IGNORECASE)))
    return patterns


def check_guesses(suspects: list[dict], guess: str | None,
                  key: dict) -> list[dict]:
    """A suspect counts as a re-identification only if it matches a REAL value."""
    patterns = real_value_patterns(key)
    real_digit_strings = {re.sub(r"\D", "", v) for v, _ in patterns
                          if sum(c.isdigit() for c in v) >= 7}
    confirmed = []
    candidates = list(suspects)
    if guess:
        candidates.append({"type": "patient_identity_guess", "value": guess,
                           "reason": "model's identity guess"})
    for s in candidates:
        value = str(s.get("value") or "")
        digits = re.sub(r"\D", "", value)
        for real, rx in patterns:
            if rx.search(value) or (len(digits) >= 7 and digits in real_digit_strings):
                confirmed.append({**s, "matched_real_value_length": len(real)})
                break
    return confirmed


def run_red_team(bundle: Path, key_path: Path, model: str | None = None) -> dict:
    from intake_extractor.llm.anthropic_json import build_client, call_model_for_json

    key = json.loads(key_path.read_text())
    text = bundle_text(bundle)
    client = build_client()
    model = model or os.getenv("ANTHROPIC_DEID_MODEL", DEFAULT_MODEL)
    parsed = call_model_for_json(
        client, model_name=model, max_tokens=8000, system_prompt=SYSTEM_PROMPT,
        user_content=[],
        lead_text=("Audit this de-identified bundle and answer with the strict "
                   "JSON object described in your instructions.\n\n<bundle>\n"
                   + text + "\n</bundle>"))
    suspects = [s for s in parsed.get("suspected_identifiers", [])
                if isinstance(s, dict)]
    confirmed = check_guesses(suspects, parsed.get("patient_identity_guess"), key)
    result = {
        "status": "FAILED" if confirmed else "PASSED",
        "model": model,
        "suspects_raised": len(suspects),
        "confirmed_reidentifications": confirmed,
        "identity_guess_was_real": any(
            c.get("type") == "patient_identity_guess" for c in confirmed),
    }
    report_path = bundle / "_deid_report.json"
    if report_path.exists():
        report = json.loads(report_path.read_text())
        report["red_team"] = result
        report_path.write_text(json.dumps(report, indent=2))
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bundle", type=Path, required=True)
    ap.add_argument("--key", type=Path, required=True)
    ap.add_argument("--model", default=None)
    args = ap.parse_args(argv)
    result = run_red_team(args.bundle, args.key, args.model)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    sys.exit(main())
