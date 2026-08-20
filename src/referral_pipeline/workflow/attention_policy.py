"""Demo-default SLA durations for workflow attention.

These values are not confirmed WCW business rules. They match the existing
frontend demo timers so local development has a clock. Override any duration
with WCW_SLA_<STEP>_SECONDS. The due-soon window is WCW_ATTENTION_WARNING_SECONDS.
"""

from __future__ import annotations

import os
from typing import Mapping


# Demo defaults in seconds. Documented as unconfirmed until WCW sets SLAs.
DEMO_SLA_SECONDS: dict[str, int] = {
    "extract-and-verify": 15 * 60,
    "confirm-referral-contacted": 60 * 60,
    "assign-case-manager": 30 * 60,
    "assign-owner": 30 * 60,
    "select-provider": 30 * 60,
    "confirm-provider-availability": 60 * 60,
    "schedule-patient": 48 * 60 * 60,
    "check-scheduling-status": 24 * 60 * 60,
    "patient-seen": 4 * 60 * 60,
    "wound-healed": 4 * 60 * 60,
    "patient-expired": 4 * 60 * 60,
    "patient-on-hold": 4 * 60 * 60,
}
DEFAULT_SLA_SECONDS = 30 * 60
DEFAULT_WARNING_SECONDS = 15 * 60

STAGE_ONE_STEP_BY_STATUS: dict[str, str] = {
    "discovered": "extract-and-verify",
    "processing": "extract-and-verify",
    "needs_attention": "extract-and-verify",
    "awaiting_partner_contact": "confirm-referral-contacted",
}

UI_STEP_BY_BACKEND_STEP: dict[str, str] = {
    "assign-case-manager": "assign-owner",
}

ACTION_LABELS: dict[str, str] = {
    "extract-and-verify": "Confirm all information is correct",
    "confirm-referral-contacted": "Confirm partner is contacted",
    "assign-case-manager": "Confirm case manager",
    "assign-owner": "Confirm case manager",
    "select-provider": "Confirm provider",
    "confirm-provider-availability": "Provider confirmed",
    "schedule-patient": "Schedule patient",
    "check-scheduling-status": "Follow up with case manager",
    "patient-seen": "Mark NOT seen · reschedule",
    "wound-healed": "Send to QA discharge",
    "patient-expired": "Remove from schedule · DC",
    "patient-on-hold": "Move to holds team",
}

TERMINAL_CASE_STATUSES = frozenset({"completed", "cancelled", "failed"})
TERMINAL_WORK_ITEM_STATUSES = frozenset({"completed", "cancelled"})
OPEN_EXCEPTION_STATUS = "open"

# Monitoring exceptions (scheduling.py / visits.py) carry their own stage --
# they are not produced by the Stage 1-3 case pipeline, so they must not be
# placed by case.current_stage (which only ever advances through 1-3 today).
EXCEPTION_STAGE_STEP: dict[str, tuple[int, str]] = {
    "scheduling_exception": (5, "check-scheduling-status"),
    "noncompliance_discharge_review": (6, "patient-seen"),
    "qa_review": (6, "wound-healed"),
    "discharge_approval_review": (6, "patient-expired"),
}


def exception_stage_step(exception_type: str) -> tuple[int, str] | None:
    return EXCEPTION_STAGE_STEP.get(exception_type)


def warning_window_seconds(environ: Mapping[str, str] | None = None) -> int:
    return _env_seconds("WCW_ATTENTION_WARNING_SECONDS", DEFAULT_WARNING_SECONDS, environ)


def sla_seconds(step_id: str, environ: Mapping[str, str] | None = None) -> int:
    key = _env_key(step_id)
    default = DEMO_SLA_SECONDS.get(step_id, DEFAULT_SLA_SECONDS)
    return _env_seconds(key, default, environ)


def stage_one_step_id(status: str) -> str:
    return STAGE_ONE_STEP_BY_STATUS.get(status, "extract-and-verify")


def ui_step_id(step_id: str) -> str:
    return UI_STEP_BY_BACKEND_STEP.get(step_id, step_id)


def action_label(step_id: str, *, fallback: str | None = None) -> str:
    return ACTION_LABELS.get(step_id) or ACTION_LABELS.get(ui_step_id(step_id)) or fallback or "Needs attention"


def _env_key(step_id: str) -> str:
    token = step_id.replace("-", "_").upper()
    return f"WCW_SLA_{token}_SECONDS"


def _env_seconds(name: str, default: int, environ: Mapping[str, str] | None) -> int:
    source = os.environ if environ is None else environ
    raw = str(source.get(name, "")).strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default
