"""Send SLA templates using the frontend DEMO_TIMER_SEEDS patient for each action."""

from __future__ import annotations

from gmail_alert.catalog import ALERT_TEMPLATES
from gmail_alert.case_emails import case_emails_for
from gmail_alert.demo_patients import DemoPatient, demo_for_action
from gmail_alert.feed_bodies import feed_body_for
from gmail_alert.ids import ACTION_IDS, ConfirmationActionId
from gmail_alert.models import AlertContext
from gmail_alert.render import open_step_url
from gmail_alert.smtp import send_alert


def context_for(patient: DemoPatient, action_id: ConfirmationActionId) -> AlertContext:
    template = ALERT_TEMPLATES[action_id]
    return AlertContext(
        patient_id=patient.patient_id,
        patient_name=patient.patient_name,
        hours_overdue=patient.hours_overdue,
        open_url=open_step_url(template, patient.patient_id),
        feed_fields=feed_body_for(action_id),
        late_label=patient.late_label,
        case_emails=case_emails_for(action_id),
    )


def send_one_template(
    action_id: ConfirmationActionId,
    *,
    to: tuple[str, ...] | None = None,
) -> ConfirmationActionId:
    patient = demo_for_action(action_id)
    send_alert(action_id, context_for(patient, action_id), to=to, cc=() if to else None)
    return action_id


def send_all_templates(*, to: tuple[str, ...] | None = None) -> list[ConfirmationActionId]:
    sent: list[ConfirmationActionId] = []
    for action_id in ACTION_IDS:
        send_one_template(action_id, to=to)
        sent.append(action_id)
    return sent
