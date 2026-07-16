from __future__ import annotations

import pytest

from monday_api import monday_graphql


pytestmark = [pytest.mark.live_write]


def test_live_create_subitem_and_read_back(temp_board: dict) -> None:
    parent_id = temp_board["item_id"]
    name = f"subitem-{temp_board['run_suffix']}"

    created = monday_graphql(
        """
        mutation ($parentId: ID!, $name: String!) {
          create_subitem(parent_item_id: $parentId, item_name: $name) {
            id
            name
          }
        }
        """,
        variables={"parentId": parent_id, "name": name},
    )["data"]["create_subitem"]
    assert created["id"]
    assert created["name"] == name

    items = monday_graphql(
        """
        query ($itemIds: [ID!]) {
          items(ids: $itemIds) {
            id
            subitems { id name }
          }
        }
        """,
        variables={"itemIds": [parent_id]},
    )["data"]["items"]
    assert items
    subitems = items[0].get("subitems") or []
    assert any(s["id"] == created["id"] and s["name"] == name for s in subitems)
