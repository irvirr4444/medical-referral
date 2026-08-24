"""Small Microsoft Graph client used by the Outlook-specific adapters."""

from __future__ import annotations

import base64
import binascii
import os
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

from Outlook.mail import InboundPdfAttachment, InboundPdfMetadata, is_pdf_file


GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
DEFAULT_PAGE_SIZE = 50
# Safety bound so a pathological inbox cannot loop forever while seeking eligible mail.
MAX_INBOX_SCAN = 500


class OutlookGraphError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class OutlookGraphConfig:
    tenant_id: str
    client_id: str
    client_secret: str
    mailbox: str

    @classmethod
    def from_environment(cls) -> "OutlookGraphConfig":
        load_dotenv()
        names = ("OUTLOOK_TENANT_ID", "OUTLOOK_CLIENT_ID", "OUTLOOK_CLIENT_SECRET", "OUTLOOK_MAILBOX")
        missing = [name for name in names if not os.getenv(name)]
        if missing:
            raise OutlookGraphError(f"Missing Outlook settings: {', '.join(missing)}")
        return cls(
            tenant_id=os.environ["OUTLOOK_TENANT_ID"],
            client_id=os.environ["OUTLOOK_CLIENT_ID"],
            client_secret=os.environ["OUTLOOK_CLIENT_SECRET"],
            mailbox=os.environ["OUTLOOK_MAILBOX"],
        )


