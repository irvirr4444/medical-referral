"""Read/write routing between local SQLite and allowlisted Supabase cases.

New cases are never created in Supabase through this router. That keeps WCW
sample documents and other non-allowlisted PHI on the local store. Lookups and
lists aggregate both stores so the demo UI can show synthetic and local cases
without copying local rows remotely.
"""

from __future__ import annotations

from typing import Any

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
from referral_pipeline.monitoring.store import WorkflowStore


class RoutingWorkflowStore:
    def __init__(self, *, local: WorkflowStore, remote: WorkflowStore) -> None:
        self.local = local
        self.remote = remote

    def persistence_for(self, case_id: str) -> str:
        if self.remote.workflow_case(case_id) is not None:
            return "supabase"
        return "sqlite"

    def upsert_workflow_case(self, case: WorkflowCase) -> WorkflowCase:
        return self._store_for(case.case_id).upsert_workflow_case(case)

    def workflow_case(self, case_id: str) -> WorkflowCase | None:
        return self.remote.workflow_case(case_id) or self.local.workflow_case(case_id)

    def workflow_case_by_source_ref(self, source_ref: str) -> WorkflowCase | None:
        return self.remote.workflow_case_by_source_ref(source_ref) or self.local.workflow_case_by_source_ref(
            source_ref
        )

    def list_workflow_cases(self, *, limit: int = 100) -> list[WorkflowCase]:
        return self._merge_cases(
            self.remote.list_workflow_cases(limit=limit),
            self.local.list_workflow_cases(limit=limit),
            limit=limit,
        )

    def upsert_work_item(self, item: WorkflowWorkItem) -> WorkflowWorkItem:
        return self._store_for(item.case_id).upsert_work_item(item)

    def work_item(self, work_item_id: str) -> WorkflowWorkItem | None:
        return self.remote.work_item(work_item_id) or self.local.work_item(work_item_id)

    def list_work_items(
        self,
        *,
        stage: int | None = None,
        case_id: str | None = None,
        limit: int = 100,
    ) -> list[WorkflowWorkItem]:
        if case_id is not None:
            return self._store_for(case_id).list_work_items(stage=stage, case_id=case_id, limit=limit)
        return _unique(
            [
                *self.remote.list_work_items(stage=stage, limit=limit),
                *self.local.list_work_items(stage=stage, limit=limit),
            ],
            key=lambda item: item.work_item_id,
            limit=limit,
        )

    def record_decision(self, decision: WorkflowDecision) -> bool:
        return self._store_for(decision.case_id).record_decision(decision)

    def list_decisions(self, case_id: str) -> list[WorkflowDecision]:
        return self._store_for(case_id).list_decisions(case_id)

    def upsert_external_operation(self, operation: ExternalOperation) -> ExternalOperation:
        return self._store_for(operation.case_id).upsert_external_operation(operation)

    def claim_external_operation(
        self,
        operation_id: str,
        *,
        case_id: str,
        claimed_by: str,
        lease_seconds: int = 300,
        allow_uncertain: bool = False,
    ) -> str:
        return self._store_for(case_id).claim_external_operation(
            operation_id,
            case_id=case_id,
            claimed_by=claimed_by,
            lease_seconds=lease_seconds,
            allow_uncertain=allow_uncertain,
        )

    def list_external_operations(self, case_id: str) -> list[ExternalOperation]:
        return self._store_for(case_id).list_external_operations(case_id)

    def list_events(self, entity_id: str, *, limit: int = 100) -> list[WorkflowEvent]:
        return self._store_for(entity_id).list_events(entity_id, limit=limit)

    def enqueue_acknowledgement(self, acknowledgement: OutboundAcknowledgement) -> bool:
        return self._store_for(acknowledgement.case_id).enqueue_acknowledgement(acknowledgement)

    def claim_acknowledgement(
        self, case_id: str, *, recipient: str, payload_digest: str, lease_seconds: int = 300
    ) -> str:
        return self._store_for(case_id).claim_acknowledgement(
            case_id,
            recipient=recipient,
            payload_digest=payload_digest,
            lease_seconds=lease_seconds,
        )

    def mark_acknowledgement_sent(self, case_id: str) -> None:
        self._store_for(case_id).mark_acknowledgement_sent(case_id)

    def mark_acknowledgement_failed(self, case_id: str, error: str) -> None:
        self._store_for(case_id).mark_acknowledgement_failed(case_id, error)

    def save_snapshot(self, snapshot: OperationalSnapshot) -> bool:
        return self.local.save_snapshot(snapshot)

    def latest_snapshot(self, source: str, external_id: str) -> OperationalSnapshot | None:
        return self.remote.latest_snapshot(source, external_id) or self.local.latest_snapshot(
            source, external_id
        )

    def record_event(self, event: WorkflowEvent) -> bool:
        return self._store_for(event.entity_id).record_event(event)

    def upsert_exception(self, exception: WorkflowException) -> bool:
        return self._store_for(exception.entity_id).upsert_exception(exception)

    def resolve_exceptions(self, *, entity_id: str, exception_type: str, resolved_at: str) -> int:
        return self._store_for(entity_id).resolve_exceptions(
            entity_id=entity_id,
            exception_type=exception_type,
            resolved_at=resolved_at,
        )

    def list_exceptions(
        self, *, status: str | None = None, limit: int = 200
    ) -> list[WorkflowException]:
        return _unique(
            [
                *self.remote.list_exceptions(status=status, limit=limit),
                *self.local.list_exceptions(status=status, limit=limit),
            ],
            key=lambda exception: exception.exception_key,
            limit=limit,
        )

    def enqueue_notification(self, notification: NotificationRecord) -> bool:
        return self.local.enqueue_notification(notification)

    def pending_notifications(self, *, limit: int = 100) -> list[NotificationRecord]:
        return self.local.pending_notifications(limit=limit)

    def mark_notifications_sent(self, keys: list[str]) -> None:
        self.local.mark_notifications_sent(keys)

    def mark_notifications_failed(self, keys: list[str], error: str) -> None:
        self.local.mark_notifications_failed(keys, error)

    def upsert_patient_link(self, link: PatientLink) -> None:
        store = self.remote if self.remote.find_entity_id(
            monday_item_id=link.monday_item_id,
            drk_patient_id=link.drk_patient_id,
        ) else self.local
        store.upsert_patient_link(link)

    def list_patient_links(self) -> list[PatientLink]:
        return _unique(
            [*self.remote.list_patient_links(), *self.local.list_patient_links()],
            key=lambda link: link.entity_id,
            limit=500,
        )

    def find_entity_id(
        self, *, monday_item_id: str | None = None, drk_patient_id: str | None = None
    ) -> str | None:
        return self.remote.find_entity_id(
            monday_item_id=monday_item_id, drk_patient_id=drk_patient_id
        ) or self.local.find_entity_id(monday_item_id=monday_item_id, drk_patient_id=drk_patient_id)

    def get_counter(self, entity_id: str, counter_name: str) -> int:
        return self._store_for(entity_id).get_counter(entity_id, counter_name)

    def set_counter(self, counter: WorkflowCounter) -> None:
        self._store_for(counter.entity_id).set_counter(counter)

    def record_cursor(self, source: str, cursor: str | None) -> None:
        self.local.record_cursor(source, cursor)

    def read_cursor(self, source: str) -> str | None:
        return self.local.read_cursor(source)

    def component_health(self, component: str) -> ComponentHealth | None:
        return self.local.component_health(component)

    def list_component_health(self) -> list[ComponentHealth]:
        return self.local.list_component_health()

    def upsert_component_health(self, health: ComponentHealth) -> None:
        self.local.upsert_component_health(health)

    def status_summary(self) -> dict[str, object]:
        local = self.local.status_summary()
        remote = self.remote.status_summary()
        return {"backend": "sqlite+supabase", "local": local, "remote": remote}

    def _store_for(self, case_id: str) -> WorkflowStore:
        if self.remote.workflow_case(case_id) is not None:
            return self.remote
        return self.local

    @staticmethod
    def _merge_cases(
        remote: list[WorkflowCase],
        local: list[WorkflowCase],
        *,
        limit: int,
    ) -> list[WorkflowCase]:
        return _unique([*remote, *local], key=lambda case: case.case_id, limit=limit)


def persistence_for(store: Any, case_id: str | None) -> str:
    if not case_id:
        return "none"
    if hasattr(store, "persistence_for"):
        return str(store.persistence_for(case_id))
    name = type(store).__name__.casefold()
    if "supabase" in name:
        return "supabase"
    return "sqlite"


def _unique(items: list[Any], *, key, limit: int) -> list[Any]:
    seen: set[str] = set()
    unique: list[Any] = []
    for item in items:
        identifier = key(item)
        if identifier in seen:
            continue
        seen.add(identifier)
        unique.append(item)
        if len(unique) >= limit:
            break
    return unique
