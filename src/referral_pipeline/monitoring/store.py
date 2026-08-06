"""Persistence contract and environment-based backend selection."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from referral_pipeline.monitoring.models import (
    NotificationRecord,
    OperationalSnapshot,
    PatientLink,
    WorkflowCounter,
    WorkflowEvent,
    WorkflowException,
)


class WorkflowStore(Protocol):
    def save_snapshot(self, snapshot: OperationalSnapshot) -> bool: ...
    def latest_snapshot(self, source: str, external_id: str) -> OperationalSnapshot | None: ...
    def record_event(self, event: WorkflowEvent) -> bool: ...
    def upsert_exception(self, exception: WorkflowException) -> bool: ...
    def resolve_exceptions(self, *, entity_id: str, exception_type: str, resolved_at: str) -> int: ...
    def enqueue_notification(self, notification: NotificationRecord) -> bool: ...
    def pending_notifications(self, *, limit: int = 100) -> list[NotificationRecord]: ...
    def mark_notifications_sent(self, keys: list[str]) -> None: ...
    def mark_notifications_failed(self, keys: list[str], error: str) -> None: ...
    def upsert_patient_link(self, link: PatientLink) -> None: ...
    def find_entity_id(
        self, *, monday_item_id: str | None = None, drk_patient_id: str | None = None
    ) -> str | None: ...
    def get_counter(self, entity_id: str, counter_name: str) -> int: ...
    def set_counter(self, counter: WorkflowCounter) -> None: ...
    def record_cursor(self, source: str, cursor: str | None) -> None: ...
    def status_summary(self) -> dict[str, object]: ...


def create_workflow_store(
    *,
    backend: str | None = None,
    sqlite_path: str | Path | None = None,
) -> WorkflowStore:
    selected = (backend or os.getenv("WORKFLOW_DATABASE_BACKEND") or "sqlite").strip().casefold()
    if selected == "sqlite":
        from referral_pipeline.monitoring.sqlite_store import SQLiteWorkflowStore

        path = Path(sqlite_path or os.getenv("WORKFLOW_SQLITE_PATH") or "tmp/workflow-monitor.sqlite")
        return SQLiteWorkflowStore(path)
    if selected == "supabase":
        from referral_pipeline.monitoring.supabase_store import SupabaseWorkflowStore

        return SupabaseWorkflowStore.from_environment()
    raise ValueError("WORKFLOW_DATABASE_BACKEND must be sqlite or supabase")
