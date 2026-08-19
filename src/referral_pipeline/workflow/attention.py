"""Read-only workflow attention signals derived from durable state."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from referral_pipeline.monitoring.models import (
    WorkflowCase,
    WorkflowException,
    WorkflowWorkItem,
)
from referral_pipeline.monitoring.store import WorkflowStore
from referral_pipeline.workflow.attention_policy import (
    OPEN_EXCEPTION_STATUS,
    TERMINAL_CASE_STATUSES,
    TERMINAL_WORK_ITEM_STATUSES,
    action_label,
    stage_one_step_id,
    ui_step_id,
    warning_window_seconds,
)
from referral_pipeline.workflow.deadlines import as_utc, utc_now

Severity = Literal["normal", "due_soon", "overdue", "blocked"]
Source = Literal["workflow_case", "work_item", "exception"]

_SEVERITY_ORDER = {"blocked": 0, "overdue": 1, "due_soon": 2, "normal": 3}
_SAFE_EMPTY: dict[str, Any] = {
    "generated_at": "",
    "summary": {"overdue": 0, "due_soon": 0, "blocked": 0, "by_stage": {}},
    "items": [],
}


def workflow_attention(
    store: WorkflowStore,
    *,
    stage: int | None = None,
    limit: int = 200,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Project attention signals without writing workflow state."""
    current = as_utc(now) or utc_now()
    warning = warning_window_seconds()
    cases = {case.case_id: case for case in store.list_workflow_cases(limit=500)}
    items: list[dict[str, Any]] = []
    items.extend(_case_signals(cases.values(), now=current, warning=warning, stage=stage))
    items.extend(
        _work_item_signals(
            store.list_work_items(limit=500),
            cases=cases,
            now=current,
            warning=warning,
            stage=stage,
        )
    )
    items.extend(
        _exception_signals(
            store.list_exceptions(status=OPEN_EXCEPTION_STATUS, limit=500),
            cases=cases,
            now=current,
            stage=stage,
        )
    )
    items.sort(key=_sort_key)
    capped = items[: max(1, min(limit, 500))] if items else []
    return {
        "generated_at": current.isoformat().replace("+00:00", "Z"),
        "summary": _summary(capped),
        "items": capped,
    }


def empty_attention(*, now: datetime | None = None) -> dict[str, Any]:
    current = as_utc(now) or utc_now()
    payload = dict(_SAFE_EMPTY)
    payload["generated_at"] = current.isoformat().replace("+00:00", "Z")
    payload["summary"] = {"overdue": 0, "due_soon": 0, "blocked": 0, "by_stage": {}}
    payload["items"] = []
    return payload


def _case_signals(
    cases: Any,
    *,
    now: datetime,
    warning: int,
    stage: int | None,
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, WorkflowCase):
            continue
        if case.current_stage != 1 or case.status in TERMINAL_CASE_STATUSES or case.completed_at:
            continue
        if stage is not None and case.current_stage != stage:
            continue
        step_id = ui_step_id(stage_one_step_id(case.status))
        signals.append(
            _signal(
                signal_id=f"workflow_case:{case.case_id}",
                case_id=case.case_id,
                patient_label=_patient_label(case.patient_label),
                stage=1,
                step_id=step_id,
                status=case.status,
                due_at=case.attention_due_at,
                now=now,
                warning=warning,
                blocked=False,
                action_label=action_label(step_id),
                source="workflow_case",
            )
        )
    return signals


