"""Data structures shared by the review workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReviewRequest:
    review_id: str
    recipient: str
    status: str
    artifact_digest: str
    canonical_path: str
    intake_plan_path: str
    monday_preview_path: str
    drk_draft_path: str
    source_message_id: str
    source_conversation_id: str | None
    created_at: str
    monday_item_id: str | None = None
    drk_status: str | None = None
    email_subject: str | None = None
    email_body: str | None = None
    email_html_body: str | None = None
    email_text_body: str | None = None
    email_content_type: str | None = None
    canonical_referral: dict[str, Any] | None = None
    intake_plan: dict[str, Any] | None = None
    monday_preview: dict[str, Any] | None = None
    drk_draft: dict[str, Any] | None = None
    last_dry_run_at: str | None = None
    last_dry_run_result: dict[str, Any] | None = None


@dataclass(frozen=True)
class ApprovalCommand:
    review_id: str
    token: str
