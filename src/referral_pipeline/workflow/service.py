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
from referral_pipeline.monitoring.store import WorkflowStore
from referral_pipeline.workflow.roster import load_case_manager_roster


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
        created = 0
        for case in self.store.list_workflow_cases(limit=500):
            if case.current_stage != 1 or case.status != "completed":
                continue
            outcome = self._partner_contact_outcome(case.case_id)
            if outcome is None:
                continue
            if self.start_assignment(case.case_id, contact_outcome=outcome):
                created += 1
        return created

    def start_assignment(self, case_id: str, *, contact_outcome: str) -> bool:
        case = self._case(case_id)
        work_item_id = _id("work", case_id, "2", ASSIGNMENT_STEP)
        if self.store.work_item(work_item_id) is not None:
            return False
        now = _now()
        reached = contact_outcome == "reached"
        item = WorkflowWorkItem(
            work_item_id=work_item_id,
            case_id=case_id,
            stage=2,
            step_id=ASSIGNMENT_STEP,
            owner_role="case_manager" if reached else "intake_team",
            status="waiting" if reached else "blocked",
            recommendation_reason=(
                "Territory rules are not connected; an intake-team member must choose."
                if reached
                else "Referral follow-up remains with the intake team before handoff."
            ),
            assigned_to=None if reached else "WCW Intake Team",
            payload={"contact_outcome": contact_outcome},
            created_at=now,
            updated_at=now,
        )
        self.store.upsert_work_item(item)
        next_case = case.model_copy(
            update={
                "current_stage": 2,
                "status": "awaiting_assignment" if reached else "needs_attention",
                "updated_at": now,
                "completed_at": None,
            }
        )
        self.store.upsert_workflow_case(next_case)
        self._event(
            case_id,
            "assignment_requested" if reached else "intake_follow_up_required",
            details={
                "contact_outcome": contact_outcome,
                "owner_role": item.owner_role,
                "recommendation_available": False,
            },
        )
        return True

    def assignments(self, *, limit: int = 100) -> dict[str, Any]:
        self.reconcile_stage_one_completions()
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
        if item.status == "completed":
            if item.assigned_to != email:
                raise WorkflowExecutionError("assignment was already confirmed for another case manager")
            return self._assignment_payload(item)
        if item.status != "waiting":
            raise WorkflowExecutionError(f"assignment cannot be confirmed from status {item.status}")

        now = _now()
        decision = WorkflowDecision(
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
        self.store.record_decision(decision)
        completed = self.store.upsert_work_item(
            item.model_copy(
                update={
                    "status": "completed",
                    "assigned_to": email,
                    "updated_at": now,
                    "completed_at": now,
                }
            )
        )
        self.store.upsert_workflow_case(
            case.model_copy(
                update={
                    "current_stage": 3,
                    "status": "awaiting_handoff",
                    "updated_at": now,
                    "completed_at": None,
                }
            )
        )
        self._event(
            case_id,
            "case_manager_assigned",
            details={"case_manager": manager, "decided_by": actor},
        )
        self._prepare_handoff(case_id, manager=manager, now=now)
        return self._assignment_payload(completed)

    def handoffs(self, *, limit: int = 100) -> dict[str, Any]:
        cases: list[dict[str, Any]] = []
        for case in self.store.list_workflow_cases(limit=limit):
            if case.current_stage != 3:
                continue
            operations = self.store.list_external_operations(case.case_id)
            decisions = self.store.list_decisions(case.case_id)
            assignment = next(
                (
                    decision.selected_value
                    for decision in reversed(decisions)
                    if decision.decision_type == "case_manager_selected"
                ),
                None,
            )
            cases.append(
                {
                    "case_id": case.case_id,
                    "patient_label": case.patient_label,
                    "status": case.status,
                    "assigned_case_manager": assignment,
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
        for operation_type, label in HANDOFF_OPERATIONS:
            operation_id = _id("operation", case_id, operation_type)
            self.store.upsert_external_operation(
                ExternalOperation(
                    operation_id=operation_id,
                    idempotency_key=f"handoff:{case_id}:{operation_type}",
                    case_id=case_id,
                    stage=3,
                    operation_type=operation_type,
                    status="ready",
                    request_payload={
                        "label": label,
                        "case_manager": manager,
                        "automatic_submit": False,
                    },
                    created_at=now,
                    updated_at=now,
                )
            )
        self._event(
            case_id,
            "handoff_prepared",
            details={
                "operations": [operation_type for operation_type, _ in HANDOFF_OPERATIONS],
                "automatic_writes": False,
            },
        )

    def _assignment_payload(self, item: WorkflowWorkItem) -> dict[str, Any]:
        case = self._case(item.case_id)
        assigned = self._managers_by_email.get((item.assigned_to or "").casefold())
        return {
            **item.model_dump(mode="json"),
            "patient_label": case.patient_label,
            "assigned_case_manager": assigned,
        }

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


def _id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def _now() -> datetime:
    return datetime.now(timezone.utc)
