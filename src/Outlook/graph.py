"""Small Microsoft Graph client used by the Outlook-specific adapters."""

from __future__ import annotations

import base64
import binascii
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

from Outlook.mail import InboundPdfAttachment, is_pdf_file


GRAPH_ROOT = "https://graph.microsoft.com/v1.0"


class OutlookGraphError(RuntimeError):
    pass


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

    def list_inbox_pdf_attachments(self, *, max_messages: int = 25) -> list[InboundPdfAttachment]:
        attachments: list[InboundPdfAttachment] = []
        for message in self._list_messages(max_messages=max_messages):
            if not message.get("hasAttachments"):
                continue
            attachments.extend(self._pdf_attachments_for_message(message))
        return attachments

    def _list_messages(self, *, max_messages: int) -> list[dict[str, Any]]:
        query = urlencode(
            {
                "$select": "id,subject,receivedDateTime,hasAttachments",
                "$orderby": "receivedDateTime desc",
                "$top": str(max_messages),
            }
        )
        payload = self._get(f"/users/{self.config.mailbox}/mailFolders/inbox/messages?{query}")
        values = payload.get("value")
        if not isinstance(values, list):
            raise OutlookGraphError("Microsoft Graph did not return an inbox message list.")
        return [item for item in values if isinstance(item, dict)]

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
                )
            )
        return accepted

    def _get(self, path: str) -> dict[str, Any]:
        return self.get_json(path)

    def get_json(self, path: str) -> dict[str, Any]:
        response = requests.get(
            f"{GRAPH_ROOT}{path}",
            headers={"Authorization": f"Bearer {self._token()}"},
            timeout=self.timeout_s,
        )
        if not response.ok:
            raise OutlookGraphError(f"Microsoft Graph read failed: HTTP {response.status_code}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise OutlookGraphError("Microsoft Graph returned an unexpected response.")
        return payload

    def post_no_content(self, path: str, payload: dict[str, Any]) -> None:
        response = requests.post(
            f"{GRAPH_ROOT}{path}",
            headers={
                "Authorization": f"Bearer {self._token()}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout_s,
        )
        if not response.ok:
            raise OutlookGraphError(f"Microsoft Graph write failed: HTTP {response.status_code}")

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
            raise OutlookGraphError(f"Microsoft identity token request failed: HTTP {response.status_code}")
        payload = response.json()
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token:
            raise OutlookGraphError("Microsoft identity token response did not contain an access token.")
        self._access_token = token
        return token
