from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from intake_extractor.aligned_intake import to_master_sheet_referral_from_canonical
from intake_extractor.canonical_referral import extract_referral_pdf
from intake_extractor.models.schema import ReferralIntake
from referral_pipeline.integrations.monday.transport import monday_file_upload, monday_graphql
from referral_board_config import ReferralBoardConfig, load_referral_board_config


def build_item_name(referral: ReferralIntake, pdf_path: Path, *, mode: str) -> str:
    if mode == "source_file" and referral.source_file:
        return referral.source_file
    if referral.patient_name and referral.referral_date:
        return f"{referral.patient_name} - {referral.referral_date}"
    if referral.patient_name:
        return referral.patient_name
    if referral.source_file:
        return referral.source_file
    return pdf_path.name


def build_column_values(referral: ReferralIntake, config: ReferralBoardConfig) -> dict[str, Any]:
    columns = config.columns
    values: dict[str, Any] = {}

    _set_text(values, columns.patient_name, referral.patient_name)
    _set_date(values, columns.patient_dob, referral.patient_dob)
    _set_text(values, columns.patient_phone, _phone_for_monday(referral.patient_phone))
    _set_text(values, columns.referring_facility, referral.referring_facility)
    _set_date(values, columns.referral_date, referral.referral_date)
    _set_insurance(values, columns.insurance_provider, referral.insurance_provider, mode=config.insurance_provider_mode)
    _set_text(values, columns.requested_services, format_requested_services(referral))
    _set_status(values, columns.extraction_status, config.status_defaults.extraction_status)
    _set_status(values, columns.review_status, config.status_defaults.review_status)
    _set_text(values, columns.notes, referral.notes)

    return values


def create_referral_item(
    *,
    board_id: int,
    group_id: str,
    item_name: str,
) -> dict[str, Any]:
    return monday_graphql(
        """
        mutation ($boardId: ID!, $groupId: String!, $name: String!) {
          create_item(board_id: $boardId, group_id: $groupId, item_name: $name) {
            id
            name
          }
        }
        """,
        variables={"boardId": board_id, "groupId": group_id, "name": item_name},
    )["data"]["create_item"]


def update_item_columns(
    *,
    board_id: int,
    item_id: str,
    column_values: dict[str, Any],
) -> None:
    if not column_values:
        return
    monday_graphql(
        """
        mutation ($boardId: ID!, $itemId: ID!, $values: JSON!) {
          change_multiple_column_values(
            board_id: $boardId,
            item_id: $itemId,
            column_values: $values,
            create_labels_if_missing: true
          ) { id }
        }
        """,
        variables={"boardId": board_id, "itemId": item_id, "values": json.dumps(column_values)},
    )


def upload_pdf_to_files_column(
    *,
    item_id: str,
    column_id: str | None,
    pdf_path: Path,
) -> dict[str, Any] | None:
    if not column_id:
        return None
    return monday_file_upload(
        query=(
            "mutation ($file: File!, $itemId: ID!, $columnId: String!) {"
            "  add_file_to_column(item_id: $itemId, column_id: $columnId, file: $file) { id name }"
            "}"
        ),
        variables={"itemId": item_id, "columnId": column_id},
        file_bytes=pdf_path.read_bytes(),
        filename=pdf_path.name,
        content_type="application/pdf",
    )["data"]["add_file_to_column"]


def get_board_items(*, board_id: int) -> list[dict[str, Any]]:
    return monday_graphql(
        """
        query ($boardId: [ID!]) {
          boards(ids: $boardId) {
            items_page(limit: 500) {
              items {
                id
                name
                column_values { id text value }
              }
            }
          }
        }
        """,
        variables={"boardId": [board_id]},
    )["data"]["boards"][0]["items_page"]["items"]


def find_existing_item(
    items: list[dict[str, Any]],
    *,
    config: ReferralBoardConfig,
    pdf_filename: str,
    item_name: str,
) -> tuple[dict[str, Any] | None, str | None]:
    file_column_id = config.columns.source_pdf_file
    if file_column_id:
        file_matches = [
            item for item in items if _item_has_file_name(item, column_id=file_column_id, filename=pdf_filename)
        ]
        if len(file_matches) > 1:
            raise RuntimeError(f"Multiple Monday items already contain attached PDF {pdf_filename}; cannot upsert safely.")
        if file_matches:
            return file_matches[0], "file"

    name_matches = [item for item in items if item.get("name") == item_name]
    if len(name_matches) > 1:
        raise RuntimeError(f"Multiple Monday items already use name {item_name!r}; cannot upsert safely.")
    if name_matches:
        return name_matches[0], "name"
    return None, None


