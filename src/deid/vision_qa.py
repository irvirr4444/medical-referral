"""Vision passes for scanned pages.

1. Handwritten-PHI detector (used during de-identification): OCR cannot read
   cursive, so a handwritten patient name in the middle of a consent form is
   invisible to every text-based pass. Claude vision reads it easily and
   returns approximate regions to wipe.

2. QA gate (post-run): renders every output page and asks Claude vision two
   questions - is any PHI visible (printed or handwritten), and does anything
   look visibly edited (overlapping text, half-erased words, garbled values).

Usage of the gate:
    PYTHONPATH=src python -m deid.vision_qa \
        --bundle "patient_docs_deid/<fake name>" [--model ...]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
from pathlib import Path

import pymupdf

DEFAULT_MODEL = "claude-sonnet-5"

CLASSIFY_PROMPT = """\
You are shown a small cropped region from a scanned medical document. The
region contains ink that OCR could not read (handwriting, a signature, a logo,
or degraded print).

Answer: does this region contain any identifying information - a person's
name (handwritten OR printed), a signature, a date or date of birth, a phone
number, an address, or an ID/policy/record number{org_clause}?

Do NOT count as identifying: drug names, doses, clinical instructions,
checkmarks, underlines, generic form labels, decorative graphics without text.

Return STRICT JSON: {{"contains_phi": true/false, "kind": "<short description>"}}
"""

QA_PROMPT = """\
You are the final quality gate for a de-identified medical document page.
All identifiers should already be fake surrogates; the page should look like
an ordinary, untouched document.

Report:
1. "phi_suspects": anything that looks like REAL protected health information,
   printed or handwritten (real-looking names inconsistent with the rest of the
   bundle, handwritten names/dates/signatures, ID numbers that look authentic).
2. "artifacts": anything that looks visibly edited - overlapping/double-printed
   text, half-erased words or strokes, text in a clearly different font pasted
   over a gap, garbled or impossible values (e.g. a year like 1240), leftover
   letter fragments.

Return STRICT JSON:
{"phi_suspects": [{"description": "...", "text": "<verbatim if readable>"}],
 "artifacts": [{"description": "..."}]}
Empty lists if the page is clean.
"""


def _render_b64(page, dpi: int = 130) -> tuple[str, str]:
    png = page.get_pixmap(dpi=dpi).tobytes("png")
    return (base64.standard_b64encode(png).decode("ascii"),
            hashlib.sha256(png).hexdigest())


def _ask(client, model: str, system_prompt: str, b64: str) -> dict:
    from intake_extractor.llm.anthropic_json import call_model_for_json
    return call_model_for_json(
        client, model_name=model, max_tokens=4000, system_prompt=system_prompt,
        user_content=[{"type": "image",
                       "source": {"type": "base64", "media_type": "image/png",
                                  "data": b64}}],
        lead_text="Inspect this page and answer with the strict JSON object "
                  "described in your instructions.")


def make_handwriting_classifier(cache: dict, *, include_orgs: bool,
                                model: str | None = None):
    """Returns fn(page, rect) -> bool: True when the cropped unrecognized-ink
    region contains identifying information and must be wiped. Localization
    comes from local image analysis; the vision model only judges the crop,
    which it does far more reliably than free-form bounding boxes."""
    from intake_extractor.llm.anthropic_json import build_client

    model = model or os.getenv("ANTHROPIC_DEID_MODEL", DEFAULT_MODEL)
    org_clause = (", or a healthcare organization name or logo containing text"
                  if include_orgs else "")
    system = CLASSIFY_PROMPT.format(org_clause=org_clause)
    state = {"client": None}

    def classify(page, rect: pymupdf.Rect) -> bool:
        pad = max(rect.height * 0.3, 4)
        clip = pymupdf.Rect(rect) + (-pad, -pad, pad, pad)
        clip &= page.rect
        png = page.get_pixmap(dpi=200, clip=clip).tobytes("png")
        digest = hashlib.sha256(png).hexdigest()
        key = f"hwcrop:{digest}"
        if key in cache:
            return bool(cache[key])
        if state["client"] is None:
            state["client"] = build_client()
        parsed = _ask(state["client"], model, system,
                      base64.standard_b64encode(png).decode("ascii"))
        verdict = bool(parsed.get("contains_phi"))
        cache[key] = verdict
        return verdict

    return classify


def run_qa(bundle: Path, model: str | None = None, max_pages: int | None = None) -> dict:
    from intake_extractor.llm.anthropic_json import build_client

    model = model or os.getenv("ANTHROPIC_DEID_MODEL", DEFAULT_MODEL)
    client = build_client()
    findings = []
    pages_checked = 0
    for pdf in sorted(bundle.rglob("*.pdf")):
        doc = pymupdf.open(pdf)
        for page in doc:
            if max_pages is not None and pages_checked >= max_pages:
                doc.close()
                break
            b64, _ = _render_b64(page)
            parsed = _ask(client, model, QA_PROMPT, b64)
            pages_checked += 1
            phi = parsed.get("phi_suspects") or []
            art = parsed.get("artifacts") or []
            if phi or art:
                findings.append({"file": pdf.name, "page": page.number + 1,
                                 "phi_suspects": phi, "artifacts": art})
        else:
            doc.close()
            continue
        break
    result = {
        "status": "FAILED" if any(f["phi_suspects"] for f in findings) else "PASSED",
        "model": model,
        "pages_checked": pages_checked,
        "pages_with_findings": len(findings),
        "findings": findings,
    }
    report_path = bundle / "_deid_report.json"
    if report_path.exists():
        report = json.loads(report_path.read_text())
        report["vision_qa"] = result
        report_path.write_text(json.dumps(report, indent=2))
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bundle", type=Path, required=True)
    ap.add_argument("--model", default=None)
    ap.add_argument("--max-pages", type=int, default=None)
    args = ap.parse_args(argv)
    result = run_qa(args.bundle, args.model, args.max_pages)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    sys.exit(main())
