"""Create an advisory intake plan from a PDF or prior extraction JSON.

No code path in this CLI writes to Monday or DRK. It is intentionally suitable
for replaying sample PDFs before an infobox integration exists.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from intake_duplicate_check import check_duplicates_disabled, check_duplicates_from_snapshot, check_duplicates_live
from intake_plan import build_intake_plan
from intake_extractor.llm_direct import extract_direct_from_pdf
from intake_extractor.schema import ReferralIntake


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only referral intake action plan.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--pdf", type=Path, help="Referral PDF to extract.")
    source.add_argument("--referral-json", type=Path, help="Existing ReferralIntake JSON; skips an LLM extraction.")
    parser.add_argument("--input-mode", choices=("auto", "text", "image", "hybrid"), default="image")
    parser.add_argument("--max-pages", type=int, default=None, help="Optional maximum number of PDF pages to send.")
    parser.add_argument(
        "--monday-mode",
        choices=("disabled", "snapshot", "live-readonly"),
        default="disabled",
        help="Duplicate lookup mode. None of these modes can write to Monday.",
    )
    parser.add_argument("--monday-records-file", type=Path, help="Master Sheet records.json required for snapshot mode.")
    parser.add_argument("--include-full-row", action="store_true", help="Include full matching Monday rows in the local plan JSON.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tmp") / "intake-plans",
        help="Local output directory (default: tmp/intake-plans; contains PHI).",
    )
    return parser.parse_args(argv)


def _load_referral(args: argparse.Namespace) -> tuple[ReferralIntake, Path]:
    if args.pdf is not None:
        output = extract_direct_from_pdf(args.pdf, input_mode=args.input_mode, max_pages=args.max_pages)
        return output.referral, args.pdf
    assert args.referral_json is not None
    try:
        payload = json.loads(args.referral_json.read_text(encoding="utf-8-sig"))
        referral = ReferralIntake.model_validate(payload)
    except OSError as error:
        raise RuntimeError(f"Could not read referral JSON: {args.referral_json}") from error
    except (json.JSONDecodeError, ValidationError) as error:
        raise RuntimeError(f"Referral JSON is not a valid ReferralIntake payload: {args.referral_json}") from error
    return referral, args.referral_json


def _duplicate_check(args: argparse.Namespace, referral: ReferralIntake):
    if args.monday_mode == "disabled":
        return check_duplicates_disabled()
    if args.monday_mode == "snapshot":
        if args.monday_records_file is None:
            raise ValueError("--monday-records-file is required when --monday-mode snapshot")
        return check_duplicates_from_snapshot(
            referral,
            records_file=args.monday_records_file,
            include_full_row=args.include_full_row,
        )
    return check_duplicates_live(referral, include_full_row=args.include_full_row)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    referral, source_path = _load_referral(args)
    duplicate_check = _duplicate_check(args, referral)
    plan = build_intake_plan(referral, duplicate_check=duplicate_check)
    plan["source"] = {"path": str(source_path), "kind": "pdf" if args.pdf is not None else "referral_json"}

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / f"{source_path.stem}.intake-plan.json"
    output_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "outcome": plan["outcome"],
                "threshold_missing_count": len(plan["validation"]["threshold_missing"]),
                "supporting_missing_count": len(plan["validation"]["supporting_missing"]),
                "duplicate_candidate_count": plan["monday_duplicate_check"]["candidate_count"],
                "monday_mode": args.monday_mode,
                "written_plan": str(output_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
