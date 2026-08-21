from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from gmail_alert.models import AlertContext
from gmail_alert.recipients import GmailAlertConfigError
from gmail_alert.render import open_step_url
from gmail_alert.catalog import ALERT_TEMPLATES
from gmail_alert.smtp import GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, send_alert


CREDENTIALS = {
    "GMAIL_ALERT_USER": "alerts@example.com",
    "GMAIL_ALERT_APP_PASSWORD": "app-password-not-real",
}


def _context() -> AlertContext:
    template = ALERT_TEMPLATES["eod-follow-up-cm"]
    return AlertContext(
        patient_id="pat-1",
        patient_name="Thomas Reed",
        hours_overdue=24,
        open_url=open_step_url(template, "pat-1"),
        case_emails={"assigned_cm": ("cm@example.com",)},
    )


def test_send_alert_uses_starttls_login_and_send_message_once() -> None:
    client = MagicMock()
    smtp_factory = MagicMock(return_value=client)
    client.__enter__.return_value = client

    rendered = send_alert(
        "eod-follow-up-cm",
        _context(),
        environ=CREDENTIALS,
        smtp_factory=smtp_factory,
    )

    smtp_factory.assert_called_once_with(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT)
    client.starttls.assert_called_once()
    client.login.assert_called_once_with("alerts@example.com", "app-password-not-real")
    client.send_message.assert_called_once()
    message = client.send_message.call_args.args[0]
    assert message["To"] == "cm@example.com"
    assert message["Cc"] is None
    assert message["Subject"] == rendered.subject
    assert message["From"] == "alerts@example.com"


def test_send_alert_requires_credentials() -> None:
    with pytest.raises(GmailAlertConfigError, match="GMAIL_ALERT_USER"):
        send_alert(
            "eod-follow-up-cm",
            _context(),
            to=("cm@example.com",),
            environ={},
        )
