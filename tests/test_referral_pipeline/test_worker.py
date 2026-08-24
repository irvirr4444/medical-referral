from __future__ import annotations

from referral_pipeline import worker
from referral_pipeline.monitoring.sqlite_store import SQLiteWorkflowStore


def test_worker_once_runs_poll_retries_and_safe_approval_poll(tmp_path, monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_main(argv: list[str]) -> int:
        calls.append(list(argv))
        return 0

    class FakeApprovalProcessor:
        def poll(self, *, max_messages: int, execute: bool, dry_run: bool):
            assert max_messages == 100
            assert execute is False
            assert dry_run is False
            return {
                "mode": "check_only",
                "accepted_confirmations": [],
                "ignored_confirmations": [],
                "executed": [],
            }

    results = worker.run_worker_loop(
        data_root=tmp_path / "data",
        poll_interval_seconds=60,
        retry_interval_seconds=30,
        max_messages=25,
        max_jobs=10,
        once=True,
        quiet=True,
        run_main=fake_main,
        sleep_fn=lambda _seconds: None,
        clock=lambda: 0.0,
        approval_processor_factory=lambda _state_db: FakeApprovalProcessor(),
    )

    assert [item["kind"] for item in results] == ["retries", "poll", "approvals"]
    assert all(item["status"] == "ok" for item in results)
    assert "--process-retries" in calls[0]
    assert "--outlook-poll" in calls[1]
    assert "--newest-only" in calls[1]
    assert calls[0][calls[0].index("--monday-mode") + 1] == "live-readonly"
    assert calls[1][calls[1].index("--monday-mode") + 1] == "live-readonly"
    assert str(tmp_path / "data" / "state.sqlite") in calls[0]
    assert str(tmp_path / "data" / "state.sqlite") in calls[1]
    assert str(tmp_path / "data" / "workflow-monitor.sqlite") in calls[0]
    assert str(tmp_path / "data" / "workflow-monitor.sqlite") in calls[1]
    health = SQLiteWorkflowStore(tmp_path / "data" / "workflow-monitor.sqlite")
    assert {item.component for item in health.list_component_health()} == {
        "poll",
        "retries",
        "approvals",
    }


def test_worker_cycle_survives_runner_exceptions(tmp_path) -> None:
    def boom(_argv: list[str]) -> int:
        raise RuntimeError("mailbox auth failed")

    result = worker.run_poll_cycle(
        data_root=tmp_path / "data",
        max_messages=5,
        quiet=True,
        run_main=boom,
    )

    assert result["kind"] == "poll"
    assert result["status"] == "error"
    assert "mailbox auth failed" in result["error"]


def test_worker_stage_one_side_effects_are_explicit_opt_ins(tmp_path) -> None:
    calls: list[list[str]] = []

    worker.run_poll_cycle(
        data_root=tmp_path / "data",
        max_messages=5,
        quiet=True,
        partner_acknowledgement=True,
        stage_one_drk_check=True,
        run_main=lambda argv: calls.append(list(argv)) or 0,
    )

    assert "--send-partner-acknowledgement" in calls[0]
    assert "--drk-duplicate-check" in calls[0]


def test_worker_execute_flag_is_restricted_to_dry_run(tmp_path) -> None:
    seen = []

    class FakeApprovalProcessor:
        def poll(self, *, max_messages: int, execute: bool, dry_run: bool):
            seen.append((max_messages, execute, dry_run))
            return {
                "mode": "dry_run",
                "accepted_confirmations": [],
                "ignored_confirmations": [],
                "executed": [],
            }

    result = worker.run_approval_cycle(
        data_root=tmp_path,
        max_messages=50,
        execute=True,
        processor_factory=lambda _state_db: FakeApprovalProcessor(),
    )

    assert result["status"] == "ok"
    assert result["execution_enabled"] is False
    assert result["dry_run_enabled"] is True
    assert seen == [(50, False, True)]


def test_worker_runs_optional_monitor_cycle_without_enabling_alerts(tmp_path) -> None:
    seen: list[dict] = []

    def fake_monitor_cycle(**kwargs):
        seen.append(kwargs)
        return {"kind": "monitor", "status": "ok"}

    results = worker.run_worker_loop(
        data_root=tmp_path / "data",
        poll_interval_seconds=60,
        retry_interval_seconds=30,
        max_messages=25,
        max_jobs=10,
        once=True,
        skip_poll=True,
        skip_retries=True,
        skip_approvals=True,
        monitor_enabled=True,
        monitor_interval_seconds=300,
        monitor_send_alerts=False,
        live_drk=True,
        drk_max_patients=4,
        drk_live_profile_dir=tmp_path / "drk-profile",
        monitor_cycle=fake_monitor_cycle,
        sleep_fn=lambda _seconds: None,
        clock=lambda: 0.0,
    )

    assert results == [{"kind": "monitor", "status": "ok"}]
    assert seen[0]["send_alerts"] is False
    assert seen[0]["live_drk"] is True
    assert seen[0]["drk_max_patients"] == 4
