"""CLI for realistic PDFs and exact evaluator gold records."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .metadata import sha256_bytes, write_pdf_metadata
from .records import SYNTHETIC_CASES
from .render import render_referral


DEFAULT_OUTPUT = Path("output") / "pdf" / "synthetic-referrals"


def generate_dataset(output_dir: str | Path = DEFAULT_OUTPUT) -> dict[str, object]:
    output = Path(output_dir)
    pdf_dir = output / "pdfs"
    gold_dir = output / "gold"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    gold_dir.mkdir(parents=True, exist_ok=True)

    index: list[dict[str, object]] = []
    for case in SYNTHETIC_CASES:
        filename = f"SYNTHETIC-{case.slug}.pdf"
        with TemporaryDirectory(prefix="synthetic-referral-source-") as temporary:
            source_pdf = render_referral(
                case,
                Path(temporary) / filename,
                apply_scan_style=False,
            )
            pdf_path = render_referral(case, pdf_dir / filename)
            digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
            metadata_path = pdf_path.with_suffix(".metadata.json")
            write_pdf_metadata(
                metadata_path,
                source_pdf=source_pdf,
                final_pdf=pdf_path,
                case=case,
            )
        gold = case.gold_record(filename)
        gold_path = gold_dir / f"{case.slug}.json"
        gold_path.write_text(json.dumps(gold, indent=2) + "\n", encoding="utf-8")
        index.append(
            {
                "slug": case.slug,
                "filename": filename,
                "layout": case.layout,
                "scenario": case.scenario,
                "scan_style": case.scan_style,
                "patient_name": case.patient_name,
                "sha256": digest,
                "metadata_file": str(metadata_path.relative_to(output)),
                "metadata_sha256": sha256_bytes(metadata_path.read_bytes()),
                "gold_file": str(gold_path.relative_to(output)),
                "expected_outcome": case.expected_outcome,
                "expected_monday_duplicate": case.expected_monday_duplicate,
                "expected_drk_duplicate": case.expected_drk_duplicate,
                "email_subject": f"[SYNTHETIC TEST] Referral - {case.patient_name}",
            }
        )

    (output / "dataset.json").write_text(
        json.dumps({"version": 1, "synthetic_only": True, "cases": index}, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_csv(output / "send-list.csv", index)
    _write_readme(output / "README.md", len(index))
    return {
        "output_dir": str(output.resolve()),
        "pdf_count": len(index),
        "dataset": str((output / "dataset.json").resolve()),
        "send_list": str((output / "send-list.csv").resolve()),
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    columns = (
        "filename",
        "email_subject",
        "scenario",
        "scan_style",
        "expected_outcome",
        "expected_monday_duplicate",
        "expected_drk_duplicate",
        "sha256",
    )
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_readme(path: Path, count: int) -> None:
    path.write_text(
        f"""# Realistic synthetic referral set

This folder contains {count} generated referral PDFs. Every person, identifier,
address, phone number, insurer, and clinical scenario is synthetic test data.

- `pdfs/`: attachments to send individually to the testing infobox.
- `pdfs/*.metadata.json`: clean source pages and typed PHI spans for each PDF.
- `gold/`: exact expected extraction JSON; do not attach these files to emails.
- `dataset.json`: case-to-file/hash manifest for automated evaluation.
- `send-list.csv`: suggested email subject and expected workflow branch.

Send one PDF per email. Keep the generated filename unchanged so extraction output
can be joined to its gold record. These documents must never be used for care.
""",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate realistic synthetic referral PDFs and gold JSON.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    print(json.dumps(generate_dataset(args.output_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
