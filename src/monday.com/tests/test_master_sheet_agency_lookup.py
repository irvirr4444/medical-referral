from __future__ import annotations

import json

from master_sheet_agency_lookup import find_agency_matches_from_snapshot


def test_snapshot_lookup_requires_exact_normalized_agency_name(tmp_path) -> None:
    records = tmp_path / "accounts.json"
    records.write_text(
        json.dumps(
            {
                "board": {"id": "2"},
                "items": [
                    {"id": "1", "name": "Example Home Health", "column_values": []},
                    {"id": "2", "name": "Example Home Health West", "column_values": []},
                ],
            }
        )
    )

    matches = find_agency_matches_from_snapshot("Example Home-Health", records_file=records)

    assert matches == [{"id": "1", "name": "Example Home Health"}]
