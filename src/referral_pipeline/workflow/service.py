"""Minimal Stage 2 assignment and Stage 3 handoff coordination."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from referral_pipeline.monitoring.models import (
    ExternalOperation,
    WorkflowCase,
    WorkflowDecision,
    WorkflowEvent,
    WorkflowWorkItem,
)
from referral_pipeline.monitoring.routing import persistence_for
from referral_pipeline.monitoring.store import WorkflowStore
from referral_pipeline.email_alerts import email_alert_key, queue_assignment_email_alert
from referral_pipeline.workflow.handoff import HandoffExecutionError, run_handoff
from referral_pipeline.workflow.operation_policy import (
    MONDAY,
    NOTIFY,
    is_false_preview_success,
    is_real_execution,
    public_operation_payload,
    reconcile_operation,
)
from referral_pipeline.workflow.roster import load_case_manager_roster
from referral_pipeline.workflow.deadlines import with_case_deadline, with_work_item_deadline


ASSIGNMENT_STEP = "assign-case-manager"
HANDOFF_OPERATIONS = (
    ("notify-assigned-case-manager", "Notify assigned case manager"),
    ("create-monday-record", "Create Monday.com record"),
    ("prefill-drk-chart", "Prefill DRK chart"),
)


class WorkflowExecutionError(RuntimeError):
    pass


class WorkflowExecutionService:
    def __init__(
        self,
        store: WorkflowStore,
        *,
        case_managers: list[dict[str, str]] | None = None,
    ) -> None:
        self.store = store
        self.case_managers = case_managers if case_managers is not None else load_case_manager_roster()
        self._managers_by_email = {
            manager["email"].casefold(): manager for manager in self.case_managers
        }

    def reconcile_stage_one_completions(self) -> int:
        """Bulk safety net for cases the per-confirmation apply path missed.

        Scans every case, so it belongs on a periodic background cycle
        (the approval worker calls this once per interval), not on-demand
        read paths like assignments() -- each case can cost a remote
        Supabase round trip through RoutingWorkflowStore.
        """
        repaired = 0
        for case in self.store.list_workflow_cases(limit=500):
            if case.current_stage > 2:
                continue
            item = self._assignment_item(case.case_id)
            outcome = self._partner_contact_outcome(case.case_id)
            if outcome is None and item is not None:
                outcome = str(item.payload.get("contact_outcome") or "reached")
            if outcome is None:
                continue
            if case.current_stage == 1 and case.status != "completed" and item is None:
                continue
            if self.start_assignment(case.case_id, contact_outcome=outcome):
                repaired += 1
        return repaired

    def start_assignment(self, case_id: str, *, contact_outcome: str) -> bool:
        """Ensure the Stage 2 work item and case header both exist.

        Partial writes are repaired on later calls. A completed Stage 3+ case is
        left untouched. Returns True when this call created or repaired state.
        """
        case = self._case(case_id)
        if case.current_stage > 2:
            return False
        work_item_id = _id("work", case_id, "2", ASSIGNMENT_STEP)
        existing = self.store.work_item(work_item_id)
        if existing is not None and existing.status == "completed":
            return False

        now = _now()
        reached = contact_outcome == "reached"
        desired_item_status = "waiting" if reached else "blocked"
        desired_case_status = "awaiting_assignment" if reached else "needs_attention"
        owner_role = "case_manager" if reached else "intake_team"
        changed = False

        if existing is None:
            existing = self.store.upsert_work_item(
                with_work_item_deadline(
                    WorkflowWorkItem(
                        work_item_id=work_item_id,
                        case_id=case_id,
                        stage=2,
                        step_id=ASSIGNMENT_STEP,
                        owner_role=owner_role,
                        status=desired_item_status,
                        recommendation_reason=(
                            "Territory rules are not connected; an intake-team member must choose."
                            if reached
                            else "Referral follow-up remains with the intake team before handoff."
                        ),
                        assigned_to=None if reached else "WCW Intake Team",
                        payload={"contact_outcome": contact_outcome},
                        created_at=now,
                        updated_at=now,
                    ),
                    now=now,
                )
            )
            changed = True
        elif existing.status != desired_item_status or existing.owner_role != owner_role:
            existing = self.store.upsert_work_item(
                with_work_item_deadline(
                    existing.model_copy(
                        update={
                            "owner_role": owner_role,
                            "status": desired_item_status,
                            "assigned_to": None if reached else "WCW Intake Team",
                            "payload": {**existing.payload, "contact_outcome": contact_outcome},
                            "updated_at": now,
                        }
                    ),
                    previous=existing,
                    now=now,
                )
            )
            changed = True

        case = self._case(case_id)
        if case.current_stage != 2 or case.status != desired_case_status:
            self.store.upsert_workflow_case(
                with_case_deadline(
                    case.model_copy(
                        update={
                            "current_stage": 2,
                            "status": desired_case_status,
                            "updated_at": now,
                            "completed_at": None,
                        }
                    ),
                    previous=case,
                    now=now,
                )
            )
            changed = True

        event_type = "assignment_requested" if reached else "intake_follow_up_required"
        if not any(event.event_type == event_type for event in self.store.list_events(case_id, limit=100)):
            self._event(
                case_id,
                event_type,
                details={
                    "contact_outcome": contact_outcome,
                    "owner_role": owner_role,
                    "recommendation_available": False,
                },
            )
            changed = True
        return changed

    def assignments(self, *, limit: int = 100) -> dict[str, Any]:
        items = [self._assignment_payload(item) for item in self.store.list_work_items(stage=2, limit=limit)]
        return {
            "items": items,
            "case_managers": self.case_managers,
            "recommendation_available": False,
            "recommendation_note": "WCW territory rules are not connected.",
        }

    def confirm_assignment(
        self,
        case_id: str,
        *,
        case_manager_email: str,
        decided_by: str,
    ) -> dict[str, Any]:
        """Record the decision and ensure Stage 3 case state plus every handoff operation."""
        email = case_manager_email.strip().casefold()
        actor = decided_by.strip()
        manager = self._managers_by_email.get(email)
        if manager is None:
            raise WorkflowExecutionError("selected case manager is not in the configured roster")
        if not actor:
            raise WorkflowExecutionError("decided_by is required")

        case = self._case(case_id)
        work_item_id = _id("work", case_id, "2", ASSIGNMENT_STEP)
        item = self.store.work_item(work_item_id)
        if item is None:
            raise WorkflowExecutionError("assignment is not ready")
        if item.owner_role != "case_manager":
            raise WorkflowExecutionError("this case remains assigned to intake-team follow-up")

        recorded = self._assignment_decision(case_id)
        if recorded is not None:
            recorded_email = str(recorded.selected_value.get("email") or "").casefold()
            if recorded_email != email:
                raise WorkflowExecutionError("assignment was already confirmed for another case manager")
            manager = {
                "name": str(recorded.selected_value.get("name") or manager["name"]),
                "email": recorded_email,
            }
            actor = recorded.decided_by or actor
        elif item.status == "completed" and item.assigned_to and item.assigned_to != email:
            raise WorkflowExecutionError("assignment was already confirmed for another case manager")
        elif item.status not in {"waiting", "completed"}:
            raise WorkflowExecutionError(f"assignment cannot be confirmed from status {item.status}")

        now = _now()
        if recorded is None:
            self.store.record_decision(
                WorkflowDecision(
                    decision_id=_id("decision", case_id, "assignment"),
                    idempotency_key=f"assignment:{case_id}",
                    case_id=case_id,
                    stage=2,
                    step_id=ASSIGNMENT_STEP,
                    decision_type="case_manager_selected",
                    selected_value=manager,
                    decided_by=actor,
                    created_at=now,
                )
            )
        if item.status != "completed" or item.assigned_to != email:
            item = self.store.upsert_work_item(
                with_work_item_deadline(
                    item.model_copy(
                        update={
                            "status": "completed",
                            "assigned_to": email,
                            "updated_at": now,
                            "completed_at": item.completed_at or now,
                        }
                    ),
                    previous=item,
                    now=now,
                )
            )
        case = self._case(case_id)
        if case.current_stage != 3 or case.status != "awaiting_handoff":
            self.store.upsert_workflow_case(
                with_case_deadline(
                    case.model_copy(
                        update={
                            "current_stage": 3,
                            "status": "awaiting_handoff",
                            "updated_at": now,
                            "completed_at": None,
                        }
                    ),
                    previous=case,
                    now=now,
                )
            )
        if not any(
            event.event_type == "case_manager_assigned"
            for event in self.store.list_events(case_id, limit=100)
        ):
            self._event(
                case_id,
                "case_manager_assigned",
                details={"case_manager": manager, "decided_by": actor},
            )
        self._prepare_handoff(case_id, manager=manager, now=now)
        current_case = self._case(case_id)
        queue_assignment_email_alert(
            store=self.store,
            case_id=case_id,
            patient_name=current_case.patient_label or case_id,
            manager=manager,
            now=now,
        )
        return self._assignment_payload(item)

    def preview_handoff_operation(
        self,
        case_id: str,
        operation_type: str,
        *,
        mailbox: Any | None = None,
        drk_executor: Any | None = None,
    ) -> dict[str, Any]:
        """Return a dry-run result without claiming or consuming the operation."""
        operation = self._handoff_operation(case_id, operation_type)
        try:
            result = run_handoff(
                operation.operation_type,
                operation.request_payload,
                execute=False,
                confirm_monday_write=False,
                mailbox=mailbox,
                drk_executor=drk_executor,
            )
        except HandoffExecutionError as error:
            result = {
                "status": "blocked",
                "error": str(error),
                "written": False,
                "sent": False,
                "filled": False,
                "dry_run": True,
                "submitted": False,
            }
        return public_operation_payload(
            operation,
            extra={"preview": result, "consumed": False, "mode": "preview"},
        )

    def execute_handoff_operation(
        self,
        case_id: str,
        operation_type: str,
        *,
        execute: bool = False,
        confirm_monday_write: bool = False,
        mailbox: Any | None = None,
        drk_executor: Any | None = None,
        monday_lookup: Any | None = None,
        operator_retry: bool = False,
        claimed_by: str = "operator",
    ) -> dict[str, Any]:
        """Run one real Stage 3 operation with at-most-once claiming.

        Previews never change persisted status or attempts. Uncertain operations
        are reconciled before any retry and are never repeated automatically.
        """
        if not is_real_execution(
            operation_type,
            execute=execute,
            confirm_monday_write=confirm_monday_write,
        ):
            return self.preview_handoff_operation(
                case_id,
                operation_type,
                mailbox=mailbox,
                drk_executor=drk_executor,
            )

        operation = self._handoff_operation(case_id, operation_type)
        if operation_type == NOTIFY:
            manager = operation.request_payload.get("case_manager")
            if not isinstance(manager, dict):
                raise WorkflowExecutionError("case-manager notification is missing assignment data")
            case = self._case(case_id)
            queue_assignment_email_alert(
                store=self.store,
                case_id=case_id,
                patient_name=case.patient_label or case_id,
                manager=manager,
                now=_now(),
            )
            succeeded = self.store.upsert_external_operation(
                operation.model_copy(
                    update={
                        "status": "succeeded",
                        "result": {
                            "queued": True,
                            "channel": "gmail",
                            "alert_key": email_alert_key(case_id, "cm-assigned"),
                        },
                        "last_error": None,
                        "lease_until": None,
                        "updated_at": _now(),
                        "completed_at": operation.completed_at or _now(),
                    }
                )
            )
            return public_operation_payload(
                succeeded,
                extra={"consumed": True, "mode": "queued"},
            )
        if operation.status == "succeeded" and is_false_preview_success(operation):
            operation = self.store.upsert_external_operation(
                operation.model_copy(
                    update={
                        "status": "ready",
                        "completed_at": None,
                        "last_error": "reopened; persisted result was a preview, not a real write",
                        "updated_at": _now(),
                    }
                )
            )
        if operation.status == "succeeded":
            return public_operation_payload(operation, extra={"consumed": False, "mode": "already_succeeded"})

        case = self.store.workflow_case(case_id)
        if operation.status == "uncertain" or operator_retry:
            outcome = reconcile_operation(
                operation,
                case=case,
                monday_lookup=monday_lookup,
                inspect_drk=(
                    None
                    if drk_executor is None
                    else (lambda _op: drk_executor.inspect(operation.request_payload))
                ),
            )
            if outcome == "succeeded":
                succeeded = self.store.upsert_external_operation(
                    operation.model_copy(
                        update={
                            "status": "succeeded",
                            "lease_until": None,
                            "last_error": None,
                            "updated_at": _now(),
                            "completed_at": operation.completed_at or _now(),
                        }
                    )
                )
                return public_operation_payload(
                    succeeded, extra={"consumed": False, "mode": "reconciled"}
                )
            if operation.status == "uncertain" and outcome == "unknown" and not operator_retry:
                raise WorkflowExecutionError(
                    "handoff operation is uncertain after reconciliation; "
                    "refusing to repeat an unknown external write"
                )
            if operation.status == "uncertain" and not operator_retry:
                raise WorkflowExecutionError(
                    "handoff operation is uncertain; pass operator_retry after reviewing evidence"
                )

        claim = self.store.claim_external_operation(
            operation.operation_id,
            case_id=case_id,
            claimed_by=claimed_by,
            allow_uncertain=bool(operator_retry and operation.status == "uncertain"),
        )
        if claim == "already_succeeded":
            current = self._handoff_operation(case_id, operation_type)
            return public_operation_payload(current, extra={"consumed": False, "mode": "already_succeeded"})
        if claim == "busy":
            raise WorkflowExecutionError("handoff operation is already running")
        if claim == "uncertain":
            raise WorkflowExecutionError(
                "running lease expired; operation marked uncertain and will not rerun automatically"
            )
        if claim != "claimed":
            raise WorkflowExecutionError(f"handoff operation could not be claimed ({claim})")

        running = self._handoff_operation(case_id, operation_type)
        on_monday_item_created = None
        if running.operation_type == MONDAY:
            def persist_monday_item(item: dict[str, Any]) -> None:
                item_id = str(item.get("id") or "").strip()
                if not item_id:
                    raise WorkflowExecutionError("Monday create callback did not receive an item id")
                current = self._handoff_operation(case_id, operation_type)
                self.store.upsert_external_operation(
                    current.model_copy(
                        update={
                            "result": {
                                **current.result,
                                "written": True,
                                "monday_item_id": item_id,
                                "post_create_pending": True,
                            },
                            "updated_at": _now(),
                        }
                    )
                )
                current_case = self._case(case_id)
                if current_case.monday_item_id != item_id:
                    self.store.upsert_workflow_case(
                        with_case_deadline(
                            current_case.model_copy(
                                update={"monday_item_id": item_id, "updated_at": _now()}
                            ),
                            previous=current_case,
                        )
                    )

            on_monday_item_created = persist_monday_item
        try:
            result = run_handoff(
                running.operation_type,
                running.request_payload,
                execute=execute,
                confirm_monday_write=confirm_monday_write,
                mailbox=mailbox,
                drk_executor=drk_executor,
                on_monday_item_created=on_monday_item_created,
            )
        except HandoffExecutionError as error:
            self.store.upsert_external_operation(
                running.model_copy(
                    update={
                        "status": "failed",
                        "last_error": str(error),
                        "lease_until": None,
                        "updated_at": _now(),
                    }
                )
            )
            raise WorkflowExecutionError(str(error)) from error
        except Exception as error:
            current = self._handoff_operation(case_id, operation_type)
            self.store.upsert_external_operation(
                current.model_copy(
                    update={
                        "status": "uncertain",
                        "last_error": (
                            "external operation raised after execution began; "
                            f"outcome requires reconciliation: {error}"
                        ),
                        "lease_until": None,
                        "updated_at": _now(),
                    }
                )
            )
            raise WorkflowExecutionError(
                "external operation outcome is uncertain; inspect the destination before retrying"
            ) from error
        if result.get("status") == "blocked" or result.get("blockers") and not result.get("filled") and not result.get("written") and not result.get("sent"):
            blocked = self.store.upsert_external_operation(
                running.model_copy(
                    update={
                        "status": "blocked" if result.get("blockers") else "failed",
                        "result": result,
                        "last_error": ", ".join(str(item) for item in result.get("blockers") or []) or None,
                        "lease_until": None,
                        "updated_at": _now(),
                    }
                )
            )
            return public_operation_payload(blocked, extra={"consumed": True, "mode": "execute"})
        try:
            succeeded = self.store.upsert_external_operation(
                running.model_copy(
                    update={
                        "status": "succeeded",
                        "result": result,
                        "last_error": None,
                        "lease_until": None,
                        "updated_at": _now(),
                        "completed_at": _now(),
                    }
                )
            )
        except Exception as error:
            current = self._handoff_operation(case_id, operation_type)
            try:
                self.store.upsert_external_operation(
                    current.model_copy(
                        update={
                            "status": "uncertain",
                            "result": {**current.result, **result},
                            "last_error": (
                                "external operation completed but its success state could not be "
                                f"persisted; reconciliation is required: {error}"
                            ),
                            "lease_until": None,
                            "updated_at": _now(),
                        }
                    )
                )
            except Exception:
                pass
            raise WorkflowExecutionError(
                "external operation completed but its success state is uncertain; "
                "inspect the destination before retrying"
            ) from error
        return public_operation_payload(succeeded, extra={"consumed": True, "mode": "execute"})

    def handoffs(self, *, limit: int = 100) -> dict[str, Any]:
        cases: list[dict[str, Any]] = []
        for case in self.store.list_workflow_cases(limit=limit):
            if case.current_stage != 3:
                continue
            operations = self.store.list_external_operations(case.case_id)
            assignment = self._assignment_decision(case.case_id)
            cases.append(
                {
                    "case_id": case.case_id,
                    "patient_label": case.patient_label,
                    "status": case.status,
                    "persistence": persistence_for(self.store, case.case_id),
                    "assigned_case_manager": None if assignment is None else assignment.selected_value,
                    "operations": [operation.model_dump(mode="json") for operation in operations],
                }
            )
        return {"items": cases}

    def _prepare_handoff(
        self,
        case_id: str,
        *,
        manager: dict[str, str],
        now: datetime,
    ) -> None:
        existing = {
            operation.operation_type: operation
            for operation in self.store.list_external_operations(case_id)
        }
        payload = self._handoff_payload(case_id, manager=manager)
        created = False
        for operation_type, label in HANDOFF_OPERATIONS:
            current = existing.get(operation_type)
            request_payload = {**payload, "label": label, "operation_type": operation_type}
            if current is None:
                self.store.upsert_external_operation(
                    ExternalOperation(
                        operation_id=_id("operation", case_id, operation_type),
                        idempotency_key=f"handoff:{case_id}:{operation_type}",
                        case_id=case_id,
                        stage=3,
                        operation_type=operation_type,
                        status="ready",
                        request_payload=request_payload,
                        created_at=now,
                        updated_at=now,
                    )
                )
                created = True
                continue
            if current.status in {"succeeded", "running", "uncertain"}:
                continue
            if not _payload_complete(current.request_payload):
                self.store.upsert_external_operation(
                    current.model_copy(
                        update={
                            "request_payload": {
                                **current.request_payload,
                                **request_payload,
                                "label": label,
                                "case_manager": manager,
                            },
                            "updated_at": now,
                        }
                    )
                )
                created = True
        if created or not any(
            event.event_type == "handoff_prepared"
            for event in self.store.list_events(case_id, limit=100)
        ):
            self._event(
                case_id,
                "handoff_prepared",
                details={
                    "operations": [operation_type for operation_type, _ in HANDOFF_OPERATIONS],
                    "automatic_writes": False,
                },
            )

    def _handoff_payload(self, case_id: str, *, manager: dict[str, str]) -> dict[str, Any]:
        case = self._case(case_id)
        fields = self._normalized_fields(case_id)
        assignment = self._assignment_item(case_id)
        contact_outcome = None
        if assignment is not None:
            contact_outcome = assignment.payload.get("contact_outcome")
        return {
            "case_id": case_id,
            "patient_label": case.patient_label,
            "referral_id": case.referral_id,
            "source_ref": case.source_ref,
            "case_manager": manager,
            "contact_outcome": contact_outcome,
            "automatic_submit": False,
            "monday_write_confirmed": False,
            "normalized": {
                "patient_name": case.patient_label,
                "referral_id": case.referral_id,
                **fields,
            },
            "monday_preview": self._artifact_snapshot(case_id, "monday_preview"),
            "drk_draft": self._artifact_snapshot(case_id, "drk_draft"),
            "source_message_id": self._source_message_id(case_id),
        }

    def _handoff_operation(self, case_id: str, operation_type: str) -> ExternalOperation:
        operation = next(
            (
                item
                for item in self.store.list_external_operations(case_id)
                if item.operation_type == operation_type
            ),
            None,
        )
        if operation is None:
            raise WorkflowExecutionError(f"handoff operation {operation_type} is not prepared")
        return operation

    def _assignment_payload(self, item: WorkflowWorkItem) -> dict[str, Any]:
        case = self._case(item.case_id)
        assigned = self._managers_by_email.get((item.assigned_to or "").casefold())
        return {
            **item.model_dump(mode="json"),
            "patient_label": case.patient_label,
            "assigned_case_manager": assigned,
            "persistence": persistence_for(self.store, item.case_id),
        }

    def _assignment_item(self, case_id: str) -> WorkflowWorkItem | None:
        return self.store.work_item(_id("work", case_id, "2", ASSIGNMENT_STEP))

    def _assignment_decision(self, case_id: str) -> WorkflowDecision | None:
        for decision in self.store.list_decisions(case_id):
            if decision.decision_type == "case_manager_selected":
                return decision
        return None

    def _normalized_fields(self, case_id: str) -> dict[str, Any]:
        for event in reversed(self.store.list_events(case_id, limit=100)):
            if event.event_type == "extraction_completed":
                fields = event.details.get("fields")
                return dict(fields) if isinstance(fields, dict) else {}
        return {}

    def _artifact_snapshot(self, case_id: str, name: str) -> dict[str, Any]:
        for event in reversed(self.store.list_events(case_id, limit=100)):
            snapshot = event.details.get(name)
            if isinstance(snapshot, dict):
                return snapshot
        return {}

    def _source_message_id(self, case_id: str) -> str | None:
        for event in self.store.list_events(case_id, limit=100):
            for key in ("message_id", "source_message_id", "confirmation_message_id"):
                value = str(event.details.get(key) or "").strip()
                if value:
                    return value
        return None

    def _partner_contact_outcome(self, case_id: str) -> str | None:
        events = self.store.list_events(case_id, limit=100)
        for event in reversed(events):
            if event.event_type == "partner_contact_confirmed":
                return str(event.details.get("contact_outcome") or "reached")
        return None

    def _case(self, case_id: str) -> WorkflowCase:
        case = self.store.workflow_case(case_id)
        if case is None:
            raise WorkflowExecutionError("workflow case was not found")
        return case

    def _event(self, case_id: str, event_type: str, *, details: dict[str, Any]) -> None:
        self.store.record_event(
            WorkflowEvent(
                event_key=f"workflow:{case_id}:{event_type}",
                event_type=event_type,
                entity_id=case_id,
                source="workflow",
                occurred_at=_now(),
                details=details,
            )
        )


def _payload_complete(payload: dict[str, Any]) -> bool:
    manager = payload.get("case_manager")
    normalized = payload.get("normalized")
    return (
        isinstance(manager, dict)
        and bool(manager.get("email"))
        and isinstance(normalized, dict)
        and "automatic_submit" in payload
    )


def _id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def _now() -> datetime:
    return datetime.now(timezone.utc)
