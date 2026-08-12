"""Read-only projection of Outlook PDF arrivals for the operations console."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

from Outlook.graph import OutlookGraphClient
from Outlook.mail import InboundPdfMetadata
from referral_pipeline.monitoring.store import WorkflowStore
from referral_pipeline.stage_one.identity import source_ref


class IntakeInboxFeed:
    """Fetch and briefly cache safe attachment metadata from the test inbox."""

    def __init__(
        self,
        client_factory: Callable[[], OutlookGraphClient],
        *,
        cache_ttl_seconds: int = 30,
        clock: Callable[[], float] = time.monotonic,
        workflow_store: WorkflowStore | None = None,
    ) -> None:
        if cache_ttl_seconds < 0:
            raise ValueError("cache_ttl_seconds cannot be negative")
        self._client_factory = client_factory
        self._cache_ttl_seconds = cache_ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._cached_at = 0.0
        self._cached_limit = 0
        self._cached_payload: dict[str, Any] | None = None
        self._references: dict[str, InboundPdfMetadata] = {}
        self._workflow_store = workflow_store

    def read(self, *, limit: int = 10, force: bool = False) -> dict[str, Any]:
        safe_limit = min(max(limit, 1), 25)
        with self._lock:
            now = self._clock()
            cache_valid = (
                not force
                and self._cached_payload is not None
                and self._cached_limit >= safe_limit
                and now - self._cached_at < self._cache_ttl_seconds
            )
            if cache_valid:
                return _with_limited_referrals(self._cached_payload, safe_limit)

            attachments = self._client_factory().list_inbox_pdf_metadata(
                max_messages=safe_limit,
            )
            references = {
                source_ref(attachment.message_id, attachment.attachment_id): attachment
                for attachment in attachments
            }
            referrals = [
                {
                    "id": referral_id,
                    "filename": attachment.filename,
                    "subject": attachment.subject,
                    "sender": attachment.sender,
                    "received_at": attachment.received_at,
                    "source": "testing-infobox",
                    **self._workflow_projection(referral_id),
                }
                for referral_id, attachment in references.items()
            ]
            referrals.sort(key=lambda item: item.get("received_at") or "", reverse=True)
            payload = {
                "connected": True,
                "source": "testing-infobox",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "referrals": referrals,
            }
            self._cached_at = now
            self._cached_limit = safe_limit
            self._cached_payload = payload
            self._references = references
            return payload

    def read_pdf(self, referral_id: str) -> tuple[str, bytes]:
        with self._lock:
            metadata = self._references.get(referral_id)
        if metadata is None:
            raise KeyError(referral_id)
        attachment = self._client_factory().download_pdf_attachment(metadata)
        return attachment.safe_filename, attachment.content

    def read_timeline(self, referral_id: str) -> dict[str, Any]:
        if self._workflow_store is None:
            raise KeyError(referral_id)
        case = self._workflow_store.workflow_case_by_source_ref(referral_id)
        if case is None:
            case = self._workflow_store.workflow_case(referral_id)
        if case is None:
            raise KeyError(referral_id)
        events = self._workflow_store.list_events(case.case_id, limit=100)
        return {
            "case": case.model_dump(mode="json"),
            "steps": _step_projection(events),
            "events": [event.model_dump(mode="json") for event in events],
        }

    def list_cases(self, *, limit: int = 100) -> dict[str, Any]:
        if self._workflow_store is None:
            return {"cases": []}
        return {
            "cases": [
                case.model_dump(mode="json")
                for case in self._workflow_store.list_workflow_cases(limit=limit)
            ]
        }

    def _workflow_projection(self, referral_id: str) -> dict[str, Any]:
        if self._workflow_store is None:
            return {"status": "pending_extraction", "case_id": None, "steps": {}}
        case = self._workflow_store.workflow_case_by_source_ref(referral_id)
        if case is None:
            return {"status": "pending_extraction", "case_id": None, "steps": {}}
        events = self._workflow_store.list_events(case.case_id, limit=100)
        return {
            "status": case.status,
            "case_id": case.case_id,
            "patient_label": case.patient_label,
            "steps": _step_projection(events),
        }


def _with_limited_referrals(payload: dict[str, Any], limit: int) -> dict[str, Any]:
    return {
        **payload,
        "referrals": list(payload.get("referrals") or [])[:limit],
    }


def _step_projection(events: list[Any]) -> dict[str, dict[str, Any]]:
    mapping = {
        "referral_received": ("receive-referral", "Referral email identified", "done"),
        "extraction_started": ("extract-and-verify", "Extracting referral details", "current"),
        "extraction_completed": ("extract-and-verify", "Referral details extracted", "done"),
        "monday_duplicate_checked": ("check-monday", "Monday duplicate check complete", "done"),
        "drk_duplicate_checked": ("check-drk", "DRK chart check complete", "done"),
        "partner_contact_confirmation_requested": (
            "confirm-referral-contacted",
            "Waiting for referral partner follow-up",
            "current",
        ),
        "partner_contact_confirmed": (
            "confirm-referral-contacted",
            "Referral partner contact confirmed",
            "done",
        ),
        "partner_acknowledgement_sent": (
            "confirm-referral-contacted",
            "Referral partner acknowledgement sent",
            "done",
        ),
        "stage_one_failed": ("extract-and-verify", "Stage 1 needs attention", "blocked"),
    }
    steps: dict[str, dict[str, Any]] = {}
    for event in events:
        projected = mapping.get(event.event_type)
        if projected is None:
            continue
        step_id, summary, status = projected
        steps[step_id] = {
            "step_id": step_id,
            "status": status,
            "summary": summary,
            "occurred_at": event.occurred_at.isoformat(),
            "details": event.details,
        }
    return steps
