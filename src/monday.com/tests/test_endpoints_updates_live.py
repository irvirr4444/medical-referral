from __future__ import annotations

import pytest

from referral_pipeline.integrations.monday.transport import monday_graphql


pytestmark = [pytest.mark.live_write]


def test_live_create_update_and_read_back(temp_board: dict) -> None:
    item_id = temp_board["item_id"]
    body = f"api-test-update-{temp_board['run_suffix']}"

    created = monday_graphql(
        """
        mutation ($itemId: ID!, $body: String!) {
          create_update(item_id: $itemId, body: $body) { id body }
        }
        """,
        variables={"itemId": item_id, "body": body},
    )["data"]["create_update"]
    assert created["id"]
    assert body in (created.get("body") or "")

    items = monday_graphql(
        """
        query ($itemIds: [ID!]) {
          items(ids: $itemIds) {
            id
            updates { id body text_body }
          }
        }
        """,
        variables={"itemIds": [item_id]},
    )["data"]["items"]
    assert items
    updates = items[0].get("updates") or []
    assert any(
        (u.get("id") == created["id"])
        or body in (u.get("body") or "")
        or body in (u.get("text_body") or "")
        for u in updates
    )
