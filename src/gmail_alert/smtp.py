"""Gmail SMTP send for SLA alerts.

Dedup is the caller's job until a worker is wired: one send per
``{patient_id}:{action_id}`` until the miss promotes to a later timer.
"""

from __future__ import annotations

import logging
import os
import smtplib
from collections.abc import Sequence
from email.message import EmailMessage

from gmail_alert.catalog import template_for
from gmail_alert.ids import ConfirmationActionId
from gmail_alert.models import AlertContext, RenderedAlert
from gmail_alert.oauth import (
    from_address,
    has_oauth_credentials,
    refresh_access_token,
    send_via_gmail_api,
)
from gmail_alert.recipients import GmailAlertConfigError, resolve_recipients
from gmail_alert.render import render_alert

logger = logging.getLogger(__name__)

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587


def _smtp_credentials(*, environ: dict[str, str] | None = None) -> tuple[str, str, str]:
    env = os.environ if environ is None else environ
    user = (env.get("GMAIL_ALERT_USER") or "").strip()
    password = (env.get("GMAIL_ALERT_APP_PASSWORD") or "").strip()
    if not user or not password:
        raise GmailAlertConfigError("GMAIL_ALERT_USER and GMAIL_ALERT_APP_PASSWORD are required")
    from_addr = (env.get("GMAIL_ALERT_FROM") or user).strip()
    return user, password, from_addr


def build_message(
    rendered: RenderedAlert,
    *,
    from_addr: str,
    to: Sequence[str],
    cc: Sequence[str] = (),
) -> EmailMessage:
    message = EmailMessage()
    if from_addr and from_addr != "me":
        message["From"] = from_addr
    message["To"] = ", ".join(to)
    if cc:
        message["Cc"] = ", ".join(cc)
    message["Subject"] = rendered.subject
    message.set_content(rendered.body_text)
    message.add_alternative(rendered.body_html, subtype="html")
    return message


def send_rendered_alert(
    rendered: RenderedAlert,
    *,
    to: Sequence[str],
    cc: Sequence[str] = (),
    environ: dict[str, str] | None = None,
    smtp_factory=smtplib.SMTP,
) -> None:
    if not to:
        raise GmailAlertConfigError("Gmail alert requires at least one To recipient")
    env = os.environ if environ is None else environ
    logger.info(
        "Sending Gmail SLA alert action_id=%s patient_id=%s to_count=%s",
        rendered.action_id,
        rendered.patient_id,
        len(to),
    )
    if has_oauth_credentials(dict(env)):
        token = refresh_access_token(dict(env))
        from_addr = from_address(dict(env), token)
        message = build_message(rendered, from_addr=from_addr, to=to, cc=cc)
        send_via_gmail_api(message, access_token=token)
        return
    user, password, from_addr = _smtp_credentials(environ=env)
    message = build_message(rendered, from_addr=from_addr, to=to, cc=cc)
    with smtp_factory(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT) as client:
        client.starttls()
        client.login(user, password)
        client.send_message(message)


def send_alert(
    action_id: ConfirmationActionId,
    context: AlertContext,
    *,
    to: Sequence[str] | None = None,
    cc: Sequence[str] | None = None,
    environ: dict[str, str] | None = None,
    smtp_factory=smtplib.SMTP,
) -> RenderedAlert:
    """Render and send. Caller owns once-per-timer dedup: ``{patient_id}:{action_id}``."""

    rendered = render_alert(action_id, context)
    template = template_for(action_id)
    if to is None:
        resolved_to, resolved_cc = resolve_recipients(
            template.to_roles,
            template.cc_roles,
            case_emails=context.case_emails,
            environ=environ,
        )
        to = resolved_to
        if cc is None:
            cc = resolved_cc
    send_rendered_alert(
        rendered,
        to=to,
        cc=cc or (),
        environ=environ,
        smtp_factory=smtp_factory,
    )
    return rendered
