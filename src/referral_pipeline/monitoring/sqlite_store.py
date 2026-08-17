"""SQLite implementation used for local runs and deterministic tests."""

from __future__ import annotations

import json
import sqlite3
from datetime import timedelta
from pathlib import Path

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


class SQLiteWorkflowStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    def upsert_workflow_case(self, case: WorkflowCase) -> WorkflowCase:
        payload = case.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO wcw_workflow_cases
                    (case_id, source_ref, source, attachment_sha256, referral_id,
                     patient_label, current_stage, status, source_received_at,
                     monday_item_id, drk_patient_id, created_at, updated_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(case_id) DO UPDATE SET
                    attachment_sha256 = COALESCE(excluded.attachment_sha256, attachment_sha256),
                    referral_id = COALESCE(excluded.referral_id, referral_id),
                    patient_label = COALESCE(excluded.patient_label, patient_label),
                    current_stage = excluded.current_stage,
                    status = excluded.status,
                    source_received_at = COALESCE(excluded.source_received_at, source_received_at),
                    monday_item_id = COALESCE(excluded.monday_item_id, monday_item_id),
                    drk_patient_id = COALESCE(excluded.drk_patient_id, drk_patient_id),
                    updated_at = excluded.updated_at,
                    completed_at = excluded.completed_at
                """,
                (
                    payload["case_id"], payload["source_ref"], payload["source"],
                    payload["attachment_sha256"], payload["referral_id"], payload["patient_label"],
                    payload["current_stage"], payload["status"], payload["source_received_at"],
                    payload["monday_item_id"], payload["drk_patient_id"], payload["created_at"],
                    payload["updated_at"], payload["completed_at"],
                ),
            )
        stored = self.workflow_case(case.case_id)
        if stored is None:
            raise RuntimeError("workflow case upsert did not return a row")
        return stored

    def workflow_case(self, case_id: str) -> WorkflowCase | None:
        return self._workflow_case_where("case_id", case_id)

    def workflow_case_by_source_ref(self, source_ref: str) -> WorkflowCase | None:
        return self._workflow_case_where("source_ref", source_ref)

    def list_workflow_cases(self, *, limit: int = 100) -> list[WorkflowCase]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM wcw_workflow_cases ORDER BY updated_at DESC LIMIT ?",
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [WorkflowCase.model_validate(dict(row)) for row in rows]

    def upsert_work_item(self, item: WorkflowWorkItem) -> WorkflowWorkItem:
        payload = item.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO wcw_work_items
                    (work_item_id, case_id, stage, step_id, owner_role, status,
                     recommended_assignee, recommendation_reason, assigned_to,
                     payload_json, created_at, updated_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(work_item_id) DO UPDATE SET
                    status = excluded.status,
                    recommended_assignee = excluded.recommended_assignee,
                    recommendation_reason = excluded.recommendation_reason,
                    assigned_to = excluded.assigned_to,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at,
                    completed_at = excluded.completed_at
                """,
                (
                    payload["work_item_id"], payload["case_id"], payload["stage"],
                    payload["step_id"], payload["owner_role"], payload["status"],
                    payload["recommended_assignee"], payload["recommendation_reason"],
                    payload["assigned_to"], _json(payload["payload"]),
                    payload["created_at"], payload["updated_at"], payload["completed_at"],
                ),
            )
        stored = self.work_item(item.work_item_id)
        if stored is None:
            raise RuntimeError("workflow work item upsert did not return a row")
        return stored

    def work_item(self, work_item_id: str) -> WorkflowWorkItem | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM wcw_work_items WHERE work_item_id = ?",
                (work_item_id,),
            ).fetchone()
        return None if row is None else _work_item_from_row(row)

    def list_work_items(
        self,
        *,
        stage: int | None = None,
        case_id: str | None = None,
        limit: int = 100,
    ) -> list[WorkflowWorkItem]:
        clauses: list[str] = []
        values: list[object] = []
        if stage is not None:
            clauses.append("stage = ?")
            values.append(stage)
        if case_id is not None:
            clauses.append("case_id = ?")
            values.append(case_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        values.append(max(1, min(limit, 500)))
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM wcw_work_items{where} ORDER BY updated_at DESC LIMIT ?",
                values,
            ).fetchall()
        return [_work_item_from_row(row) for row in rows]

    def record_decision(self, decision: WorkflowDecision) -> bool:
        payload = decision.model_dump(mode="json")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO wcw_workflow_decisions
                    (decision_id, idempotency_key, case_id, stage, step_id,
                     decision_type, selected_value_json, decided_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["decision_id"], payload["idempotency_key"], payload["case_id"],
                    payload["stage"], payload["step_id"], payload["decision_type"],
                    _json(payload["selected_value"]), payload["decided_by"], payload["created_at"],
                ),
            )
        return cursor.rowcount == 1

    def list_decisions(self, case_id: str) -> list[WorkflowDecision]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM wcw_workflow_decisions WHERE case_id = ? ORDER BY created_at",
                (case_id,),
            ).fetchall()
        return [_decision_from_row(row) for row in rows]

    def upsert_external_operation(self, operation: ExternalOperation) -> ExternalOperation:
        payload = operation.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO wcw_external_operations
                    (operation_id, idempotency_key, case_id, stage, operation_type,
                     status, request_payload_json, result_json, attempts, last_error,
                     lease_until, claimed_by, created_at, updated_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(operation_id) DO UPDATE SET
                    status = excluded.status,
                    request_payload_json = excluded.request_payload_json,
                    result_json = excluded.result_json,
                    attempts = excluded.attempts,
                    last_error = excluded.last_error,
                    lease_until = excluded.lease_until,
                    claimed_by = excluded.claimed_by,
                    updated_at = excluded.updated_at,
                    completed_at = excluded.completed_at
                """,
                (
                    payload["operation_id"], payload["idempotency_key"], payload["case_id"],
                    payload["stage"], payload["operation_type"], payload["status"],
                    _json(payload["request_payload"]), _json(payload["result"]),
                    payload["attempts"], payload["last_error"], payload.get("lease_until"),
                    payload.get("claimed_by"), payload["created_at"],
                    payload["updated_at"], payload["completed_at"],
                ),
            )
        operations = [
            item for item in self.list_external_operations(operation.case_id)
            if item.operation_id == operation.operation_id
        ]
        if not operations:
            raise RuntimeError("external operation upsert did not return a row")
        return operations[0]

    def list_external_operations(self, case_id: str) -> list[ExternalOperation]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM wcw_external_operations WHERE case_id = ? ORDER BY created_at",
                (case_id,),
            ).fetchall()
        return [_external_operation_from_row(row) for row in rows]

    def claim_external_operation(
        self,
        operation_id: str,
        *,
        case_id: str,
        claimed_by: str,
        lease_seconds: int = 300,
        allow_uncertain: bool = False,
    ) -> str:
        now = utc_now()
        now_iso = now.isoformat()
        lease_until = now + timedelta(seconds=max(30, lease_seconds))
        with self._connect() as connection:
            expired = connection.execute(
                """
                UPDATE wcw_external_operations
                SET status = 'uncertain', lease_until = NULL,
                    last_error = 'running lease expired; external outcome is unknown',
                    updated_at = ?
                WHERE operation_id = ? AND case_id = ?
                  AND status = 'running'
                  AND (lease_until IS NULL OR lease_until <= ?)
                """,
                (now_iso, operation_id, case_id, now_iso),
            )
            if expired.rowcount:
                return "uncertain"
            claimed = connection.execute(
                """
                UPDATE wcw_external_operations
                SET status = 'running', attempts = attempts + 1, claimed_by = ?,
                    lease_until = ?, last_error = NULL, updated_at = ?
                WHERE operation_id = ? AND case_id = ?
                  AND (
                    status IN ('ready', 'failed', 'blocked')
                    OR (status = 'uncertain' AND ? = 1)
                  )
                """,
                (
                    claimed_by or None,
                    lease_until.isoformat(),
                    now_iso,
                    operation_id,
                    case_id,
                    int(bool(allow_uncertain)),
                ),
            )
            if claimed.rowcount:
                return "claimed"
            row = connection.execute(
                """
                SELECT status, lease_until FROM wcw_external_operations
                WHERE operation_id = ? AND case_id = ?
                """,
                (operation_id, case_id),
            ).fetchone()
            if row is None:
                return "not_found"
            status = str(row["status"])
            if status == "succeeded":
                return "already_succeeded"
            if status == "running":
                return "busy"
            if status == "uncertain":
                return "uncertain"
            return "not_retryable"

    def list_events(self, entity_id: str, *, limit: int = 100) -> list[WorkflowEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT event_key, event_type, entity_id, source, occurred_at, details_json
                FROM wcw_workflow_events
                WHERE entity_id = ?
                ORDER BY occurred_at ASC, event_key ASC LIMIT ?
                """,
                (entity_id, max(1, min(limit, 500))),
            ).fetchall()
        return [
            WorkflowEvent(
                event_key=row["event_key"],
                event_type=row["event_type"],
                entity_id=row["entity_id"],
                source=row["source"],
                occurred_at=row["occurred_at"],
                details=json.loads(row["details_json"]),
            )
            for row in rows
        ]

    def enqueue_acknowledgement(self, acknowledgement: OutboundAcknowledgement) -> bool:
        payload = acknowledgement.model_dump(mode="json")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO wcw_outbound_acknowledgements
                    (case_id, recipient, payload_digest, status, attempts, lease_until,
                     sent_at, last_error, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuple(payload[name] for name in (
                    "case_id", "recipient", "payload_digest", "status", "attempts",
                    "lease_until", "sent_at", "last_error", "created_at", "updated_at",
                )),
            )
        return cursor.rowcount == 1

    def claim_acknowledgement(
        self,
        case_id: str,
        *,
        recipient: str,
        payload_digest: str,
        lease_seconds: int = 300,
    ) -> str:
        now = utc_now()
        lease_until = now + timedelta(seconds=max(30, lease_seconds))
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT status, lease_until FROM wcw_outbound_acknowledgements WHERE case_id = ?",
                (case_id,),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO wcw_outbound_acknowledgements
                        (case_id, recipient, payload_digest, status, attempts, lease_until,
                         sent_at, last_error, created_at, updated_at)
                    VALUES (?, ?, ?, 'sending', 1, ?, NULL, NULL, ?, ?)
                    """,
                    (case_id, recipient.casefold(), payload_digest, lease_until.isoformat(), now.isoformat(), now.isoformat()),
                )
                return "claimed"
            if row["status"] == "sent":
                return "already_sent"
            if row["status"] == "sending" and row["lease_until"] and row["lease_until"] > now.isoformat():
                return "busy"
            connection.execute(
                """
                UPDATE wcw_outbound_acknowledgements
                SET recipient = ?, payload_digest = ?, status = 'sending', attempts = attempts + 1,
                    lease_until = ?, last_error = NULL, updated_at = ?
                WHERE case_id = ?
                """,
                (recipient.casefold(), payload_digest, lease_until.isoformat(), now.isoformat(), case_id),
            )
            return "claimed"

    def mark_acknowledgement_sent(self, case_id: str) -> None:
        now = utc_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE wcw_outbound_acknowledgements
                SET status = 'sent', sent_at = ?, lease_until = NULL, last_error = NULL, updated_at = ?
                WHERE case_id = ? AND status = 'sending'
                """,
                (now, now, case_id),
            )

    def mark_acknowledgement_failed(self, case_id: str, error: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE wcw_outbound_acknowledgements
                SET status = 'failed', lease_until = NULL, last_error = ?, updated_at = ?
                WHERE case_id = ? AND status = 'sending'
                """,
                (error[:500], utc_now().isoformat(), case_id),
            )

    def save_snapshot(self, snapshot: OperationalSnapshot) -> bool:
        previous = self.latest_snapshot(snapshot.source, snapshot.external_id)
        if previous is not None and previous.payload_digest == snapshot.payload_digest:
            return False
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO wcw_system_snapshots
                    (source, external_id, observed_at, payload_digest, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    snapshot.source,
                    snapshot.external_id,
                    snapshot.observed_at.isoformat(),
                    snapshot.payload_digest,
                    _json(snapshot.model_dump(mode="json")),
                ),
            )
        return True

    def latest_snapshot(self, source: str, external_id: str) -> OperationalSnapshot | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json FROM wcw_system_snapshots
                WHERE source = ? AND external_id = ?
                ORDER BY observed_at DESC, id DESC LIMIT 1
                """,
                (source, external_id),
            ).fetchone()
        return None if row is None else OperationalSnapshot.model_validate_json(row[0])

    def record_event(self, event: WorkflowEvent) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO wcw_workflow_events
                    (event_key, event_type, entity_id, source, occurred_at, details_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_key,
                    event.event_type,
                    event.entity_id,
                    event.source,
                    event.occurred_at.isoformat(),
                    _json(event.details),
                ),
            )
        return cursor.rowcount == 1

    def upsert_exception(self, exception: WorkflowException) -> bool:
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT status FROM wcw_workflow_exceptions WHERE exception_key = ?",
                (exception.exception_key,),
            ).fetchone()
            connection.execute(
                """
                INSERT INTO wcw_workflow_exceptions
                    (exception_key, exception_type, entity_id, severity, status,
                     first_seen_at, last_seen_at, resolved_at, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(exception_key) DO UPDATE SET
                    severity = excluded.severity,
                    status = excluded.status,
                    last_seen_at = excluded.last_seen_at,
                    resolved_at = excluded.resolved_at,
                    details_json = excluded.details_json
                """,
                (
                    exception.exception_key,
                    exception.exception_type,
                    exception.entity_id,
                    exception.severity,
                    exception.status,
                    exception.first_seen_at.isoformat(),
                    exception.last_seen_at.isoformat(),
                    None if exception.resolved_at is None else exception.resolved_at.isoformat(),
                    _json(exception.details),
                ),
            )
        return existing is None or existing[0] == "resolved"

    def resolve_exceptions(self, *, entity_id: str, exception_type: str, resolved_at: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE wcw_workflow_exceptions
                SET status = 'resolved', resolved_at = ?, last_seen_at = ?
                WHERE entity_id = ? AND exception_type = ? AND status = 'open'
                """,
                (resolved_at, resolved_at, entity_id, exception_type),
            )
        return cursor.rowcount

    def enqueue_notification(self, notification: NotificationRecord) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO wcw_notification_outbox
                    (notification_key, exception_key, recipient, subject, body,
                     status, attempts, last_error, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    notification.notification_key,
                    notification.exception_key,
                    notification.recipient,
                    notification.subject,
                    notification.body,
                    notification.status,
                    notification.attempts,
                    notification.last_error,
                    notification.created_at.isoformat(),
                ),
            )
        return cursor.rowcount == 1

    def pending_notifications(self, *, limit: int = 100) -> list[NotificationRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT notification_key, exception_key, recipient, subject, body,
                       created_at, status, attempts, last_error
                FROM wcw_notification_outbox
                WHERE status IN ('pending', 'failed')
                ORDER BY created_at LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [NotificationRecord.model_validate(dict(row)) for row in rows]

    def mark_notifications_sent(self, keys: list[str]) -> None:
        self._mark_notifications(keys, status="sent", error=None)

    def mark_notifications_failed(self, keys: list[str], error: str) -> None:
        self._mark_notifications(keys, status="failed", error=error)

    def upsert_patient_link(self, link: PatientLink) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO wcw_patient_links
                    (entity_id, monday_item_id, drk_patient_id, patient_label,
                     identity_digest, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(entity_id) DO UPDATE SET
                    monday_item_id = COALESCE(excluded.monday_item_id, monday_item_id),
                    drk_patient_id = COALESCE(excluded.drk_patient_id, drk_patient_id),
                    patient_label = COALESCE(excluded.patient_label, patient_label),
                    identity_digest = COALESCE(excluded.identity_digest, identity_digest),
                    updated_at = excluded.updated_at
                """,
                (
                    link.entity_id,
                    link.monday_item_id,
                    link.drk_patient_id,
                    link.patient_label,
                    link.identity_digest,
                    link.updated_at.isoformat(),
                ),
            )

    def list_patient_links(self) -> list[PatientLink]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM wcw_patient_links ORDER BY updated_at, entity_id"
            ).fetchall()
        return [PatientLink.model_validate(dict(row)) for row in rows]

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
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT entity_id FROM wcw_patient_links WHERE {column} = ? LIMIT 1",
                (value,),
            ).fetchone()
        return None if row is None else str(row[0])

    def get_counter(self, entity_id: str, counter_name: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM wcw_workflow_counters WHERE entity_id = ? AND counter_name = ?",
                (entity_id, counter_name),
            ).fetchone()
        return 0 if row is None else int(row[0])

    def set_counter(self, counter: WorkflowCounter) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO wcw_workflow_counters (entity_id, counter_name, value, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(entity_id, counter_name) DO UPDATE SET
                    value = excluded.value, updated_at = excluded.updated_at
                """,
                (counter.entity_id, counter.counter_name, counter.value, counter.updated_at.isoformat()),
            )

    def record_cursor(self, source: str, cursor: str | None) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO wcw_sync_cursors (source, cursor, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(source) DO UPDATE SET cursor = excluded.cursor, updated_at = excluded.updated_at
                """,
                (source, cursor, utc_now().isoformat()),
            )

    def read_cursor(self, source: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT cursor FROM wcw_sync_cursors WHERE source = ?",
                (source,),
            ).fetchone()
        return None if row is None or row[0] is None else str(row[0])

    def component_health(self, component: str) -> ComponentHealth | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM wcw_component_health WHERE component = ?",
                (component,),
            ).fetchone()
        return None if row is None else ComponentHealth.model_validate(dict(row))

    def list_component_health(self) -> list[ComponentHealth]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM wcw_component_health ORDER BY component"
            ).fetchall()
        return [ComponentHealth.model_validate(dict(row)) for row in rows]

    def upsert_component_health(self, health: ComponentHealth) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO wcw_component_health
                    (component, status, last_attempt_at, last_success_at,
                     consecutive_failures, duration_seconds, error_code)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(component) DO UPDATE SET
                    status = excluded.status,
                    last_attempt_at = excluded.last_attempt_at,
                    last_success_at = excluded.last_success_at,
                    consecutive_failures = excluded.consecutive_failures,
                    duration_seconds = excluded.duration_seconds,
                    error_code = excluded.error_code
                """,
                (
                    health.component,
                    health.status,
                    health.last_attempt_at.isoformat(),
                    None if health.last_success_at is None else health.last_success_at.isoformat(),
                    health.consecutive_failures,
                    health.duration_seconds,
                    health.error_code,
                ),
            )

    def status_summary(self) -> dict[str, object]:
        with self._connect() as connection:
            counts = {
                "workflow_cases": connection.execute("SELECT COUNT(*) FROM wcw_workflow_cases").fetchone()[0],
                "pending_acknowledgements": connection.execute(
                    "SELECT COUNT(*) FROM wcw_outbound_acknowledgements WHERE status IN ('pending', 'sending', 'failed')"
                ).fetchone()[0],
                "snapshots": connection.execute("SELECT COUNT(*) FROM wcw_system_snapshots").fetchone()[0],
                "events": connection.execute("SELECT COUNT(*) FROM wcw_workflow_events").fetchone()[0],
                "open_exceptions": connection.execute("SELECT COUNT(*) FROM wcw_workflow_exceptions WHERE status = 'open'").fetchone()[0],
                "pending_notifications": connection.execute("SELECT COUNT(*) FROM wcw_notification_outbox WHERE status IN ('pending', 'failed')").fetchone()[0],
                "patient_links": connection.execute("SELECT COUNT(*) FROM wcw_patient_links").fetchone()[0],
                "unhealthy_components": connection.execute(
                    "SELECT COUNT(*) FROM wcw_component_health WHERE status != 'healthy'"
                ).fetchone()[0],
            }
        return {"backend": "sqlite", **counts}

    def _mark_notifications(self, keys: list[str], *, status: str, error: str | None) -> None:
        if not keys:
            return
        placeholders = ",".join("?" for _ in keys)
        with self._connect() as connection:
            connection.execute(
                f"""
                UPDATE wcw_notification_outbox
                SET status = ?, attempts = attempts + 1, last_error = ?
                WHERE notification_key IN ({placeholders})
                """,
                (status, error, *keys),
            )

    def _workflow_case_where(self, column: str, value: str) -> WorkflowCase | None:
        if column not in {"case_id", "source_ref"}:
            raise ValueError("unsupported workflow case lookup")
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT * FROM wcw_workflow_cases WHERE {column} = ? LIMIT 1",
                (value,),
            ).fetchone()
        return None if row is None else WorkflowCase.model_validate(dict(row))

    def _migrate(self) -> None:
        with self._connect() as connection:
            connection.executescript(_SQLITE_SCHEMA)
            _allow_duplicate_referral_ids(connection)
            _ensure_external_operation_columns(connection)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _work_item_from_row(row: sqlite3.Row) -> WorkflowWorkItem:
    payload = dict(row)
    payload["payload"] = json.loads(payload.pop("payload_json"))
    return WorkflowWorkItem.model_validate(payload)


def _decision_from_row(row: sqlite3.Row) -> WorkflowDecision:
    payload = dict(row)
    payload["selected_value"] = json.loads(payload.pop("selected_value_json"))
    return WorkflowDecision.model_validate(payload)


def _external_operation_from_row(row: sqlite3.Row) -> ExternalOperation:
    payload = dict(row)
    payload["request_payload"] = json.loads(payload.pop("request_payload_json"))
    payload["result"] = json.loads(payload.pop("result_json"))
    return ExternalOperation.model_validate(payload)


def _ensure_external_operation_columns(connection: sqlite3.Connection) -> None:
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(wcw_external_operations)")
    }
    if "lease_until" not in columns:
        connection.execute("ALTER TABLE wcw_external_operations ADD COLUMN lease_until TEXT")
    if "claimed_by" not in columns:
        connection.execute("ALTER TABLE wcw_external_operations ADD COLUMN claimed_by TEXT")


def _allow_duplicate_referral_ids(connection: sqlite3.Connection) -> None:
    """Migrate the early Stage 1 schema without discarding workflow history."""
    unique_referral_index = False
    for index in connection.execute("PRAGMA index_list('wcw_workflow_cases')").fetchall():
        if not index["unique"]:
            continue
        columns = connection.execute(
            f"PRAGMA index_info('{index['name']}')"
        ).fetchall()
        if [column["name"] for column in columns] == ["referral_id"]:
            unique_referral_index = True
            break
    if not unique_referral_index:
        return

    connection.executescript(
        """
        DROP TABLE IF EXISTS wcw_workflow_cases_v2;
        CREATE TABLE wcw_workflow_cases_v2 (
            case_id TEXT PRIMARY KEY,
            source_ref TEXT NOT NULL UNIQUE,
            source TEXT NOT NULL,
            attachment_sha256 TEXT,
            referral_id TEXT,
            patient_label TEXT,
            current_stage INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL,
            source_received_at TEXT,
            monday_item_id TEXT UNIQUE,
            drk_patient_id TEXT UNIQUE,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT
        );
        INSERT INTO wcw_workflow_cases_v2
        SELECT * FROM wcw_workflow_cases;
        DROP TABLE wcw_workflow_cases;
        ALTER TABLE wcw_workflow_cases_v2 RENAME TO wcw_workflow_cases;
        CREATE INDEX IF NOT EXISTS idx_wcw_workflow_cases_updated
            ON wcw_workflow_cases(updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_wcw_workflow_cases_attachment_sha256
            ON wcw_workflow_cases(attachment_sha256)
            WHERE attachment_sha256 IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_wcw_workflow_cases_referral_id
            ON wcw_workflow_cases(referral_id)
            WHERE referral_id IS NOT NULL;
        """
    )


_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS wcw_workflow_cases (
    case_id TEXT PRIMARY KEY,
    source_ref TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    attachment_sha256 TEXT,
    referral_id TEXT,
    patient_label TEXT,
    current_stage INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL,
    source_received_at TEXT,
    monday_item_id TEXT UNIQUE,
    drk_patient_id TEXT UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_wcw_workflow_cases_updated
    ON wcw_workflow_cases(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_wcw_workflow_cases_attachment_sha256
    ON wcw_workflow_cases(attachment_sha256)
    WHERE attachment_sha256 IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_wcw_workflow_cases_referral_id
    ON wcw_workflow_cases(referral_id)
    WHERE referral_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS wcw_work_items (
    work_item_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES wcw_workflow_cases(case_id) ON DELETE CASCADE,
    stage INTEGER NOT NULL,
    step_id TEXT NOT NULL,
    owner_role TEXT NOT NULL,
    status TEXT NOT NULL,
    recommended_assignee TEXT,
    recommendation_reason TEXT,
    assigned_to TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    UNIQUE(case_id, stage, step_id)
);
CREATE INDEX IF NOT EXISTS idx_wcw_work_items_queue
    ON wcw_work_items(stage, status, updated_at DESC);
CREATE TABLE IF NOT EXISTS wcw_workflow_decisions (
    decision_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    case_id TEXT NOT NULL REFERENCES wcw_workflow_cases(case_id) ON DELETE CASCADE,
    stage INTEGER NOT NULL,
    step_id TEXT NOT NULL,
    decision_type TEXT NOT NULL,
    selected_value_json TEXT NOT NULL,
    decided_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wcw_workflow_decisions_case
    ON wcw_workflow_decisions(case_id, created_at DESC);
CREATE TABLE IF NOT EXISTS wcw_external_operations (
    operation_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    case_id TEXT NOT NULL REFERENCES wcw_workflow_cases(case_id) ON DELETE CASCADE,
    stage INTEGER NOT NULL,
    operation_type TEXT NOT NULL,
    status TEXT NOT NULL,
    request_payload_json TEXT NOT NULL DEFAULT '{}',
    result_json TEXT NOT NULL DEFAULT '{}',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    lease_until TEXT,
    claimed_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_wcw_external_operations_case
    ON wcw_external_operations(case_id, stage, updated_at DESC);
CREATE TABLE IF NOT EXISTS wcw_outbound_acknowledgements (
    case_id TEXT PRIMARY KEY REFERENCES wcw_workflow_cases(case_id) ON DELETE CASCADE,
    recipient TEXT NOT NULL,
    payload_digest TEXT NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    lease_until TEXT,
    sent_at TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS wcw_patient_links (
    entity_id TEXT PRIMARY KEY,
    monday_item_id TEXT UNIQUE,
    drk_patient_id TEXT UNIQUE,
    patient_label TEXT,
    identity_digest TEXT,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS wcw_system_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    payload_digest TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(source, external_id, payload_digest)
);
CREATE INDEX IF NOT EXISTS idx_wcw_snapshots_latest
    ON wcw_system_snapshots(source, external_id, observed_at DESC);
CREATE TABLE IF NOT EXISTS wcw_workflow_events (
    event_key TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    source TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    details_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wcw_workflow_events_timeline
    ON wcw_workflow_events(entity_id, occurred_at DESC);
CREATE TABLE IF NOT EXISTS wcw_workflow_exceptions (
    exception_key TEXT PRIMARY KEY,
    exception_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    resolved_at TEXT,
    details_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wcw_exceptions_open
    ON wcw_workflow_exceptions(status, exception_type);
CREATE TABLE IF NOT EXISTS wcw_notification_outbox (
    notification_key TEXT PRIMARY KEY,
    exception_key TEXT NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS wcw_workflow_counters (
    entity_id TEXT NOT NULL,
    counter_name TEXT NOT NULL,
    value INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(entity_id, counter_name)
);
CREATE TABLE IF NOT EXISTS wcw_sync_cursors (
    source TEXT PRIMARY KEY,
    cursor TEXT,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS wcw_component_health (
    component TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    last_attempt_at TEXT NOT NULL,
    last_success_at TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    duration_seconds REAL,
    error_code TEXT
);
"""
