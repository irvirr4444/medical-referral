from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

import pytest

from referral_pipeline.integrations.monday.transport import monday_graphql


pytestmark = [pytest.mark.live_write, pytest.mark.webhook]


def _get_json(url: str, *, timeout_s: int = 10) -> dict:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post_clear(base: str) -> None:
    # Prefer GET /clear for tunnel friendliness; fall back silently.
    try:
        urllib.request.urlopen(urllib.request.Request(f"{base}/clear", method="GET"), timeout=10)
    except (urllib.error.URLError, urllib.error.HTTPError):
        pass


@pytest.fixture
def webhook_board(live_webhook_enabled: None, temp_board: dict) -> dict:
    """Ensure webhook prereqs are checked before creating a temp board."""
    return temp_board


def test_live_webhook_create_trigger_verify_delete(webhook_board: dict) -> None:
    temp_board = webhook_board
    public_url = os.environ["MONDAY_WEBHOOK_PUBLIC_URL"].rstrip("/")
    # Accept either full /webhook URL or base URL.
    if public_url.endswith("/webhook"):
        webhook_url = public_url
        events_base = public_url[: -len("/webhook")] or public_url
    else:
        webhook_url = f"{public_url}/webhook"
        events_base = public_url

    board_id = temp_board["board_id"]
    item_id = temp_board["item_id"]
    text_col = temp_board["columns"]["text"]
    run_suffix = temp_board["run_suffix"]

    # Clear prior events if receiver supports it.
    _post_clear(events_base)

    created = monday_graphql(
        """
        mutation ($boardId: ID!, $url: String!) {
          create_webhook(board_id: $boardId, url: $url, event: change_column_value) {
            id
            board_id
          }
        }
        """,
        variables={"boardId": board_id, "url": webhook_url},
    )["data"]["create_webhook"]
    webhook_id = created["id"]
    assert webhook_id

    try:
        # Trigger an event.
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
                "values": json.dumps({text_col: f"webhook-ping-{run_suffix}"}),
            },
        )

        # Poll the receiver for inbound events.
        deadline = time.time() + 45
        seen = False
        last_payload: dict | list | None = None
        while time.time() < deadline:
            try:
                last_payload = _get_json(f"{events_base}/events")
            except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
                time.sleep(2)
                continue
            events = last_payload.get("events") if isinstance(last_payload, dict) else None
            if events:
                # Any non-challenge event counts as delivery success.
                for ev in events:
                    body = ev.get("body") if isinstance(ev, dict) else None
                    if isinstance(body, dict) and "challenge" not in body:
                        seen = True
                        break
                    if isinstance(body, dict) and body.get("event"):
                        seen = True
                        break
            if seen:
                break
            time.sleep(2)

        assert seen, f"No webhook delivery observed at {events_base}/events; last={last_payload!r}"
    finally:
        monday_graphql(
            """
            mutation ($id: ID!) {
              delete_webhook(id: $id) { id }
            }
            """,
            variables={"id": webhook_id},
        )
