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
    attempts: int = 0
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
    value: int
    updated_at: datetime


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
