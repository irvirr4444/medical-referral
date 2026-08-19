"""Read-only projection of Outlook PDF arrivals for the operations console."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

from Outlook.graph import OutlookGraphClient
from Outlook.mail import InboundPdfMetadata
from referral_pipeline.monitoring.routing import persistence_for
from referral_pipeline.monitoring.store import WorkflowStore
from referral_pipeline.stage_one.identity import source_ref


class IntakeInboxFeed:
    """Cache safe attachment metadata from the test inbox.

    A dedicated heartbeat thread (start_heartbeat/stop_heartbeat) is the only
    thing that talks to Outlook Graph on its own clock. Ordinary reads
    (force=False, what every UI poll uses) never fetch and never block on
    Graph latency -- they only ever look at whatever the heartbeat last
    cached. Only an explicit force=True (the "Refresh" button, or the
    heartbeat itself) performs a real fetch. This keeps a slow or throttled
    Graph call from ever stalling a live UI poll.
    """

    def __init__(
        self,
        client_factory: Callable[[], OutlookGraphClient],
        *,
        cache_ttl_seconds: int = 30,
        refresh_wait_timeout_seconds: float = 45.0,
        heartbeat_interval_seconds: float = 15.0,
        clock: Callable[[], float] = time.monotonic,
        workflow_store: WorkflowStore | None = None,
    ) -> None:
        if cache_ttl_seconds < 0:
            raise ValueError("cache_ttl_seconds cannot be negative")
        if refresh_wait_timeout_seconds <= 0:
            raise ValueError("refresh_wait_timeout_seconds must be positive")
        if heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat_interval_seconds must be positive")
        self._client_factory = client_factory
        self._cache_ttl_seconds = cache_ttl_seconds
        self._refresh_wait_timeout_seconds = refresh_wait_timeout_seconds
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._refresh_finished = threading.Event()
        self._refresh_finished.set()
        self._refreshing = False
        self._cached_at = 0.0
        self._cached_limit = 0
        self._cached_payload: dict[str, Any] | None = None
        self._references: dict[str, InboundPdfMetadata] = {}
        self._workflow_store = workflow_store
        self._heartbeat_thread: threading.Thread | None = None
        self._heartbeat_stop = threading.Event()
        self._heartbeat_limit = 25

    def read(self, *, limit: int = 10, force: bool = False) -> dict[str, Any]:
        safe_limit = min(max(limit, 1), 25)
        if force:
            return self._refresh_and_read(safe_limit)
        with self._lock:
            have_cache = self._cached_payload is not None and self._cached_limit >= safe_limit
            snapshot = _copy_cached_payload(self._cached_payload) if have_cache else None
            stale = have_cache and self._clock() - self._cached_at >= self._cache_ttl_seconds
        if snapshot is None:
            return _empty_payload()
        payload = _with_limited_referrals(snapshot, safe_limit)
        if stale:
            payload["stale"] = True
        return payload

    def start_heartbeat(self, *, limit: int = 25) -> None:
        """Keep the cache warm on a fixed clock, independent of any request."""
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_limit = min(max(limit, 1), 25)
        self._heartbeat_stop.clear()
        thread = threading.Thread(
            target=self._heartbeat_loop,
            name="intake-inbox-feed-heartbeat",
            daemon=True,
        )
        self._heartbeat_thread = thread
        thread.start()

    def stop_heartbeat(self) -> None:
        self._heartbeat_stop.set()
        thread = self._heartbeat_thread
        if thread is not None:
            thread.join(timeout=2)
        self._heartbeat_thread = None

    def _heartbeat_loop(self) -> None:
        while not self._heartbeat_stop.is_set():
            try:
                self._refresh_and_read(self._heartbeat_limit)
            except Exception:  # noqa: BLE001 - the heartbeat must survive a bad cycle
                pass
            self._heartbeat_stop.wait(self._heartbeat_interval_seconds)

    def _refresh_and_read(self, safe_limit: int) -> dict[str, Any]:
        while True:
            snapshot: dict[str, Any] | None = None
            wait_for_refresh = False
            become_refresher = False
            served_stale = False
            with self._lock:
                if self._refreshing:
                    if self._cached_payload is not None:
                        snapshot = _copy_cached_payload(self._cached_payload)
                        served_stale = True
                    else:
                        wait_for_refresh = True
                else:
                    become_refresher = True
                    self._refreshing = True
                    self._refresh_finished.clear()

            if snapshot is not None:
                payload = _with_limited_referrals(snapshot, safe_limit)
                if served_stale:
                    payload["stale"] = True
                return payload
            if wait_for_refresh:
                if not self._refresh_finished.wait(
                    timeout=self._refresh_wait_timeout_seconds,
                ):
                    raise TimeoutError(
                        "Timed out waiting for the test infobox refresh to finish"
                    )
                # The fetch we waited for just finished (or failed). Use
                # whatever it left cached instead of starting a second,
                # redundant fetch of our own -- only retry ourselves if it
                # failed and left nothing behind.
                with self._lock:
                    settled = (
                        _copy_cached_payload(self._cached_payload)
                        if self._cached_payload is not None
                        else None
                    )
                if settled is not None:
                    return _with_limited_referrals(settled, safe_limit)
                continue

            assert become_refresher
            try:
                raw_payload, references = self._fetch_mailbox_metadata(safe_limit)
                # The only I/O-heavy step (case + event + persistence lookups
                # against RoutingWorkflowStore, which checks Supabase on
                # nearly every call) happens exactly once per fetch cycle
                # here, never per read.
                projected = self._with_current_workflow(raw_payload, safe_limit)
                with self._lock:
                    self._cached_payload = projected
                    self._cached_limit = safe_limit
                    self._cached_at = self._clock()
                    self._references = references
            finally:
                with self._lock:
                    self._refreshing = False
                    self._refresh_finished.set()
            return _with_limited_referrals(_copy_cached_payload(projected), safe_limit)

    def _fetch_mailbox_metadata(
        self, safe_limit: int
    ) -> tuple[dict[str, Any], dict[str, InboundPdfMetadata]]:
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
        return payload, references

    def _with_current_workflow(
        self,
        payload: dict[str, Any],
        limit: int,
    ) -> dict[str, Any]:
        """Project raw Outlook metadata into current workflow state.

        Called exactly once per real fetch cycle (never per read): looks up
        every case once (list_workflow_cases) instead of once per referral,
        since RoutingWorkflowStore checks Supabase on every single-case
        lookup and that used to mean N sequential remote round trips here.
        """
        cases_by_source_ref = self._cases_by_source_ref()
        referrals = []
        for cached in list(payload.get("referrals") or [])[:limit]:
            referral_id = str(cached.get("id") or "")
            metadata = {
                key: value
                for key, value in cached.items()
                if key not in {"status", "case_id", "patient_label", "steps", "persistence"}
            }
            projection = self._workflow_projection(
                referral_id, case=cases_by_source_ref.get(referral_id)
            )
            referrals.append({**metadata, **projection})
        return {**payload, "referrals": referrals}

    def _cases_by_source_ref(self) -> dict[str, Any]:
        if self._workflow_store is None:
            return {}
        try:
            cases = self._workflow_store.list_workflow_cases(limit=500)
        except Exception:  # noqa: BLE001 - projection falls back to per-id lookups
            return {}
        return {case.source_ref: case for case in cases}

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
            "case": {
                **case.model_dump(mode="json"),
                "persistence": persistence_for(self._workflow_store, case.case_id),
            },
            "steps": _step_projection(events, case_status=case.status),
            "events": [event.model_dump(mode="json") for event in events],
        }

    def list_cases(self, *, limit: int = 100) -> dict[str, Any]:
        if self._workflow_store is None:
            return {"cases": []}
        return {
            "cases": [
                {
                    **case.model_dump(mode="json"),
                    "persistence": persistence_for(self._workflow_store, case.case_id),
                }
                for case in self._workflow_store.list_workflow_cases(limit=limit)
            ]
        }

    def _workflow_projection(self, referral_id: str, *, case: Any | None = None) -> dict[str, Any]:
        if self._workflow_store is None:
            return {"status": "pending_extraction", "case_id": None, "steps": {}, "persistence": "none"}
        if case is None:
            case = self._workflow_store.workflow_case_by_source_ref(referral_id)
        if case is None:
            return {"status": "pending_extraction", "case_id": None, "steps": {}, "persistence": "none"}
        events = self._workflow_store.list_events(case.case_id, limit=100)
        effective_status = "completed" if case.current_stage > 1 else case.status
        return {
            "status": effective_status,
            "case_id": case.case_id,
            "patient_label": case.patient_label,
            "persistence": persistence_for(self._workflow_store, case.case_id),
            "steps": _step_projection(events, case_status=effective_status),
        }


def _empty_payload() -> dict[str, Any]:
    return {
        "connected": True,
        "source": "testing-infobox",
        "fetched_at": None,
        "referrals": [],
        "stale": True,
    }


def _copy_cached_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        **payload,
        "referrals": [dict(item) for item in payload.get("referrals") or []],
    }


def _with_limited_referrals(payload: dict[str, Any], limit: int) -> dict[str, Any]:
    return {
        **payload,
        "referrals": list(payload.get("referrals") or [])[:limit],
    }


def _step_projection(
    events: list[Any],
    *,
    case_status: str | None = None,
) -> dict[str, dict[str, Any]]:
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
        "stage_one_retry_scheduled": (
            "extract-and-verify",
            "Stage 1 dependency retry scheduled",
            "current",
        ),
        "stage_one_failed": ("extract-and-verify", "Stage 1 needs attention", "blocked"),
    }
    steps: dict[str, dict[str, Any]] = {}
    for event in events:
        projected = mapping.get(event.event_type)
        if projected is None:
            continue
        step_id, summary, status = projected
        details = dict(event.details or {})
        if event.event_type in {"monday_duplicate_checked", "drk_duplicate_checked"}:
            summary, details = _duplicate_check_presentation(event.event_type, details)
        elif event.event_type == "partner_contact_confirmed":
            summary, details = _partner_contact_presentation(details)
        elif event.event_type == "partner_contact_confirmation_requested":
            details = {
                "assigned_to": details.get("recipient"),
            }
        steps[step_id] = {
            "step_id": step_id,
            "status": status,
            "summary": summary,
            "occurred_at": event.occurred_at.isoformat(),
            "details": details,
        }
    extraction = steps.get("extract-and-verify")
    if extraction is not None and extraction["status"] == "blocked":
        if case_status == "processing":
            steps["extract-and-verify"] = {
                "step_id": "extract-and-verify",
                "status": "current",
                "summary": "Retrying referral processing",
                "occurred_at": extraction["occurred_at"],
                "details": {},
            }
        elif case_status in {"awaiting_partner_contact", "completed"}:
            completed = next(
                (
                    event
                    for event in reversed(events)
                    if event.event_type == "extraction_completed"
                ),
                None,
            )
            if completed is not None:
                steps["extract-and-verify"] = {
                    "step_id": "extract-and-verify",
                    "status": "done",
                    "summary": "Referral details extracted",
                    "occurred_at": completed.occurred_at.isoformat(),
                    "details": dict(completed.details or {}),
                }
    return steps


def _partner_contact_presentation(
    details: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    outcome = str(details.get("contact_outcome") or "reached")
    presentations = {
        "reached": ("Referral partner reached", "Reached"),
        "not_reached": ("Referral partner not reached", "Not reached"),
        "information_still_missing": (
            "Referral information still missing",
            "Information still missing",
        ),
    }
    summary, label = presentations.get(
        outcome,
        ("Referral partner follow-up recorded", "Follow-up recorded"),
    )
    return summary, {
        "confirmed_by": details.get("confirmed_by"),
        "contact_outcome": label,
    }


def _duplicate_check_presentation(
    event_type: str,
    details: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    code = str(details.get("status") or "unknown")
    is_monday = event_type == "monday_duplicate_checked"
    system = "Monday.com" if is_monday else "DRK"
    labels = {
        "no_candidates_found": "No matching patient found",
        "clear_to_create": "No matching chart found",
        "duplicate_found": "Possible existing record found",
        "manual_review_required": "Manual identity review required",
        "skipped_missing_identity": "Check could not run because identity is incomplete",
        "disabled": "Check disabled",
    }
    label = labels.get(code, "Check completed")
    if code in {"no_candidates_found", "clear_to_create"}:
        summary = f"No matching {system} {'patient' if is_monday else 'chart'} found"
    elif code == "duplicate_found":
        summary = f"Possible existing {system} {'patient' if is_monday else 'chart'} found"
    else:
        summary = f"{system} identity check needs review" if code != "disabled" else f"{system} check disabled"

    presented = {**details, "status_code": code, "status": label}
    reason = str(details.get("reason") or "")
    if reason:
        presented["reason_code"] = reason
        presented["reason"] = {
            "stable_zero_search_results": "Search completed with no matching records",
        }.get(reason, "See technical details for the recorded check result")
    return summary, presented