class OutlookGraphClient:
    def __init__(self, config: OutlookGraphConfig, *, timeout_s: int = 30) -> None:
        self.config = config
        self.timeout_s = timeout_s
        self._access_token: str | None = None

    def list_inbox_pdf_attachments(
        self,
        *,
        max_messages: int = 25,
        include_attachment: Callable[[InboundPdfAttachment], bool] | None = None,
        scan_past_ineligible: bool = True,
    ) -> list[InboundPdfAttachment]:
        """Return PDFs from the newest eligible referral emails.

        The optional predicate lets the durable job ledger exclude attachments
        that were already discovered. `max_messages` counts emails retaining at
        least one eligible PDF, not raw inbox rows.
        """
        if max_messages < 1:
            raise ValueError("max_messages must be at least 1")

        attachments: list[InboundPdfAttachment] = []
        eligible_messages = 0
        for message in self._iter_inbox_messages(limit=MAX_INBOX_SCAN):
            if not message.get("hasAttachments"):
                continue
            pdfs = self._pdf_attachments_for_message(message)
            if not pdfs:
                continue
            if not scan_past_ineligible:
                eligible_messages += 1
            if include_attachment is not None:
                pdfs = [attachment for attachment in pdfs if include_attachment(attachment)]
            attachments.extend(pdfs)
            if scan_past_ineligible and pdfs:
                eligible_messages += 1
            if eligible_messages >= max_messages:
                break
        # Selected batch is newest-first; process oldest-to-newest within the batch.
        attachments.reverse()
        return attachments

    def list_inbox_pdf_metadata(self, *, max_messages: int = 25) -> list[InboundPdfMetadata]:
        """Return PDF attachment metadata without downloading attachment bytes."""
        if max_messages < 1:
            raise ValueError("max_messages must be at least 1")

        attachments: list[InboundPdfMetadata] = []
        eligible_messages = 0
        for message in self._iter_inbox_messages(limit=MAX_INBOX_SCAN):
            if not message.get("hasAttachments"):
                continue
            pdfs = self._pdf_metadata_for_message(message)
            if not pdfs:
                continue
            attachments.extend(pdfs)
            eligible_messages += 1
            if eligible_messages >= max_messages:
                break
        attachments.sort(key=lambda item: item.received_at or "", reverse=True)
        return attachments

    def download_pdf_attachment(self, metadata: InboundPdfMetadata) -> InboundPdfAttachment:
        """Download and signature-check one attachment selected from trusted metadata."""
        matches = self._pdf_attachments_for_message(
            {
                "id": metadata.message_id,
                "subject": metadata.subject,
                "receivedDateTime": metadata.received_at,
            }
        )
        for attachment in matches:
            if attachment.attachment_id == metadata.attachment_id:
                return attachment
        raise OutlookGraphError("The selected PDF attachment is no longer available.", status_code=404)

    def _iter_inbox_messages(self, *, limit: int):
        """Yield inbox messages newest-first, following Graph pagination."""
        page_size = min(DEFAULT_PAGE_SIZE, max(limit, 1))
        query = urlencode(
            {
                "$select": "id,subject,receivedDateTime,hasAttachments,conversationId,from",
                "$orderby": "receivedDateTime desc",
                "$top": str(page_size),
            }
        )
        next_url: str | None = f"{GRAPH_ROOT}/users/{self.config.mailbox}/mailFolders/inbox/messages?{query}"
        yielded = 0
        while next_url and yielded < limit:
            payload = self._get_url(next_url)
            values = payload.get("value")
            if not isinstance(values, list):
                raise OutlookGraphError("Microsoft Graph did not return an inbox message list.")
            for item in values:
                if not isinstance(item, dict):
                    continue
                yield item
                yielded += 1
                if yielded >= limit:
                    return
            next_link = payload.get("@odata.nextLink")
            next_url = next_link if isinstance(next_link, str) and next_link else None

    def _list_messages(self, *, max_messages: int) -> list[dict[str, Any]]:
        """Compatibility helper used by older tests; prefer `_iter_inbox_messages`."""
        return list(self._iter_inbox_messages(limit=max_messages))

    def _pdf_attachments_for_message(self, message: dict[str, Any]) -> list[InboundPdfAttachment]:
        message_id = str(message.get("id") or "")
        if not message_id:
            return []
        payload = self._get(f"/users/{self.config.mailbox}/messages/{message_id}/attachments")
        values = payload.get("value")
        if not isinstance(values, list):
            return []
        accepted: list[InboundPdfAttachment] = []
        for item in values:
            if not isinstance(item, dict) or item.get("@odata.type") != "#microsoft.graph.fileAttachment":
                continue
            filename = str(item.get("name") or "")
            encoded = item.get("contentBytes")
            if not isinstance(encoded, str):
                continue
            try:
                content = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error):
                continue
            if not is_pdf_file(filename, content):
                continue
            accepted.append(
                InboundPdfAttachment(
                    source="outlook-graph",
                    message_id=message_id,
                    attachment_id=str(item.get("id") or filename),
                    filename=filename,
                    content=content,
                    received_at=str(message.get("receivedDateTime") or "") or None,
                    subject=str(message.get("subject") or "") or None,
                    sender=_message_sender(message),
                    conversation_id=str(message.get("conversationId") or "") or None,
                )
            )
        return accepted

    def _pdf_metadata_for_message(self, message: dict[str, Any]) -> list[InboundPdfMetadata]:
        message_id = str(message.get("id") or "")
        if not message_id:
            return []
        query = urlencode({"$select": "id,name,contentType,size"})
        payload = self._get(f"/users/{self.config.mailbox}/messages/{message_id}/attachments?{query}")
        values = payload.get("value")
        if not isinstance(values, list):
            return []

        accepted: list[InboundPdfMetadata] = []
        for item in values:
            if not isinstance(item, dict) or item.get("@odata.type") != "#microsoft.graph.fileAttachment":
                continue
            filename = str(item.get("name") or "")
            if not filename.lower().endswith(".pdf"):
                continue
            raw_size = item.get("size")
            accepted.append(
                InboundPdfMetadata(
                    message_id=message_id,
                    attachment_id=str(item.get("id") or filename),
                    filename=filename,
                    received_at=str(message.get("receivedDateTime") or "") or None,
                    subject=str(message.get("subject") or "") or None,
                    sender=_message_sender(message),
                    size=raw_size if isinstance(raw_size, int) else None,
                )
            )
        return accepted

    def _get(self, path: str) -> dict[str, Any]:
        return self.get_json(path)

    def _get_url(self, url: str) -> dict[str, Any]:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {self._token()}"},
            timeout=self.timeout_s,
        )
        if response.status_code == 401:
            self._access_token = None
            response = requests.get(
                url,
                headers={"Authorization": f"Bearer {self._token()}"},
                timeout=self.timeout_s,
            )
        if not response.ok:
            raise OutlookGraphError(
                f"Microsoft Graph read failed: HTTP {response.status_code}",
                status_code=response.status_code,
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise OutlookGraphError("Microsoft Graph returned an unexpected response.")
        return payload

    def get_json(self, path: str) -> dict[str, Any]:
        return self._get_url(f"{GRAPH_ROOT}{path}")

    def post_no_content(self, path: str, payload: dict[str, Any]) -> None:
        url = f"{GRAPH_ROOT}{path}"

        def send():
            return requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {self._token()}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout_s,
            )

        response = send()
        if response.status_code == 401:
            self._access_token = None
            response = send()
        if not response.ok:
            raise OutlookGraphError(
                f"Microsoft Graph write failed: HTTP {response.status_code}",
                status_code=response.status_code,
            )

    def _token(self) -> str:
        if self._access_token:
            return self._access_token
        response = requests.post(
            f"https://login.microsoftonline.com/{self.config.tenant_id}/oauth2/v2.0/token",
            data={
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
            timeout=self.timeout_s,
        )
        if not response.ok:
            raise OutlookGraphError(
                f"Microsoft identity token request failed: HTTP {response.status_code}",
                status_code=response.status_code,
            )
        payload = response.json()
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token:
            raise OutlookGraphError("Microsoft identity token response did not contain an access token.")
        self._access_token = token
        return token


def _message_sender(message: dict[str, Any]) -> str | None:
    sender = message.get("from") or {}
    email = sender.get("emailAddress") if isinstance(sender, dict) else {}
    address = str(email.get("address") or "").strip() if isinstance(email, dict) else ""
    return address or None
