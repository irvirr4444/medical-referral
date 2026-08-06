"""SQLite implementation used for local runs and deterministic tests."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from referral_pipeline.monitoring.models import (
    NotificationRecord,
    OperationalSnapshot,
    PatientLink,
    WorkflowCounter,
    WorkflowEvent,
    WorkflowException,
    utc_now,
)


class SQLiteWorkflowStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

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

    def status_summary(self) -> dict[str, object]:
        with self._connect() as connection:
            counts = {
                "snapshots": connection.execute("SELECT COUNT(*) FROM wcw_system_snapshots").fetchone()[0],
                "events": connection.execute("SELECT COUNT(*) FROM wcw_workflow_events").fetchone()[0],
                "open_exceptions": connection.execute("SELECT COUNT(*) FROM wcw_workflow_exceptions WHERE status = 'open'").fetchone()[0],
                "pending_notifications": connection.execute("SELECT COUNT(*) FROM wcw_notification_outbox WHERE status IN ('pending', 'failed')").fetchone()[0],
                "patient_links": connection.execute("SELECT COUNT(*) FROM wcw_patient_links").fetchone()[0],
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

    def _migrate(self) -> None:
        with self._connect() as connection:
            connection.executescript(_SQLITE_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


_SQLITE_SCHEMA = """
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
"""
