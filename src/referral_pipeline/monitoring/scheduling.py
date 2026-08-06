"""Step 4 end-of-day scheduling rules with no external writes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from referral_pipeline.monitoring.config import MonitoringConfig
from referral_pipeline.monitoring.models import OperationalSnapshot


@dataclass(frozen=True)
class SchedulingDecision:
    status: str
    reason: str
    business_date: date
    exception_required: bool = False


def evaluate_scheduling(
    snapshot: OperationalSnapshot,
    *,
    config: MonitoringConfig,
    now: datetime,
) -> SchedulingDecision:
    local_now = now.astimezone(ZoneInfo(config.timezone))
    business_date = local_now.date()
    if not _is_active(snapshot, config):
        return SchedulingDecision("not_applicable", "referral is not active for scheduling", business_date)
    if _norm(snapshot.sent_to_case_manager) not in config.sent_to_case_manager_labels:
        return SchedulingDecision("not_applicable", "referral has not been sent to a case manager", business_date)

    scheduled = _norm(snapshot.scheduled_status) in config.scheduled_status_labels
    complete = _norm(snapshot.scheduling_complete) in config.scheduling_complete_labels
    has_appointment = bool((snapshot.appointment_date or "").strip())
    if scheduled and complete and has_appointment:
        return SchedulingDecision("scheduled", "all scheduling completion fields agree", business_date)

    cutoff = _cutoff(config.end_of_day)
    due_date = _parse_date(snapshot.due_date)
    if local_now.time() < cutoff or (due_date is not None and due_date > business_date):
        return SchedulingDecision("pending", "end-of-day deadline has not arrived", business_date)

    if scheduled or complete or has_appointment:
        return SchedulingDecision(
            "indeterminate",
            "scheduling fields conflict or are incomplete",
            business_date,
            exception_required=True,
        )
    if due_date is None:
        return SchedulingDecision(
            "indeterminate",
            "active referral has no due date or scheduling completion evidence",
            business_date,
            exception_required=True,
        )
    return SchedulingDecision(
        "unscheduled",
        "due referral remains unscheduled after the end-of-day deadline",
        business_date,
        exception_required=True,
    )


def _is_active(snapshot: OperationalSnapshot, config: MonitoringConfig) -> bool:
    group = _norm(snapshot.group)
    if any(fragment and fragment in group for fragment in config.inactive_group_fragments):
        return False
    return _norm(snapshot.visit_status) not in config.inactive_visit_statuses


def _cutoff(value: str) -> time:
    try:
        hour, minute = value.split(":", 1)
        return time(int(hour), int(minute))
    except (TypeError, ValueError) as error:
        raise ValueError("monitoring end_of_day must use HH:MM") from error


def _parse_date(value: str | None) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    for candidate in (text, text[:10]):
        try:
            return date.fromisoformat(candidate)
        except ValueError:
            continue
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _norm(value: object) -> str:
    return " ".join(str(value or "").casefold().split())
