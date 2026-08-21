"""One AlertTemplate per email humans should receive."""

from __future__ import annotations

from gmail_alert.ids import ACTION_IDS, ConfirmationActionId
from gmail_alert.models import AlertTemplate

ALERT_TEMPLATES: dict[ConfirmationActionId, AlertTemplate] = {
    "confirm-intake-review": AlertTemplate(
        action_id="confirm-intake-review",
        stage_id="intake",
        step_id="extract-and-verify",
        sla_label="15 min",
        stage_label="Intake",
        label="Confirm all information is correct",
        reason="The chart isn’t confirmed so nothing can move.",
        kind="decide",
        to_roles=("intake_lead",),
    ),
    "confirm-partner-contacted": AlertTemplate(
        action_id="confirm-partner-contacted",
        stage_id="intake",
        step_id="confirm-referral-contacted",
        sla_label="1 hour",
        stage_label="Intake",
        label="Confirm partner is contacted",
        reason="The referral partner still hasn’t been reached.",
        kind="decide",
        to_roles=("intake_lead",),
    ),
    "cm-assigned": AlertTemplate(
        action_id="cm-assigned",
        stage_id="assignment",
        step_id="assign-owner",
        sla_label="on assign",
        stage_label="Assignment",
        label="You own this patient",
        reason="This patient is yours. Pick a provider.",
        kind="notify",
        to_roles=("assigned_cm",),
        subject_prefix="New assignment",
    ),
    "use-fallback-provider": AlertTemplate(
        action_id="use-fallback-provider",
        stage_id="provider",
        step_id="select-provider",
        sla_label="30 min",
        stage_label="Provider",
        label="No provider confirmed",
        reason="Providers are available but none are confirmed yet.",
        kind="decide",
        to_roles=("assigned_cm",),
    ),
    "no-area-provider": AlertTemplate(
        action_id="no-area-provider",
        stage_id="provider",
        step_id="select-provider",
        sla_label="immediate",
        stage_label="Provider",
        label="No company provider in area",
        reason="No provider in this area. This needs your call.",
        kind="notify",
        to_roles=("management",),
        cc_roles=("assigned_cm",),
    ),
    "send-referral-provider": AlertTemplate(
        action_id="send-referral-provider",
        stage_id="scheduling",
        step_id="send-referral-provider",
        sla_label="on send",
        stage_label="Scheduling",
        label="New patient referral",
        reason="A new referral packet is ready. Confirm and schedule.",
        kind="notify",
        to_roles=("provider",),
        cc_roles=("assigned_cm",),
        subject_prefix="New referral",
    ),
    "eod-follow-up-cm": AlertTemplate(
        action_id="eod-follow-up-cm",
        stage_id="end-of-day",
        step_id="check-scheduling-status",
        sla_label="24 hours",
        stage_label="End of day",
        label="Patient still unscheduled",
        reason="The provider is set but the patient still isn’t scheduled.",
        kind="notify",
        to_roles=("assigned_cm",),
    ),
    "eod-escalate": AlertTemplate(
        action_id="eod-escalate",
        stage_id="end-of-day",
        step_id="check-scheduling-status",
        sla_label="48 hours",
        stage_label="End of day",
        label="Still unscheduled needs escalation",
        reason="Still unscheduled after follow up. This needs escalation.",
        kind="notify",
        to_roles=("management",),
        cc_roles=("scheduling_lead",),
    ),
    "not-seen-week-1": AlertTemplate(
        action_id="not-seen-week-1",
        stage_id="weekly",
        step_id="patient-seen",
        sla_label="weekly",
        stage_label="Weekly",
        label="Patient not seen 1 week",
        reason="Not seen this week. Reschedule is owed.",
        kind="notify",
        to_roles=("assigned_cm",),
    ),
    "not-seen-week-2": AlertTemplate(
        action_id="not-seen-week-2",
        stage_id="weekly",
        step_id="patient-seen",
        sla_label="weekly",
        stage_label="Weekly",
        label="Patient not seen 2 weeks in a row",
        reason="Not seen two weeks running. Reschedule now.",
        kind="notify",
        to_roles=("assigned_cm",),
    ),
    "not-seen-week-3": AlertTemplate(
        action_id="not-seen-week-3",
        stage_id="weekly",
        step_id="patient-seen",
        sla_label="weekly",
        stage_label="Weekly",
        label="Patient not seen 3 weeks discharge risk",
        reason="Not seen three weeks. This needs a discharge decision.",
        kind="notify",
        to_roles=("management",),
        cc_roles=("assigned_cm",),
    ),
}


def template_for(action_id: ConfirmationActionId) -> AlertTemplate:
    return ALERT_TEMPLATES[action_id]


def _assert_catalog_complete() -> None:
    missing = set(ACTION_IDS) - set(ALERT_TEMPLATES)
    extra = set(ALERT_TEMPLATES) - set(ACTION_IDS)
    if missing or extra:
        raise RuntimeError(f"gmail_alert catalog mismatch: missing={missing!r} extra={extra!r}")
    for template in ALERT_TEMPLATES.values():
        if "—" in template.reason or " – " in template.reason or " - " in template.reason:
            raise RuntimeError(f"reason looks AI-dashed: {template.action_id!r}")
        if "—" in template.label or " – " in template.label:
            raise RuntimeError(f"label looks AI-dashed: {template.action_id!r}")
        # "case" as work-item jargon is internal; allow "case manager" (job title).
        reason_lower = template.reason.lower()
        if "case manager" not in reason_lower and "case" in reason_lower:
            raise RuntimeError(f"reason uses internal 'case' jargon: {template.action_id!r}")


_assert_catalog_complete()
