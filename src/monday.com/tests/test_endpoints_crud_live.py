from __future__ import annotations

import json

import pytest

from monday_api import monday_graphql


pytestmark = [pytest.mark.live_write]


def test_live_crud_board_group_columns_item_values(temp_board: dict) -> None:
    board_id = temp_board["board_id"]
    group_id = temp_board["group_id"]
    columns = temp_board["columns"]
    run_suffix = temp_board["run_suffix"]

    # Read-back board shape.
    board = monday_graphql(
        """
        query ($boardId: [ID!]) {
          boards(ids: $boardId) {
            id
            name
            groups { id title }
            columns { id title type }
          }
        }
        """,
        variables={"boardId": [board_id]},
    )["data"]["boards"][0]

    assert board["id"] == str(board_id) or board["id"] == board_id
    assert any(g["id"] == group_id for g in board["groups"])
    col_ids = {c["id"] for c in board["columns"]}
    assert columns["text"] in col_ids
    assert columns["status"] in col_ids
    assert columns["date"] in col_ids

    # Create another item and update multiple column values.
    item = monday_graphql(
        """
        mutation ($boardId: ID!, $groupId: String!, $name: String!) {
          create_item(board_id: $boardId, group_id: $groupId, item_name: $name) {
            id
            name
          }
        }
        """,
        variables={
            "boardId": board_id,
            "groupId": group_id,
            "name": f"crud-item-{run_suffix}",
        },
    )["data"]["create_item"]
    item_id = item["id"]

    values = {
        columns["text"]: f"hello-{run_suffix}",
        columns["date"]: {"date": "2026-07-16"},
        # Status labels vary by board defaults; omit if unsettable.
    }
    monday_graphql(
        """
        mutation ($boardId: ID!, $itemId: ID!, $values: JSON!) {
          change_multiple_column_values(
            board_id: $boardId,
            item_id: $itemId,
            column_values: $values
          ) { id }
        }
        """,
        variables={
            "boardId": board_id,
            "itemId": item_id,
            "values": json.dumps(values),
        },
    )

    read = monday_graphql(
        """
        query ($itemIds: [ID!]) {
          items(ids: $itemIds) {
            id
            name
            column_values { id text value }
          }
        }
        """,
        variables={"itemIds": [item_id]},
    )["data"]["items"][0]

    by_id = {cv["id"]: cv for cv in read["column_values"]}
    assert by_id[columns["text"]]["text"] == f"hello-{run_suffix}"
    assert "2026-07-16" in (by_id[columns["date"]]["text"] or "")
