"""Microsoft Graph transport for referral review messages and replies."""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from typing import Any
from urllib.parse import urlencode
import re

from Outlook.graph import OutlookGraphClient


@dataclass(frozen=True)
class ReviewReply:
    message_id: str
    sender: str
    subject: str
    received_at: str | None
    conversation_id: str | None
    text: str


class OutlookReviewMailbox:
    def __init__(self, client: OutlookGraphClient) -> None:
        self.client = client

    def send_review(
        self,
        *,
        recipient: str,
        subject: str,
        text_body: str | None = None,
        html_body: str | None = None,
        content_type: str = "HTML",
        body: str | None = None,
    ) -> None:
        """Send a standalone review message to an authorized internal recipient."""
        if not recipient.strip():
            raise ValueError("review recipient cannot be empty")
        if not subject.strip():
            raise ValueError("review subject cannot be empty")
        selected_type = content_type.strip().upper()
        if selected_type not in {"HTML", "TEXT"}:
            raise ValueError("content_type must be HTML or Text")
        if body is not None:
            content = body
        elif selected_type == "HTML":
            content = html_body if html_body is not None else text_body
        else:
            content = text_body if text_body is not None else html_body
        if not content:
            raise ValueError("review message body cannot be empty")
        self.client.post_no_content(
            f"/users/{self.client.config.mailbox}/sendMail",
            {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": "HTML" if selected_type == "HTML" else "Text",
                        "content": content,
                    },
                    "toRecipients": [{"emailAddress": {"address": recipient}}],
                },
                "saveToSentItems": True,
            },
        )

    def list_replies(self, *, max_messages: int = 25) -> list[ReviewReply]:
        query = urlencode(
            {
                "$select": "id,subject,receivedDateTime,from,uniqueBody,conversationId",
                "$orderby": "receivedDateTime desc",
                "$top": str(max_messages),
            }
        )
        payload = self.client.get_json(
            f"/users/{self.client.config.mailbox}/mailFolders/inbox/messages?{query}"
        )
        values = payload.get("value")
        if not isinstance(values, list):
            return []
        replies: list[ReviewReply] = []
        for item in values:
            if not isinstance(item, dict):
                continue
            sender = _sender_address(item)
            message_id = str(item.get("id") or "")
            if not sender or not message_id:
                continue
            unique_body = item.get("uniqueBody") or {}
            replies.append(
                ReviewReply(
                    message_id=message_id,
                    sender=sender,
                    subject=str(item.get("subject") or ""),
                    received_at=str(item.get("receivedDateTime") or "") or None,
                    conversation_id=str(item.get("conversationId") or "") or None,
                    text=_plain_text(str(unique_body.get("content") or "")),
                )
            )
        return replies


def _sender_address(message: dict[str, Any]) -> str:
    sender = message.get("from") or {}
    email = sender.get("emailAddress") if isinstance(sender, dict) else {}
    return str(email.get("address") or "") if isinstance(email, dict) else ""


def _plain_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", "\n", value)
    return unescape(without_tags).replace("\xa0", " ").strip()
