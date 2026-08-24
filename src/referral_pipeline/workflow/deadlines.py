"""Assign stored attention deadlines. Does not compute due_soon or overdue."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from referral_pipeline.monitoring.models import WorkflowCase, WorkflowWorkItem
from referral_pipeline.workflow.attention_policy import (
    TERMINAL_CASE_STATUSES,
    TERMINAL_WORK_ITEM_STATUSES,
    sla_seconds,
    stage_one_step_id,
)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def with_case_deadline(
    case: WorkflowCase,
    *,
    previous: WorkflowCase | None = None,
    now: datetime | None = None,
) -> WorkflowCase:
    current = as_utc(now) or utc_now()
    due = _case_deadline(case, previous=previous, now=current)
    if case.attention_due_at == due:
        return case
    return case.model_copy(update={"attention_due_at": due})


def with_work_item_deadline(
    item: WorkflowWorkItem,
    *,
    previous: WorkflowWorkItem | None = None,
    now: datetime | None = None,
) -> WorkflowWorkItem:
    current = as_utc(now) or utc_now()
    due = _work_item_deadline(item, previous=previous, now=current)
    if item.due_at == due:
        return item
    return item.model_copy(update={"due_at": due})


def _case_deadline(
    case: WorkflowCase,
    *,
    previous: WorkflowCase | None,
    now: datetime,
) -> datetime | None:
    if case.current_stage != 1 or case.status in TERMINAL_CASE_STATUSES or case.completed_at is not None:
        return None
    if (
        previous is not None
        and previous.current_stage == 1
        and previous.status == case.status
        and previous.attention_due_at is not None
    ):
        return as_utc(previous.attention_due_at)
    step_id = stage_one_step_id(case.status)
    return now + timedelta(seconds=sla_seconds(step_id))


def _work_item_deadline(
    item: WorkflowWorkItem,
    *,
    previous: WorkflowWorkItem | None,
    now: datetime,
) -> datetime | None:
    if item.status in TERMINAL_WORK_ITEM_STATUSES or item.completed_at is not None:
        return None
    if (
        previous is not None
        and previous.work_item_id == item.work_item_id
        and previous.step_id == item.step_id
        and previous.due_at is not None
        and previous.status not in TERMINAL_WORK_ITEM_STATUSES
    ):
        return as_utc(previous.due_at)
    return now + timedelta(seconds=sla_seconds(item.step_id))
