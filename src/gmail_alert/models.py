from __future__ import annotations

from dataclasses import dataclass, field

from gmail_alert.ids import AlertKind, ConfirmationActionId, RecipientRole

FeedField = tuple[str, str]


@dataclass(frozen=True)
class AlertTemplate:
    action_id: ConfirmationActionId
    stage_id: str
    step_id: str
    sla_label: str
    stage_label: str
    label: str
    reason: str
    kind: AlertKind
    to_roles: tuple[RecipientRole, ...]
    cc_roles: tuple[RecipientRole, ...] = ()
    subject_prefix: str = "Immediate attention"


@dataclass(frozen=True)
class AlertContext:
    patient_id: str
    patient_name: str
    hours_overdue: float
    open_url: str
    feed_fields: tuple[FeedField, ...] = ()
    late_label: str | None = None
    urgency: str = "Overdue"
    """Case-specific addresses keyed by semantic role (CM, provider, …)."""
    case_emails: dict[RecipientRole, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class RenderedAlert:
    action_id: ConfirmationActionId
    patient_id: str
    subject: str
    body_text: str
    body_html: str
    to_roles: tuple[RecipientRole, ...]
    cc_roles: tuple[RecipientRole, ...] = field(default_factory=tuple)
