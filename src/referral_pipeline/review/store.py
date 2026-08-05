"""SQLite-backed review state, token validation, and write idempotency."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from referral_pipeline.review.models import ReviewRequest


CONFIRMABLE_STATUSES = ("awaiting_confirmation",)
REVIEW_SELECT = """
    SELECT review_id, recipient, status, artifact_digest, canonical_path,
           intake_plan_path, monday_preview_path, drk_draft_path, source_message_id,
           created_at, monday_item_id, drk_status, email_subject, email_body,
           email_html_body, email_text_body, email_content_type
    FROM referral_reviews
"""


class ReviewStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS referral_reviews (
                    review_id TEXT PRIMARY KEY,
                    recipient TEXT NOT NULL,
                    status TEXT NOT NULL,
                    token_hash TEXT NOT NULL,
                    artifact_digest TEXT NOT NULL,
                    canonical_path TEXT NOT NULL,
                    intake_plan_path TEXT NOT NULL,
                    monday_preview_path TEXT NOT NULL,
                    drk_draft_path TEXT NOT NULL,
                    source_message_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    confirmed_at TEXT,
                    confirmation_message_id TEXT UNIQUE,
                    monday_item_id TEXT,
                    drk_status TEXT,
                    error TEXT
                )
                """
            )
            self._ensure_email_columns(connection)

    def add(
        self,
        *,
        review_id: str,
        token: str,
        recipient: str,
        artifact_digest: str,
        canonical_path: str,
        intake_plan_path: str,
        monday_preview_path: str,
        drk_draft_path: str,
        source_message_id: str,
        status: str = "awaiting_confirmation",
        email_subject: str | None = None,
        email_body: str | None = None,
        email_html_body: str | None = None,
        email_text_body: str | None = None,
        email_content_type: str | None = None,
    ) -> ReviewRequest:
        created_at = _now()
        text_body = email_text_body if email_text_body is not None else email_body
        html_body = email_html_body
        content_type = (email_content_type or ("HTML" if html_body else "Text")).upper()
        legacy_body = html_body if content_type == "HTML" and html_body else text_body
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO referral_reviews (
                    review_id, recipient, status, token_hash, artifact_digest,
                    canonical_path, intake_plan_path, monday_preview_path, drk_draft_path,
                    source_message_id, created_at, email_subject, email_body,
                    email_html_body, email_text_body, email_content_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    recipient.casefold(),
                    status,
                    _token_hash(token),
                    artifact_digest,
                    canonical_path,
                    intake_plan_path,
                    monday_preview_path,
                    drk_draft_path,
                    source_message_id,
                    created_at,
                    email_subject,
                    legacy_body,
                    html_body,
                    text_body,
                    content_type,
                ),
            )
        return self.get(review_id)

    def find_active(
        self,
        *,
        artifact_digest: str,
        source_message_id: str,
        recipient: str,
    ) -> ReviewRequest | None:
        with self._connect() as connection:
            row = connection.execute(
                REVIEW_SELECT
                + """
                WHERE artifact_digest = ? AND source_message_id = ? AND recipient = ?
                  AND status IN (?, ?, ?)
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (
                    artifact_digest,
                    source_message_id,
                    recipient.casefold(),
                    "awaiting_confirmation",
                    "needs_correction",
                    "review_send_failed",
                ),
            ).fetchone()
        if row is None:
            return None
        return _row_to_request(row)

    def get(self, review_id: str) -> ReviewRequest:
        with self._connect() as connection:
            row = connection.execute(REVIEW_SELECT + " WHERE review_id = ?", (review_id,)).fetchone()
        if row is None:
            raise KeyError(review_id)
        return _row_to_request(row)

    def mark_sent(
        self,
        review_id: str,
        *,
        status: str,
        email_subject: str,
        email_body: str | None = None,
        email_html_body: str | None = None,
        email_text_body: str | None = None,
        email_content_type: str | None = None,
    ) -> None:
        text_body = email_text_body if email_text_body is not None else email_body
        html_body = email_html_body
        content_type = (email_content_type or ("HTML" if html_body else "Text")).upper()
        legacy_body = html_body if content_type == "HTML" and html_body else text_body
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE referral_reviews
                SET status = ?, email_subject = ?, email_body = ?, email_html_body = ?,
                    email_text_body = ?, email_content_type = ?, error = NULL
                WHERE review_id = ?
                """,
                (status, email_subject, legacy_body, html_body, text_body, content_type, review_id),
            )

    def confirm(
        self,
        *,
        review_id: str,
        token: str,
        sender: str,
        message_id: str,
    ) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT recipient, token_hash, status FROM referral_reviews
                WHERE review_id = ?
                """,
                (review_id,),
            ).fetchone()
            if row is None:
                return False
            recipient, expected_hash, status = row
            if status not in CONFIRMABLE_STATUSES:
                return False
            if str(recipient).casefold() != sender.casefold():
                return False
            if not _constant_time_equal(str(expected_hash), _token_hash(token)):
                return False
            try:
                cursor = connection.execute(
                    """
                    UPDATE referral_reviews
                    SET status = 'confirmed', confirmed_at = ?, confirmation_message_id = ?
                    WHERE review_id = ? AND status = 'awaiting_confirmation'
                    """,
                    (_now(), message_id, review_id),
                )
            except sqlite3.IntegrityError:
                return False
        return cursor.rowcount == 1

    def confirmed(self) -> list[ReviewRequest]:
        with self._connect() as connection:
            rows = connection.execute(
                REVIEW_SELECT + " WHERE status = 'confirmed' ORDER BY created_at"
            ).fetchall()
        return [_row_to_request(row) for row in rows]

    def mark_monday_applied(self, review_id: str, *, item_id: str, drk_status: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE referral_reviews
                SET status = 'monday_applied_drk_pending', monday_item_id = ?, drk_status = ?, error = NULL
                WHERE review_id = ? AND status = 'applying_monday'
                """,
                (item_id, drk_status, review_id),
            )

    def begin_monday_apply(self, review_id: str) -> bool:
        """Claim a confirmed write once; an interrupted remote call needs reconciliation."""
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE referral_reviews SET status = 'applying_monday', error = NULL
                WHERE review_id = ? AND status = 'confirmed'
                """,
                (review_id,),
            )
        return cursor.rowcount == 1

    def mark_failed(self, review_id: str, *, error: str, status: str = "execution_failed") -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE referral_reviews SET status = ?, error = ? WHERE review_id = ?",
                (status, error, review_id),
            )

    def _ensure_email_columns(self, connection: sqlite3.Connection) -> None:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(referral_reviews)").fetchall()}
        additions = {
            "email_subject": "TEXT",
            "email_body": "TEXT",
            "email_html_body": "TEXT",
            "email_text_body": "TEXT",
            "email_content_type": "TEXT",
        }
        for name, declaration in additions.items():
            if name not in columns:
                connection.execute(f"ALTER TABLE referral_reviews ADD COLUMN {name} {declaration}")
        connection.execute(
            """
            UPDATE referral_reviews
            SET email_text_body = COALESCE(email_text_body, email_body),
                email_content_type = COALESCE(email_content_type, CASE WHEN email_html_body IS NOT NULL THEN 'HTML' ELSE 'Text' END)
            WHERE email_text_body IS NULL OR email_content_type IS NULL
            """
        )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)


def _row_to_request(row: tuple) -> ReviewRequest:
    return ReviewRequest(
        review_id=row[0],
        recipient=row[1],
        status=row[2],
        artifact_digest=row[3],
        canonical_path=row[4],
        intake_plan_path=row[5],
        monday_preview_path=row[6],
        drk_draft_path=row[7],
        source_message_id=row[8],
        created_at=row[9],
        monday_item_id=row[10],
        drk_status=row[11],
        email_subject=row[12],
        email_body=row[13],
        email_html_body=row[14],
        email_text_body=row[15],
        email_content_type=row[16],
    )


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _constant_time_equal(left: str, right: str) -> bool:
    import hmac

    return hmac.compare_digest(left, right)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
