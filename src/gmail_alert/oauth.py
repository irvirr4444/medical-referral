"""Gmail REST send using OAuth refresh tokens (GMAIL_CLIENT_ID / SECRET / REFRESH_TOKEN)."""

from __future__ import annotations

import base64
import logging
from collections.abc import Callable
from email.message import EmailMessage
from typing import Any

import requests

from gmail_alert.recipients import GmailAlertConfigError

logger = logging.getLogger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
PROFILE_URL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"

HttpPost = Callable[..., Any]


def has_oauth_credentials(environ: dict[str, str]) -> bool:
    return bool(
        (environ.get("GMAIL_CLIENT_ID") or "").strip()
        and (environ.get("GMAIL_CLIENT_SECRET") or "").strip()
        and (environ.get("GMAIL_REFRESH_TOKEN") or "").strip()
    )


def refresh_access_token(
    environ: dict[str, str],
    *,
    http_post: HttpPost | None = None,
) -> str:
    post = http_post or requests.post
    response = post(
        TOKEN_URL,
        data={
            "client_id": environ["GMAIL_CLIENT_ID"].strip(),
            "client_secret": environ["GMAIL_CLIENT_SECRET"].strip(),
            "refresh_token": environ["GMAIL_REFRESH_TOKEN"].strip(),
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    if response.status_code >= 400:
        detail = (response.text or "")[:300]
        raise GmailAlertConfigError(
            f"Gmail OAuth refresh failed: HTTP {response.status_code} {detail}"
        )
    token = (response.json().get("access_token") or "").strip()
    if not token:
        raise GmailAlertConfigError("Gmail OAuth refresh returned no access_token")
    return token


def from_address(
    environ: dict[str, str],
    access_token: str,
    *,
    http_get: Callable[..., Any] | None = None,
) -> str:
    configured = (environ.get("GMAIL_ALERT_FROM") or environ.get("GMAIL_ALERT_USER") or "").strip()
    if configured:
        return configured
    get = http_get or requests.get
    response = get(
        PROFILE_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    if response.status_code < 400:
        email = (response.json().get("emailAddress") or "").strip()
        if email:
            return email
    userinfo = get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    if userinfo.status_code < 400:
        email = (userinfo.json().get("email") or "").strip()
        if email:
            return email
    # gmail.send tokens often cannot read profile; Gmail still sends as the auth user.
    return "me"


def send_via_gmail_api(
    message: EmailMessage,
    *,
    access_token: str,
    http_post: HttpPost | None = None,
) -> None:
    post = http_post or requests.post
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii").rstrip("=")
    response = post(
        SEND_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={"raw": raw},
        timeout=30,
    )
    if response.status_code >= 400:
        detail = (response.text or "")[:300]
        raise GmailAlertConfigError(
            f"Gmail send failed: HTTP {response.status_code} {detail}"
        )
    logger.info("Sent Gmail SLA alert via API")