def _work_item_signals(
    work_items: list[WorkflowWorkItem],
    *,
    cases: dict[str, WorkflowCase],
    now: datetime,
    warning: int,
    stage: int | None,
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for item in work_items:
        if item.status in TERMINAL_WORK_ITEM_STATUSES or item.completed_at:
            continue
        if stage is not None and item.stage != stage:
            continue
        case = cases.get(item.case_id)
        step_id = ui_step_id(item.step_id)
        blocked = item.status in {"blocked", "failed"}
        signals.append(
            _signal(
                signal_id=f"work_item:{item.work_item_id}",
                case_id=item.case_id,
                patient_label=_patient_label(None if case is None else case.patient_label),
                stage=item.stage,
                step_id=step_id,
                status=item.status,
                due_at=item.due_at,
                now=now,
                warning=warning,
                blocked=blocked,
                action_label=action_label(step_id),
                source="work_item",
            )
        )
    return signals


def _exception_signals(
    exceptions: list[WorkflowException],
    *,
    cases: dict[str, WorkflowCase],
    now: datetime,
    stage: int | None,
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for exception in exceptions:
        if exception.status != OPEN_EXCEPTION_STATUS:
            continue
        case = cases.get(exception.entity_id)
        current_stage = 1 if case is None else case.current_stage
        if stage is not None and current_stage != stage:
            continue
        step_id = ui_step_id(stage_one_step_id(case.status)) if case is not None else ""
        signals.append(
            _signal(
                signal_id=f"exception:{exception.exception_key}",
                case_id=exception.entity_id,
                patient_label=_patient_label(None if case is None else case.patient_label),
                stage=current_stage,
                step_id=step_id,
                status=exception.status,
                due_at=None,
                now=now,
                warning=0,
                blocked=True,
                action_label=action_label(step_id, fallback="Resolve workflow exception"),
                source="exception",
            )
        )
    return signals


def _signal(
    *,
    signal_id: str,
    case_id: str,
    patient_label: str,
    stage: int,
    step_id: str,
    status: str,
    due_at: datetime | None,
    now: datetime,
    warning: int,
    blocked: bool,
    action_label: str,
    source: Source,
) -> dict[str, Any]:
    due = as_utc(due_at)
    severity = _severity(due_at=due, now=now, warning=warning, blocked=blocked)
    overdue_seconds = 0
    if due is not None and due <= now:
        overdue_seconds = int((now - due).total_seconds())
    return {
        "signal_id": signal_id,
        "case_id": case_id,
        "patient_label": patient_label,
        "stage": stage,
        "step_id": step_id,
        "severity": severity,
        "status": status,
        "due_at": None if due is None else due.isoformat().replace("+00:00", "Z"),
        "overdue_seconds": overdue_seconds,
        "action_label": action_label,
        "source": source,
    }


def _severity(
    *,
    due_at: datetime | None,
    now: datetime,
    warning: int,
    blocked: bool,
) -> Severity:
    if blocked:
        return "blocked"
    if due_at is None:
        return "normal"
    if due_at <= now:
        return "overdue"
    remaining = (due_at - now).total_seconds()
    if remaining <= warning:
        return "due_soon"
    return "normal"


def _summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    overdue = due_soon = blocked = 0
    by_stage: dict[str, dict[str, int]] = {}
    for item in items:
        severity = str(item.get("severity") or "normal")
        stage_key = str(item.get("stage") or "")
        bucket = by_stage.setdefault(stage_key, {"overdue": 0, "due_soon": 0, "blocked": 0})
        if severity == "overdue":
            overdue += 1
            bucket["overdue"] += 1
        elif severity == "due_soon":
            due_soon += 1
            bucket["due_soon"] += 1
        elif severity == "blocked":
            blocked += 1
            bucket["blocked"] += 1
    return {
        "overdue": overdue,
        "due_soon": due_soon,
        "blocked": blocked,
        "by_stage": {key: value for key, value in sorted(by_stage.items()) if any(value.values())},
    }


def _sort_key(item: dict[str, Any]) -> tuple[int, str, str]:
    due_at = str(item.get("due_at") or "9999-12-31T00:00:00Z")
    return (
        _SEVERITY_ORDER.get(str(item.get("severity") or "normal"), 9),
        due_at,
        str(item.get("signal_id") or ""),
    )


def _patient_label(value: str | None) -> str:
    text = (value or "").strip()
    return text or "Patient"
