"""Typed records shared by monitoring rules, sources, and persistence."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OperationalSnapshot(StrictModel):
    source: Literal["monday", "drk", "schedule"]
    external_id: str
    observed_at: datetime
    referral_id: str | None = None
    patient_label: str | None = None
    monday_item_id: str | None = None
    drk_patient_id: str | None = None
    group: str | None = None
    case_manager: str | None = None
    provider: str | None = None
    sent_to_case_manager: str | None = None
    referral_sent_to_provider: str | None = None
    due_date: str | None = None
    appointment_date: str | None = None
    scheduling_complete: str | None = None
    scheduled_status: str | None = None
    visit_status: str | None = None
    visit_outcome: str | None = None
    visit_event_id: str | None = None
    progress_note_status: str | None = None
    qa_hold_reason: str | None = None
    discharge_reason: str | None = None
    source_updated_at: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    @property
    def entity_id(self) -> str:
        return self.referral_id or self.monday_item_id or self.drk_patient_id or self.external_id

    @property
    def payload_digest(self) -> str:
        payload = self.model_dump(mode="json", exclude={"observed_at"})
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class WorkflowEvent(StrictModel):
    event_key: str
    event_type: str
    entity_id: str
    source: str
    occurred_at: datetime
    details: dict[str, Any] = Field(default_factory=dict)


class WorkflowCase(StrictModel):
    """Minimal cross-stage identity and current state for one referral."""

    case_id: str
    source_ref: str
    source: Literal["outlook-graph", "eml-fixture"]
    attachment_sha256: str | None = None
    referral_id: str | None = None
    patient_label: str | None = None
    current_stage: int = Field(default=1, ge=1, le=7)
    status: Literal[
        "discovered",
        "processing",
        "awaiting_partner_contact",
        "needs_attention",
        "completed",
        "failed",
        "awaiting_assignment",
        "awaiting_handoff",
        "handoff_in_progress",
        "handoff_blocked",
    ]
    source_received_at: datetime | None = None
    monday_item_id: str | None = None
    drk_patient_id: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class WorkflowWorkItem(StrictModel):
    """One operator-visible action, not a copy of a destination record."""

    work_item_id: str
    case_id: str
    stage: int = Field(ge=2, le=7)
    step_id: str
    owner_role: Literal["case_manager", "intake_team", "system"]
    status: Literal["waiting", "ready", "completed", "blocked", "failed"]
    recommended_assignee: str | None = None
    recommendation_reason: str | None = None
    assigned_to: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class WorkflowDecision(StrictModel):
    """Append-only record of a person crossing a workflow gate."""

    decision_id: str
    idempotency_key: str
    case_id: str
    stage: int = Field(ge=2, le=7)
    step_id: str
    decision_type: str
    selected_value: dict[str, Any]
    decided_by: str
    created_at: datetime


class ExternalOperation(StrictModel):
    """Independently retryable destination action."""

    operation_id: str
    idempotency_key: str
    case_id: str
    stage: int = Field(ge=2, le=7)
    operation_type: str
    status: Literal["ready", "running", "succeeded", "blocked", "failed"]
    request_payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    attempts: int = Field(default=0, ge=0)
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class OutboundAcknowledgement(StrictModel):
    """Idempotency and delivery state for the one partner acknowledgement."""

    case_id: str
    recipient: str
    payload_digest: str
    status: Literal["pending", "sending", "sent", "failed"] = "pending"
    attempts: int = Field(default=0, ge=0)
    lease_until: datetime | None = None
    sent_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class WorkflowException(StrictModel):
    exception_key: str
    exception_type: str
    entity_id: str
    severity: Literal["info", "warning", "critical"] = "warning"
    status: Literal["open", "resolved"] = "open"
    first_seen_at: datetime
    last_seen_at: datetime
    resolved_at: datetime | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class NotificationRecord(StrictModel):
    notification_key: str
    exception_key: str
    recipient: str
    subject: str
    body: str
    created_at: datetime
    status: Literal["pending", "sent", "failed"] = "pending"
    attempts: int = Field(default=0, ge=0)
    last_error: str | None = None


class PatientLink(StrictModel):
    entity_id: str
    monday_item_id: str | None = None
    drk_patient_id: str | None = None
    patient_label: str | None = None
    identity_digest: str | None = None
    updated_at: datetime


class WorkflowCounter(StrictModel):
    entity_id: str
    counter_name: str
    value: int = Field(ge=0)
    updated_at: datetime


class ComponentHealth(StrictModel):
    component: str
    status: Literal["healthy", "degraded", "failed"]
    last_attempt_at: datetime
    last_success_at: datetime | None = None
    consecutive_failures: int = Field(default=0, ge=0)
    duration_seconds: float | None = None
    error_code: str | None = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
