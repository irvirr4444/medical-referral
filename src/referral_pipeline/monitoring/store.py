"""Persistence contract and environment-based backend selection."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from referral_pipeline.monitoring.models import (
    ComponentHealth,
    ExternalOperation,
    NotificationRecord,
    OperationalSnapshot,
    OutboundAcknowledgement,
    PatientLink,
    WorkflowCase,
    WorkflowCounter,
    WorkflowDecision,
    WorkflowEvent,
    WorkflowException,
    WorkflowWorkItem,
)


class WorkflowStore(Protocol):
    def upsert_workflow_case(self, case: WorkflowCase) -> WorkflowCase: ...
    def workflow_case(self, case_id: str) -> WorkflowCase | None: ...
    def workflow_case_by_source_ref(self, source_ref: str) -> WorkflowCase | None: ...
    def workflow_case_by_monday_item_id(self, monday_item_id: str) -> WorkflowCase | None: ...
    def workflow_case_by_drk_patient_id(self, drk_patient_id: str) -> WorkflowCase | None: ...
    def list_workflow_cases(self, *, limit: int = 100) -> list[WorkflowCase]: ...
    def upsert_work_item(self, item: WorkflowWorkItem) -> WorkflowWorkItem: ...
    def work_item(self, work_item_id: str) -> WorkflowWorkItem | None: ...
    def list_work_items(
        self,
        *,
        stage: int | None = None,
        case_id: str | None = None,
        limit: int = 100,
    ) -> list[WorkflowWorkItem]: ...
    def record_decision(self, decision: WorkflowDecision) -> bool: ...
    def list_decisions(self, case_id: str) -> list[WorkflowDecision]: ...
    def upsert_external_operation(self, operation: ExternalOperation) -> ExternalOperation: ...
    def claim_external_operation(
        self,
        operation_id: str,
        *,
        case_id: str,
        claimed_by: str,
        lease_seconds: int = 300,
        allow_uncertain: bool = False,
    ) -> str: ...
    def list_external_operations(self, case_id: str) -> list[ExternalOperation]: ...
    def list_events(self, entity_id: str, *, limit: int = 100) -> list[WorkflowEvent]: ...
    def enqueue_acknowledgement(self, acknowledgement: OutboundAcknowledgement) -> bool: ...
    def claim_acknowledgement(
        self, case_id: str, *, recipient: str, payload_digest: str, lease_seconds: int = 300
    ) -> str: ...
    def mark_acknowledgement_sent(self, case_id: str) -> None: ...
    def mark_acknowledgement_failed(self, case_id: str, error: str) -> None: ...
    def save_snapshot(self, snapshot: OperationalSnapshot) -> bool: ...
    def latest_snapshot(self, source: str, external_id: str) -> OperationalSnapshot | None: ...
    def record_event(self, event: WorkflowEvent) -> bool: ...
    def upsert_exception(self, exception: WorkflowException) -> bool: ...
    def resolve_exceptions(self, *, entity_id: str, exception_type: str, resolved_at: str) -> int: ...
    def list_exceptions(
        self, *, status: str | None = None, limit: int = 200
    ) -> list[WorkflowException]: ...
    def enqueue_notification(self, notification: NotificationRecord) -> bool: ...
    def pending_notifications(self, *, limit: int = 100) -> list[NotificationRecord]: ...
    def mark_notifications_sent(self, keys: list[str]) -> None: ...
    def mark_notifications_failed(self, keys: list[str], error: str) -> None: ...
    def upsert_patient_link(self, link: PatientLink) -> None: ...
    def list_patient_links(self) -> list[PatientLink]: ...
    def find_entity_id(
        self, *, monday_item_id: str | None = None, drk_patient_id: str | None = None
    ) -> str | None: ...
    def get_counter(self, entity_id: str, counter_name: str) -> int: ...
    def set_counter(self, counter: WorkflowCounter) -> None: ...
    def record_cursor(self, source: str, cursor: str | None) -> None: ...
    def read_cursor(self, source: str) -> str | None: ...
    def component_health(self, component: str) -> ComponentHealth | None: ...
    def list_component_health(self) -> list[ComponentHealth]: ...
    def upsert_component_health(self, health: ComponentHealth) -> None: ...
    def status_summary(self) -> dict[str, object]: ...


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().casefold() in {"1", "true", "yes", "on"}


def selected_workflow_backend(backend: str | None = None) -> str:
    raw = (backend or os.getenv("WORKFLOW_DATABASE_BACKEND") or "sqlite").strip().casefold()
    return raw if raw in {"sqlite", "supabase"} else "sqlite"


def workflow_reads_existing_remote(*, backend: str | None = None) -> bool:
    """Live sessions read existing Supabase cases even when this process writes sqlite."""
    if selected_workflow_backend(backend) == "supabase":
        return True
    return _truthy_env("WORKFLOW_READ_EXISTING_REMOTE")


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


def create_routed_workflow_store(
    *,
    sqlite_path: str | Path | None = None,
    include_remote: bool | None = None,
    allow_local_fallback: bool = False,
) -> WorkflowStore:
    """Read both stores when Supabase is configured; never create new remote cases here.

    When include_remote is true, Supabase initialization failure raises unless
    allow_local_fallback is explicitly enabled for development.
    """
    from referral_pipeline.monitoring.sqlite_store import SQLiteWorkflowStore

    local = SQLiteWorkflowStore(
        Path(sqlite_path or os.getenv("WORKFLOW_SQLITE_PATH") or "tmp/workflow-monitor.sqlite")
    )
    selected = (os.getenv("WORKFLOW_DATABASE_BACKEND") or "sqlite").strip().casefold()
    want_remote = include_remote if include_remote is not None else selected == "supabase"
    if not want_remote:
        return local
    from referral_pipeline.monitoring.supabase_store import SupabaseWorkflowStore

    try:
        remote = SupabaseWorkflowStore.from_environment()
    except Exception as error:
        if allow_local_fallback:
            return local
        raise RuntimeError(
            "Supabase workflow store is required but could not be initialized. "
            "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY, or pass "
            "allow_local_fallback=True only for local development."
        ) from error
    from referral_pipeline.monitoring.routing import RoutingWorkflowStore

    return RoutingWorkflowStore(local=local, remote=remote)


def create_live_workflow_store(
    *,
    sqlite_path: str | Path | None = None,
    backend: str | None = None,
) -> WorkflowStore:
    """Operator UI and approvals see local plus already-written remote cases.

    New cases are never created in Supabase through this router. Stage 1 still
    writes through create_workflow_store using the selected backend.
    """
    selected = selected_workflow_backend(backend)
    return create_routed_workflow_store(
        sqlite_path=sqlite_path,
        include_remote=workflow_reads_existing_remote(backend=selected),
        allow_local_fallback=selected != "supabase",
    )
