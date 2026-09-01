"""Explicit Monday webhook subscription management.

Registration is deliberately an operator action. Importing this module or
starting the webhook receiver never creates a Monday subscription.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from referral_pipeline.integrations.monday.transport import monday_graphql


@dataclass(frozen=True)
class MondayWebhookSubscription:
    board_id: str
    callback_url: str
    event: str = "change_column_value"


class MondayWebhookRegistry:
    """Small, injectable wrapper around Monday's webhook mutations."""

    def __init__(self, graphql: Callable[..., dict[str, Any]] = monday_graphql) -> None:
        self._graphql = graphql

    def create(self, subscription: MondayWebhookSubscription) -> dict[str, Any]:
        response = self._graphql(
            """
            mutation ($boardId: ID!, $url: String!, $event: WebhookEventType!) {
              create_webhook(board_id: $boardId, url: $url, event: $event) { id }
            }
            """,
            variables={
                "boardId": subscription.board_id,
                "url": subscription.callback_url,
                "event": subscription.event,
            },
        )
        result = response.get("data", {}).get("create_webhook")
        if not isinstance(result, dict) or not result.get("id"):
            raise RuntimeError("Monday did not return a webhook subscription ID.")
        return result

    def delete(self, webhook_id: str) -> dict[str, Any]:
        response = self._graphql(
            "mutation ($id: ID!) { delete_webhook(id: $id) { id } }",
            variables={"id": str(webhook_id)},
        )
        result = response.get("data", {}).get("delete_webhook")
        if not isinstance(result, dict) or not result.get("id"):
            raise RuntimeError("Monday did not confirm webhook deletion.")
        return result
