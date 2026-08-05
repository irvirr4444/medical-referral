"""Data structures shared by the review workflow."""

from __future__ import annotations

from dataclasses import dataclass


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
    created_at: str
    monday_item_id: str | None = None
    drk_status: str | None = None


@dataclass(frozen=True)
class ApprovalCommand:
    review_id: str
    token: str
