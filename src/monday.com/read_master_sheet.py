"""Read-only command-line views of the WCW Monday.com Master Sheet."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from master_sheet_reader import (
    DEFAULT_RESULT_FIELDS,
    FIELD_COLUMNS,
    MASTER_SHEET_BOARD_ID,
    SERVER_FILTERABLE_FIELDS,
    count_field_values,
    fetch_items,
    fetch_items_by_column_value,
    fetch_items_by_name_search,
    filter_by_field,
    find_patients,
    load_export_items,
    select_fields,
)


def _parse_fields(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return DEFAULT_RESULT_FIELDS
    fields = tuple(part.strip() for part in raw.split(",") if part.strip())
    unknown = sorted(set(fields) - set(FIELD_COLUMNS))
    if unknown:
        raise ValueError(f"Unknown fields: {', '.join(unknown)}")
    return fields


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--board-id", default=MASTER_SHEET_BOARD_ID, help="Monday board ID (default: WCW Master Sheet).")
    parser.add_argument("--page-size", type=int, default=500, help="Monday page size from 1 to 500 (default: 500).")
    parser.add_argument("--max-results", type=int, default=50, help="Maximum rows printed (default: 50).")
    parser.add_argument("--all", action="store_true", help="Include every matched row in the report.")
    parser.add_argument(
        "--fields",
        default=None,
        help=f"Comma-separated aliases to print. Default: {','.join(DEFAULT_RESULT_FIELDS)}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tmp") / "monday-reports",
        help="Local report directory (default: tmp/monday-reports; contains PHI).",
    )
    parser.add_argument("--report-name", default=None, help="Optional report filename stem; do not use patient names.")
    parser.add_argument("--records-file", type=Path, default=None, help="Use an existing local records.json export instead of live Monday.")
    parser.add_argument("--format", choices=("json", "csv", "both"), default="both", help="Report format (default: both).")
    parser.add_argument(
        "--include-full-row",
        action="store_true",
        help="Include each matched item's full Monday payload in JSON and a JSON column in CSV. Handle as PHI.",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read selected Monday Master Sheet data. Output can contain PHI; do not redirect it into tracked files.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    find = subparsers.add_parser("find", help="Find patient candidates by name, optionally narrowed by DOB.")
    _add_common_arguments(find)
    find.add_argument("--name", required=True, help="Patient name to match.")
    find.add_argument("--dob", default=None, help="Optional DOB to narrow matches, e.g. 10/04/1940.")
    find.add_argument("--contains", action="store_true", help="Allow partial normalized-name matching; review results carefully.")

    status = subparsers.add_parser("status", help="List patients whose selected field equals a displayed value.")
    _add_common_arguments(status)
    status.add_argument(
        "--field",
        required=True,
        choices=sorted(SERVER_FILTERABLE_FIELDS - {"name"}),
        help="Server-filterable Master Sheet field alias.",
    )
    status_group = status.add_mutually_exclusive_group(required=True)
    status_group.add_argument("--equals", help="Exact displayed value to include.")
    status_group.add_argument("--not-equals", help="Exact displayed value to exclude.")

    intake = subparsers.add_parser("intake", help="List the configured intake-stage rows (default: In intake).")
    _add_common_arguments(intake)
    intake.add_argument("--stage", default="In intake", help="Exact Stage value (default: In intake).")

    summary = subparsers.add_parser("summary", help="Count values for a workflow field without printing patient rows.")
    summary.add_argument("--board-id", default=MASTER_SHEET_BOARD_ID, help="Monday board ID (default: WCW Master Sheet).")
    summary.add_argument("--page-size", type=int, default=500, help="Monday page size from 1 to 500 (default: 500).")
    summary.add_argument("--output-dir", type=Path, default=Path("tmp") / "monday-reports", help="Local report directory (default: tmp/monday-reports).")
    summary.add_argument("--report-name", default=None, help="Optional report filename stem.")
    summary.add_argument("--records-file", type=Path, default=None, help="Use an existing local records.json export instead of live Monday.")
    summary.add_argument("--format", choices=("json", "csv", "both"), default="both", help="Report format (default: both).")
    summary.add_argument("--field", required=True, choices=sorted(FIELD_COLUMNS), help="Field alias to count.")
    return parser


def _row_payload(
    items: list[dict[str, Any]],
    *,
    fields: tuple[str, ...],
    max_results: int,
    include_full_row: bool,
    truncated: bool = False,
) -> dict[str, Any]:
    if max_results < 1:
        raise ValueError("max_results must be at least 1")
    rows = []
    for item in items:
        row = select_fields(item, fields)
        if include_full_row:
            row["monday_item"] = item
        rows.append(row)
    return {
        "matched_count": len(items),
        "returned_count": len(items),
        "truncated": truncated,
        "items": rows,
    }


def _report_stem(args: argparse.Namespace) -> str:
    if args.report_name:
        return args.report_name
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    if args.command == "status":
        return f"status-{args.field}-{timestamp}"
    if args.command == "summary":
        return f"summary-{args.field}-{timestamp}"
    return f"{args.command}-{timestamp}"


def _write_reports(payload: dict[str, Any], *, args: argparse.Namespace) -> list[Path]:
    """Write local PHI-bearing reports rather than printing full rows to the terminal."""
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = _report_stem(args)
    written: list[Path] = []
    if args.format in {"json", "both"}:
        json_path = args.output_dir / f"{stem}.json"
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(json_path)
    if args.format in {"csv", "both"}:
        csv_path = args.output_dir / f"{stem}.csv"
        _write_csv(csv_path, payload)
        written.append(csv_path)
    return written


def _write_csv(path: Path, payload: dict[str, Any]) -> None:
    if "counts" in payload:
        rows = payload["counts"]
        headers = ("value", "count")
    else:
        rows = []
        for item in payload["items"]:
            row = {"id": item["id"], "group": item["group"], **item["fields"]}
            if "monday_item" in item:
                row["monday_item_json"] = json.dumps(item["monday_item"], ensure_ascii=False)
            rows.append(row)
        headers = tuple(dict.fromkeys(key for row in rows for key in row)) or ("id", "group")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        board: dict[str, Any] = {"id": str(args.board_id), "name": None}
        snapshot_items: list[dict[str, Any]] | None = None
        if args.records_file is not None:
            board, snapshot_items = load_export_items(args.records_file)
        if args.command == "find":
            if snapshot_items is not None:
                items = snapshot_items
                truncated = False
            else:
                result = fetch_items_by_name_search(
                    board_id=str(args.board_id),
                    name=args.name,
                    page_size=args.page_size,
                    # A DOB filter needs all same-name candidates before local narrowing.
                    max_items=None if args.all or args.dob else args.max_results,
                )
                items = result.items
                truncated = result.has_more
            matches = find_patients(items, name=args.name, dob=args.dob, contains=args.contains)
            payload: dict[str, Any] = _row_payload(
                matches,
                fields=_parse_fields(args.fields),
                max_results=args.max_results,
                include_full_row=args.include_full_row,
                truncated=truncated,
            )
        elif args.command == "status":
            if snapshot_items is not None:
                items = snapshot_items
                matches = filter_by_field(items, field=args.field, equals=args.equals, not_equals=args.not_equals)
                truncated = False
            elif args.equals is not None:
                result = fetch_items_by_column_value(
                    board_id=str(args.board_id),
                    field=args.field,
                    value=args.equals,
                    page_size=args.page_size,
                    max_items=None if args.all else args.max_results,
                )
                items = result.items
                matches = filter_by_field(items, field=args.field, equals=args.equals)
                truncated = result.has_more
            else:
                board, items = fetch_items(board_id=str(args.board_id), page_size=args.page_size)
                matches = filter_by_field(items, field=args.field, not_equals=args.not_equals)
                truncated = False
            payload = _row_payload(
                matches,
                fields=_parse_fields(args.fields),
                max_results=args.max_results,
                include_full_row=args.include_full_row,
                truncated=truncated,
            )
        elif args.command == "intake":
            if snapshot_items is not None:
                items = snapshot_items
                truncated = False
            else:
                result = fetch_items_by_column_value(
                    board_id=str(args.board_id),
                    field="stage",
                    value=args.stage,
                    page_size=args.page_size,
                    max_items=None if args.all else args.max_results,
                )
                items = result.items
                truncated = result.has_more
            matches = filter_by_field(items, field="stage", equals=args.stage)
            payload = _row_payload(
                matches,
                fields=_parse_fields(args.fields),
                max_results=args.max_results,
                include_full_row=args.include_full_row,
                truncated=truncated,
            )
        elif args.command == "summary":
            if snapshot_items is not None:
                items = snapshot_items
            else:
                board, items = fetch_items(board_id=str(args.board_id), page_size=args.page_size)
            payload = {"field": args.field, "counts": count_field_values(items, field=args.field)}
        else:  # pragma: no cover - argparse guarantees a known command.
            raise ValueError(f"Unsupported command: {args.command}")
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))
        return 2

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "board": {"id": str(board.get("id") or args.board_id), "name": board.get("name")},
        "query": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in vars(args).items()
            if key not in {"output_dir", "format", "report_name"}
        },
        **payload,
    }
    written = _write_reports(payload, args=args)
    print(json.dumps({"matched_count": payload.get("matched_count"), "reports": [str(path) for path in written]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
