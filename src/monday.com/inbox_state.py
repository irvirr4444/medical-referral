"""Minimal local idempotency store for inbound referral attachments."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from inbound_mail import InboundPdfAttachment


class InboxState:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
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

    def is_completed(self, attachment: InboundPdfAttachment) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT status FROM processed_attachments
                WHERE source = ? AND message_id = ? AND attachment_id = ? AND sha256 = ?
                """,
                _key(attachment),
            ).fetchone()
        return bool(row and row[0] == "completed")

    def mark(self, attachment: InboundPdfAttachment, *, status: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO processed_attachments (source, message_id, attachment_id, sha256, status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, message_id, attachment_id, sha256)
                DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at
                """,
                (*_key(attachment), status, datetime.now(timezone.utc).isoformat()),
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)


def _key(attachment: InboundPdfAttachment) -> tuple[str, str, str, str]:
    return attachment.source, attachment.message_id, attachment.attachment_id, attachment.sha256
