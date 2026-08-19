"""Heartbeat-refreshed cache for the Stage 2/3 read projections.

Same pattern as IntakeInboxFeed's heartbeat: WorkflowExecutionService.
assignments()/handoffs() each do a RoutingWorkflowStore existence-check
against Supabase per case or work item, so an ordinary UI poll landing on
one of these directly could block on N sequential remote round trips. Only
a background heartbeat (or an explicit refresh_now(), used right after a
write) ever calls into the service; every other read is a pure cache read.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

from referral_pipeline.workflow.service import WorkflowExecutionService

_EMPTY_ASSIGNMENTS: dict[str, Any] = {
    "items": [],
    "case_managers": [],
    "recommendation_available": False,
    "recommendation_note": "WCW territory rules are not connected.",
}
_EMPTY_HANDOFFS: dict[str, Any] = {"items": []}


class WorkflowExecutionCache:
    def __init__(
        self,
        service: WorkflowExecutionService,
        *,
        heartbeat_interval_seconds: float = 15.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat_interval_seconds must be positive")
        self._service = service
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._assignments_limit = 100
        self._handoffs_limit = 100
        self._cached_assignments: dict[str, Any] | None = None
        self._cached_handoffs: dict[str, Any] | None = None
        self._heartbeat_thread: threading.Thread | None = None
        self._heartbeat_stop = threading.Event()

    def assignments(self, *, limit: int = 100) -> dict[str, Any]:
        with self._lock:
            self._assignments_limit = max(self._assignments_limit, limit)
            cached = self._cached_assignments
        return dict(_EMPTY_ASSIGNMENTS) if cached is None else cached

    def handoffs(self, *, limit: int = 100) -> dict[str, Any]:
        with self._lock:
            self._handoffs_limit = max(self._handoffs_limit, limit)
            cached = self._cached_handoffs
        return dict(_EMPTY_HANDOFFS) if cached is None else cached

    def refresh_now(self) -> None:
        """Pull a fresh projection immediately. Never raises."""
        with self._lock:
            assignments_limit = self._assignments_limit
            handoffs_limit = self._handoffs_limit
        try:
            assignments = self._service.assignments(limit=assignments_limit)
        except Exception:  # noqa: BLE001 - keep the previous cache on failure
            assignments = None
        try:
            handoffs = self._service.handoffs(limit=handoffs_limit)
        except Exception:  # noqa: BLE001 - keep the previous cache on failure
            handoffs = None
        with self._lock:
            if assignments is not None:
                self._cached_assignments = assignments
            if handoffs is not None:
                self._cached_handoffs = handoffs

    def start_heartbeat(self) -> None:
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_stop.clear()
        thread = threading.Thread(
            target=self._heartbeat_loop,
            name="workflow-execution-cache-heartbeat",
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
            self.refresh_now()
            self._heartbeat_stop.wait(self._heartbeat_interval_seconds)
