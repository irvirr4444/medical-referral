"""Turn a Monday.com column-change webhook event into a monitoring update.

Scaffolding only: nothing here calls the create_webhook mutation, and no route
is exposed on a public URL yet (render.yaml still deploys a worker-only
service with no public endpoint). Once a public URL exists, wiring up the
real subscription is the only remaining step -- this module already does the
identity resolution, rule evaluation, and stage-mapped exception handling via
the same WorkflowMonitoringService path the polling monitor cycle uses.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from referral_pipeline.monitoring.config import MonitoringConfig
from referral_pipeline.monitoring.monday_source import monday_item_to_snapshot
from referral_pipeline.monitoring.service import WorkflowMonitoringService
from referral_pipeline.monitoring.store import WorkflowStore

SRC_ROOT = Path(__file__).resolve().parents[2]
MONDAY_DIR = SRC_ROOT / "monday.com"
if str(MONDAY_DIR) not in sys.path:
    sys.path.insert(0, str(MONDAY_DIR))

from master_sheet_reader import FIELD_COLUMNS, fetch_items_by_ids  # noqa: E402

FetchItemsFn = Callable[..., tuple[dict[str, Any], list[dict[str, Any]]]]

# Only these columns matter for Stage 5/6 -- everything else (name edits,
# notes, unrelated statuses) is noise the monitor doesn't need to react to.
WEBHOOK_COLUMN_ALIASES: tuple[str, ...] = (
    "scheduled_status",
    "scheduling_complete",
    "appointment_date",
    "visit_status",
)
WEBHOOK_COLUMN_IDS: frozenset[str] = frozenset(
    FIELD_COLUMNS[alias] for alias in WEBHOOK_COLUMN_ALIASES
)


class WebhookAuthError(Exception):
    """Raised when a webhook request fails the shared-secret check."""


def verify_webhook_token(query_token: str | None, *, expected: str | None) -> None:
    """Reject requests that don't carry the secret placed in the registered URL.

    Monday does not sign webhook payloads, so the URL itself (chosen when we
    call create_webhook) is the only thing standing between this endpoint and
    the open internet once it is public. expected=None means no secret has
    been configured -- that's a "not ready to go public" state, not a bypass.
    """
    if not expected:
        raise WebhookAuthError("MONDAY_WEBHOOK_TOKEN is not configured")
    if query_token != expected:
        raise WebhookAuthError("invalid or missing webhook token")


def handle_webhook_payload(
    payload: dict[str, Any],
    *,
    store: WorkflowStore,
    config: MonitoringConfig,
    now: datetime | None = None,
    fetch_items_fn: FetchItemsFn = fetch_items_by_ids,
) -> dict[str, Any]:
    """Process one Monday webhook delivery. Returns the JSON body to send back."""
    if not isinstance(payload, dict):
        return {"ignored": "invalid_payload"}

    # Monday's one-time subscription handshake: echo the challenge back verbatim.
    if "challenge" in payload:
        return {"challenge": payload["challenge"]}

    event = payload.get("event")
    if not isinstance(event, dict):
        return {"ignored": "no_event"}

    column_id = str(event.get("columnId") or "")
    if column_id not in WEBHOOK_COLUMN_IDS:
        return {"ignored": "column_not_tracked", "column_id": column_id}

    item_id = str(event.get("pulseId") or event.get("itemId") or "")
    if not item_id:
        return {"ignored": "missing_item_id"}

    observed_at = now or datetime.now(timezone.utc)
    _, items = fetch_items_fn(ids=[item_id])
    if not items:
        return {"ignored": "item_not_found", "item_id": item_id}

    snapshot = monday_item_to_snapshot(items[0], observed_at=observed_at)
    service = WorkflowMonitoringService(store=store, config=config)
    report = service.process([snapshot], now=observed_at)
    return {"processed": True, "item_id": item_id, "report": report}
