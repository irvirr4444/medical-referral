"""Backend-only Supabase Data API implementation of the workflow store."""

from __future__ import annotations

import os
from typing import Any

import requests

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
    utc_now,
)


class SupabaseWorkflowError(RuntimeError):
    pass


class SupabaseWorkflowStore:
    def __init__(self, *, url: str, service_role_key: str, timeout_seconds: float = 30.0) -> None:
        self.url = url.rstrip("/")
        self.service_role_key = service_role_key
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_environment(cls) -> "SupabaseWorkflowStore":
        url = os.getenv("SUPABASE_URL", "").strip()
        key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            or os.getenv("SUPABASE_SERVICE_KEY", "").strip()
        )
        if not url or not key:
            raise SupabaseWorkflowError(
                "Supabase monitoring requires SUPABASE_URL and "
                "SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_SERVICE_KEY)"
            )
        return cls(url=url, service_role_key=key)

    def upsert_workflow_case(self, case: WorkflowCase) -> WorkflowCase:
        self._upsert(
            "wcw_workflow_cases",
            case.model_dump(mode="json"),
            on_conflict="case_id",
        )
        stored = self.workflow_case(case.case_id)
        if stored is None:
            raise SupabaseWorkflowError("workflow case upsert did not return a row")
        return stored

    def workflow_case(self, case_id: str) -> WorkflowCase | None:
        return self._workflow_case_by("case_id", case_id)

    def workflow_case_by_source_ref(self, source_ref: str) -> WorkflowCase | None:
        return self._workflow_case_by("source_ref", source_ref)

    def workflow_case_by_monday_item_id(self, monday_item_id: str) -> WorkflowCase | None:
        return self._workflow_case_by("monday_item_id", monday_item_id)

    def workflow_case_by_drk_patient_id(self, drk_patient_id: str) -> WorkflowCase | None:
        return self._workflow_case_by("drk_patient_id", drk_patient_id)

    def list_workflow_cases(self, *, limit: int = 100) -> list[WorkflowCase]:
        rows = self._request(
            "GET",
            "wcw_workflow_cases",
            params={"select": "*", "order": "updated_at.desc", "limit": str(max(1, min(limit, 500)))},
        )
        return [WorkflowCase.model_validate(row) for row in rows]

    def upsert_work_item(self, item: WorkflowWorkItem) -> WorkflowWorkItem:
        self._upsert(
            "wcw_work_items",
            item.model_dump(mode="json"),
            on_conflict="work_item_id",
        )
        stored = self.work_item(item.work_item_id)
        if stored is None:
            raise SupabaseWorkflowError("workflow work item upsert did not return a row")
        return stored

    def work_item(self, work_item_id: str) -> WorkflowWorkItem | None:
        rows = self._request(
            "GET",
            "wcw_work_items",
            params={"select": "*", "work_item_id": f"eq.{work_item_id}", "limit": "1"},
        )
        return None if not rows else WorkflowWorkItem.model_validate(rows[0])

    def list_work_items(
        self,
        *,
        stage: int | None = None,
        case_id: str | None = None,
        limit: int = 100,
    ) -> list[WorkflowWorkItem]:
        params = {
            "select": "*",
            "order": "updated_at.desc",
            "limit": str(max(1, min(limit, 500))),
        }
        if stage is not None:
            params["stage"] = f"eq.{stage}"
        if case_id is not None:
            params["case_id"] = f"eq.{case_id}"
        rows = self._request("GET", "wcw_work_items", params=params)
        return [WorkflowWorkItem.model_validate(row) for row in rows]

    def record_decision(self, decision: WorkflowDecision) -> bool:
        rows = self._request(
            "POST",
            "wcw_workflow_decisions",
            json_body=decision.model_dump(mode="json"),
            params={"on_conflict": "idempotency_key"},
            prefer="resolution=ignore-duplicates,return=representation",
        )
        return bool(rows)

    def list_decisions(self, case_id: str) -> list[WorkflowDecision]:
        rows = self._request(
            "GET",
            "wcw_workflow_decisions",
            params={
                "select": "*",
                "case_id": f"eq.{case_id}",
                "order": "created_at.asc",
            },
        )
        return [WorkflowDecision.model_validate(row) for row in rows]

    def upsert_external_operation(self, operation: ExternalOperation) -> ExternalOperation:
        self._upsert(
            "wcw_external_operations",
            operation.model_dump(mode="json"),
            on_conflict="operation_id",
        )
        operations = [
            item for item in self.list_external_operations(operation.case_id)
            if item.operation_id == operation.operation_id
        ]
        if not operations:
            raise SupabaseWorkflowError("external operation upsert did not return a row")
        return operations[0]

    def claim_external_operation(
        self,
        operation_id: str,
        *,
        case_id: str,
        claimed_by: str,
        lease_seconds: int = 300,
        allow_uncertain: bool = False,
    ) -> str:
        del case_id
        rows = self._request(
            "POST",
            "rpc/claim_wcw_external_operation",
            json_body={
                "p_operation_id": operation_id,
                "p_claimed_by": claimed_by,
                "p_lease_seconds": max(30, lease_seconds),
                "p_allow_uncertain": bool(allow_uncertain),
            },
        )
        if not isinstance(rows, str):
            raise SupabaseWorkflowError("external operation claim returned an unexpected response")
        return rows

    def list_external_operations(self, case_id: str) -> list[ExternalOperation]:
        rows = self._request(
            "GET",
            "wcw_external_operations",
            params={
                "select": "*",
                "case_id": f"eq.{case_id}",
                "order": "created_at.asc",
            },
        )
        return [ExternalOperation.model_validate(row) for row in rows]

    def list_events(self, entity_id: str, *, limit: int = 100) -> list[WorkflowEvent]:
        rows = self._request(
            "GET",
            "wcw_workflow_events",
            params={
                "select": "*",
                "entity_id": f"eq.{entity_id}",
                "order": "occurred_at.asc,event_key.asc",
                "limit": str(max(1, min(limit, 500))),
            },
        )
        return [WorkflowEvent.model_validate(row) for row in rows]

    def enqueue_acknowledgement(self, acknowledgement: OutboundAcknowledgement) -> bool:
        rows = self._request(
            "POST",
            "wcw_outbound_acknowledgements",
            json_body=acknowledgement.model_dump(mode="json"),
            params={"on_conflict": "case_id"},
            prefer="resolution=ignore-duplicates,return=representation",
        )
        return bool(rows)

    def claim_acknowledgement(
        self,
        case_id: str,
        *,
        recipient: str,
        payload_digest: str,
        lease_seconds: int = 300,
    ) -> str:
        rows = self._request(
            "POST",
            "rpc/claim_wcw_acknowledgement",
            json_body={
                "p_case_id": case_id,
                "p_recipient": recipient.casefold(),
                "p_payload_digest": payload_digest,
                "p_lease_seconds": max(30, lease_seconds),
            },
        )
        if not isinstance(rows, str):
            raise SupabaseWorkflowError("acknowledgement claim returned an unexpected response")
        return rows

    def mark_acknowledgement_sent(self, case_id: str) -> None:
        now = utc_now().isoformat()
        self._request(
            "PATCH",
            "wcw_outbound_acknowledgements",
            params={"case_id": f"eq.{case_id}", "status": "eq.sending"},
            json_body={
                "status": "sent",
                "sent_at": now,
                "lease_until": None,
                "last_error": None,
                "updated_at": now,
            },
            prefer="return=minimal",
        )

    def mark_acknowledgement_failed(self, case_id: str, error: str) -> None:
        self._request(
            "PATCH",
            "wcw_outbound_acknowledgements",
            params={"case_id": f"eq.{case_id}", "status": "eq.sending"},
            json_body={
                "status": "failed",
                "lease_until": None,
                "last_error": error[:500],
                "updated_at": utc_now().isoformat(),
            },
            prefer="return=minimal",
        )

    def save_snapshot(self, snapshot: OperationalSnapshot) -> bool:
        previous = self.latest_snapshot(snapshot.source, snapshot.external_id)
        if previous is not None and previous.payload_digest == snapshot.payload_digest:
            return False
        self._request(
            "POST",
            "wcw_system_snapshots",
            json_body={
                "source": snapshot.source,
                "external_id": snapshot.external_id,
                "observed_at": snapshot.observed_at.isoformat(),
                "payload_digest": snapshot.payload_digest,
                "payload": snapshot.model_dump(mode="json"),
            },
            params={"on_conflict": "source,external_id,payload_digest"},
            prefer="resolution=ignore-duplicates,return=minimal",
        )
        return True

    def latest_snapshot(self, source: str, external_id: str) -> OperationalSnapshot | None:
        rows = self._request(
            "GET",
            "wcw_system_snapshots",
            params={
                "select": "payload",
                "source": f"eq.{source}",
                "external_id": f"eq.{external_id}",
                "order": "observed_at.desc",
                "limit": "1",
            },
        )
        return None if not rows else OperationalSnapshot.model_validate(rows[0]["payload"])

    def record_event(self, event: WorkflowEvent) -> bool:
        rows = self._request(
            "POST",
            "wcw_workflow_events",
            json_body={
                "event_key": event.event_key,
                "event_type": event.event_type,
                "entity_id": event.entity_id,
                "source": event.source,
                "occurred_at": event.occurred_at.isoformat(),
                "details": event.details,
            },
            params={"on_conflict": "event_key"},
            prefer="resolution=ignore-duplicates,return=representation",
        )
        return bool(rows)

    def upsert_exception(self, exception: WorkflowException) -> bool:
        existing = self._request(
            "GET",
            "wcw_workflow_exceptions",
            params={
                "select": "status,first_seen_at",
                "exception_key": f"eq.{exception.exception_key}",
                "limit": "1",
            },
        )
        created_or_reopened = not existing or existing[0].get("status") == "resolved"
        first_seen = existing[0].get("first_seen_at") if existing else exception.first_seen_at.isoformat()
        self._upsert(
            "wcw_workflow_exceptions",
            {
                "exception_key": exception.exception_key,
                "exception_type": exception.exception_type,
                "entity_id": exception.entity_id,
                "severity": exception.severity,
                "status": exception.status,
                "first_seen_at": first_seen,
                "last_seen_at": exception.last_seen_at.isoformat(),
                "resolved_at": None if exception.resolved_at is None else exception.resolved_at.isoformat(),
                "details": exception.details,
            },
            on_conflict="exception_key",
        )
        return created_or_reopened

    def resolve_exceptions(self, *, entity_id: str, exception_type: str, resolved_at: str) -> int:
        rows = self._request(
            "PATCH",
            "wcw_workflow_exceptions",
            params={
                "entity_id": f"eq.{entity_id}",
                "exception_type": f"eq.{exception_type}",
                "status": "eq.open",
            },
            json_body={"status": "resolved", "resolved_at": resolved_at, "last_seen_at": resolved_at},
            prefer="return=representation",
        )
        return len(rows or [])

    def list_exceptions(
        self, *, status: str | None = None, limit: int = 200
    ) -> list[WorkflowException]:
        params = {
            "select": (
                "exception_key,exception_type,entity_id,severity,status,"
                "first_seen_at,last_seen_at,resolved_at"
            ),
            "order": "last_seen_at.desc",
            "limit": str(max(1, min(limit, 500))),
        }
        if status is not None:
            params["status"] = f"eq.{status}"
        rows = self._request("GET", "wcw_workflow_exceptions", params=params)
        return [
            WorkflowException.model_validate({**row, "details": {}})
            for row in rows
        ]

    def enqueue_notification(self, notification: NotificationRecord) -> bool:
        rows = self._request(
            "POST",
            "wcw_notification_outbox",
            json_body={
                "notification_key": notification.notification_key,
                "exception_key": notification.exception_key,
                "recipient": notification.recipient,
                "subject": notification.subject,
                "body": notification.body,
                "status": notification.status,
                "attempts": notification.attempts,
                "last_error": notification.last_error,
                "created_at": notification.created_at.isoformat(),
            },
            params={"on_conflict": "notification_key"},
            prefer="resolution=ignore-duplicates,return=representation",
        )
        return bool(rows)

    def pending_notifications(self, *, limit: int = 100) -> list[NotificationRecord]:
        rows = self._request(
            "GET",
            "wcw_notification_outbox",
            params={
                "select": "notification_key,exception_key,recipient,subject,body,created_at,status,attempts,last_error",
                "status": "in.(pending,failed)",
                "order": "created_at.asc",
                "limit": str(limit),
            },
        )
        return [NotificationRecord.model_validate(row) for row in rows]

    def mark_notifications_sent(self, keys: list[str]) -> None:
        self._mark_notifications(keys, status="sent", error=None)

    def mark_notifications_failed(self, keys: list[str], error: str) -> None:
        self._mark_notifications(keys, status="failed", error=error)

    def upsert_patient_link(self, link: PatientLink) -> None:
        existing = self._request(
            "GET",
            "wcw_patient_links",
            params={"select": "*", "entity_id": f"eq.{link.entity_id}", "limit": "1"},
        )
        current = existing[0] if existing else {}
        self._upsert(
            "wcw_patient_links",
            {
                "entity_id": link.entity_id,
                "monday_item_id": link.monday_item_id or current.get("monday_item_id"),
                "drk_patient_id": link.drk_patient_id or current.get("drk_patient_id"),
                "patient_label": link.patient_label or current.get("patient_label"),
                "identity_digest": link.identity_digest or current.get("identity_digest"),
                "updated_at": link.updated_at.isoformat(),
            },
            on_conflict="entity_id",
        )

    def list_patient_links(self) -> list[PatientLink]:
        rows = self._all_rows(
            "wcw_patient_links",
            params={"select": "*", "order": "updated_at.asc,entity_id.asc"},
        )
        return [PatientLink.model_validate(row) for row in rows]

    def find_entity_id(
        self, *, monday_item_id: str | None = None, drk_patient_id: str | None = None
    ) -> str | None:
        if not monday_item_id and not drk_patient_id:
            return None
        column, value = (
            ("monday_item_id", monday_item_id)
            if monday_item_id
            else ("drk_patient_id", drk_patient_id)
        )
        rows = self._request(
            "GET",
            "wcw_patient_links",
            params={"select": "entity_id", column: f"eq.{value}", "limit": "1"},
        )
        return None if not rows else str(rows[0]["entity_id"])

    def get_counter(self, entity_id: str, counter_name: str) -> int:
        rows = self._request(
            "GET",
            "wcw_workflow_counters",
            params={
                "select": "value",
                "entity_id": f"eq.{entity_id}",
                "counter_name": f"eq.{counter_name}",
                "limit": "1",
            },
        )
        return 0 if not rows else int(rows[0]["value"])

    def set_counter(self, counter: WorkflowCounter) -> None:
        self._upsert(
            "wcw_workflow_counters",
            {
                "entity_id": counter.entity_id,
                "counter_name": counter.counter_name,
                "value": counter.value,
                "updated_at": counter.updated_at.isoformat(),
            },
            on_conflict="entity_id,counter_name",
        )

    def record_cursor(self, source: str, cursor: str | None) -> None:
        self._upsert(
            "wcw_sync_cursors",
            {"source": source, "cursor": cursor, "updated_at": utc_now().isoformat()},
            on_conflict="source",
        )

    def read_cursor(self, source: str) -> str | None:
        rows = self._request(
            "GET",
            "wcw_sync_cursors",
            params={"select": "cursor", "source": f"eq.{source}", "limit": "1"},
        )
        return None if not rows or rows[0].get("cursor") is None else str(rows[0]["cursor"])

    def component_health(self, component: str) -> ComponentHealth | None:
        rows = self._request(
            "GET",
            "wcw_component_health",
            params={"select": "*", "component": f"eq.{component}", "limit": "1"},
        )
        return None if not rows else ComponentHealth.model_validate(rows[0])

    def list_component_health(self) -> list[ComponentHealth]:
        rows = self._request(
            "GET",
            "wcw_component_health",
            params={"select": "*", "order": "component.asc"},
        )
        return [ComponentHealth.model_validate(row) for row in rows]

    def upsert_component_health(self, health: ComponentHealth) -> None:
        self._upsert(
            "wcw_component_health",
            health.model_dump(mode="json"),
            on_conflict="component",
        )

    def status_summary(self) -> dict[str, object]:
        return {
            "backend": "supabase",
            "workflow_cases": self._count("wcw_workflow_cases"),
            "pending_acknowledgements": self._count(
                "wcw_outbound_acknowledgements", status="in.(pending,sending,failed)"
            ),
            "snapshots": self._count("wcw_system_snapshots"),
            "events": self._count("wcw_workflow_events"),
            "open_exceptions": self._count("wcw_workflow_exceptions", status="eq.open"),
            "pending_notifications": self._count(
                "wcw_notification_outbox", status="in.(pending,failed)"
            ),
            "patient_links": self._count("wcw_patient_links"),
            "unhealthy_components": self._count(
                "wcw_component_health", status="neq.healthy"
            ),
        }

    def _upsert(self, table: str, row: dict[str, Any], *, on_conflict: str) -> None:
        self._request(
            "POST",
            table,
            json_body=row,
            params={"on_conflict": on_conflict},
            prefer="resolution=merge-duplicates,return=minimal",
        )

    def _workflow_case_by(self, column: str, value: str) -> WorkflowCase | None:
        if column not in {"case_id", "source_ref", "monday_item_id", "drk_patient_id"}:
            raise ValueError("unsupported workflow case lookup")
        rows = self._request(
            "GET",
            "wcw_workflow_cases",
            params={"select": "*", column: f"eq.{value}", "limit": "1"},
        )
        return None if not rows else WorkflowCase.model_validate(rows[0])

    def _mark_notifications(self, keys: list[str], *, status: str, error: str | None) -> None:
        for key in keys:
            existing = self._request(
                "GET",
                "wcw_notification_outbox",
                params={"select": "attempts", "notification_key": f"eq.{key}", "limit": "1"},
            )
            attempts = int(existing[0].get("attempts") or 0) + 1 if existing else 1
            self._request(
                "PATCH",
                "wcw_notification_outbox",
                params={"notification_key": f"eq.{key}"},
                json_body={"status": status, "attempts": attempts, "last_error": error},
                prefer="return=minimal",
            )

    def _count(self, table: str, **filters: str) -> int:
        response = self._request_raw(
            "GET",
            table,
            params={"select": "notification_key" if table == "wcw_notification_outbox" else "*", **filters},
            prefer="count=exact",
            extra_headers={"Range": "0-0"},
        )
        content_range = response.headers.get("Content-Range", "")
        try:
            return int(content_range.rsplit("/", 1)[1])
        except (IndexError, ValueError):
            return len(response.json() or [])

    def _all_rows(
        self,
        table: str,
        *,
        params: dict[str, str],
        page_size: int = 1000,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            response = self._request_raw(
                "GET",
                table,
                params=params,
                extra_headers={"Range": f"{offset}-{offset + page_size - 1}"},
            )
            page = response.json() or []
            rows.extend(page)
            if len(page) < page_size:
                return rows
            offset += page_size

    def _request(
        self,
        method: str,
        table: str,
        *,
        params: dict[str, str] | None = None,
        json_body: object | None = None,
        prefer: str | None = None,
    ) -> Any:
        response = self._request_raw(
            method,
            table,
            params=params,
            json_body=json_body,
            prefer=prefer,
        )
        if not response.content:
            return []
        return response.json()

    def _request_raw(
        self,
        method: str,
        table: str,
        *,
        params: dict[str, str] | None = None,
        json_body: object | None = None,
        prefer: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> requests.Response:
        headers = {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
            **(extra_headers or {}),
        }
        if prefer:
            headers["Prefer"] = prefer
        response = requests.request(
            method,
            f"{self.url}/rest/v1/{table}",
            headers=headers,
            params=params,
            json=json_body,
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            detail = response.text[:1000]
            raise SupabaseWorkflowError(
                f"Supabase workflow request failed: {method} {table} HTTP {response.status_code}: {detail}"
            )
        return response
