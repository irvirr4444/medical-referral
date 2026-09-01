from __future__ import annotations

import monday_board_metadata as metadata
from referral_pipeline.integrations.monday.transport import MondayAPIError
from export_monday_boards import _board_directory_name, _is_retryable_graphql_error, _page_query


def test_build_metadata_parses_status_relation_and_population() -> None:
    board = {
        "id": "1",
        "name": "Example",
        "columns": [
            {"id": "name", "title": "Name", "type": "name", "settings_str": "{}"},
            {"id": "stage", "title": "Stage", "type": "status", "settings_str": '{"labels":{"0":"New","1":"Done"}}'},
            {"id": "agency", "title": "Agency", "type": "board_relation", "settings_str": '{"boardIds":["2"]}'},
            {"id": "computed", "title": "Computed", "type": "formula", "settings_str": "{}"},
        ],
    }
    items = [{"group": {"title": "Intake"}, "column_values": [{"id": "stage", "text": "New", "value": None}]}]
    items[0]["name"] = "Referral 1"

    result = metadata.build_board_metadata(board, items)

    by_id = {column["id"]: column for column in result["columns"]}
    assert by_id["stage"]["configured_values"] == ["New", "Done"]
    assert by_id["stage"]["populated_percent"] == 100
    assert by_id["stage"]["populated_item_count"] == 1
    assert by_id["name"]["populated_percent"] == 100
    assert by_id["agency"]["related_board_ids"] == ["2"]
    assert by_id["agency"]["automation_classification"] == "relation_requires_lookup"
    assert by_id["agency"]["relationship"] == {"kind": "board_relation", "target_board_ids": ["2"]}
    assert "does not prove" in by_id["agency"]["population_measurement"]
    assert by_id["computed"]["automation_classification"] == "derived_read_only"


def test_rate_limit_error_is_retryable() -> None:
    error = MondayAPIError("GraphQL errors", response={"errors": [{"message": "Complexity budget exhausted"}]})
    quota_error = MondayAPIError("GraphQL errors", response={"errors": [{"message": "Query quota exceeded"}]})

    assert _is_retryable_graphql_error(error)
    assert _is_retryable_graphql_error(quota_error)


def test_raw_values_are_opt_in() -> None:
    template = "column_values { __COLUMN_VALUE_FIELDS__ }"

    assert _page_query(template, include_raw_values=False) == "column_values { id text type }"
    assert _page_query(template, include_raw_values=True) == "column_values { id text type value }"


def test_board_directory_names_are_readable_and_unique() -> None:
    used: set[str] = set()

    assert _board_directory_name({"id": "1", "name": "Master Sheet"}, used) == "master-sheet"
    assert _board_directory_name({"id": "2", "name": "Master Sheet"}, used) == "master-sheet-2"
