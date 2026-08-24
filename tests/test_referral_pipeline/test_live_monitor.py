from __future__ import annotations

import threading
from pathlib import Path

from referral_pipeline.live_monitor import LiveInboxMonitor, LiveInboxMonitorConfig


def test_live_monitor_is_single_instance_and_stops_cooperatively(tmp_path: Path) -> None:
    entered = threading.Event()
    runner_calls = 0

    def fake_runner(*, stop_event, on_cycle_start, on_result, **_kwargs):
        nonlocal runner_calls
        runner_calls += 1
        on_cycle_start("poll")
        entered.set()
        assert stop_event.wait(2)
        on_result({"kind": "poll", "status": "ok", "elapsed_seconds": 0.1})
        return []

    monitor = LiveInboxMonitor(
        LiveInboxMonitorConfig(data_root=tmp_path, review_recipient="reviewer@example.test"),
        runner=fake_runner,
    )

    monitor.start()
    assert entered.wait(1)
    assert monitor.status()["state"] == "processing"
    monitor.start()
    assert runner_calls == 1

    stopped = monitor.stop(wait=True, timeout=2)
    assert stopped["state"] == "stopped"
    assert stopped["cycle_count"] == 1
    assert stopped["last_cycle"]["kind"] == "poll"
    assert stopped["safety"]["monday_writes"] is False
    assert stopped["safety"]["drk_writes"] is False


def test_live_monitor_surfaces_runner_failure_without_exposing_message(tmp_path: Path) -> None:
    failed = threading.Event()

    def fake_runner(**_kwargs):
        failed.set()
        raise RuntimeError("secret mailbox details")

    monitor = LiveInboxMonitor(
        LiveInboxMonitorConfig(data_root=tmp_path, review_recipient="reviewer@example.test"),
        runner=fake_runner,
    )
    monitor.start()
    assert failed.wait(1)
    for _ in range(100):
        status = monitor.status()
        if status["state"] == "error":
            break
        threading.Event().wait(0.01)

    assert status["state"] == "error"
    assert status["error_type"] == "RuntimeError"
    assert "secret" not in str(status)


def test_live_monitor_refuses_to_start_without_internal_reviewer(tmp_path: Path) -> None:
    monitor = LiveInboxMonitor(LiveInboxMonitorConfig(data_root=tmp_path))

    status = monitor.start()

    assert status["state"] == "error"
    assert status["error_type"] == "ReviewRecipientNotConfigured"
