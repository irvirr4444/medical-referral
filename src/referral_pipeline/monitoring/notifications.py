"""Dispatch notification outbox entries as recipient-level email digests."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from referral_pipeline.monitoring.models import NotificationRecord
from referral_pipeline.monitoring.store import WorkflowStore


SendEmail = Callable[[str, str, str], None]


def dispatch_pending_notifications(
    *,
    store: WorkflowStore,
    send_email: SendEmail,
    limit: int = 100,
    exception_key_prefix: str | None = None,
) -> dict[str, object]:
    pending = store.pending_notifications(limit=limit)
    if exception_key_prefix is not None:
        pending = [
            notification
            for notification in pending
            if notification.exception_key.startswith(exception_key_prefix)
        ]
    by_recipient: dict[str, list[NotificationRecord]] = defaultdict(list)
    for notification in pending:
        by_recipient[notification.recipient].append(notification)

    sent: list[str] = []
    failed: list[dict[str, str]] = []
    for recipient, records in by_recipient.items():
        keys = [record.notification_key for record in records]
        prefix = "WCW HEALTH" if all(
            record.exception_key.startswith("health:") for record in records
        ) else "WCW WORKFLOW"
        subject = (
            f"[{prefix}] {len(records)} exception"
            f"{'s' if len(records) != 1 else ''} require review"
        )
        body = _digest_body(records)
        try:
            send_email(recipient, subject, body)
        except Exception as error:  # noqa: BLE001 - failures remain durable in the outbox
            store.mark_notifications_failed(keys, str(error))
            failed.append({"recipient": recipient, "error": str(error)})
        else:
            store.mark_notifications_sent(keys)
            sent.extend(keys)
    return {"pending": len(pending), "sent": len(sent), "failed": failed}


def outlook_sender() -> SendEmail:
    from Outlook.graph import OutlookGraphClient, OutlookGraphConfig
    from Outlook.review_mail import OutlookReviewMailbox

    mailbox = OutlookReviewMailbox(OutlookGraphClient(OutlookGraphConfig.from_environment()))

    def send(recipient: str, subject: str, body: str) -> None:
        mailbox.send_review(recipient=recipient, subject=subject, text_body=body, content_type="Text")

    return send


def _digest_body(records: list[NotificationRecord]) -> str:
    sections = [record.body for record in records]
    return "\n\n---\n\n".join(sections)
