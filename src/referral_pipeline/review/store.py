"""SQLite-backed review state, token validation, and write idempotency."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from referral_pipeline.review.models import ReviewRequest


CONFIRMABLE_STATUSES = ("awaiting_confirmation",)
REVIEW_SELECT = """
    SELECT review_id, recipient, status, artifact_digest, canonical_path,
           intake_plan_path, monday_preview_path, drk_draft_path, source_message_id,
           source_conversation_id, created_at, monday_item_id, drk_status, email_subject, email_body,
           email_html_body, email_text_body, email_content_type, last_dry_run_at, last_dry_run_result,
           review_purpose, workflow_case_id
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
                    source_conversation_id TEXT,
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS review_responses (
                    outlook_message_id TEXT PRIMARY KEY,
                    review_id TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    classifier_source TEXT NOT NULL,
                    classifier_reason TEXT,
                    body_sha256 TEXT NOT NULL,
                    processed_at TEXT NOT NULL,
                    FOREIGN KEY (review_id) REFERENCES referral_reviews(review_id)
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
        source_conversation_id: str | None = None,
        source_attachment_sha256: str | None = None,
        canonical_referral: dict | None = None,
        intake_plan: dict | None = None,
        monday_preview: dict | None = None,
        drk_draft: dict | None = None,
        status: str = "awaiting_confirmation",
        purpose: str = "destination_write",
        workflow_case_id: str | None = None,
        email_subject: str | None = None,
        email_body: str | None = None,
        email_html_body: str | None = None,
        email_text_body: str | None = None,
        email_content_type: str | None = None,
    ) -> ReviewRequest:
        del (
            source_attachment_sha256,
            canonical_referral,
            intake_plan,
            monday_preview,
            drk_draft,
        )
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
                    source_message_id, source_conversation_id, created_at, email_subject, email_body,
                    email_html_body, email_text_body, email_content_type, review_purpose,
                    workflow_case_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    source_conversation_id,
                    created_at,
                    email_subject,
                    legacy_body,
                    html_body,
                    text_body,
                    content_type,
                    purpose,
                    workflow_case_id,
                ),
            )
        return self.get(review_id)

    def find_active(
        self,
        *,
        artifact_digest: str,
        source_message_id: str,
        recipient: str,
        purpose: str = "destination_write",
    ) -> ReviewRequest | None:
        with self._connect() as connection:
            row = connection.execute(
                REVIEW_SELECT
                + """
                WHERE artifact_digest = ? AND source_message_id = ? AND recipient = ?
                  AND review_purpose = ?
                  AND status IN (?, ?, ?)
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (
                    artifact_digest,
                    source_message_id,
                    recipient.casefold(),
                    purpose,
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
                SELECT recipient, token_hash, status, review_purpose FROM referral_reviews
                WHERE review_id = ?
                """,
                (review_id,),
            ).fetchone()
            if row is None:
                return False
            recipient, expected_hash, status, purpose = row
            if status not in CONFIRMABLE_STATUSES:
                return False
            if purpose != "destination_write":
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
                      AND review_purpose = 'destination_write'
                    """,
                    (_now(), message_id, review_id),
                )
            except sqlite3.IntegrityError:
                return False
        return cursor.rowcount == 1

    def find_confirmable_for_reply(
        self,
        *,
        sender: str,
        conversation_id: str,
    ) -> ReviewRequest | None:
        """Find one pending review bound to this authorized sender and thread."""
        with self._connect() as connection:
            rows = connection.execute(
                REVIEW_SELECT
                + """
                WHERE recipient = ? AND source_conversation_id = ?
                  AND status = 'awaiting_confirmation'
                ORDER BY created_at DESC
                LIMIT 2
                """,
                (sender.casefold(), conversation_id),
            ).fetchall()
        if len(rows) != 1:
            return None
        return _row_to_request(rows[0])

    def response_exists(self, message_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM review_responses WHERE outlook_message_id = ?",
                (message_id,),
            ).fetchone()
        return row is not None

    def record_response(
        self,
        *,
        review_id: str,
        message_id: str,
        sender: str,
        conversation_id: str,
        received_at: str,
        text: str,
        intent: str,
        classifier_source: str,
        classifier_reason: str,
    ) -> bool:
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO review_responses (
                        outlook_message_id, review_id, sender, conversation_id,
                        received_at, intent, classifier_source, classifier_reason,
                        body_sha256, processed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        message_id,
                        review_id,
                        sender.casefold(),
                        conversation_id,
                        received_at,
                        intent,
                        classifier_source,
                        classifier_reason,
                        hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        _now(),
                    ),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def process_response(
        self,
        *,
        review_id: str,
        message_id: str,
        sender: str,
        conversation_id: str,
        received_at: str,
        text: str,
        intent: str,
        classifier_source: str,
        classifier_reason: str,
    ) -> str:
        with self._connect() as connection:
            if connection.execute(
                "SELECT 1 FROM review_responses WHERE outlook_message_id = ?",
                (message_id,),
            ).fetchone():
                return "duplicate"
            row = connection.execute(
                """
                SELECT status, review_purpose FROM referral_reviews
                WHERE review_id = ? AND recipient = ? AND source_conversation_id = ?
                """,
                (review_id, sender.casefold(), conversation_id),
            ).fetchone()
            if row is None:
                return "no_matching_review"
            if row[0] != "awaiting_confirmation":
                return "review_state_changed"
            purpose = str(row[1] or "destination_write")
            connection.execute(
                """
                INSERT INTO review_responses (
                    outlook_message_id, review_id, sender, conversation_id,
                    received_at, intent, classifier_source, classifier_reason,
                    body_sha256, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    review_id,
                    sender.casefold(),
                    conversation_id,
                    received_at,
                    intent,
                    classifier_source,
                    classifier_reason,
                    hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    _now(),
                ),
            )
            if intent == "confirm":
                confirmed_status = (
                    "partner_contact_confirmed"
                    if purpose == "partner_contact"
                    else "confirmed"
                )
                connection.execute(
                    """
                    UPDATE referral_reviews
                    SET status = ?, confirmed_at = ?,
                        confirmation_message_id = ?, error = NULL
                    WHERE review_id = ?
                    """,
                    (confirmed_status, _now(), message_id, review_id),
                )
                return confirmed_status
            if intent == "correction":
                connection.execute(
                    """
                    UPDATE referral_reviews
                    SET status = 'needs_correction', confirmation_message_id = ?, error = NULL
                    WHERE review_id = ?
                    """,
                    (message_id, review_id),
                )
                return "needs_correction"
        return "unclear"

    def confirm_by_context(
        self,
        *,
        review_id: str,
        sender: str,
        conversation_id: str,
        message_id: str,
    ) -> bool:
        """Confirm once using deterministic sender/thread/state binding."""
        with self._connect() as connection:
            try:
                cursor = connection.execute(
                    """
                    UPDATE referral_reviews
                    SET status = 'confirmed', confirmed_at = ?, confirmation_message_id = ?
                    WHERE review_id = ? AND status = 'awaiting_confirmation'
                      AND review_purpose = 'destination_write'
                      AND recipient = ? AND source_conversation_id = ?
                    """,
                    (_now(), message_id, review_id, sender.casefold(), conversation_id),
                )
            except sqlite3.IntegrityError:
                return False
        return cursor.rowcount == 1

    def mark_needs_correction(self, review_id: str, *, message_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE referral_reviews
                SET status = 'needs_correction', confirmation_message_id = ?
                WHERE review_id = ? AND status = 'awaiting_confirmation'
                """,
                (message_id, review_id),
            )
        return cursor.rowcount == 1

    def mark_dry_run_completed(self, review_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE referral_reviews
                SET status = 'dry_run_completed', drk_status = 'dry_run_only', error = NULL
                WHERE review_id = ? AND status IN ('confirmed', 'dry_run_completed')
                """,
                (review_id,),
            )

    def record_dry_run(self, review_id: str, *, result: dict) -> None:
        import json

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE referral_reviews
                SET status = 'dry_run_completed',
                    last_dry_run_at = ?,
                    last_dry_run_result = ?,
                    drk_status = 'pending_draft',
                    error = NULL
                WHERE review_id = ? AND status IN ('confirmed', 'dry_run_completed')
                """,
                (_now(), json.dumps(result), review_id),
            )

    def record_dry_run_failure(self, review_id: str, *, error: str) -> None:
        import json

        result = {
            "review_id": review_id,
            "status": "dry_run_failed",
            "writes_performed": False,
            "error": error,
        }
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE referral_reviews
                SET last_dry_run_at = ?,
                    last_dry_run_result = ?,
                    error = ?
                WHERE review_id = ? AND status IN ('confirmed', 'dry_run_completed')
                """,
                (_now(), json.dumps(result), error, review_id),
            )

    def claim_for_monday_execution(self, review_id: str) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status, review_purpose FROM referral_reviews WHERE review_id = ?",
                (review_id,),
            ).fetchone()
            if row is None:
                return "missing"
            status, purpose = row
            if purpose != "destination_write":
                return "wrong_purpose"
            if status == "applying_monday":
                return "already_claiming"
            if status == "monday_applied_drk_pending":
                return "already_applied"
            if status not in {"confirmed", "dry_run_completed"}:
                return "not_confirmed"
            cursor = connection.execute(
                """
                UPDATE referral_reviews
                SET status = 'applying_monday', error = NULL
                WHERE review_id = ? AND review_purpose = 'destination_write'
                  AND status IN ('confirmed', 'dry_run_completed')
                """,
                (review_id,),
            )
            return "claimed" if cursor.rowcount == 1 else "race_lost"

    def mark_monday_item_created(self, review_id: str, *, item_id: str) -> None:
        """Persist the Monday item ID immediately after create, before secondary work."""
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE referral_reviews
                SET monday_item_id = ?, error = NULL
                WHERE review_id = ? AND status = 'applying_monday'
                """,
                (item_id, review_id),
            )

    def confirmed(self) -> list[ReviewRequest]:
        with self._connect() as connection:
            rows = connection.execute(
                REVIEW_SELECT
                + " WHERE review_purpose = 'destination_write' "
                  "AND status IN ('confirmed', 'dry_run_completed') ORDER BY created_at"
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
        return self.claim_for_monday_execution(review_id) == "claimed"

    def mark_failed(self, review_id: str, *, error: str, status: str = "failed") -> None:
        safe_status = status if status in {"review_send_failed", "failed"} else "failed"
        with self._connect() as connection:
            connection.execute(
                "UPDATE referral_reviews SET status = ?, error = ? WHERE review_id = ?",
                (safe_status, error, review_id),
            )

    def _ensure_email_columns(self, connection: sqlite3.Connection) -> None:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(referral_reviews)").fetchall()}
        additions = {
            "email_subject": "TEXT",
            "email_body": "TEXT",
            "email_html_body": "TEXT",
            "email_text_body": "TEXT",
            "email_content_type": "TEXT",
            "source_conversation_id": "TEXT",
            "last_dry_run_at": "TEXT",
            "last_dry_run_result": "TEXT",
            "review_purpose": "TEXT NOT NULL DEFAULT 'destination_write'",
            "workflow_case_id": "TEXT",
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
    import json

    dry_run_result = None
    if len(row) > 19 and row[19]:
        try:
            dry_run_result = json.loads(row[19])
        except (TypeError, json.JSONDecodeError):
            dry_run_result = None
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
        source_conversation_id=row[9],
        created_at=row[10],
        monday_item_id=row[11],
        drk_status=row[12],
        email_subject=row[13],
        email_body=row[14],
        email_html_body=row[15],
        email_text_body=row[16],
        email_content_type=row[17],
        last_dry_run_at=row[18] if len(row) > 18 else None,
        last_dry_run_result=dry_run_result,
        purpose=str(row[20] or "destination_write") if len(row) > 20 else "destination_write",
        workflow_case_id=str(row[21]) if len(row) > 21 and row[21] else None,
    )


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _constant_time_equal(left: str, right: str) -> bool:
    import hmac

    return hmac.compare_digest(left, right)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_review_store(path: str | Path, *, allow_supabase: bool = True):
    """Use Supabase when configured; retain SQLite for offline tests and tools."""
    from referral_pipeline.review.supabase_store import SupabaseReviewStore

    backend = os.getenv("REFERRAL_REVIEW_STORE", "").strip().casefold()
    if backend == "sqlite" or not allow_supabase:
        return ReviewStore(path)
    supabase = SupabaseReviewStore.from_environment()
    if backend == "supabase" and supabase is None:
        raise RuntimeError("REFERRAL_REVIEW_STORE=supabase but Supabase credentials are missing")
    return supabase if supabase is not None else ReviewStore(path)
