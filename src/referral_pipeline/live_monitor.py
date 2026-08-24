"""Controllable, single-instance Stage 1 inbox worker for local testing."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from referral_pipeline.worker import run_worker_loop


WorkerRunner = Callable[..., list[dict]]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class LiveInboxMonitorConfig:
    data_root: Path
    poll_interval_seconds: int = 60
    retry_interval_seconds: int = 60
    approval_interval_seconds: int = 30
    max_messages: int = 1
    max_retry_jobs: int = 10
    max_approval_messages: int = 100
    partner_acknowledgement: bool = False
    stage_one_drk_check: bool = False
    workflow_database_backend: str | None = None
    workflow_sqlite_path: Path | None = None
    review_recipient: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "poll_interval_seconds",
            "retry_interval_seconds",
            "approval_interval_seconds",
            "max_messages",
            "max_retry_jobs",
            "max_approval_messages",
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be at least 1")


class LiveInboxMonitor:
    """Own one cooperative worker thread and expose PHI-free runtime state."""

    def __init__(
        self,
        config: LiveInboxMonitorConfig,
        *,
        runner: WorkerRunner = run_worker_loop,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._config = config
        self._runner = runner
        self._now = now
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._generation = 0
        self._state = "stopped"
        self._started_at: datetime | None = None
        self._stopped_at: datetime | None = None
        self._last_heartbeat_at: datetime | None = None
        self._next_poll_at: datetime | None = None
        self._active_cycle: str | None = None
        self._last_cycle: dict[str, Any] | None = None
        self._cycle_count = 0
        self._error_type: str | None = None

    def start(self) -> dict[str, Any]:
        with self._lock:
            if not (self._config.review_recipient or "").strip():
                self._state = "error"
                self._error_type = "ReviewRecipientNotConfigured"
                return self.status()
            if self._thread is not None and self._thread.is_alive():
                return self.status()
            self._generation += 1
            generation = self._generation
            stop_event = threading.Event()
            self._stop_event = stop_event
            self._state = "starting"
            self._started_at = self._now()
            self._stopped_at = None
            self._last_heartbeat_at = self._started_at
            self._next_poll_at = self._started_at
            self._active_cycle = None
            self._error_type = None
            self._thread = threading.Thread(
                target=self._run,
                args=(generation, stop_event),
                name="stage-one-live-inbox-monitor",
                daemon=True,
            )
            self._thread.start()
            return self.status()

    def stop(self, *, wait: bool = False, timeout: float | None = None) -> dict[str, Any]:
        with self._lock:
            thread = self._thread
            stop_event = self._stop_event
            if thread is None or not thread.is_alive():
                self._state = "stopped"
                self._active_cycle = None
                self._next_poll_at = None
                return self.status()
            self._state = "stopping"
            if stop_event is not None:
                stop_event.set()
        if wait and thread is not threading.current_thread():
            thread.join(timeout=timeout)
        return self.status()

    def status(self) -> dict[str, Any]:
        with self._lock:
            thread_alive = self._thread is not None and self._thread.is_alive()
            return {
                "available": True,
                "state": self._state,
                "enabled": thread_alive and self._state not in {"stopping", "error"},
                "active_cycle": self._active_cycle,
                "started_at": _iso(self._started_at),
                "stopped_at": _iso(self._stopped_at),
                "last_heartbeat_at": _iso(self._last_heartbeat_at),
                "next_poll_at": _iso(self._next_poll_at),
                "cycle_count": self._cycle_count,
                "last_cycle": dict(self._last_cycle) if self._last_cycle else None,
                "error_type": self._error_type,
                "poll_interval_seconds": self._config.poll_interval_seconds,
                "max_messages": self._config.max_messages,
                "safety": {
                    "monday_writes": False,
                    "drk_writes": False,
                    "review_email": True,
                    "partner_acknowledgement": self._config.partner_acknowledgement,
                    "drk_duplicate_check": self._config.stage_one_drk_check,
                },
            }

    def _run(self, generation: int, stop_event: threading.Event) -> None:
        with self._lock:
            if generation != self._generation:
                return
            self._state = "monitoring"
            self._last_heartbeat_at = self._now()
        try:
            self._runner(
                data_root=self._config.data_root.resolve(),
                poll_interval_seconds=self._config.poll_interval_seconds,
                retry_interval_seconds=self._config.retry_interval_seconds,
                approval_interval_seconds=self._config.approval_interval_seconds,
                max_messages=self._config.max_messages,
                max_jobs=self._config.max_retry_jobs,
                max_approval_messages=self._config.max_approval_messages,
                execute_approvals=False,
                dry_run_approvals=False,
                monitor_enabled=False,
                health_enabled=True,
                partner_acknowledgement=self._config.partner_acknowledgement,
                stage_one_drk_check=self._config.stage_one_drk_check,
                workflow_database_backend=self._config.workflow_database_backend,
                workflow_sqlite_path=self._config.workflow_sqlite_path,
                review_recipient=self._config.review_recipient,
                stop_event=stop_event,
                on_cycle_start=self._on_cycle_start,
                on_result=self._on_result,
            )
        except Exception as error:  # noqa: BLE001 - state must surface worker failure
            with self._lock:
                if generation == self._generation:
                    self._state = "error"
                    self._error_type = type(error).__name__
                    self._last_heartbeat_at = self._now()
        finally:
            with self._lock:
                if generation == self._generation:
                    if self._state != "error":
                        self._state = "stopped"
                    self._active_cycle = None
                    self._next_poll_at = None
                    self._stopped_at = self._now()
                    self._last_heartbeat_at = self._stopped_at

    def _on_cycle_start(self, kind: str) -> None:
        with self._lock:
            self._state = "processing"
            self._active_cycle = kind
            self._last_heartbeat_at = self._now()

    def _on_result(self, result: dict) -> None:
        now = self._now()
        kind = str(result.get("kind") or "unknown")
        with self._lock:
            self._cycle_count += 1
            self._last_heartbeat_at = now
            self._active_cycle = None
            self._last_cycle = {
                "kind": kind,
                "status": str(result.get("status") or "unknown"),
                "completed_at": now.isoformat(),
                "elapsed_seconds": result.get("elapsed_seconds"),
            }
            if kind == "poll":
                self._next_poll_at = now + timedelta(
                    seconds=self._config.poll_interval_seconds
                )
            if self._state != "stopping":
                self._state = "monitoring"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
