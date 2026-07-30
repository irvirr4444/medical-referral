from __future__ import annotations

import csv
import json
from pathlib import Path

from read_master_sheet import _row_payload, _write_reports


def _item() -> dict:
    return {
        "id": "1",
        "name": "Synthetic Patient",
        "group": {"title": "Working pipeline"},
        "column_values": [
            {"id": "date12", "text": "01/02/1980"},
            {"id": "status5__1", "text": "Seen"},
        ],
    }


class _Args:
    command = "find"
    report_name = "synthetic-report"
    format = "both"

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir


def test_row_payload_can_embed_complete_monday_item() -> None:
    payload = _row_payload(
        [_item()],
        fields=("name", "dob", "visit_status"),
        max_results=50,
        include_full_row=True,
    )

    assert payload["matched_count"] == 1
    assert payload["items"][0]["fields"]["visit_status"] == "Seen"
    assert payload["items"][0]["monday_item"] == _item()


def test_write_reports_writes_json_and_csv(tmp_path: Path) -> None:
    payload = _row_payload(
        [_item()],
        fields=("name", "dob"),
        max_results=50,
        include_full_row=True,
    )
    written = _write_reports(payload, args=_Args(tmp_path))

    json_path = tmp_path / "synthetic-report.json"
    csv_path = tmp_path / "synthetic-report.csv"
    assert written == [json_path, csv_path]
    assert json.loads(json_path.read_text(encoding="utf-8"))["items"][0]["monday_item"]["id"] == "1"
    with csv_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["name"] == "Synthetic Patient"
    assert json.loads(rows[0]["monday_item_json"])["id"] == "1"
