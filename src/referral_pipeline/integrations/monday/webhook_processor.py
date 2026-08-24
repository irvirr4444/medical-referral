"""Process validated Monday events through the normal monitoring service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from referral_pipeline.integrations.monday.legacy import fetch_items_by_ids_readonly
from referral_pipeline.integrations.monday.webhook_contract import (
    MondayWebhookEvent,
    parse_webhook_payload,
)
from referral_pipeline.monitoring.config import MonitoringConfig
from referral_pipeline.monitoring.models import WorkflowEvent
from referral_pipeline.monitoring.monday_source import monday_item_to_snapshot
from referral_pipeline.monitoring.service import WorkflowMonitoringService
from referral_pipeline.monitoring.store import WorkflowStore

FetchItemsFn = Callable[..., tuple[dict[str, Any], list[dict[str, Any]]]]


def process_webhook_payload(
    payload: Mapping[str, Any],
    *,
    store: WorkflowStore,
    config: MonitoringConfig,
    now: datetime | None = None,
    fetch_items_fn: FetchItemsFn = fetch_items_by_ids_readonly,
    expected_board_id: str | None = None,
) -> dict[str, Any]:
    """Validate, deduplicate, fetch, and monitor one Monday delivery."""

    parsed = parse_webhook_payload(payload, expected_board_id=expected_board_id)
    if not isinstance(parsed, MondayWebhookEvent):
        return parsed

    if any(event.event_key == parsed.event_key for event in store.list_events(parsed.item_id)):
        return {"ignored": "duplicate_event", "item_id": parsed.item_id, "event_key": parsed.event_key}

    observed_at = now or datetime.now(timezone.utc)
    _, items = fetch_items_fn(ids=[parsed.item_id])
    if not items:
        return {"ignored": "item_not_found", "item_id": parsed.item_id}

    snapshot = monday_item_to_snapshot(items[0], observed_at=observed_at)
    report = WorkflowMonitoringService(store=store, config=config).process(
        [snapshot], now=observed_at
    )
    recorded = store.record_event(
        WorkflowEvent(
            event_key=parsed.event_key,
            event_type="monday.webhook.received",
            entity_id=parsed.item_id,
            source="monday-webhook",
            occurred_at=observed_at,
            details={
                "column_id": parsed.column_id,
                "board_id": parsed.board_id,
                "item_id": parsed.item_id,
            },
        )
    )
    return {
        "processed": True,
        "duplicate_after_processing": not recorded,
        "item_id": parsed.item_id,
        "column_id": parsed.column_id,
        "report": report,
    }
