"""Durable SQLite job ledger and Anthropic circuit breaker for intake retries."""

from __future__ import annotations

import json
import os
import random
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from Outlook.mail import InboundPdfAttachment


SCHEMA_VERSION = 2
DEFAULT_LEASE_SECONDS = 30 * 60
DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_RETRY_BASE_MINUTES = 1.0
DEFAULT_RETRY_MAX_MINUTES = 60.0
DEFAULT_CIRCUIT_FAILURE_THRESHOLD = 3
DEFAULT_CIRCUIT_COOLDOWN_SECONDS = 15 * 60
ANTHROPIC_DEPENDENCY = "anthropic"

STATUS_DISCOVERED = "discovered"
STATUS_PROCESSING = "processing"
STATUS_PENDING_RETRY = "pending_retry"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

CIRCUIT_CLOSED = "closed"
CIRCUIT_OPEN = "open"
CIRCUIT_HALF_OPEN = "half_open"


@dataclass(frozen=True)
class AttachmentJob:
    source: str
    message_id: str
    attachment_id: str
    sha256: str
    status: str
    filename: str | None
    subject: str | None
    received_at: str | None
    artifact_path: str | None
    options_json: str | None
    attempt_count: int
    next_attempt_at: str | None
    last_attempt_at: str | None
    last_error: str | None
    error_kind: str | None
    lease_until: str | None
    created_at: str
    updated_at: str

    @property
    def options(self) -> dict[str, Any]:
        if not self.options_json:
            return {}
        value = json.loads(self.options_json)
        return value if isinstance(value, dict) else {}


