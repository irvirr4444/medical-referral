"""Preview vs real Stage 3 execution, plus at-most-once claim outcomes.

Kept separate from WorkflowExecutionService so preview, claiming, and
reconciliation stay small and testable.
"""

from __future__ import annotations

from typing import Any, Callable, Literal

from referral_pipeline.monitoring.models import ExternalOperation, WorkflowCase


class HandoffExecutionError(RuntimeError):
    pass


NOTIFY = "notify-assigned-case-manager"
MONDAY = "create-monday-record"
DRK = "prefill-drk-chart"

ReconcileOutcome = Literal["succeeded", "not_done", "unknown"]
ClaimOutcome = Literal[
    "claimed",
    "already_succeeded",
    "busy",
    "uncertain",
    "not_found",
    "not_retryable",
]


def is_real_execution(
    operation_type: str,
    *,
    execute: bool = False,
    confirm_monday_write: bool = False,
) -> bool:
    """Return True only when the caller asked for a real external side effect."""
    if operation_type == MONDAY:
        return bool(confirm_monday_write)
    if operation_type in {NOTIFY, DRK}:
        return bool(execute)
    return False


def graph_message_id_from(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        for key in ("id", "message_id", "graph_message_id"):
            text = str(value.get(key) or "").strip()
            if text:
                return text
    return None


def monday_item_id_from(operation: ExternalOperation, case: WorkflowCase | None = None) -> str | None:
    for source in (operation.result, operation.request_payload):
        for key in ("monday_item_id", "created_item_id"):
            value = str(source.get(key) or "").strip()
            if value:
                return value
        item = source.get("item")
        if isinstance(item, dict):
            value = str(item.get("id") or "").strip()
            if value:
                return value
    if case is not None and case.monday_item_id:
        return str(case.monday_item_id)
    return None


def evidence_proves_success(operation: ExternalOperation, case: WorkflowCase | None = None) -> bool:
    if operation.status == "succeeded" and operation.result:
        if operation.operation_type == NOTIFY:
            return bool(operation.result.get("sent")) and bool(
                graph_message_id_from(operation.result) or operation.result.get("sent")
            )
        if operation.operation_type == MONDAY:
            return bool(operation.result.get("written")) and bool(monday_item_id_from(operation, case))
        if operation.operation_type == DRK:
            return bool(operation.result.get("filled")) and bool(operation.result.get("populated_fields"))
    if operation.operation_type == NOTIFY:
        return bool(graph_message_id_from(operation.result))
    if operation.operation_type == MONDAY:
        return bool(monday_item_id_from(operation, case))
    if operation.operation_type == DRK:
        return bool(operation.result.get("filled")) and bool(operation.result.get("populated_fields"))
    return False


def is_false_preview_success(operation: ExternalOperation) -> bool:
    """True when an older preview was persisted as succeeded without a real write."""
    if operation.status != "succeeded":
        return False
    result = operation.result or {}
    if result.get("dry_run") or result.get("would_create") or result.get("would_notify") or result.get("would_prefill"):
        return True
    if operation.operation_type == MONDAY and not result.get("written") and not monday_item_id_from(operation):
        return bool(result.get("dry_run") or result.get("would_create"))
    return False


def reconcile_operation(
    operation: ExternalOperation,
    *,
    case: WorkflowCase | None = None,
    monday_lookup: Callable[[ExternalOperation], str | None] | None = None,
    inspect_drk: Callable[[ExternalOperation], dict[str, Any]] | None = None,
) -> ReconcileOutcome:
    """Decide whether a prior real attempt already succeeded.

    unknown means a write may already have happened and must not be repeated.
    """
    if evidence_proves_success(operation, case):
        return "succeeded"
    if operation.operation_type == MONDAY and monday_lookup is not None:
        try:
            found = monday_lookup(operation)
        except Exception:
            return "unknown"
        if found:
            return "succeeded"
        if operation.status in {"failed", "ready"}:
            return "not_done"
        return "unknown"
    if operation.operation_type == DRK and inspect_drk is not None:
        try:
            snapshot = inspect_drk(operation)
        except Exception:
            return "unknown"
        if snapshot.get("filled") and snapshot.get("populated_fields"):
            return "succeeded"
        if operation.status in {"failed", "ready"}:
            return "not_done"
        return "unknown"
    if operation.status in {"failed", "ready", "blocked"}:
        return "not_done"
    return "unknown"


def public_operation_payload(operation: ExternalOperation, *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = operation.model_dump(mode="json")
    if extra:
        payload.update(extra)
    return payload
