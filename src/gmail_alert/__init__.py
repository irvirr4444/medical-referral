"""Gmail SLA alerts for overdue confirmation timers. Separate from Outlook review mail."""

from gmail_alert.catalog import ALERT_TEMPLATES, template_for
from gmail_alert.feed_bodies import feed_body_for
from gmail_alert.ids import ACTION_IDS, ConfirmationActionId, RecipientRole
from gmail_alert.models import AlertContext, AlertTemplate, RenderedAlert
from gmail_alert.recipients import GmailAlertConfigError, resolve_recipients
from gmail_alert.render import open_step_url, render_alert
from gmail_alert.smtp import send_alert

__all__ = [
    "ACTION_IDS",
    "ALERT_TEMPLATES",
    "AlertContext",
    "AlertTemplate",
    "ConfirmationActionId",
    "GmailAlertConfigError",
    "RecipientRole",
    "RenderedAlert",
    "feed_body_for",
    "open_step_url",
    "render_alert",
    "resolve_recipients",
    "send_alert",
    "template_for",
]
