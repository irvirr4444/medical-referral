"""Ground-truth evaluation of the de-identification pipeline ("Measure").

Generates labeled synthetic referral PDFs with the stress generator
(referral_pipeline.synthetic_data.stress), arranges each into a patient
folder the de-identifier understands, runs `deidentify_patient_docs.py`
over the batch, and verifies that ZERO ground-truth PHI values survive in
the output. Reports per-entity-type recall.

Usage:
    PYTHONPATH=src python -m deid.eval_deid --count 25 [--seed N]
        [--include-scans] [--workdir DIR] [--report PATH]

Recall here means containment: a PHI value counts as caught only if no
component of it (name tokens, date, phone, street, city, ZIP, ID) remains
anywhere in the de-identified document text (pixel OCR for scanned
profiles with --include-scans).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pymupdf

REPO_ROOT = Path(__file__).resolve().parents[2]
DEID_SCRIPT = REPO_ROOT / "deidentify_patient_docs.py"

# stress-manifest phi_values key -> metadata.json entity type
ENTITY_TYPES = {
    "patient_name": "PATIENT_NAME",
    "date_of_birth": "DATE_OF_BIRTH",
    "phone": "PATIENT_PHONE_NUMBER",
    "address": "PATIENT_ADDRESS",
    "medical_record_number": "MEDICAL_RECORD_NUMBER",
    "insurance_id": "HEALTH_PLAN_BENEFICIARY_NUMBER",
    "emergency_contact": "EMERGENCY_CONTACT",
}

# tokens too generic to count as a leak on their own (address words,
# relationship descriptors - these legitimately appear in clinical prose)
STOPWORDS = {"apt", "suite", "unit", "ste", "north", "south", "east", "west",
             "avenue", "street", "drive", "road", "lane", "court", "boulevard",
             "jr", "sr", "ii", "iii",
             "caregiver", "daughter", "son", "spouse", "wife", "husband",
             "mother", "father", "sister", "brother", "friend", "neighbor",
             "guardian", "partner", "cousin", "aunt", "uncle", "grandson",
             "granddaughter", "niece", "nephew"}


def build_patient_folder(row: dict, pdf_src: Path, dest: Path) -> None:
    """One patient folder per synthetic doc: the PDF + a metadata.json sidecar
    in the format harvest_phi() consumes."""
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pdf_src, dest / pdf_src.name)
    entities = []
    for key, etype in ENTITY_TYPES.items():
        value = (row.get("phi_values") or {}).get(key)
        if value:
            entities.append({"type": etype, "value": str(value), "occurrences": []})
    sidecar = {
        "schema_version": "1.0",
        "document_id": row.get("document_id", dest.name),
        "pdf_filename": pdf_src.name,
        "source_pages": [],
        "entities": entities,
    }
    (dest / f"{dest.name}.metadata.json").write_text(json.dumps(sidecar, indent=2))


def leak_terms(phi: dict) -> dict[str, list[str]]:
    """Per entity type, the strings whose presence in output counts as a leak."""
    terms: dict[str, list[str]] = {}

    def add(etype: str, *values):
        bucket = terms.setdefault(etype, [])
        for v in values:
            v = (v or "").strip()
            if len(v) >= 4 and v.lower() not in STOPWORDS:
                bucket.append(v)

    name = phi.get("patient_name") or ""
    add("patient_name", name, *[t for t in re.split(r"[,\s]+", name) if len(t) >= 4])
    add("date_of_birth", phi.get("date_of_birth"))
    phone = phi.get("phone") or ""
    add("phone", phone, re.sub(r"\D", "", phone))
    address = phi.get("address") or ""
    add("address", address)
    parts = [p.strip() for p in address.split(",")]
    if parts:
        add("address", parts[0])                      # street line
    if len(parts) >= 2:
        add("address", parts[1])                      # city
    m = re.search(r"\b\d{5}(?:-\d{4})?\b", address)
    if m:
        add("address", m.group(0))                    # ZIP
    add("medical_record_number", phi.get("medical_record_number"))
    add("insurance_id", phi.get("insurance_id"))
    ec = phi.get("emergency_contact") or ""
    add("emergency_contact", ec,
        *[t for t in re.split(r"[,()\s]+", ec) if len(t) >= 4 and not t.isdigit()])
    ec_phone = re.search(r"\d{3}[-.\s]?\d{3}[-.\s]?\d{4}", ec)
    if ec_phone:
        add("emergency_contact", ec_phone.group(0),
            re.sub(r"\D", "", ec_phone.group(0)))
    return terms


def extract_output_text(pdf: Path, *, ocr: bool) -> str:
    doc = pymupdf.open(pdf)
    chunks = []
    for page in doc:
        chunks.append(page.get_text())
        for w in page.widgets() or []:
            if isinstance(w.field_value, str):
                chunks.append(w.field_value)
        if ocr and any(im[2] > 900 and im[3] > 900 for im in page.get_images(full=True)):
            for dpi in (200, 300):
                tp = page.get_textpage_ocr(dpi=dpi, full=True)
                chunks.append(page.get_text(textpage=tp))
    doc.close()
    return "\n".join(chunks)


def find_leaks(text: str, terms: dict[str, list[str]]) -> dict[str, list[str]]:
    low = text.lower()
    digits = re.sub(r"\D", "", text)
    leaks: dict[str, list[str]] = {}
    for etype, values in terms.items():
        hit = [v for v in values
               if (v.lower() in low) or (v.isdigit() and len(v) >= 7 and v in digits)]
        if hit:
            leaks[etype] = sorted(set(hit))
    return leaks


def run_eval(*, count: int, seed: int, profiles: tuple[str, ...],
             include_scans: bool, workdir: Path) -> dict:
    from referral_pipeline.synthetic_data.stress import generate_stress_dataset

    gen_dir = workdir / "generated"
    summary_gen = generate_stress_dataset(
        gen_dir, count=count, seed=seed, profiles=profiles,
        workers=2, shard_size=1000, progress_interval=0)
    rows = [json.loads(line) for line in
            (gen_dir / "manifest.jsonl").read_text().splitlines() if line.strip()]

    patients_dir = workdir / "patients"
    for row in rows:
        build_patient_folder(row, gen_dir / row["path"],
                             patients_dir / row["document_id"])

    out_dir, keys_dir = workdir / "deid_out", workdir / "keys"
    proc = subprocess.run(
        [sys.executable, str(DEID_SCRIPT), "--input", str(patients_dir),
         "--output", str(out_dir), "--keys", str(keys_dir), "--no-llm"],
        capture_output=True, text=True, cwd=REPO_ROOT)
    if proc.returncode != 0:
        raise RuntimeError(f"de-identifier failed:\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")

    def bundle_for(document_id: str) -> Path | None:
        # de-id renames folders/files; the per-bundle report still keys its
        # "files" map by SOURCE filenames, which carry the document_id
        for bundle in sorted(p for p in out_dir.iterdir() if p.is_dir()):
            rep = bundle / "_deid_report.json"
            if rep.exists() and any(document_id in k for k in
                                    json.loads(rep.read_text()).get("files", {})):
                return bundle
        return None

    per_type = {etype: {"total": 0, "leaked": 0} for etype in ENTITY_TYPES}
    failures = []
    for row in rows:
        if not row.get("text_layer_expected", True) and not include_scans:
            continue  # scanned profile skipped in fast mode
        terms = leak_terms(row.get("phi_values") or {})
        ocr = include_scans and not row.get("text_layer_expected", True)
        bundle = bundle_for(row["document_id"])
        if bundle is None:
            failures.append({"document_id": row["document_id"],
                             "leaks": {"_pipeline": ["output bundle not found"]}})
            continue
        text = "".join(extract_output_text(pdf, ocr=ocr)
                       for pdf in bundle.rglob("*.pdf"))
        leaks = find_leaks(text, terms)
        for etype in terms:
            per_type.setdefault(etype, {"total": 0, "leaked": 0})
            per_type[etype]["total"] += 1
            if etype in leaks:
                per_type[etype]["leaked"] += 1
        if leaks:
            failures.append({"document_id": row["document_id"],
                             "scan_profile": row.get("scan_profile"),
                             "leaks": leaks})

    for etype, c in per_type.items():
        c["recall"] = round(1 - c["leaked"] / c["total"], 4) if c["total"] else None
    return {
        "count": count, "seed": seed, "profiles": list(profiles),
        "include_scans": include_scans,
        "documents_evaluated": sum(1 for r in rows
                                   if include_scans or r.get("text_layer_expected", True)),
        "per_type": per_type,
        "failures": failures,
        "overall": "PASS" if not failures else "FAIL",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--count", type=int, default=25)
    ap.add_argument("--seed", type=int, default=20260831)
    ap.add_argument("--profiles", default="native",
                    help="comma-separated scan profiles (default: native)")
    ap.add_argument("--include-scans", action="store_true",
                    help="also OCR-verify rasterized profiles (slow)")
    ap.add_argument("--workdir", type=Path, default=None)
    ap.add_argument("--report", type=Path, default=None)
    args = ap.parse_args(argv)

    workdir = args.workdir or Path(tempfile.mkdtemp(prefix="deid-eval-"))
    workdir.mkdir(parents=True, exist_ok=True)
    summary = run_eval(count=args.count, seed=args.seed,
                       profiles=tuple(args.profiles.split(",")),
                       include_scans=args.include_scans, workdir=workdir)
    report_path = args.report or workdir / "deid_eval_summary.json"
    report_path.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary["per_type"], indent=2))
    print(f"documents: {summary['documents_evaluated']}  overall: {summary['overall']}")
    print(f"report: {report_path}\nworkdir: {workdir}")
    return 0 if summary["overall"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
