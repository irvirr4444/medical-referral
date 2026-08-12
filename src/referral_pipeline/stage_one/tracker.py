"""Small Stage 1 facade over the shared workflow store."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from referral_pipeline.monitoring.models import WorkflowCase, WorkflowEvent
from referral_pipeline.monitoring.store import WorkflowStore
from referral_pipeline.stage_one.identity import case_id_for_source, source_ref


class StageOneTracker:
    def __init__(self, store: WorkflowStore) -> None:
        self.store = store

    def discover(self, attachment: Any) -> WorkflowCase:
        now = _utc_now()
        case_id = case_id_for_source(attachment.message_id, attachment.attachment_id)
        existing = self.store.workflow_case(case_id)
        case = WorkflowCase(
            case_id=case_id,
            source_ref=source_ref(attachment.message_id, attachment.attachment_id),
            source=attachment.source,
            attachment_sha256=getattr(attachment, "sha256", None),
            referral_id=None if existing is None else existing.referral_id,
            patient_label=None if existing is None else existing.patient_label,
            current_stage=1,
            status="discovered" if existing is None else existing.status,
            source_received_at=_parse_datetime(getattr(attachment, "received_at", None)),
            monday_item_id=None if existing is None else existing.monday_item_id,
            drk_patient_id=None if existing is None else existing.drk_patient_id,
            created_at=now if existing is None else existing.created_at,
            updated_at=now,
            completed_at=None if existing is None else existing.completed_at,
        )
        stored = self.store.upsert_workflow_case(case)
        self.record(
            stored.case_id,
            "referral_received",
            source="outlook" if attachment.source == "outlook-graph" else "fixture",
            event_key=f"stage1:{stored.source_ref}:received",
            details={
                "filename": getattr(attachment, "safe_filename", None) or attachment.filename,
                "received_at": getattr(attachment, "received_at", None),
                "sender": getattr(attachment, "sender", None),
            },
        )
        return stored

    def processing_started(self, case: WorkflowCase) -> WorkflowCase:
        status = "completed" if case.status == "completed" else "processing"
        updated = case.model_copy(update={"status": status, "updated_at": _utc_now()})
        stored = self.store.upsert_workflow_case(updated)
        self.record(
            case.case_id,
            "extraction_started",
            source="extractor",
            event_key=f"stage1:{case.source_ref}:extraction-started",
        )
        return stored

    def extraction_completed(self, case: WorkflowCase, manifest: dict[str, Any]) -> WorkflowCase:
        now = _utc_now()
        referral = _load_manifest_referral(manifest)
        patient_label = _text(referral.get("patient_name"))
        outcome = _text(manifest.get("outcome")) or "manual_review_required"
        status = (
            "completed"
            if case.status == "completed"
            else "needs_attention" if outcome != "ready_for_human_approval" else "processing"
        )
        updated = case.model_copy(
            update={
                "referral_id": _text(manifest.get("referral_id")),
                "patient_label": patient_label,
                "status": status,
                "updated_at": now,
            }
        )
        stored = self.store.upsert_workflow_case(updated)
        self.record(
            case.case_id,
            "extraction_completed",
            source="extractor",
            event_key=f"stage1:{case.source_ref}:extraction-completed",
            details={
                "outcome": outcome,
                "patient_label": patient_label,
                "fields": _stage_one_fields(referral),
            },
        )
        self.record(
            case.case_id,
            "monday_duplicate_checked",
            source="monday",
            event_key=f"stage1:{case.source_ref}:monday-duplicate",
            details={
                "status": manifest.get("duplicate_status"),
                "write_performed": False,
            },
        )
        return stored

    def drk_checked(self, case: WorkflowCase, decision: dict[str, Any]) -> None:
        self.record(
            case.case_id,
            "drk_duplicate_checked",
            source="drk",
            event_key=f"stage1:{case.source_ref}:drk-duplicate",
            details={
                "status": decision.get("status"),
                "reason": decision.get("reason"),
                "candidate_count": len(decision.get("candidate_patient_ids") or []),
                "write_performed": False,
            },
        )

    def acknowledgement_sent(self, case: WorkflowCase, *, recipient: str) -> WorkflowCase:
        now = _utc_now()
        updated = case.model_copy(
            update={"status": "completed", "updated_at": now, "completed_at": now}
        )
        stored = self.store.upsert_workflow_case(updated)
        self.record(
            case.case_id,
            "partner_acknowledgement_sent",
            source="outlook",
            event_key=f"stage1:{case.source_ref}:partner-acknowledgement",
            details={"recipient": recipient, "delivery": "accepted_by_graph"},
        )
        return stored

    def contact_confirmation_requested(
        self,
        case: WorkflowCase,
        *,
        recipient: str,
        review_id: str,
    ) -> WorkflowCase:
        now = _utc_now()
        updated = case.model_copy(
            update={"status": "awaiting_partner_contact", "updated_at": now}
        )
        stored = self.store.upsert_workflow_case(updated)
        self.record(
            case.case_id,
            "partner_contact_confirmation_requested",
            source="outlook",
            event_key=f"stage1:{case.source_ref}:partner-contact-requested",
            details={"recipient": recipient, "review_id": review_id},
        )
        return stored

    def partner_contact_confirmed(
        self,
        case_id: str,
        *,
        confirmed_by: str,
        message_id: str,
    ) -> WorkflowCase | None:
        case = self.store.workflow_case(case_id)
        if case is None:
            return None
        now = _utc_now()
        stored = self.store.upsert_workflow_case(
            case.model_copy(
                update={"status": "completed", "updated_at": now, "completed_at": now}
            )
        )
        self.record(
            case.case_id,
            "partner_contact_confirmed",
            source="outlook",
            event_key=f"stage1:{case.source_ref}:partner-contact-confirmed:{message_id}",
            details={"confirmed_by": confirmed_by, "confirmation_message_id": message_id},
        )
        return stored

    def failed(self, case: WorkflowCase, *, event_type: str, error_code: str) -> WorkflowCase:
        updated = case.model_copy(update={"status": "failed", "updated_at": _utc_now()})
        stored = self.store.upsert_workflow_case(updated)
        self.record(
            case.case_id,
            event_type,
            source="pipeline",
            event_key=f"stage1:{case.source_ref}:{event_type}",
            details={"error_code": error_code},
        )
        return stored

    def record(
        self,
        case_id: str,
        event_type: str,
        *,
        source: str,
        event_key: str,
        details: dict[str, Any] | None = None,
    ) -> bool:
        return self.store.record_event(
            WorkflowEvent(
                event_key=event_key,
                event_type=event_type,
                entity_id=case_id,
                source=source,
                occurred_at=_utc_now(),
                details=details or {},
            )
        )


def acknowledgement_digest(*, case_id: str, recipient: str, template_version: str) -> str:
    value = f"{case_id}\0{recipient.casefold()}\0{template_version}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _load_manifest_referral(manifest: dict[str, Any]) -> dict[str, Any]:
    path = manifest.get("plan_path")
    if not path:
        return {}
    try:
        import json
        from pathlib import Path

        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    referral = payload.get("referral") if isinstance(payload, dict) else None
    return referral if isinstance(referral, dict) else {}


def _stage_one_fields(referral: dict[str, Any]) -> dict[str, Any]:
    return {
        name: referral.get(name)
        for name in (
            "patient_name",
            "patient_dob",
            "patient_phone",
            "patient_address",
            "referring_facility",
            "diagnosis_text",
            "insurance_provider",
        )
    }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _text(value: Any) -> str | None:
    return str(value).strip() if value is not None and str(value).strip() else None
