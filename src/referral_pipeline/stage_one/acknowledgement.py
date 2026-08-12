"""Idempotency-gated referral partner acknowledgement delivery."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from Outlook.review_mail import OutlookReviewMailbox
from referral_pipeline.monitoring.store import WorkflowStore
from referral_pipeline.stage_one.tracker import StageOneTracker, acknowledgement_digest


TEMPLATE_VERSION = "partner-ack-v1"


def send_partner_acknowledgement(
    *,
    case: Any,
    manifest: dict[str, Any],
    recipient: str,
    source_message_id: str,
    mailbox: OutlookReviewMailbox,
    store: WorkflowStore,
    tracker: StageOneTracker,
) -> str:
    """Send at most one acknowledged payload per case under normal retries."""
    address = recipient.strip().casefold()
    if not address:
        raise ValueError("referral partner email address is unavailable")
    digest = acknowledgement_digest(
        case_id=case.case_id,
        recipient=address,
        template_version=TEMPLATE_VERSION,
    )
    claim = store.claim_acknowledgement(
        case.case_id,
        recipient=address,
        payload_digest=digest,
    )
    if claim == "already_sent":
        tracker.acknowledgement_sent(case, recipient=address)
        return claim
    if claim != "claimed":
        raise TimeoutError(f"partner acknowledgement is temporarily unavailable ({claim})")

    text, html = _render_acknowledgement(manifest)
    try:
        mailbox.send_reply(
            source_message_id=source_message_id,
            recipient=address,
            content_type="HTML",
            html_body=html,
            text_body=text,
        )
    except Exception as error:
        store.mark_acknowledgement_failed(case.case_id, _safe_error(error))
        raise
    store.mark_acknowledgement_sent(case.case_id)
    tracker.acknowledgement_sent(case, recipient=address)
    return "sent"


def _render_acknowledgement(manifest: dict[str, Any]) -> tuple[str, str]:
    missing = _missing_field_labels(manifest)
    if missing:
        missing_text = ", ".join(missing)
        text = (
            "Thank you. We received the referral and began intake.\n\n"
            f"The following information still needs review: {missing_text}.\n\n"
            "The West Coast Wound intake team will follow up if anything else is required."
        )
        html = (
            "<p>Thank you. We received the referral and began intake.</p>"
            f"<p>The following information still needs review: <strong>{_escape(missing_text)}</strong>.</p>"
            "<p>The West Coast Wound intake team will follow up if anything else is required.</p>"
        )
        return text, html
    return (
        "Thank you. We received the referral and began intake.\n\n"
        "The West Coast Wound intake team will follow up if anything else is required.",
        "<p>Thank you. We received the referral and began intake.</p>"
        "<p>The West Coast Wound intake team will follow up if anything else is required.</p>",
    )


def _missing_field_labels(manifest: dict[str, Any]) -> list[str]:
    path = manifest.get("plan_path")
    if not path:
        return []
    try:
        import json

        plan = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return []
    validation = plan.get("validation") if isinstance(plan, dict) else None
    if not isinstance(validation, dict):
        return []
    labels = validation.get("field_labels") if isinstance(validation.get("field_labels"), dict) else {}
    missing = list(validation.get("threshold_missing") or []) + list(validation.get("supporting_missing") or [])
    return [str(labels.get(field) or field).strip() for field in missing if str(field).strip()]


def _safe_error(error: Exception) -> str:
    status = getattr(error, "status_code", None)
    return f"{type(error).__name__}: status={status or 'unavailable'}"


def _escape(value: str) -> str:
    from html import escape

    return escape(value)
