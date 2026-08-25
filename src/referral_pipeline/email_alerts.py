"""Bridge workflow state to Irvi's Gmail catalog and durable delivery."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any, cast

from gmail_alert.catalog import template_for
from gmail_alert.ids import ConfirmationActionId, RecipientRole
from gmail_alert.models import AlertContext, RenderedAlert
from gmail_alert.recipients import resolve_recipients
from gmail_alert.render import open_step_url, render_alert
from gmail_alert.smtp import send_rendered_alert
from referral_pipeline.monitoring.models import EmailAlertRecord, OperationalSnapshot
from referral_pipeline.monitoring.store import WorkflowStore


ROLE_EMAILS_ENV = "GMAIL_ALERT_ROLE_EMAILS"

SendAlert = Callable[[EmailAlertRecord, tuple[str, ...], tuple[str, ...]], None]

_OVERDUE_ACTION_BY_STEP: dict[str, ConfirmationActionId] = {
    "extract-and-verify": "confirm-intake-review",
    "confirm-referral-contacted": "confirm-partner-contacted",
}


def queue_email_alert(
    *,
    store: WorkflowStore,
    action_id: ConfirmationActionId,
    patient_id: str,
    patient_name: str,
    now: datetime,
    hours_overdue: float = 0,
    feed_fields: tuple[tuple[str, str], ...] = (),
    case_emails: Mapping[RecipientRole, tuple[str, ...]] | None = None,
) -> bool:
    """Render and enqueue one action per referral; the primary key is the dedup gate."""

    template = template_for(action_id)
    normalized_case_emails = {
        role: _addresses(addresses) for role, addresses in (case_emails or {}).items()
    }
    context = AlertContext(
        patient_id=patient_id,
        patient_name=patient_name,
        hours_overdue=max(0, hours_overdue),
        open_url=open_step_url(template, patient_id),
        feed_fields=feed_fields,
        case_emails=normalized_case_emails,
    )
    rendered = render_alert(action_id, context)
    return store.enqueue_email_alert(
        EmailAlertRecord(
            alert_key=email_alert_key(patient_id, action_id),
            action_id=action_id,
            patient_id=patient_id,
            subject=rendered.subject,
            body_text=rendered.body_text,
            body_html=rendered.body_html,
            to_roles=rendered.to_roles,
            cc_roles=rendered.cc_roles,
            case_emails=normalized_case_emails,
            created_at=now,
        )
    )


def email_alert_key(patient_id: str, action_id: ConfirmationActionId) -> str:
    return hashlib.sha256(f"{patient_id}\0{action_id}".encode("utf-8")).hexdigest()


def queue_assignment_email_alert(
    *,
    store: WorkflowStore,
    case_id: str,
    patient_name: str,
    manager: Mapping[str, Any],
    now: datetime,
) -> bool:
    email = _email(manager.get("email"))
    fields = [("Case manager", str(manager.get("name") or email or "Assigned"))]
    if email:
        fields[0] = ("Case manager", f"{fields[0][1]} ({email})")
    fields.append(("Next step", "Select provider"))
    queued = queue_email_alert(
        store=store,
        action_id="cm-assigned",
        patient_id=case_id,
        patient_name=patient_name,
        now=now,
        feed_fields=tuple(fields),
        case_emails={"assigned_cm": (email,)} if email else {},
    )
    return queued


def queue_workflow_email_alerts(
    *,
    store: WorkflowStore,
    now: datetime,
    limit: int = 500,
) -> dict[str, int]:
    """Queue observable Stage 1/assignment emails from durable workflow state."""

    from referral_pipeline.workflow.attention import workflow_attention

    queued = eligible = 0
    attention = workflow_attention(store, now=now, limit=limit)
    for signal in attention["items"]:
        if signal.get("severity") != "overdue":
            continue
        action_id = _OVERDUE_ACTION_BY_STEP.get(str(signal.get("step_id") or ""))
        if action_id is None:
            continue
        case_id = str(signal.get("case_id") or "").strip()
        case = store.workflow_case(case_id)
        if case is None:
            continue
        eligible += 1
        queued += int(
            queue_email_alert(
                store=store,
                action_id=action_id,
                patient_id=case.case_id,
                patient_name=case.patient_label or "Patient",
                now=now,
                hours_overdue=float(signal.get("overdue_seconds") or 0) / 3600,
                feed_fields=_workflow_feed_fields(store, case.case_id, signal),
                case_emails=case_role_emails(store, case.case_id),
            )
        )
    for case in store.list_workflow_cases(limit=limit):
        assigned = next(
            (
                event
                for event in reversed(store.list_events(case.case_id, limit=100))
                if event.event_type == "case_manager_assigned"
            ),
            None,
        )
        if assigned is None:
            continue
        manager = assigned.details.get("case_manager")
        if not isinstance(manager, dict):
            continue
        eligible += 1
        queued += int(
            queue_assignment_email_alert(
                store=store,
                case_id=case.case_id,
                patient_name=case.patient_label or case.case_id,
                manager=manager,
                now=now,
            )
        )
    return {"eligible": eligible, "queued": queued}


def queue_snapshot_email_alert(
    *,
    store: WorkflowStore,
    action_id: ConfirmationActionId,
    snapshot: OperationalSnapshot,
    now: datetime,
    hours_overdue: float = 0,
) -> bool:
    return queue_email_alert(
        store=store,
        action_id=action_id,
        patient_id=snapshot.entity_id,
        patient_name=snapshot.patient_label or snapshot.entity_id,
        now=now,
        hours_overdue=hours_overdue,
        feed_fields=_snapshot_feed_fields(action_id, snapshot),
        case_emails=case_role_emails(store, snapshot.entity_id, snapshot=snapshot),
    )


def case_role_emails(
    store: WorkflowStore,
    case_id: str,
    *,
    snapshot: OperationalSnapshot | None = None,
) -> dict[RecipientRole, tuple[str, ...]]:
    """Read case-varying CM/provider addresses; organization roles resolve at send time."""

    result: dict[RecipientRole, tuple[str, ...]] = {}
    for decision in reversed(store.list_decisions(case_id)):
        if decision.decision_type != "case_manager_selected":
            continue
        email = _email(decision.selected_value.get("email"))
        if email:
            result["assigned_cm"] = (email,)
        break
    if snapshot is not None:
        if "assigned_cm" not in result:
            email = _email(snapshot.details.get("case_manager_email")) or _email(
                snapshot.case_manager
            )
            if not email and snapshot.case_manager:
                email = _case_manager_email(snapshot.case_manager)
            if email:
                result["assigned_cm"] = (email,)
        provider_email = _email(snapshot.details.get("provider_email")) or _email(
            snapshot.provider
        )
        if provider_email:
            result["provider"] = (provider_email,)
    return result


def dispatch_pending_email_alerts(
    *,
    store: WorkflowStore,
    send_alert: SendAlert | None = None,
    environ: Mapping[str, str] | None = None,
    limit: int = 100,
) -> dict[str, object]:
    """Resolve recipients at delivery time and retry each rendered alert independently."""

    env = dict(os.environ if environ is None else environ)
    sender = send_alert or _gmail_sender(env)
    pending = store.pending_email_alerts(limit=limit)
    sent: list[str] = []
    failed: list[dict[str, str]] = []
    try:
        configured = configured_role_emails(env)
    except ValueError as error:
        for alert in pending:
            store.mark_email_alerts_failed([alert.alert_key], str(error))
            failed.append({"alert_key": alert.alert_key, "error": str(error)})
        return {"pending": len(pending), "sent": 0, "failed": failed}
    for alert in pending:
        case_emails = _merge_role_emails(configured, alert.case_emails)
        try:
            to, cc = resolve_recipients(
                cast(tuple[RecipientRole, ...], alert.to_roles),
                cast(tuple[RecipientRole, ...], alert.cc_roles),
                case_emails=cast(dict[RecipientRole, tuple[str, ...]], case_emails),
                environ=env,
            )
            sender(alert, to, cc)
        except Exception as error:  # noqa: BLE001 - failed delivery stays retryable
            store.mark_email_alerts_failed([alert.alert_key], str(error))
            failed.append({"alert_key": alert.alert_key, "error": str(error)})
        else:
            store.mark_email_alerts_sent([alert.alert_key])
            sent.append(alert.alert_key)
    return {"pending": len(pending), "sent": len(sent), "failed": failed}


def configured_role_emails(
    environ: Mapping[str, str] | None = None,
) -> dict[str, tuple[str, ...]]:
    """Load organization-level routing from one JSON variable, with intake fallback."""

    env = os.environ if environ is None else environ
    raw = str(env.get(ROLE_EMAILS_ENV) or "").strip()
    parsed: Any = {}
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError(f"{ROLE_EMAILS_ENV} must be a JSON object") from error
        if not isinstance(parsed, dict):
            raise ValueError(f"{ROLE_EMAILS_ENV} must be a JSON object")
    result: dict[str, tuple[str, ...]] = {}
    for role, values in parsed.items():
        if role not in {"intake_lead", "assigned_cm", "provider", "scheduling_lead", "management"}:
            raise ValueError(f"unsupported Gmail alert recipient role: {role}")
        addresses = _addresses(values if isinstance(values, (list, tuple)) else (values,))
        if addresses:
            result[role] = addresses
    review_recipient = _email(env.get("REVIEW_RECIPIENT_EMAIL"))
    if review_recipient and "intake_lead" not in result:
        result["intake_lead"] = (review_recipient,)
    return result


def _gmail_sender(environ: dict[str, str]) -> SendAlert:
    def send(
        alert: EmailAlertRecord,
        to: tuple[str, ...],
        cc: tuple[str, ...],
    ) -> None:
        send_rendered_alert(
            RenderedAlert(
                action_id=cast(ConfirmationActionId, alert.action_id),
                patient_id=alert.patient_id,
                subject=alert.subject,
                body_text=alert.body_text,
                body_html=alert.body_html,
                to_roles=cast(tuple[RecipientRole, ...], alert.to_roles),
                cc_roles=cast(tuple[RecipientRole, ...], alert.cc_roles),
            ),
            to=to,
            cc=cc,
            environ=environ,
        )

    return send


def _workflow_feed_fields(
    store: WorkflowStore,
    case_id: str,
    signal: Mapping[str, Any],
) -> tuple[tuple[str, str], ...]:
    fields: list[tuple[str, str]] = [
        ("Workflow status", str(signal.get("status") or "Needs attention")),
        ("Due", str(signal.get("due_at") or "Not recorded")),
    ]
    for event in reversed(store.list_events(case_id, limit=100)):
        if event.event_type != "extraction_completed":
            continue
        extracted = event.details.get("fields")
        if isinstance(extracted, dict):
            for key in ("date_of_birth", "phone", "address", "home_health", "wound", "insurance"):
                value = extracted.get(key)
                if value:
                    fields.append((key.replace("_", " ").title(), _display(value)))
        break
    return tuple(fields)


def _snapshot_feed_fields(
    action_id: ConfirmationActionId,
    snapshot: OperationalSnapshot,
) -> tuple[tuple[str, str], ...]:
    values = {
        "Provider": snapshot.provider,
        "Case manager": snapshot.case_manager,
        "Due date": snapshot.due_date,
        "Appointment": snapshot.appointment_date,
        "Scheduled status": snapshot.scheduled_status,
        "Scheduling complete": snapshot.scheduling_complete,
        "Visit status": snapshot.visit_status or snapshot.visit_outcome,
    }
    if action_id.startswith("not-seen-week-"):
        values["Consecutive not seen"] = action_id.removeprefix("not-seen-week-") + " week(s)"
    return tuple((label, str(value)) for label, value in values.items() if value)


def _merge_role_emails(
    configured: Mapping[str, tuple[str, ...]],
    case_specific: Mapping[str, tuple[str, ...]],
) -> dict[str, tuple[str, ...]]:
    merged = dict(configured)
    for role, addresses in case_specific.items():
        if addresses:
            merged[role] = _addresses(addresses)
    return merged


def _addresses(values: Any) -> tuple[str, ...]:
    if isinstance(values, str):
        values = (values,)
    result: list[str] = []
    seen: set[str] = set()
    for value in values or ():
        address = _email(value)
        if address and address not in seen:
            seen.add(address)
            result.append(address)
    return tuple(result)


def _email(value: Any) -> str:
    text = str(value or "").strip().casefold()
    return text if "@" in text and " " not in text else ""


def _case_manager_email(name: str) -> str:
    from referral_pipeline.workflow.roster import load_case_manager_roster

    wanted = " ".join(name.casefold().split())
    for manager in load_case_manager_roster():
        if " ".join(manager["name"].casefold().split()) == wanted:
            return manager["email"]
    return ""


def _display(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)
