"""Best-effort database audit hooks for the existing intake lifecycle."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from referral_pipeline.monitoring.models import PatientLink, WorkflowEvent
from referral_pipeline.monitoring.store import WorkflowStore, create_workflow_store


logger = logging.getLogger(__name__)


def configured_store() -> WorkflowStore | None:
    if not os.getenv("WORKFLOW_DATABASE_BACKEND", "").strip():
        return None
    return create_workflow_store()


def record_lifecycle_event(
    event_type: str,
    *,
    entity_id: str,
    source: str,
    event_key: str,
    details: dict[str, Any] | None = None,
    patient_link: PatientLink | None = None,
    allow_remote_persistence: bool = True,
) -> None:
    if (
        not allow_remote_persistence
        and os.getenv("WORKFLOW_DATABASE_BACKEND", "").strip().casefold() == "supabase"
    ):
        return
    try:
        store = configured_store()
        if store is None:
            return
        if patient_link is not None:
            store.upsert_patient_link(patient_link)
        store.record_event(
            WorkflowEvent(
                event_key=event_key,
                event_type=event_type,
                entity_id=entity_id,
                source=source,
                occurred_at=datetime.now(timezone.utc),
                details=details or {},
            )
        )
    except Exception:  # noqa: BLE001 - supplemental monitoring must not corrupt primary workflow state
        logger.exception("Could not record workflow lifecycle event %s", event_type)
