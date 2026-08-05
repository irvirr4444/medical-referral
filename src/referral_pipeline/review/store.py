"""SQLite-backed review state, token validation, and write idempotency."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from referral_pipeline.review.models import ReviewRequest


ACTIVE_STATUSES = ("awaiting_confirmation", "confirmed")


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
    ) -> ReviewRequest:
        created_at = _now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO referral_reviews (
                    review_id, recipient, status, token_hash, artifact_digest,
                    canonical_path, intake_plan_path, monday_preview_path, drk_draft_path,
                    source_message_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )
        return self.get(review_id)

    def get(self, review_id: str) -> ReviewRequest:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT review_id, recipient, status, artifact_digest, canonical_path,
                       intake_plan_path, monday_preview_path, drk_draft_path, source_message_id,
                       created_at, monday_item_id, drk_status
                FROM referral_reviews WHERE review_id = ?
                """,
                (review_id,),
            ).fetchone()
        if row is None:
            raise KeyError(review_id)
        return ReviewRequest(*row)

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
            if status not in ACTIVE_STATUSES:
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
                """
                SELECT review_id, recipient, status, artifact_digest, canonical_path,
                       intake_plan_path, monday_preview_path, drk_draft_path, source_message_id,
                       created_at, monday_item_id, drk_status
                FROM referral_reviews WHERE status = 'confirmed' ORDER BY created_at
                """
            ).fetchall()
        return [ReviewRequest(*row) for row in rows]

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

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _constant_time_equal(left: str, right: str) -> bool:
    import hmac

    return hmac.compare_digest(left, right)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
