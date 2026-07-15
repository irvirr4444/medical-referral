from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .extract_images import DEFAULT_MAX_PAGES
from .extract_text import extract_text
from .pdf_inspect import PopplerNotInstalledError, get_page_count, has_text_layer


@dataclass(frozen=True)
class RoutingReport:
    pdf: Path
    page_count: int
    routed_to: str  # "text" | "vision"
    pages_used: int
    text_chars_by_page: list[int] | None
    detected_labels: list[str]
    note: str | None = None


_LABEL_PATTERNS: dict[str, re.Pattern[str]] = {
    "patient_name": re.compile(r"\bpatient\s+name\b|\bname\s*:", re.I),
    "dob": re.compile(r"\b(dob|date\s+of\s+birth)\b", re.I),
    "mrn": re.compile(r"\bmrn\b|\bpatient\s+id\b|\baccount#\b|\bacct#\b", re.I),
    "diagnosis": re.compile(r"\bdiagnos(is|es)\b|\breason\s+for\s+referral\b|\bicd\b", re.I),
    "insurance": re.compile(r"\binsurance\b|\bpolicy\b|\bmember\b|\bsubscriber\b", re.I),
    "provider": re.compile(r"\bprovider\b|\bphysician\b|\breferr", re.I),
    "phone_fax": re.compile(r"\bphone\b|\bfax\b", re.I),
    "service": re.compile(r"\breferral\b|\brequested\s+service\b|\bprocedure\b|\bhome\s+health\b|\bwound\b|\btherapy\b", re.I),
}


def _detect_labels_from_text(text: str) -> list[str]:
    found: list[str] = []
    for label, pat in _LABEL_PATTERNS.items():
        if pat.search(text):
            found.append(label)
    return found


def inspect_and_route_pdf(pdf_path: str | Path, *, max_pages: int = DEFAULT_MAX_PAGES) -> RoutingReport:
    """
    Step 2 smoke inspection for routing correctness.

    IMPORTANT: This function intentionally avoids printing extracted PHI. It only
    reports counts and the presence of common field labels.
    """
    p = Path(pdf_path)
    page_count = get_page_count(p)
    pages_used = min(page_count, max_pages)

    try:
        text_layer = has_text_layer(p)
        note = None
    except PopplerNotInstalledError as e:
        # Dev convenience: allow running this script without Poppler installed.
        # The actual pipeline path will require Poppler; this is only for the
        # Step 2 routing confirmation.
        try:
            import pdfplumber

            with pdfplumber.open(p) as pdf:
                sample_pages = min(len(pdf.pages), 2)
                sample = "\n".join([(pdf.pages[i].extract_text() or "") for i in range(sample_pages)])
            # Heuristic: scanned PDFs usually yield empty text; a true text layer
            # yields non-trivial text containing at least some alphanumerics.
            text_layer = bool(re.search(r"[A-Za-z0-9]{10,}", sample))
            note = f"pdffonts unavailable ({e}) → used pdfplumber heuristic: {text_layer=}"
        except Exception:
            text_layer = False
            note = f"pdffonts unavailable ({e}) → used pdfplumber heuristic but it failed; defaulted to vision"

    if text_layer:
        extracted = extract_text(p, max_pages=max_pages)
        combined = extracted.combined
        labels = _detect_labels_from_text(combined)
        chars = [len(t) for t in extracted.pages]
        return RoutingReport(
            pdf=p,
            page_count=page_count,
            routed_to="text",
            pages_used=pages_used,
            text_chars_by_page=chars,
            detected_labels=labels,
            note=note,
        )

    # Vision routing: we don't run OCR here; we only confirm that we'd bundle
    # multiple page images together for a single model request.
    # (Image rasterization itself is in extract_images.py, which requires Poppler.)
    return RoutingReport(
        pdf=p,
        page_count=page_count,
        routed_to="vision",
        pages_used=pages_used,
        text_chars_by_page=None,
        detected_labels=[],
        note=note,
    )


def run_folder(input_dir: str | Path, *, max_pages: int = DEFAULT_MAX_PAGES) -> list[RoutingReport]:
    in_dir = Path(input_dir)
    pdfs = sorted([p for p in in_dir.iterdir() if p.suffix.lower() == ".pdf"])
    return [inspect_and_route_pdf(p, max_pages=max_pages) for p in pdfs]


def main() -> None:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Step 2 routing smoke-check (no PHI output).")
    parser.add_argument("input_dir", type=str, help="Folder containing PDFs (e.g., ./samples)")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES, help="Cap pages used per PDF")
    parser.add_argument("--json", action="store_true", help="Emit JSON lines")
    args = parser.parse_args()

    reports = run_folder(args.input_dir, max_pages=args.max_pages)

    if args.json:
        for r in reports:
            print(
                json.dumps(
                    {
                        "file": r.pdf.name,
                        "pages": r.page_count,
                        "routed_to": r.routed_to,
                        "pages_used": r.pages_used,
                        "text_chars_by_page": r.text_chars_by_page,
                        "detected_labels": r.detected_labels,
                        "note": r.note,
                    }
                )
            )
        return

    for r in reports:
        bits = [f"{r.pdf.name}: pages={r.page_count}", f"route={r.routed_to}", f"pages_used={r.pages_used}"]
        if r.text_chars_by_page is not None:
            bits.append(f"text_chars_by_page={r.text_chars_by_page}")
            bits.append(f"labels={r.detected_labels}")
        if r.note:
            bits.append(f"note={r.note}")
        print(" | ".join(bits))


if __name__ == "__main__":
    main()

