"""Validated Monday webhook contracts and Stage 5/6 column subscriptions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from referral_pipeline.integrations.monday.legacy import FIELD_COLUMNS


# These are the fields whose changes can alter Stage 5 or Stage 6 monitoring.
# The subscription itself is board/event based; this allowlist prevents noisy
# changes elsewhere on the board from causing an unnecessary fetch.
STAGE_WEBHOOK_COLUMN_ALIASES: dict[int, tuple[str, ...]] = {
    5: (
        "stage",
        "case_manager",
        "sent_to_cm",
        "due_date",
        "appointment_date",
        "scheduling_complete",
        "scheduled_status",
    ),
    6: (
        "stage",
        "appointment_date",
        "visit_status",
        "qa_hold_reason",
        "discharge_reason",
    ),
}
WEBHOOK_COLUMN_ALIASES: tuple[str, ...] = tuple(
    dict.fromkeys(alias for aliases in STAGE_WEBHOOK_COLUMN_ALIASES.values() for alias in aliases)
)
WEBHOOK_COLUMN_IDS: frozenset[str] = frozenset(
    FIELD_COLUMNS[alias] for alias in WEBHOOK_COLUMN_ALIASES
)
# Monday names the subscription `change_column_value`, but the documented
# delivery payload uses `update_column_value`. Accept both so API-created and
# Automations Center subscriptions share the same internal contract.
COLUMN_CHANGE_EVENT_TYPES: frozenset[str] = frozenset(
    {"change_column_value", "update_column_value"}
)


class WebhookPayloadError(ValueError):
    """Raised when a Monday delivery cannot be trusted or understood."""


@dataclass(frozen=True)
class MondayWebhookEvent:
    """The small, source-independent event contract used by the processor."""

    event_key: str
    item_id: str
    column_id: str
    board_id: str | None
    event_type: str


def parse_webhook_payload(
    payload: Mapping[str, Any],
    *,
    expected_board_id: str | None = None,
) -> MondayWebhookEvent | dict[str, str]:
    """Return a validated event or an ignored-result body."""

    if not isinstance(payload, Mapping):
        return {"ignored": "invalid_payload"}
    if "challenge" in payload:
        return {"challenge": str(payload["challenge"])}

    raw_event = payload.get("event")
    if not isinstance(raw_event, Mapping):
        return {"ignored": "no_event"}

    event_type = str(raw_event.get("type") or raw_event.get("eventType") or "change_column_value")
    if event_type not in COLUMN_CHANGE_EVENT_TYPES:
        return {"ignored": "event_type_not_tracked", "event_type": event_type}

    column_id = str(raw_event.get("columnId") or raw_event.get("column_id") or "")
    if column_id not in WEBHOOK_COLUMN_IDS:
        return {"ignored": "column_not_tracked", "column_id": column_id}

    item_id = str(
        raw_event.get("pulseId")
        or raw_event.get("itemId")
        or raw_event.get("item_id")
        or ""
    )
    if not item_id:
        return {"ignored": "missing_item_id"}

    board_id = _first_string(raw_event, "boardId", "board_id", "boardID")
    expected = str(expected_board_id or "").strip()
    if expected and board_id != expected:
        return {
            "ignored": "board_not_tracked" if board_id else "board_id_missing",
            "board_id": board_id or "",
        }

    supplied_event_id = _first_string(
        raw_event,
        "id",
        "eventId",
        "event_id",
        "triggerUuid",
        "trigger_uuid",
    )
    identity = supplied_event_id or _payload_digest(raw_event)
    return MondayWebhookEvent(
        event_key=f"monday-webhook:{identity}",
        item_id=item_id,
        column_id=column_id,
        board_id=board_id,
        event_type="change_column_value",
    )


def _first_string(payload: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _payload_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
