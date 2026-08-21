from __future__ import annotations

import html
import os
from urllib.parse import urlencode

from gmail_alert.catalog import template_for
from gmail_alert.ids import ConfirmationActionId
from gmail_alert.models import AlertContext, AlertTemplate, FeedField, RenderedAlert

DEFAULT_APP_BASE_URL = "http://localhost:5173"

# Quiet letter layout: patient → reason → fields → optional CTA. No badges.
_CARD_STYLE = (
    "font-family:Georgia,'Times New Roman',serif;max-width:560px;"
    "padding:28px 8px;color:#111111;"
)
_PATIENT_STYLE = (
    "margin:0 0 12px 0;font-family:Arial,Helvetica,sans-serif;"
    "font-size:22px;font-weight:700;letter-spacing:-0.02em;line-height:1.25;color:#111111;"
)
_REASON_STYLE = (
    "margin:0 0 24px 0;font-family:Arial,Helvetica,sans-serif;"
    "font-size:16px;font-weight:400;line-height:1.5;color:#333333;"
)
_RULE_STYLE = "border:none;border-top:1px solid #e5e5e5;margin:0 0 20px 0;"
_FIELD_ROW_STYLE = (
    "margin:0 0 10px 0;font-family:Arial,Helvetica,sans-serif;"
    "font-size:13px;line-height:1.45;color:#333333;"
)
_FIELD_LABEL_STYLE = "color:#888888;font-weight:400;"
_BUTTON_STYLE = (
    "display:inline-block;margin-top:8px;padding:14px 22px;"
    "background:#111111;color:#ffffff;font-family:Arial,Helvetica,sans-serif;"
    "font-size:14px;font-weight:600;text-decoration:none;border-radius:6px;"
)


def person_name(name: str) -> str:
    """Turn 'BUTLER, ALVA' / 'Gonzalez, Eric' into a normal greeting name."""
    raw = " ".join(name.split())
    if "," in raw:
        last, first = (part.strip() for part in raw.split(",", 1))
        first = first.title() if first.isupper() else first
        last = last.title() if last.isupper() else last
        return f"{first} {last}".strip()
    return raw


def format_late(hours: float) -> str:
    minutes = hours * 60
    if minutes < 120:
        return f"{max(1, int(round(minutes)))} min"
    if abs(hours - round(hours)) < 0.05:
        return f"{int(round(hours))} hr"
    return f"{hours:.1f} hr"


def format_hours_overdue(hours: float) -> str:
    """Back-compat alias used by tests."""
    return format_late(hours)


def open_step_url(
    template: AlertTemplate,
    patient_id: str,
    *,
    base_url: str | None = None,
) -> str:
    root = (base_url or os.environ.get("GMAIL_ALERT_APP_BASE_URL") or DEFAULT_APP_BASE_URL).rstrip(
        "/"
    )
    query = urlencode(
        {
            "patient": patient_id,
            "stage": template.stage_id,
            "step": template.step_id,
        }
    )
    return f"{root}/automation?{query}"


def _build_body_text(
    *,
    label: str,
    name: str,
    reason: str,
    fields: tuple[FeedField, ...],
    show_cta: bool,
) -> str:
    lines = [name, reason, ""]
    for field_label, value in fields:
        if value:
            lines.append(f"{field_label}: {value}")
    if show_cta:
        lines.extend(["", f"[ {label} ]"])
    return "\n".join(lines) + "\n"


def _build_body_html(
    *,
    label: str,
    name: str,
    reason: str,
    fields: tuple[FeedField, ...],
    show_cta: bool,
) -> str:
    field_rows = []
    for field_label, value in fields:
        if not value:
            continue
        field_rows.append(
            f'<p style="{_FIELD_ROW_STYLE}">'
            f'<span style="{_FIELD_LABEL_STYLE}">{html.escape(field_label)}</span><br>'
            f"{html.escape(value)}</p>"
        )
    fields_html = ""
    if field_rows:
        fields_html = f'<hr style="{_RULE_STYLE}">\n' + "\n".join(field_rows) + "\n"
    cta_html = (
        f'<p style="margin:28px 0 0 0;">'
        f'<a href="#" style="{_BUTTON_STYLE}">{html.escape(label)}</a></p>\n'
        if show_cta
        else ""
    )
    return (
        f'<div style="{_CARD_STYLE}">\n'
        f'<p style="{_PATIENT_STYLE}">{html.escape(name)}</p>\n'
        f'<p style="{_REASON_STYLE}">{html.escape(reason)}</p>\n'
        f"{fields_html}"
        f"{cta_html}"
        f"</div>\n"
    )


def render_alert(action_id: ConfirmationActionId, context: AlertContext) -> RenderedAlert:
    template = template_for(action_id)
    name = person_name(context.patient_name)
    subject = f"{template.subject_prefix} · {name}"
    show_cta = template.kind == "decide"
    fields = context.feed_fields
    body_text = _build_body_text(
        label=template.label,
        name=name,
        reason=template.reason,
        fields=fields,
        show_cta=show_cta,
    )
    body_html = _build_body_html(
        label=template.label,
        name=name,
        reason=template.reason,
        fields=fields,
        show_cta=show_cta,
    )
    return RenderedAlert(
        action_id=action_id,
        patient_id=context.patient_id,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        to_roles=template.to_roles,
        cc_roles=template.cc_roles,
    )
