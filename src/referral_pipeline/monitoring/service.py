"""Orchestrate snapshot persistence, Step 4 rules, and Step 5 transitions."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Iterable

from referral_pipeline.email_alerts import queue_snapshot_email_alert
from referral_pipeline.monitoring.config import MonitoringConfig
from referral_pipeline.monitoring.models import (
    NotificationRecord,
    OperationalSnapshot,
    PatientLink,
    WorkflowCounter,
    WorkflowEvent,
    WorkflowException,
)
from referral_pipeline.monitoring.scheduling import evaluate_scheduling
from referral_pipeline.monitoring.store import WorkflowStore
from referral_pipeline.monitoring.visits import evaluate_visit_transition


class WorkflowMonitoringService:
    def __init__(self, *, store: WorkflowStore, config: MonitoringConfig) -> None:
        self.store = store
        self.config = config

    def process(self, snapshots: Iterable[OperationalSnapshot], *, now: datetime) -> dict[str, object]:
        report: dict[str, object] = {
            "observed": 0,
            "changed": 0,
            "scheduling": {},
            "events_created": 0,
            "exceptions_created": 0,
            "exceptions_resolved": 0,
            "notifications_queued": 0,
            "email_alerts_queued": 0,
        }
        scheduling_counts: dict[str, int] = {}
        for incoming in snapshots:
            report["observed"] = int(report["observed"]) + 1
            snapshot = self._resolve_entity(incoming)
            previous = self.store.latest_snapshot(snapshot.source, snapshot.external_id)
            changed = self.store.save_snapshot(snapshot)
            self._upsert_link(snapshot, now=now)
            if changed:
                report["changed"] = int(report["changed"]) + 1

            if snapshot.source == "monday":
                decision = evaluate_scheduling(snapshot, config=self.config, now=now)
                scheduling_counts[decision.status] = scheduling_counts.get(decision.status, 0) + 1
                if decision.status == "scheduled":
                    resolved = self.store.resolve_exceptions(
                        entity_id=snapshot.entity_id,
                        exception_type="scheduling_exception",
                        resolved_at=now.isoformat(),
                    )
                    report["exceptions_resolved"] = int(report["exceptions_resolved"]) + resolved
                elif decision.exception_required:
                    created, queued = self._record_exception(
                        snapshot,
                        exception_key=f"scheduling:{snapshot.entity_id}:{decision.business_date.isoformat()}",
                        exception_type="scheduling_exception",
                        severity="warning",
                        now=now,
                        details={
                            "classification": decision.status,
                            "reason": decision.reason,
                            "business_date": decision.business_date.isoformat(),
                            **_operational_details(snapshot),
                        },
                    )
                    report["exceptions_created"] = int(report["exceptions_created"]) + created
                    report["notifications_queued"] = int(report["notifications_queued"]) + queued
                    scheduling_occurrences = sum(
                        1
                        for exception in self.store.list_exceptions(limit=500)
                        if exception.entity_id == snapshot.entity_id
                        and exception.exception_type == "scheduling_exception"
                    )
                    action_id = (
                        "eod-follow-up-cm"
                        if scheduling_occurrences <= 1
                        else "eod-escalate"
                    )
                    report["email_alerts_queued"] = int(report["email_alerts_queued"]) + int(
                        queue_snapshot_email_alert(
                            store=self.store,
                            action_id=action_id,
                            snapshot=snapshot,
                            now=now,
                            hours_overdue=24.0 if action_id == "eod-follow-up-cm" else 48.0,
                        )
                    )

            if changed and previous is not None:
                events, exceptions, queued, email_alerts = self._process_visit_transition(
                    previous, snapshot, now=now
                )
                report["events_created"] = int(report["events_created"]) + events
                report["exceptions_created"] = int(report["exceptions_created"]) + exceptions
                report["notifications_queued"] = int(report["notifications_queued"]) + queued
                report["email_alerts_queued"] = int(report["email_alerts_queued"]) + email_alerts

        report["scheduling"] = scheduling_counts
        return report

    def _process_visit_transition(
        self,
        previous: OperationalSnapshot,
        current: OperationalSnapshot,
        *,
        now: datetime,
    ) -> tuple[int, int, int, int]:
        counter_name = "consecutive_not_seen"
        current_count = self.store.get_counter(current.entity_id, counter_name)
        transition = evaluate_visit_transition(
            previous,
            current,
            config=self.config,
            consecutive_not_seen=current_count,
        )
        if transition.consecutive_not_seen != current_count:
            self.store.set_counter(
                WorkflowCounter(
                    entity_id=current.entity_id,
                    counter_name=counter_name,
                    value=transition.consecutive_not_seen,
                    updated_at=now,
                )
            )

        events_created = 0
        exceptions_created = 0
        notifications_queued = 0
        email_alerts_queued = 0
        for event_type in transition.event_types:
            event = WorkflowEvent(
                event_key=f"{current.entity_id}:{event_type}:{current.payload_digest[:20]}",
                event_type=event_type,
                entity_id=current.entity_id,
                source=current.source,
                occurred_at=now,
                details={
                    "previous_visit_status": previous.visit_status,
                    "current_visit_status": current.visit_status,
                    "previous_visit_outcome": previous.visit_outcome,
                    "current_visit_outcome": current.visit_outcome,
                    "previous_visit_event_id": previous.visit_event_id,
                    "current_visit_event_id": current.visit_event_id,
                    "consecutive_not_seen": transition.consecutive_not_seen,
                },
            )
            events_created += int(self.store.record_event(event))

        if "visit_not_seen" in transition.event_types:
            action_id = {
                1: "not-seen-week-1",
                2: "not-seen-week-2",
            }.get(transition.consecutive_not_seen, "not-seen-week-3")
            email_alerts_queued += int(
                queue_snapshot_email_alert(
                    store=self.store,
                    action_id=action_id,
                    snapshot=current,
                    now=now,
                )
            )

        if _became_sent_to_provider(previous, current):
            event = WorkflowEvent(
                event_key=f"{current.entity_id}:referral_sent_to_provider:{current.payload_digest[:20]}",
                event_type="referral_sent_to_provider",
                entity_id=current.entity_id,
                source=current.source,
                occurred_at=now,
                details={
                    "provider": current.provider,
                    "case_manager": current.case_manager,
                    "recorded_value": current.referral_sent_to_provider,
                },
            )
            events_created += int(self.store.record_event(event))
            email_alerts_queued += int(
                queue_snapshot_email_alert(
                    store=self.store,
                    action_id="send-referral-provider",
                    snapshot=current,
                    now=now,
                )
            )

        exception_specs: list[tuple[str, str, str]] = []
        if transition.review_required:
            exception_specs.append(
                (
                    f"noncompliance-review:{current.entity_id}:{transition.consecutive_not_seen}",
                    "noncompliance_discharge_review",
                    "critical",
                )
            )
        if "recorded_healed_status" in transition.event_types:
            exception_specs.append(
                (f"healed-review:{current.entity_id}:{current.payload_digest[:12]}", "qa_review", "warning")
            )
        if "recorded_expired_status" in transition.event_types:
            exception_specs.append(
                (
                    f"expired-review:{current.entity_id}:{current.payload_digest[:12]}",
                    "discharge_approval_review",
                    "critical",
                )
            )
        for key, kind, severity in exception_specs:
            created, queued = self._record_exception(
                current,
                exception_key=key,
                exception_type=kind,
                severity=severity,
                now=now,
                details={
                    "recorded_status": current.visit_outcome or current.visit_status,
                    "qa_hold_reason": current.qa_hold_reason,
                    "discharge_reason": current.discharge_reason,
                    "consecutive_not_seen": transition.consecutive_not_seen,
                    "human_decision_required": True,
                },
            )
            exceptions_created += created
            notifications_queued += queued
        return events_created, exceptions_created, notifications_queued, email_alerts_queued

    def _record_exception(
        self,
        snapshot: OperationalSnapshot,
        *,
        exception_key: str,
        exception_type: str,
        severity: str,
        now: datetime,
        details: dict[str, object],
    ) -> tuple[int, int]:
        exception = WorkflowException(
            exception_key=exception_key,
            exception_type=exception_type,
            entity_id=snapshot.entity_id,
            severity=severity,
            status="open",
            first_seen_at=now,
            last_seen_at=now,
            details=details,
        )
        created = self.store.upsert_exception(exception)
        queued = 0
        if created:
            for recipient in self.config.notification_recipients:
                notification = _notification(exception, snapshot=snapshot, recipient=recipient, now=now)
                queued += int(self.store.enqueue_notification(notification))
        return int(created), queued

    def _resolve_entity(self, snapshot: OperationalSnapshot) -> OperationalSnapshot:
        """Attach this snapshot to the Stage 1-3 case it belongs to, if any.

        wcw_workflow_cases.monday_item_id / .drk_patient_id are already the
        real link (written during the Stage 3 handoff), so a case lookup by
        either one is tried first -- when it hits, every downstream event and
        exception for this snapshot lands on the same case_id Stages 1-3
        already use, instead of a synthetic identity the rest of the app
        never sees. The older patient-links bridge stays as a fallback only
        for snapshots that don't match an existing case (e.g. a Monday row
        this pipeline never created).
        """
        if snapshot.referral_id:
            return snapshot
        case = None
        if snapshot.monday_item_id:
            case = self.store.workflow_case_by_monday_item_id(snapshot.monday_item_id)
        if case is None and snapshot.drk_patient_id:
            case = self.store.workflow_case_by_drk_patient_id(snapshot.drk_patient_id)
        if case is not None:
            return snapshot.model_copy(update={"referral_id": case.case_id})
        entity_id = self.store.find_entity_id(
            monday_item_id=snapshot.monday_item_id,
            drk_patient_id=snapshot.drk_patient_id,
        )
        if entity_id:
            return snapshot.model_copy(update={"referral_id": entity_id})
        prefix = "monday" if snapshot.monday_item_id else "drk" if snapshot.drk_patient_id else snapshot.source
        return snapshot.model_copy(update={"referral_id": f"{prefix}:{snapshot.external_id}"})

    def _upsert_link(self, snapshot: OperationalSnapshot, *, now: datetime) -> None:
        self.store.upsert_patient_link(
            PatientLink(
                entity_id=snapshot.entity_id,
                monday_item_id=snapshot.monday_item_id,
                drk_patient_id=snapshot.drk_patient_id,
                patient_label=snapshot.patient_label,
                identity_digest=_identity_digest(snapshot),
                updated_at=now,
            )
        )


def _notification(
    exception: WorkflowException,
    *,
    snapshot: OperationalSnapshot,
    recipient: str,
    now: datetime,
) -> NotificationRecord:
    label = snapshot.patient_label or snapshot.entity_id
    subject = f"[WCW WORKFLOW] {exception.exception_type.replace('_', ' ').title()}"
    lines = [
        f"Patient: {label}",
        f"Exception: {exception.exception_type}",
        f"Severity: {exception.severity}",
        f"Case manager: {snapshot.case_manager or 'Not recorded'}",
        f"Provider: {snapshot.provider or 'Not recorded'}",
        f"Appointment: {snapshot.appointment_date or 'Not recorded'}",
        f"Visit status: {snapshot.visit_status or snapshot.visit_outcome or 'Not recorded'}",
        "",
        "This alert reports recorded system state. A human must decide and record the next action.",
    ]
    key_material = f"{exception.exception_key}|{recipient.casefold()}"
    return NotificationRecord(
        notification_key=hashlib.sha256(key_material.encode("utf-8")).hexdigest(),
        exception_key=exception.exception_key,
        recipient=recipient,
        subject=subject,
        body="\n".join(lines),
        created_at=now,
    )


def _identity_digest(snapshot: OperationalSnapshot) -> str | None:
    name = " ".join((snapshot.patient_label or "").casefold().split())
    dob = "".join(ch for ch in str(snapshot.details.get("dob") or "") if ch.isdigit())
    if not name or not dob:
        return None
    return hashlib.sha256(f"{name}|{dob}".encode("utf-8")).hexdigest()


def _operational_details(snapshot: OperationalSnapshot) -> dict[str, object]:
    return {
        "patient_label": snapshot.patient_label,
        "monday_item_id": snapshot.monday_item_id,
        "case_manager": snapshot.case_manager,
        "provider": snapshot.provider,
        "due_date": snapshot.due_date,
        "appointment_date": snapshot.appointment_date,
        "scheduled_status": snapshot.scheduled_status,
        "scheduling_complete": snapshot.scheduling_complete,
        "visit_status": snapshot.visit_status,
    }


def _became_sent_to_provider(
    previous: OperationalSnapshot,
    current: OperationalSnapshot,
) -> bool:
    return not _positive(previous.referral_sent_to_provider) and _positive(
        current.referral_sent_to_provider
    )


def _positive(value: object) -> bool:
    return " ".join(str(value or "").casefold().split()) in {
        "yes",
        "sent",
        "complete",
        "completed",
        "true",
    }