class InboxState:
    def __init__(
        self,
        path: str | Path,
        *,
        clock: Callable[[], datetime] | None = None,
        random_source: Callable[[], float] | None = None,
        max_attempts: int | None = None,
        circuit_failure_threshold: int | None = None,
        circuit_cooldown_seconds: int | None = None,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._random = random_source or random.random
        self.max_attempts = max_attempts or int(os.getenv("INTAKE_MAX_ATTEMPTS", str(DEFAULT_MAX_ATTEMPTS)))
        self.circuit_failure_threshold = circuit_failure_threshold or int(
            os.getenv("INTAKE_ANTHROPIC_CIRCUIT_FAILURES", str(DEFAULT_CIRCUIT_FAILURE_THRESHOLD))
        )
        self.circuit_cooldown_seconds = circuit_cooldown_seconds or int(
            os.getenv("INTAKE_ANTHROPIC_CIRCUIT_COOLDOWN_SECONDS", str(DEFAULT_CIRCUIT_COOLDOWN_SECONDS))
        )
        self.lease_seconds = lease_seconds
        with self._connect() as connection:
            self._migrate(connection)

    def is_completed(self, attachment: InboundPdfAttachment) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT status FROM processed_attachments
                WHERE source = ? AND message_id = ? AND attachment_id = ? AND sha256 = ?
                """,
                _key(attachment),
            ).fetchone()
        return bool(row and row[0] == STATUS_COMPLETED)

    def mark(self, attachment: InboundPdfAttachment, *, status: str) -> None:
        """Compatibility helper for simple completed/failed marking."""
        now = _iso(self._clock())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO processed_attachments (
                    source, message_id, attachment_id, sha256, status, filename, subject,
                    received_at, artifact_path, options_json, attempt_count, next_attempt_at,
                    last_attempt_at, last_error, error_kind, lease_until, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, 0, NULL, NULL, NULL, NULL, NULL, ?, ?)
                ON CONFLICT(source, message_id, attachment_id, sha256) DO UPDATE SET
                    status = excluded.status,
                    filename = COALESCE(excluded.filename, processed_attachments.filename),
                    subject = COALESCE(excluded.subject, processed_attachments.subject),
                    received_at = COALESCE(excluded.received_at, processed_attachments.received_at),
                    updated_at = excluded.updated_at,
                    lease_until = NULL
                """,
                (
                    *_key(attachment),
                    status,
                    attachment.filename,
                    attachment.subject,
                    attachment.received_at,
                    now,
                    now,
                ),
            )

    def enqueue(
        self,
        attachment: InboundPdfAttachment,
        *,
        artifact_path: str | Path | None = None,
        options: dict[str, Any] | None = None,
        force: bool = False,
    ) -> AttachmentJob | None:
        """Insert or refresh a job.

        Returns None when already completed unless force=True. Permanent failures
        are preserved and returned so rediscovery does not retry them until an
        operator explicitly requeues.
        """
        now = _iso(self._clock())
        options_json = json.dumps(options or {}, sort_keys=True)
        artifact = str(Path(artifact_path).resolve()) if artifact_path else None
        with self._connect() as connection:
            existing = connection.execute(
                """
                SELECT status FROM processed_attachments
                WHERE source = ? AND message_id = ? AND attachment_id = ? AND sha256 = ?
                """,
                _key(attachment),
            ).fetchone()
            if existing and existing[0] == STATUS_COMPLETED and not force:
                return None
            if existing and existing[0] == STATUS_FAILED and not force:
                connection.execute(
                    """
                    UPDATE processed_attachments
                    SET filename = ?, subject = ?, received_at = ?,
                        artifact_path = COALESCE(?, artifact_path),
                        options_json = ?, updated_at = ?
                    WHERE source = ? AND message_id = ? AND attachment_id = ? AND sha256 = ?
                    """,
                    (
                        attachment.filename,
                        attachment.subject,
                        attachment.received_at,
                        artifact,
                        options_json,
                        now,
                        *_key(attachment),
                    ),
                )
                return self._get(connection, attachment)
            if force and existing and existing[0] in {STATUS_COMPLETED, STATUS_FAILED}:
                connection.execute(
                    """
                    UPDATE processed_attachments
                    SET status = ?, artifact_path = COALESCE(?, artifact_path),
                        options_json = ?, attempt_count = 0, next_attempt_at = ?,
                        last_error = NULL, error_kind = NULL, lease_until = NULL, updated_at = ?,
                        filename = ?, subject = ?, received_at = ?
                    WHERE source = ? AND message_id = ? AND attachment_id = ? AND sha256 = ?
                    """,
                    (
                        STATUS_DISCOVERED,
                        artifact,
                        options_json,
                        now,
                        now,
                        attachment.filename,
                        attachment.subject,
                        attachment.received_at,
                        *_key(attachment),
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO processed_attachments (
                        source, message_id, attachment_id, sha256, status, filename, subject,
                        received_at, artifact_path, options_json, attempt_count, next_attempt_at,
                        last_attempt_at, last_error, error_kind, lease_until, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, NULL, NULL, NULL, NULL, ?, ?)
                    ON CONFLICT(source, message_id, attachment_id, sha256) DO UPDATE SET
                        filename = excluded.filename,
                        subject = excluded.subject,
                        received_at = excluded.received_at,
                        artifact_path = COALESCE(excluded.artifact_path, processed_attachments.artifact_path),
                        options_json = excluded.options_json,
                        status = CASE
                            WHEN processed_attachments.status IN (?, ?, ?) THEN processed_attachments.status
                            ELSE excluded.status
                        END,
                        next_attempt_at = CASE
                            WHEN processed_attachments.status = ? THEN processed_attachments.next_attempt_at
                            WHEN processed_attachments.status = ? THEN processed_attachments.next_attempt_at
                            WHEN processed_attachments.status = ? THEN processed_attachments.next_attempt_at
                            ELSE excluded.next_attempt_at
                        END,
                        updated_at = excluded.updated_at
                    """,
                    (
                        *_key(attachment),
                        STATUS_DISCOVERED,
                        attachment.filename,
                        attachment.subject,
                        attachment.received_at,
                        artifact,
                        options_json,
                        now,
                        now,
                        now,
                        STATUS_PENDING_RETRY,
                        STATUS_PROCESSING,
                        STATUS_FAILED,
                        STATUS_PENDING_RETRY,
                        STATUS_PROCESSING,
                        STATUS_FAILED,
                    ),
                )
            return self._get(connection, attachment)

    def claim_due(self, *, limit: int = 1) -> list[AttachmentJob]:
        self.recover_expired_leases()
        if not self.circuit_allows_work():
            return []
        now = self._clock()
        now_iso = _iso(now)
        lease_until = _iso(now + timedelta(seconds=self.lease_seconds))
        claimed: list[AttachmentJob] = []
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT source, message_id, attachment_id, sha256
                FROM processed_attachments
                WHERE status IN (?, ?)
                  AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
                ORDER BY COALESCE(next_attempt_at, created_at), created_at
                LIMIT ?
                """,
                (STATUS_DISCOVERED, STATUS_PENDING_RETRY, now_iso, limit),
            ).fetchall()
            for source, message_id, attachment_id, sha256 in rows:
                job = self._try_claim(connection, source, message_id, attachment_id, sha256, now_iso, lease_until)
                if job is not None:
                    claimed.append(job)
                    if self.circuit_state() == CIRCUIT_HALF_OPEN:
                        break
        return claimed

    def claim_job(self, attachment: InboundPdfAttachment) -> AttachmentJob | None:
        """Atomically claim one known attachment when the circuit allows work."""
        self.recover_expired_leases()
        if not self.circuit_allows_work():
            return None
        now = self._clock()
        now_iso = _iso(now)
        lease_until = _iso(now + timedelta(seconds=self.lease_seconds))
        with self._connect() as connection:
            return self._try_claim(
                connection,
                attachment.source,
                attachment.message_id,
                attachment.attachment_id,
                attachment.sha256,
                now_iso,
                lease_until,
            )

    def _try_claim(
        self,
        connection: sqlite3.Connection,
        source: str,
        message_id: str,
        attachment_id: str,
        sha256: str,
        now_iso: str,
        lease_until: str,
    ) -> AttachmentJob | None:
        cursor = connection.execute(
            """
            UPDATE processed_attachments
            SET status = ?, lease_until = ?, last_attempt_at = ?, updated_at = ?,
                attempt_count = attempt_count + 1
            WHERE source = ? AND message_id = ? AND attachment_id = ? AND sha256 = ?
              AND status IN (?, ?)
              AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
            """,
            (
                STATUS_PROCESSING,
                lease_until,
                now_iso,
                now_iso,
                source,
                message_id,
                attachment_id,
                sha256,
                STATUS_DISCOVERED,
                STATUS_PENDING_RETRY,
                now_iso,
            ),
        )
        if cursor.rowcount != 1:
            return None
        return self._get_key(connection, source, message_id, attachment_id, sha256)

    def mark_completed(self, job: AttachmentJob) -> None:
        now = _iso(self._clock())
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE processed_attachments
                SET status = ?, lease_until = NULL, last_error = NULL, error_kind = NULL,
                    next_attempt_at = NULL, updated_at = ?
                WHERE source = ? AND message_id = ? AND attachment_id = ? AND sha256 = ?
                """,
                (STATUS_COMPLETED, now, job.source, job.message_id, job.attachment_id, job.sha256),
            )
        self.record_dependency_success(ANTHROPIC_DEPENDENCY)

    def mark_retryable_failure(
        self,
        job: AttachmentJob,
        *,
        error: str,
        error_kind: str = "capacity",
    ) -> AttachmentJob:
        now = self._clock()
        sanitized = _sanitize_error(error)
        if job.attempt_count >= self.max_attempts:
            return self.mark_terminal_failure(job, error=sanitized, error_kind=error_kind)
        delay_minutes = min(
            DEFAULT_RETRY_BASE_MINUTES * (2 ** max(job.attempt_count - 1, 0)),
            DEFAULT_RETRY_MAX_MINUTES,
        )
        delay_seconds = delay_minutes * 60.0 * self._random()
        next_attempt = _iso(now + timedelta(seconds=max(delay_seconds, 30.0)))
        now_iso = _iso(now)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE processed_attachments
                SET status = ?, next_attempt_at = ?, last_error = ?, error_kind = ?,
                    lease_until = NULL, updated_at = ?
                WHERE source = ? AND message_id = ? AND attachment_id = ? AND sha256 = ?
                """,
                (
                    STATUS_PENDING_RETRY,
                    next_attempt,
                    sanitized,
                    error_kind,
                    now_iso,
                    job.source,
                    job.message_id,
                    job.attachment_id,
                    job.sha256,
                ),
            )
            updated = self._get_key(connection, job.source, job.message_id, job.attachment_id, job.sha256)
        if error_kind == "capacity":
            self.record_dependency_failure(ANTHROPIC_DEPENDENCY, error=sanitized)
        return updated

    def mark_terminal_failure(
        self,
        job: AttachmentJob,
        *,
        error: str,
        error_kind: str = "permanent",
    ) -> AttachmentJob:
        now = _iso(self._clock())
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE processed_attachments
                SET status = ?, last_error = ?, error_kind = ?, lease_until = NULL,
                    next_attempt_at = NULL, updated_at = ?
                WHERE source = ? AND message_id = ? AND attachment_id = ? AND sha256 = ?
                """,
                (
                    STATUS_FAILED,
                    _sanitize_error(error),
                    error_kind,
                    now,
                    job.source,
                    job.message_id,
                    job.attachment_id,
                    job.sha256,
                ),
            )
            return self._get_key(connection, job.source, job.message_id, job.attachment_id, job.sha256)

    def recover_expired_leases(self) -> int:
        now = _iso(self._clock())
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE processed_attachments
                SET status = ?, next_attempt_at = ?, lease_until = NULL, updated_at = ?,
                    last_error = COALESCE(last_error, 'processing lease expired')
                WHERE status = ? AND lease_until IS NOT NULL AND lease_until < ?
                """,
                (STATUS_PENDING_RETRY, now, now, STATUS_PROCESSING, now),
            )
            return cursor.rowcount

    def due_count(self) -> int:
        self.recover_expired_leases()
        now = _iso(self._clock())
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) FROM processed_attachments
                WHERE status IN (?, ?)
                  AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
                """,
                (STATUS_DISCOVERED, STATUS_PENDING_RETRY, now),
            ).fetchone()
        return int(row[0] if row else 0)

    def pending_retry_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM processed_attachments WHERE status = ?",
                (STATUS_PENDING_RETRY,),
            ).fetchone()
        return int(row[0] if row else 0)

    def failed_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM processed_attachments WHERE status = ?",
                (STATUS_FAILED,),
            ).fetchone()
        return int(row[0] if row else 0)

    def list_failed(self, *, limit: int = 50) -> list[AttachmentJob]:
        """Return permanent failures newest-updated first for operator reporting."""
        if limit < 1:
            raise ValueError("limit must be at least 1")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT source, message_id, attachment_id, sha256, status, filename, subject, received_at,
                       artifact_path, options_json, attempt_count, next_attempt_at, last_attempt_at,
                       last_error, error_kind, lease_until, created_at, updated_at
                FROM processed_attachments
                WHERE status = ?
                ORDER BY updated_at DESC, created_at DESC
                LIMIT ?
                """,
                (STATUS_FAILED, limit),
            ).fetchall()
        return [AttachmentJob(*row) for row in rows]

    def requeue_failed(self, *, sha256: str) -> AttachmentJob:
        """Move one permanent failure back to discovered for a deliberate retry."""
        digest = (sha256 or "").strip().lower()
        if not digest:
            raise ValueError("sha256 is required to requeue a failed job")
        now = _iso(self._clock())
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE processed_attachments
                SET status = ?, attempt_count = 0, next_attempt_at = ?, last_error = NULL,
                    error_kind = NULL, lease_until = NULL, updated_at = ?
                WHERE sha256 = ? AND status = ?
                """,
                (STATUS_DISCOVERED, now, now, digest, STATUS_FAILED),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"No failed job found for sha256={digest}")
            row = connection.execute(
                """
                SELECT source, message_id, attachment_id, sha256, status, filename, subject, received_at,
                       artifact_path, options_json, attempt_count, next_attempt_at, last_attempt_at,
                       last_error, error_kind, lease_until, created_at, updated_at
                FROM processed_attachments
                WHERE sha256 = ?
                """,
                (digest,),
            ).fetchone()
        if row is None:
            raise KeyError(f"No failed job found for sha256={digest}")
        return AttachmentJob(*row)

    def get_job(self, attachment: InboundPdfAttachment) -> AttachmentJob | None:
        with self._connect() as connection:
            try:
                return self._get(connection, attachment)
            except KeyError:
                return None

    def circuit_state(self) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT state, next_probe_at FROM dependency_circuits WHERE dependency = ?",
                (ANTHROPIC_DEPENDENCY,),
            ).fetchone()
        if row is None:
            return CIRCUIT_CLOSED
        state, next_probe_at = row
        if state == CIRCUIT_OPEN and next_probe_at and next_probe_at <= _iso(self._clock()):
            self._set_circuit(CIRCUIT_HALF_OPEN)
            return CIRCUIT_HALF_OPEN
        return str(state)

    def circuit_allows_work(self) -> bool:
        state = self.circuit_state()
        return state in {CIRCUIT_CLOSED, CIRCUIT_HALF_OPEN}

    def record_dependency_success(self, dependency: str = ANTHROPIC_DEPENDENCY) -> None:
        now = _iso(self._clock())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO dependency_circuits (
                    dependency, consecutive_failures, state, opened_at, next_probe_at, last_error, updated_at
                ) VALUES (?, 0, ?, NULL, NULL, NULL, ?)
                ON CONFLICT(dependency) DO UPDATE SET
                    consecutive_failures = 0,
                    state = excluded.state,
                    opened_at = NULL,
                    next_probe_at = NULL,
                    last_error = NULL,
                    updated_at = excluded.updated_at
                """,
                (dependency, CIRCUIT_CLOSED, now),
            )

    def record_dependency_failure(self, dependency: str = ANTHROPIC_DEPENDENCY, *, error: str) -> None:
        now = self._clock()
        now_iso = _iso(now)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT consecutive_failures, state FROM dependency_circuits WHERE dependency = ?",
                (dependency,),
            ).fetchone()
            failures = int(row[0]) + 1 if row else 1
            state = CIRCUIT_OPEN if failures >= self.circuit_failure_threshold else CIRCUIT_CLOSED
            opened_at = now_iso if state == CIRCUIT_OPEN else None
            next_probe = (
                _iso(now + timedelta(seconds=self.circuit_cooldown_seconds)) if state == CIRCUIT_OPEN else None
            )
            connection.execute(
                """
                INSERT INTO dependency_circuits (
                    dependency, consecutive_failures, state, opened_at, next_probe_at, last_error, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(dependency) DO UPDATE SET
                    consecutive_failures = excluded.consecutive_failures,
                    state = excluded.state,
                    opened_at = excluded.opened_at,
                    next_probe_at = excluded.next_probe_at,
                    last_error = excluded.last_error,
                    updated_at = excluded.updated_at
                """,
                (dependency, failures, state, opened_at, next_probe, _sanitize_error(error), now_iso),
            )

    def _set_circuit(self, state: str) -> None:
        now = _iso(self._clock())
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE dependency_circuits
                SET state = ?, updated_at = ?
                WHERE dependency = ?
                """,
                (state, now, ANTHROPIC_DEPENDENCY),
            )

    def _migrate(self, connection: sqlite3.Connection) -> None:
        connection.execute("PRAGMA busy_timeout = 5000")
        current = connection.execute("PRAGMA user_version").fetchone()[0]
        if current < 1:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_attachments (
                    source TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    attachment_id TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (source, message_id, attachment_id, sha256)
                )
                """
            )
            connection.execute("PRAGMA user_version = 1")
            current = 1
        if current < 2:
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(processed_attachments)").fetchall()
            }
            additions = {
                "filename": "TEXT",
                "subject": "TEXT",
                "received_at": "TEXT",
                "artifact_path": "TEXT",
                "options_json": "TEXT",
                "attempt_count": "INTEGER NOT NULL DEFAULT 0",
                "next_attempt_at": "TEXT",
                "last_attempt_at": "TEXT",
                "last_error": "TEXT",
                "error_kind": "TEXT",
                "lease_until": "TEXT",
                "created_at": "TEXT",
            }
            for name, declaration in additions.items():
                if name not in columns:
                    connection.execute(
                        f"ALTER TABLE processed_attachments ADD COLUMN {name} {declaration}"
                    )
            connection.execute(
                """
                UPDATE processed_attachments
                SET created_at = COALESCE(created_at, updated_at),
                    next_attempt_at = CASE
                        WHEN status = 'failed' THEN updated_at
                        ELSE next_attempt_at
                    END,
                    status = CASE
                        WHEN status = 'failed' THEN ?
                        ELSE status
                    END
                """,
                (STATUS_PENDING_RETRY,),
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS dependency_circuits (
                    dependency TEXT PRIMARY KEY,
                    consecutive_failures INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    opened_at TEXT,
                    next_probe_at TEXT,
                    last_error TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_processed_attachments_due
                ON processed_attachments (status, next_attempt_at)
                """
            )
            connection.execute("PRAGMA user_version = 2")

    def _get(self, connection: sqlite3.Connection, attachment: InboundPdfAttachment) -> AttachmentJob:
        return self._get_key(
            connection,
            attachment.source,
            attachment.message_id,
            attachment.attachment_id,
            attachment.sha256,
        )

    def _get_key(
        self,
        connection: sqlite3.Connection,
        source: str,
        message_id: str,
        attachment_id: str,
        sha256: str,
    ) -> AttachmentJob:
        row = connection.execute(
            """
            SELECT source, message_id, attachment_id, sha256, status, filename, subject, received_at,
                   artifact_path, options_json, attempt_count, next_attempt_at, last_attempt_at,
                   last_error, error_kind, lease_until, created_at, updated_at
            FROM processed_attachments
            WHERE source = ? AND message_id = ? AND attachment_id = ? AND sha256 = ?
            """,
            (source, message_id, attachment_id, sha256),
        ).fetchone()
        if row is None:
            raise KeyError((source, message_id, attachment_id, sha256))
        return AttachmentJob(*row)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection


def _key(attachment: InboundPdfAttachment) -> tuple[str, str, str, str]:
    return attachment.source, attachment.message_id, attachment.attachment_id, attachment.sha256


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _sanitize_error(error: str, *, limit: int = 500) -> str:
    cleaned = " ".join(str(error).split())
    return cleaned[:limit]
