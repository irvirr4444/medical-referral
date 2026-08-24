"""Explicit, stage-scoped Monday write capability.

Webhook ingestion is read-only. Any future write-back must pass through this
gateway, where the board, stage, column allowlist, and operator confirmation
are checked independently. The default policy is disabled.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from referral_pipeline.integrations.monday.legacy import FIELD_COLUMNS, monday_graphql


@dataclass(frozen=True)
class MondayWritePolicy:
    board_id: str
    enabled: bool = False
    stage_columns: Mapping[int, frozenset[str]] = field(default_factory=dict)

    @classmethod
    def from_environment(cls) -> "MondayWritePolicy":
        return cls(
            board_id=os.getenv("MONDAY_WRITE_BOARD_ID") or os.getenv("MONDAY_WEBHOOK_BOARD_ID") or "",
            enabled=_truthy(os.getenv("MONDAY_WRITE_ENABLED")),
            stage_columns={
                5: _env_columns("MONDAY_WRITE_STAGE5_COLUMNS"),
                6: _env_columns("MONDAY_WRITE_STAGE6_COLUMNS"),
            },
        )

    def validate(self, *, stage: int, values_by_alias: Mapping[str, Any], confirm: bool) -> None:
        if not self.enabled:
            raise PermissionError("Monday write-back is disabled")
        if not confirm:
            raise PermissionError("Monday write-back requires explicit confirmation")
        if not self.board_id:
            raise ValueError("Monday write board is not configured")
        allowed = self.stage_columns.get(stage, frozenset())
        unknown = set(values_by_alias) - set(allowed)
        if unknown:
            names = ", ".join(sorted(unknown))
            raise PermissionError(f"Monday column write is not allowed for stage {stage}: {names}")
        invalid = set(values_by_alias) - set(FIELD_COLUMNS)
        if invalid:
            raise ValueError(f"Unknown Monday field aliases: {', '.join(sorted(invalid))}")


class MondayWriteGateway:
    """Injectable implementation of Monday's multi-column mutation."""

    def __init__(
        self,
        policy: MondayWritePolicy,
        graphql: Callable[..., dict[str, Any]] = monday_graphql,
    ) -> None:
        self.policy = policy
        self._graphql = graphql

    def change_columns(
        self,
        *,
        item_id: str,
        stage: int,
        values_by_alias: Mapping[str, Any],
        confirm: bool = False,
    ) -> dict[str, Any]:
        self.policy.validate(stage=stage, values_by_alias=values_by_alias, confirm=confirm)
        column_values = {
            FIELD_COLUMNS[alias]: value for alias, value in values_by_alias.items()
        }
        response = self._graphql(
            """
            mutation ($boardId: ID!, $itemId: ID!, $columnValues: JSON!) {
              change_multiple_column_values(
                board_id: $boardId,
                item_id: $itemId,
                column_values: $columnValues
              ) { id }
            }
            """,
            variables={
                "boardId": self.policy.board_id,
                "itemId": str(item_id),
                "columnValues": json.dumps(column_values),
            },
        )
        result = response.get("data", {}).get("change_multiple_column_values")
        if not isinstance(result, dict) or not result.get("id"):
            raise RuntimeError("Monday did not confirm the column update.")
        return result


def _env_columns(name: str) -> frozenset[str]:
    return frozenset(value.strip() for value in os.getenv(name, "").split(",") if value.strip())


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}
