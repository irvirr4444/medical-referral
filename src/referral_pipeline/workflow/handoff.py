"""Independent, idempotent Stage 3 destination executors.

Monday writes default to dry-run. DRK stops before the irreversible Create/Submit
action. Callers must pass explicit execute/confirm flags; these helpers never
infer permission from environment variables.
"""

from __future__ import annotations

from typing import Any, Callable

from referral_pipeline.workflow.operation_policy import (
    DRK,
    MONDAY,
    NOTIFY,
    HandoffExecutionError,
    graph_message_id_from,
    is_real_execution,
)


def notify_case_manager(
    payload: dict[str, Any],
    *,
    execute: bool = False,
    mailbox: Any | None = None,
) -> dict[str, Any]:
    """Prepare or send the assigned case-manager notification."""
    manager = _manager(payload)
    recipient = str(manager.get("email") or "").strip()
    if not recipient:
        raise HandoffExecutionError("case-manager notification is missing a recipient")
    result = {
        "operation_type": NOTIFY,
        "recipient": recipient,
        "case_manager": manager,
        "patient_label": payload.get("patient_label"),
        "sent": False,
        "would_notify": not execute,
        "graph_message_id": None,
    }
    if not execute:
        return result
    if mailbox is None:
        raise HandoffExecutionError("case-manager notification requires a mailbox to send")
    source_message_id = str(payload.get("source_message_id") or "").strip()
    if not source_message_id:
        raise HandoffExecutionError("case-manager notification requires the source message id")
    text = (
        f"Referral {payload.get('patient_label') or payload.get('case_id')} "
        "is assigned to you for Stage 3 handoff."
    )
    sent = mailbox.send_reply(
        source_message_id=source_message_id,
        recipient=recipient,
        content_type="Text",
        text_body=text,
        html_body=None,
        body=text,
    )
    result["sent"] = True
    result["would_notify"] = False
    result["graph_message_id"] = graph_message_id_from(sent)
    return result


def create_monday_record(
    payload: dict[str, Any],
    *,
    confirm_write: bool = False,
    on_item_created: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Create the Monday Master Sheet item only after an explicit write confirmation."""
    preview = payload.get("monday_preview")
    if not isinstance(preview, dict):
        raise HandoffExecutionError("Monday handoff payload is missing a normalized preview")
    result = {
        "operation_type": MONDAY,
        "board_id": preview.get("board_id"),
        "group_id": preview.get("group_id"),
        "item_name": preview.get("item_name") or payload.get("patient_label"),
        "dry_run": not confirm_write,
        "written": False,
        "automatic_submit": False,
        "monday_item_id": None,
    }
    if preview.get("blocked"):
        raise HandoffExecutionError(
            "Monday preview is blocked: "
            + ", ".join(str(item) for item in preview.get("blockers") or [])
        )
    if not confirm_write:
        result["would_create"] = True
        return result
    import sys
    from pathlib import Path

    monday_dir = Path(__file__).resolve().parents[2] / "monday.com"
    if str(monday_dir) not in sys.path:
        sys.path.insert(0, str(monday_dir))
    from master_sheet_writer import apply_master_sheet_create

    applied = apply_master_sheet_create(
        {**preview, "mode": "apply"},
        on_item_created=on_item_created,
    )
    item_id = str((applied.get("item") or {}).get("id") or "")
    if not item_id:
        raise HandoffExecutionError("Monday create did not return an item id")
    result.update(
        {
            "dry_run": False,
            "written": True,
            "would_create": False,
            "monday_item_id": item_id,
            "applied_actions": applied.get("applied_actions") or [],
        }
    )
    return result


def prefill_drk_chart(
    payload: dict[str, Any],
    *,
    execute: bool = False,
    executor: Any | None = None,
) -> dict[str, Any]:
    """Preview or run a DRK chart prefill. Never reports filled unless fields were populated."""
    from referral_pipeline.workflow.drk_prefill import DrkChartPrefillExecutor

    if executor is None:
        worker = DrkChartPrefillExecutor()
    elif hasattr(executor, "preview") and hasattr(executor, "execute"):
        worker = executor
    else:
        worker = DrkChartPrefillExecutor(adapter=executor)
    if not execute:
        return worker.preview(payload)
    return worker.execute(payload)


def run_handoff(
    operation_type: str,
    payload: dict[str, Any],
    *,
    execute: bool = False,
    confirm_monday_write: bool = False,
    mailbox: Any | None = None,
    drk_executor: Any | None = None,
    on_monday_item_created: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Dispatch one Stage 3 operation. Preview flags never infer a real write."""
    if operation_type == NOTIFY:
        return notify_case_manager(payload, execute=execute, mailbox=mailbox)
    if operation_type == MONDAY:
        return create_monday_record(
            payload,
            confirm_write=confirm_monday_write,
            on_item_created=on_monday_item_created,
        )
    if operation_type == DRK:
        return prefill_drk_chart(payload, execute=execute, executor=drk_executor)
    raise HandoffExecutionError(f"unknown Stage 3 operation: {operation_type}")


def executor_for(operation_type: str):
    executors = {
        NOTIFY: notify_case_manager,
        MONDAY: create_monday_record,
        DRK: prefill_drk_chart,
    }
    executor = executors.get(operation_type)
    if executor is None:
        raise HandoffExecutionError(f"unknown Stage 3 operation: {operation_type}")
    return executor


def _manager(payload: dict[str, Any]) -> dict[str, str]:
    manager = payload.get("case_manager")
    if isinstance(manager, dict):
        return {
            "name": str(manager.get("name") or "").strip(),
            "email": str(manager.get("email") or "").strip().casefold(),
        }
    return {}


# Re-export so existing imports keep working.
__all__ = [
    "DRK",
    "HandoffExecutionError",
    "MONDAY",
    "NOTIFY",
    "create_monday_record",
    "executor_for",
    "is_real_execution",
    "notify_case_manager",
    "prefill_drk_chart",
    "run_handoff",
]