def push_pdf_to_monday(
    pdf_path: str | Path,
    *,
    config: ReferralBoardConfig,
    input_mode: str = "image",
    write_out_dir: str | Path | None = None,
    dry_run: bool = False,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    pdf = Path(pdf_path)
    _emit(progress, f"[1/6] Extracting canonical referral from {pdf.name}")
    canonical = extract_referral_pdf(pdf)
    referral = to_master_sheet_referral_from_canonical(canonical)

    item_name = build_item_name(referral, pdf, mode=config.item_name_mode)
    column_values = build_column_values(referral, config)
    _emit(
        progress,
        (
            f"[2/6] Built Monday payload for item '{item_name}' "
            f"with {len(column_values)} mapped column value(s)"
        ),
    )
    result: dict[str, Any] = {
        "board_id": config.board_id,
        "group_id": config.group_id,
        "item_name": item_name,
        "column_values": column_values,
        "canonical_referral": canonical.model_dump(mode="json"),
        "referral": referral.model_dump(mode="json"),
    }

    if write_out_dir is not None:
        out_dir = Path(write_out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{pdf.stem}.json"
        out_path.write_text(json.dumps(result["canonical_referral"], indent=2, sort_keys=True), encoding="utf-8")
        result["written_json"] = str(out_path)
        _emit(progress, f"[3/6] Wrote local extraction JSON to {out_path}")

    if dry_run:
        _emit(progress, "[4/6] Dry run enabled; skipping Monday item creation and file upload")
        return result

    _emit(progress, f"[4/6] Looking for existing Monday item for {pdf.name}")
    existing_item, match_reason = find_existing_item(
        get_board_items(board_id=config.board_id),
        config=config,
        pdf_filename=pdf.name,
        item_name=item_name,
    )
    if existing_item is None:
        _emit(progress, f"[5/6] No existing match found; creating Monday item in board {config.board_id}, group {config.group_id}")
        item = create_referral_item(board_id=config.board_id, group_id=config.group_id, item_name=item_name)
        item_id = item["id"]
    else:
        item = {"id": existing_item["id"], "name": existing_item["name"]}
        item_id = item["id"]
        _emit(progress, f"[5/6] Reusing existing item {item_id} matched by {match_reason}; updating mapped columns")
    update_item_columns(board_id=config.board_id, item_id=item_id, column_values=column_values)
    asset = None
    if existing_item is not None and _item_has_file_name(existing_item, column_id=config.columns.source_pdf_file, filename=pdf.name):
        _emit(progress, "[6/6] Existing item already has this source PDF attached; skipped duplicate upload")
    else:
        asset = upload_pdf_to_files_column(
            item_id=item_id,
            column_id=config.columns.source_pdf_file,
            pdf_path=pdf,
        )
        if asset is not None:
            _emit(progress, f"[6/6] Uploaded source PDF to file column as asset {asset['id']}")
        else:
            _emit(progress, "[6/6] No file column configured; skipped PDF upload")

    result["item"] = item
    result["file_asset"] = asset
    return result


def format_requested_services(referral: ReferralIntake) -> str | None:
    if not referral.requested_services:
        return None
    rows: list[str] = []
    for service in referral.requested_services:
        parts = [service.service or ""]
        if service.frequency:
            parts.append(f"freq: {service.frequency}")
        if service.instructions:
            parts.append(f"instr: {service.instructions}")
        row = " | ".join(part for part in parts if part)
        if row:
            rows.append(row)
    return "\n".join(rows) or None


def _set_text(values: dict[str, Any], column_id: str | None, value: str | None) -> None:
    if column_id and value:
        values[column_id] = value


def _set_dropdown(values: dict[str, Any], column_id: str | None, value: str | None) -> None:
    if column_id and value:
        values[column_id] = {"labels": [value]}


def _set_insurance(values: dict[str, Any], column_id: str | None, value: str | None, *, mode: str) -> None:
    if not column_id or not value:
        return
    if mode == "text":
        values[column_id] = value
        return
    values[column_id] = {"labels": [value]}


def _set_status(values: dict[str, Any], column_id: str | None, label: str | None) -> None:
    if column_id and label:
        values[column_id] = {"label": label}


def _set_date(values: dict[str, Any], column_id: str | None, value: str | None) -> None:
    iso = _to_iso_date(value)
    if column_id and iso:
        values[column_id] = {"date": iso}


def _to_iso_date(value: str | None) -> str | None:
    if not value:
        return None
    parts = value.split("/")
    if len(parts) != 3:
        return None
    month, day, year = parts
    if len(year) != 4:
        return None
    try:
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    except ValueError:
        return None


def _phone_for_monday(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) == 10 and len(set(digits)) == 1:
        return None
    return value


def _item_has_file_name(item: dict[str, Any], *, column_id: str | None, filename: str) -> bool:
    if not column_id:
        return False
    for column_value in item.get("column_values") or []:
        if column_value.get("id") != column_id:
            continue
        parsed = _parse_column_value_json(column_value.get("value"))
        files = parsed.get("files") if isinstance(parsed, dict) else None
        if not isinstance(files, list):
            return False
        for file_payload in files:
            if str(file_payload.get("name") or "") == filename:
                return True
    return False


def _parse_column_value_json(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _emit(progress: Callable[[str], None] | None, message: str) -> None:
    if progress is not None:
        progress(message)


def _stderr_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract a referral PDF and push it into a Monday.com board.")
    parser.add_argument("pdf_path", type=Path, help="Path to the referral PDF")
    parser.add_argument("--config", type=Path, required=True, help="Path to board config JSON")
    parser.add_argument(
        "--input-mode",
        default="image",
        choices=("auto", "text", "image", "hybrid"),
        help="Extractor PDF input mode (default: image)",
    )
    parser.add_argument("--write-out-dir", type=Path, default=None, help="Optional local JSON output directory")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to Monday; print payload only")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress logs on stderr")
    args = parser.parse_args(argv)

    config = load_referral_board_config(args.config)
    result = push_pdf_to_monday(
        args.pdf_path,
        config=config,
        input_mode=args.input_mode,
        write_out_dir=args.write_out_dir,
        dry_run=args.dry_run,
        progress=(None if args.quiet else _stderr_progress),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
