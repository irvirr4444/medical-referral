"""Score a synthetic inbox replay against its generated gold expectations."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


FIELDS = (
    "patient_name",
    "patient_dob",
    "patient_phone",
    "patient_address",
    "referring_facility",
    "diagnosis_text",
    "insurance_provider",
    "requested_services",
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a synthetic inbox replay without reading or writing Monday.")
    parser.add_argument("--fixture-dir", type=Path, default=Path("tmp") / "synthetic-referrals")
    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="Output directory produced by src/referral_pipeline/runner.py",
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args(argv)


def evaluate(fixture_dir: Path, run_dir: Path) -> dict[str, Any]:
    gold = json.loads((fixture_dir / "gold_expectations.json").read_text(encoding="utf-8"))
    expected_by_name = {case["referral"]["patient_name"]: case for case in gold}
    rows: list[dict[str, Any]] = []
    for manifest_path in run_dir.glob("*/manifest.json"):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        plan = json.loads(Path(manifest["plan_path"]).read_text(encoding="utf-8"))
        actual = plan["referral"]
        expected = expected_by_name.get(actual.get("patient_name"))
        if not expected:
            rows.append({"case": actual.get("patient_name") or manifest_path.parent.name, "field": "_case", "status": "unexpected_case"})
            continue
        for field in FIELDS:
            rows.append(
                {
                    "case": expected["slug"],
                    "field": field,
                    "expected": _display(expected["referral"].get(field)),
                    "actual": _display(actual.get(field)),
                    "status": "match" if _equal(field, expected["referral"].get(field), actual.get(field)) else "mismatch",
                }
            )
        rows.extend(
            [
                _result_row(expected["slug"], "_plan_outcome", expected["expected_outcome"], plan.get("outcome")),
                _result_row(
                    expected["slug"],
                    "_duplicate_status",
                    expected["expected_duplicate_status"],
                    (plan.get("monday_duplicate_check") or {}).get("status"),
                ),
            ]
        )
    total = len(rows)
    matched = sum(row.get("status") == "match" for row in rows)
    return {"summary": {"checks": total, "matches": matched, "accuracy": round(matched / total, 4) if total else 0.0}, "rows": rows}


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = evaluate(args.fixture_dir, args.run_dir)
    output_dir = args.output_dir or args.run_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "synthetic-evaluation.json"
    csv_path = output_dir / "synthetic-evaluation.csv"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("case", "field", "expected", "actual", "status"))
        writer.writeheader()
        writer.writerows(report["rows"])
    print(json.dumps({**report["summary"], "json_report": str(json_path), "csv_report": str(csv_path)}, indent=2))
    return 0 if report["summary"]["checks"] else 1


def _result_row(case: str, field: str, expected: object, actual: object) -> dict[str, str]:
    return {"case": case, "field": field, "expected": _display(expected), "actual": _display(actual), "status": "match" if expected == actual else "mismatch"}


def _equal(field: str, expected: object, actual: object) -> bool:
    if field == "patient_phone":
        return _digits(expected) == _digits(actual)
    if field == "requested_services":
        return _service_names(expected) == _service_names(actual)
    return _normalized(expected) == _normalized(actual)


def _service_names(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted(_normalized(item.get("service")) for item in value if isinstance(item, dict) and item.get("service"))


def _digits(value: object) -> str:
    return "".join(character for character in str(value or "") if character.isdigit())


def _normalized(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _display(value: object) -> str:
    return json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else str(value or "")


if __name__ == "__main__":
    raise SystemExit(main())
