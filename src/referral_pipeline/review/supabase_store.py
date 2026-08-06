"""Supabase persistence for durable referral reviews and reply decisions."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any

import requests
from dotenv import load_dotenv

from referral_pipeline.review.models import ReviewRequest


class SupabaseReviewStoreError(RuntimeError):
    pass


class SupabaseReviewStore:
    def __init__(
        self,
        *,
        url: str,
        service_key: str,
        timeout_s: int = 30,
        session: Any = requests,
    ) -> None:
        self.base_url = f"{url.rstrip('/')}/rest/v1"
        self.service_key = service_key
        self.timeout_s = timeout_s
        self.session = session

    @classmethod
    def from_environment(cls) -> SupabaseReviewStore | None:
        load_dotenv()
        url = os.getenv("SUPABASE_URL", "").strip()
        key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            or os.getenv("SUPABASE_SERVICE_KEY", "").strip()
        )
        if not url and not key:
            return None
        if not url or not key:
            raise SupabaseReviewStoreError(
                "Supabase review persistence requires SUPABASE_URL and "
                "SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_SERVICE_KEY)"
            )
        return cls(url=url, service_key=key)

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
        canonical_referral: dict[str, Any] | None = None,
        intake_plan: dict[str, Any] | None = None,
        monday_preview: dict[str, Any] | None = None,
        drk_draft: dict[str, Any] | None = None,
        status: str = "awaiting_confirmation",
        email_subject: str | None = None,
        email_body: str | None = None,
        email_html_body: str | None = None,
        email_text_body: str | None = None,
        email_content_type: str | None = None,
    ) -> ReviewRequest:
        del token, canonical_path, intake_plan_path, monday_preview_path, drk_draft_path
        snapshots = {
            "canonical_referral": canonical_referral,
            "intake_plan": intake_plan,
            "monday_preview": monday_preview,
            "drk_draft": drk_draft,
        }
        missing = [name for name, value in snapshots.items() if not isinstance(value, dict)]
        if missing:
            raise SupabaseReviewStoreError(
                f"Supabase review snapshots are missing: {', '.join(missing)}"
            )
        if not source_conversation_id:
            raise SupabaseReviewStoreError("source conversation ID is required")
        row = self._post(
            "referral_reviews",
            {
                "review_id": review_id,
                "recipient": recipient.casefold(),
                "status": status,
                "source_message_id": source_message_id,
                "source_conversation_id": source_conversation_id,
                "source_attachment_sha256": source_attachment_sha256,
                "artifact_digest": artifact_digest,
                **snapshots,
                "email_subject": email_subject,
                "email_html_body": email_html_body,
                "email_text_body": email_text_body if email_text_body is not None else email_body,
                "email_content_type": _content_type(email_content_type, email_html_body),
            },
        )
        return _request_from_row(row)

    def find_active(
        self,
        *,
        artifact_digest: str,
        source_message_id: str,
        recipient: str,
    ) -> ReviewRequest | None:
        rows = self._get(
            "referral_reviews",
            {
                "artifact_digest": f"eq.{artifact_digest}",
                "source_message_id": f"eq.{source_message_id}",
                "recipient": f"eq.{recipient.casefold()}",
                "status": "in.(awaiting_confirmation,needs_correction,review_send_failed)",
                "order": "created_at.desc",
                "limit": "1",
            },
        )
        return _request_from_row(rows[0]) if rows else None

    def get(self, review_id: str) -> ReviewRequest:
        rows = self._get(
            "referral_reviews",
            {"review_id": f"eq.{review_id}", "limit": "1"},
        )
        if not rows:
            raise KeyError(review_id)
        return _request_from_row(rows[0])

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
        self._patch(
            "referral_reviews",
            {"review_id": f"eq.{review_id}"},
            {
                "status": status,
                "email_subject": email_subject,
                "email_html_body": email_html_body,
                "email_text_body": email_text_body if email_text_body is not None else email_body,
                "email_content_type": _content_type(email_content_type, email_html_body),
                "review_sent_at": _now(),
                "error": None,
            },
        )

    def find_confirmable_for_reply(
        self,
        *,
        sender: str,
        conversation_id: str,
    ) -> ReviewRequest | None:
        rows = self._get(
            "referral_reviews",
            {
                "recipient": f"eq.{sender.casefold()}",
                "source_conversation_id": f"eq.{conversation_id}",
                "status": "eq.awaiting_confirmation",
                "order": "created_at.desc",
                "limit": "2",
            },
        )
        return _request_from_row(rows[0]) if len(rows) == 1 else None

    def response_exists(self, message_id: str) -> bool:
        return bool(
            self._get(
                "review_responses",
                {"outlook_message_id": f"eq.{message_id}", "select": "id", "limit": "1"},
            )
        )

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
            self._post(
                "review_responses",
                {
                    "review_id": review_id,
                    "outlook_message_id": message_id,
                    "sender": sender.casefold(),
                    "conversation_id": conversation_id,
                    "received_at": received_at,
                    "intent": intent,
                    "classifier_source": classifier_source,
                    "classifier_reason": classifier_reason,
                    "body_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                },
            )
        except SupabaseReviewStoreError as error:
            if "409" in str(error) or "23505" in str(error):
                return False
            raise
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
        response = self.session.post(
            f"{self.base_url}/rpc/process_review_response",
            headers=self._headers(),
            json={
                "p_review_id": review_id,
                "p_outlook_message_id": message_id,
                "p_sender": sender,
                "p_conversation_id": conversation_id,
                "p_received_at": received_at,
                "p_intent": intent,
                "p_classifier_source": classifier_source,
                "p_classifier_reason": classifier_reason,
                "p_body_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            },
            timeout=self.timeout_s,
        )
        if not response.ok:
            raise SupabaseReviewStoreError(
                f"Supabase response processing failed: HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )
        result = response.json()
        if not isinstance(result, str):
            raise SupabaseReviewStoreError("Supabase response function returned an unexpected result")
        return result

    def confirm_by_context(
        self,
        *,
        review_id: str,
        sender: str,
        conversation_id: str,
        message_id: str,
    ) -> bool:
        rows = self._patch(
            "referral_reviews",
            {
                "review_id": f"eq.{review_id}",
                "status": "eq.awaiting_confirmation",
                "recipient": f"eq.{sender.casefold()}",
                "source_conversation_id": f"eq.{conversation_id}",
            },
            {
                "status": "confirmed",
                "confirmed_at": _now(),
                "confirmation_message_id": message_id,
                "error": None,
            },
        )
        return len(rows) == 1

    def mark_needs_correction(self, review_id: str, *, message_id: str) -> bool:
        rows = self._patch(
            "referral_reviews",
            {"review_id": f"eq.{review_id}", "status": "eq.awaiting_confirmation"},
            {
                "status": "needs_correction",
                "confirmation_message_id": message_id,
                "error": None,
            },
        )
        return len(rows) == 1

    def mark_dry_run_completed(self, review_id: str) -> None:
        self._patch(
            "referral_reviews",
            {
                "review_id": f"eq.{review_id}",
                "status": "in.(confirmed,dry_run_completed)",
            },
            {"status": "dry_run_completed", "drk_status": "dry_run_only", "error": None},
        )

    def record_dry_run(self, review_id: str, *, result: dict[str, Any]) -> None:
        self._patch(
            "referral_reviews",
            {
                "review_id": f"eq.{review_id}",
                "status": "in.(confirmed,dry_run_completed)",
            },
            {
                "status": "dry_run_completed",
                "last_dry_run_at": _now(),
                "last_dry_run_result": result,
                "drk_status": "pending_draft",
                "error": None,
            },
        )

    def record_dry_run_failure(self, review_id: str, *, error: str) -> None:
        self._patch(
            "referral_reviews",
            {
                "review_id": f"eq.{review_id}",
                "status": "in.(confirmed,dry_run_completed)",
            },
            {
                "last_dry_run_at": _now(),
                "last_dry_run_result": {
                    "review_id": review_id,
                    "status": "dry_run_failed",
                    "writes_performed": False,
                    "error": error,
                },
                "error": error,
            },
        )

    def claim_for_monday_execution(self, review_id: str) -> str:
        response = self.session.post(
            f"{self.base_url}/rpc/claim_review_for_monday_execution",
            headers=self._headers(),
            json={"p_review_id": review_id},
            timeout=self.timeout_s,
        )
        if not response.ok:
            raise SupabaseReviewStoreError(
                f"Supabase Monday claim failed: HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )
        result = response.json()
        if not isinstance(result, str):
            raise SupabaseReviewStoreError("Supabase Monday claim returned an unexpected result")
        return result

    def mark_monday_item_created(self, review_id: str, *, item_id: str) -> None:
        self._patch(
            "referral_reviews",
            {"review_id": f"eq.{review_id}", "status": "eq.applying_monday"},
            {"monday_item_id": item_id, "error": None},
        )

    def confirmed(self) -> list[ReviewRequest]:
        return [
            _request_from_row(row)
            for row in self._get(
                "referral_reviews",
                {
                    "status": "in.(confirmed,dry_run_completed)",
                    "order": "created_at.asc",
                },
            )
        ]

    def mark_monday_applied(self, review_id: str, *, item_id: str, drk_status: str) -> None:
        self._patch(
            "referral_reviews",
            {"review_id": f"eq.{review_id}", "status": "eq.applying_monday"},
            {
                "status": "monday_applied_drk_pending",
                "monday_item_id": item_id,
                "drk_status": drk_status,
                "error": None,
            },
        )

    def begin_monday_apply(self, review_id: str) -> bool:
        return self.claim_for_monday_execution(review_id) == "claimed"

    def mark_failed(self, review_id: str, *, error: str, status: str = "failed") -> None:
        safe_status = status if status in {"review_send_failed", "failed"} else "failed"
        self._patch(
            "referral_reviews",
            {"review_id": f"eq.{review_id}"},
            {"status": safe_status, "error": error},
        )

    def _headers(self, *, return_rows: bool = False) -> dict[str, str]:
        headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
        }
        if return_rows:
            headers["Prefer"] = "return=representation"
        return headers

    def _get(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        response = self.session.get(
            f"{self.base_url}/{table}",
            headers=self._headers(),
            params={"select": "*", **params},
            timeout=self.timeout_s,
        )
        return self._rows(response)

    def _post(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(
            f"{self.base_url}/{table}",
            headers=self._headers(return_rows=True),
            json=payload,
            timeout=self.timeout_s,
        )
        rows = self._rows(response)
        if len(rows) != 1:
            raise SupabaseReviewStoreError(f"Supabase insert returned {len(rows)} rows")
        return rows[0]

    def _patch(
        self,
        table: str,
        params: dict[str, str],
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        response = self.session.patch(
            f"{self.base_url}/{table}",
            headers=self._headers(return_rows=True),
            params=params,
            json=payload,
            timeout=self.timeout_s,
        )
        return self._rows(response)

    @staticmethod
    def _rows(response: Any) -> list[dict[str, Any]]:
        if not response.ok:
            raise SupabaseReviewStoreError(
                f"Supabase review persistence failed: HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )
        payload = response.json()
        if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
            raise SupabaseReviewStoreError("Supabase returned an unexpected response")
        return payload


def _request_from_row(row: dict[str, Any]) -> ReviewRequest:
    return ReviewRequest(
        review_id=str(row["review_id"]),
        recipient=str(row["recipient"]),
        status=str(row["status"]),
        artifact_digest=str(row["artifact_digest"]),
        canonical_path="",
        intake_plan_path="",
        monday_preview_path="",
        drk_draft_path="",
        source_message_id=str(row["source_message_id"]),
        source_conversation_id=str(row.get("source_conversation_id") or "") or None,
        created_at=str(row["created_at"]),
        monday_item_id=_optional_text(row.get("monday_item_id")),
        drk_status=_optional_text(row.get("drk_status")),
        email_subject=_optional_text(row.get("email_subject")),
        email_html_body=_optional_text(row.get("email_html_body")),
        email_text_body=_optional_text(row.get("email_text_body")),
        email_content_type=_optional_text(row.get("email_content_type")),
        canonical_referral=_object(row.get("canonical_referral")),
        intake_plan=_object(row.get("intake_plan")),
        monday_preview=_object(row.get("monday_preview")),
        drk_draft=_object(row.get("drk_draft")),
        last_dry_run_at=_optional_text(row.get("last_dry_run_at")),
        last_dry_run_result=_object(row.get("last_dry_run_result")),
    )


def _object(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _optional_text(value: Any) -> str | None:
    return str(value) if value is not None else None


def _content_type(value: str | None, html_body: str | None) -> str:
    return (value or ("HTML" if html_body else "TEXT")).upper()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

