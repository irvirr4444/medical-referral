from __future__ import annotations

from unittest.mock import MagicMock

from gmail_alert.oauth import refresh_access_token, send_via_gmail_api
from gmail_alert.smtp import send_alert
from gmail_alert.catalog import ALERT_TEMPLATES
from gmail_alert.models import AlertContext
from gmail_alert.render import open_step_url


OAUTH = {
    "GMAIL_CLIENT_ID": "client",
    "GMAIL_CLIENT_SECRET": "secret",
    "GMAIL_REFRESH_TOKEN": "refresh",
    "GMAIL_ALERT_FROM": "alerts@example.com",
}


def test_refresh_access_token() -> None:
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"access_token": "ya29.example"}
    http_post = MagicMock(return_value=response)
    assert refresh_access_token(OAUTH, http_post=http_post) == "ya29.example"


def test_send_alert_prefers_oauth_over_smtp() -> None:
    token_response = MagicMock()
    token_response.status_code = 200
    token_response.json.return_value = {"access_token": "ya29.example"}
    send_response = MagicMock()
    send_response.status_code = 200
    http_post = MagicMock(side_effect=[token_response, send_response])

    template = ALERT_TEMPLATES["confirm-intake-review"]
    context = AlertContext(
        patient_id="pat-1",
        patient_name="Eric Gonzalez",
        hours_overdue=2,
        open_url=open_step_url(template, "pat-1"),
    )
    smtp_factory = MagicMock()

    from gmail_alert import oauth as oauth_mod

    original_post = oauth_mod.requests.post
    original_refresh = oauth_mod.refresh_access_token
    original_send = oauth_mod.send_via_gmail_api
    try:
        oauth_mod.requests.post = http_post
        rendered = send_alert(
            "confirm-intake-review",
            context,
            to=("irrika22@epoka.edu.al",),
            environ=OAUTH,
            smtp_factory=smtp_factory,
        )
    finally:
        oauth_mod.requests.post = original_post
        oauth_mod.refresh_access_token = original_refresh
        oauth_mod.send_via_gmail_api = original_send

    smtp_factory.assert_not_called()
    assert rendered.subject == "Immediate attention · Eric Gonzalez"
    assert http_post.call_count == 2
