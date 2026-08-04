from __future__ import annotations

import json

import pytest

from master_sheet_reader import (
    count_field_values,
    fetch_items,
    fetch_items_by_column_value,
    fetch_items_by_name_search,
    filter_by_field,
    find_patients,
    item_values,
    load_export_items,
    normalize_dob,
    normalize_name,
    select_fields,
)


def _item(item_id: str, name: str, *, dob: str = "", visit_status: str = "", scheduled: str = "") -> dict:
    return {
        "id": item_id,
        "name": name,
        "group": {"title": "Working pipeline"},
        "column_values": [
            {"id": "date12", "text": dob},
            {"id": "status5__1", "text": visit_status},
            {"id": "color_mkq3gga", "text": scheduled},
        ],
    }


def test_normalizers_match_name_punctuation_and_dob_formatting() -> None:
    assert normalize_name("Rodriguez Hernandez, Anita Berenice") == "RODRIGUEZ HERNANDEZ ANITA BERENICE"
    assert normalize_dob("05/17/1981") == "05171981"
    assert normalize_dob("1981-05-17") == "05171981"
    assert normalize_dob("Oct 4, 1940") == "10041940"


def test_find_patients_can_be_narrowed_by_dob() -> None:
    items = [_item("1", "Smith, Jamie", dob="01/02/1980"), _item("2", "Smith, Jamie", dob="01/02/1981")]

    assert [item["id"] for item in find_patients(items, name="Jamie Smith")] == ["1", "2"]
    assert [item["id"] for item in find_patients(items, name="Smith, Jamie", dob="01-02-1981")] == ["2"]


def test_status_filter_and_compact_selection_use_aliases() -> None:
    items = [_item("1", "Example, One", visit_status="Seen", scheduled="Scheduled"), _item("2", "Example, Two")]

    matched = filter_by_field(items, field="visit_status", equals="Seen")
    selected = select_fields(matched[0], ("name", "visit_status", "scheduled_status"))

    assert selected["fields"] == {"name": "Example, One", "visit_status": "Seen", "scheduled_status": "Scheduled"}
    assert count_field_values(items, field="visit_status") == [{"value": "<blank>", "count": 1}, {"value": "Seen", "count": 1}]


def test_filter_requires_one_comparison_and_known_field() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        filter_by_field([], field="visit_status")
    with pytest.raises(ValueError, match="Unknown field"):
        filter_by_field([], field="unknown", equals="x")


def test_fetch_items_follows_cursor_pages() -> None:
    calls: list[dict] = []

    def fake_query(_query: str, *, variables: dict, **_kwargs: object) -> dict:
        calls.append(variables)
        if "boardIds" in variables:
            return {
                "data": {
                    "boards": [
                        {
                            "id": "1",
                            "name": "Master Sheet",
                            "items_page": {"cursor": "next", "items": [_item("1", "Example, One")]},
                        }
                    ]
                }
            }
        return {"data": {"next_items_page": {"cursor": None, "items": [_item("2", "Example, Two")]}}}

    board, items = fetch_items(board_id="1", page_size=100, query_fn=fake_query)

    assert board == {"id": "1", "name": "Master Sheet"}
    assert [item["id"] for item in items] == ["1", "2"]
    assert calls == [{"boardIds": ["1"], "limit": 100}, {"cursor": "next", "limit": 100}]


def test_fetch_items_by_column_value_uses_root_filter_query() -> None:
    calls: list[dict] = []

    def fake_query(_query: str, *, variables: dict, **_kwargs: object) -> dict:
        calls.append(variables)
        return {"data": {"items_page_by_column_values": {"cursor": None, "items": [_item("1", "Example, One")]}}}

    result = fetch_items_by_column_value(
        field="visit_status", value="Seen", board_id="1", page_size=100, query_fn=fake_query
    )

    assert [item["id"] for item in result.items] == ["1"]
    assert not result.has_more
    assert calls == [
        {
            "boardId": "1",
            "limit": 100,
            "columns": [{"column_id": "status5__1", "column_values": ["Seen"]}],
        }
    ]


def test_filtered_fetch_stops_after_requested_rows() -> None:
    def fake_query(_query: str, *, variables: dict, **_kwargs: object) -> dict:
        return {
            "data": {
                "items_page_by_column_values": {
                    "cursor": "more",
                    "items": [_item("1", "Example, One")],
                }
            }
        }

    result = fetch_items_by_column_value(
        field="visit_status", value="Seen", board_id="1", max_items=1, query_fn=fake_query
    )

    assert [item["id"] for item in result.items] == ["1"]
    assert result.has_more


def test_name_search_uses_longest_name_token_and_local_limit() -> None:
    calls: list[dict] = []

    def fake_query(_query: str, *, variables: dict, **_kwargs: object) -> dict:
        calls.append(variables)
        return {"data": {"boards": [{"items_page": {"cursor": "more", "items": [_item("1", "Example, One")]}}]}}

    result = fetch_items_by_name_search(
        name="Smith, Jamie", board_id="1", max_items=1, query_fn=fake_query
    )

    assert [item["id"] for item in result.items] == ["1"]
    assert result.has_more
    assert calls[0]["term"] == ["SMITH"]


def test_load_export_items_reads_local_snapshot(tmp_path) -> None:
    path = tmp_path / "records.json"
    path.write_text(json.dumps({"board": {"id": "1", "name": "Master Sheet"}, "items": [_item("1", "Example, One")]}))

    board, items = load_export_items(path)

    assert board == {"id": "1", "name": "Master Sheet"}
    assert [item["id"] for item in items] == ["1"]
