from __future__ import annotations

import socket
from pathlib import Path

import pytest

from referral_pipeline import cli as intake
from referral_pipeline import local_launcher as launcher
from referral_pipeline.local_launcher import (
    LaunchOptions,
    UNSAFE_API_FLAGS,
    build_api_command,
    build_frontend_command,
    child_environment,
    resolve_data_root,
)
from referral_pipeline.local_process import port_is_occupied


class FakeProc:
    def __init__(self, *, code: int | None = None, pid: int = 101) -> None:
        self._code = code
        self.pid = pid
        self.returncode = code

    def poll(self) -> int | None:
        return self._code

    def wait(self, timeout: float | None = None) -> int | None:
        return self.returncode


def _options(tmp_path: Path, **overrides: object) -> LaunchOptions:
    values: dict[str, object] = {
        "repo_root": tmp_path,
        "data_root": tmp_path / "intake-service",
    }
    values.update(overrides)
    return LaunchOptions(**values)  # type: ignore[arg-type]


def _ready_preflight() -> dict[str, object]:
    return {"ready": True, "checks": []}


def _patch_ready_start(monkeypatch, *, procs: list[FakeProc] | None = None) -> list[list[str]]:
    spawned: list[list[str]] = []
    queue = list(procs or [FakeProc(pid=11), FakeProc(pid=22)])

    def fake_spawn(command, **kwargs):
        spawned.append(list(command))
        return queue.pop(0)

    monkeypatch.setattr(launcher, "run_start_preflight", lambda options: _ready_preflight())
    monkeypatch.setattr(launcher, "frontend_dependencies_present", lambda path: True)
    monkeypatch.setattr(launcher, "npm_executable", lambda: "npm.cmd")
    monkeypatch.setattr(launcher, "port_is_occupied", lambda host, port: False)
    monkeypatch.setattr(launcher, "spawn_child", fake_spawn)
    monkeypatch.setattr(launcher, "wait_for_http", lambda url, **kwargs: None)
    monkeypatch.setattr(
        "referral_pipeline.local_process.terminate_process_tree",
        lambda proc: None,
    )
    return spawned


def test_start_help_lists_only_the_supported_flags(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        intake.main(["start", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for flag in (
        "--no-browser",
        "--stage-one-drk-check",
        "--partner-acknowledgement",
        "--workflow-database-backend",
        "--data-root",
        "--api-port",
        "--frontend-port",
    ):
        assert flag in out
    assert "--force" not in out
    assert "--start-monitor" not in out
    assert "--max-messages" not in out


def test_default_api_command_is_safe_and_starts_the_monitor(tmp_path) -> None:
    command = build_api_command(_options(tmp_path))
    assert command[:3] == [command[0], str(tmp_path / "run_pipeline.py"), "inbox-api"]
    assert "--start-monitor" in command
    assert command[command.index("--data-root") + 1] == str(tmp_path / "intake-service")
    assert command[command.index("--port") + 1] == "8787"
    assert "--partner-acknowledgement" not in command
    assert "--stage-one-drk-check" not in command
    assert command[command.index("--workflow-database-backend") + 1] == "sqlite"
    for flag in UNSAFE_API_FLAGS:
        assert flag not in command


def test_data_root_reuses_intake_data_root_and_defaults_only_when_unset(
    tmp_path, monkeypatch
) -> None:
    stable = tmp_path / "stable-root"
    monkeypatch.setenv("INTAKE_DATA_ROOT", str(stable))
    assert resolve_data_root(None) == stable.resolve()

    monkeypatch.delenv("INTAKE_DATA_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    assert resolve_data_root(None) == (tmp_path / "tmp" / "intake-service").resolve()

    explicit = tmp_path / "cli-root"
    monkeypatch.setenv("INTAKE_DATA_ROOT", str(stable))
    assert resolve_data_root(explicit) == explicit.resolve()


def test_optional_start_flags_are_forwarded(tmp_path) -> None:
    command = build_api_command(
        _options(
            tmp_path,
            stage_one_drk_check=True,
            partner_acknowledgement=True,
            workflow_database_backend="supabase",
            api_port=9000,
        )
    )
    assert "--stage-one-drk-check" in command
    assert "--partner-acknowledgement" in command
    assert command[command.index("--workflow-database-backend") + 1] == "supabase"
    assert command[command.index("--port") + 1] == "9000"
    frontend = build_frontend_command(port=4173, npm="npm.cmd")
    assert frontend == [
        "npm.cmd",
        "run",
        "dev",
        "--",
        "--host",
        "127.0.0.1",
        "--port",
        "4173",
        "--strictPort",
    ]


def test_default_child_environment_disables_external_write_toggles(tmp_path) -> None:
    env = child_environment(
        _options(tmp_path),
        environ={
            "PATH": "/bin",
            "INTAKE_PARTNER_ACKNOWLEDGEMENT_ENABLED": "1",
            "INTAKE_STAGE_ONE_DRK_CHECK_ENABLED": "1",
            "SECRET_TOKEN": "do-not-print",
        },
    )
    assert env["INTAKE_DATA_ROOT"] == str(tmp_path / "intake-service")
    assert env["INTAKE_PARTNER_ACKNOWLEDGEMENT_ENABLED"] == "0"
    assert env["INTAKE_STAGE_ONE_DRK_CHECK_ENABLED"] == "0"
    assert env["WORKFLOW_DATABASE_BACKEND"] == "sqlite"
    assert env["WORKFLOW_READ_EXISTING_REMOTE"] == "1"
    enabled = child_environment(
        _options(tmp_path, partner_acknowledgement=True, stage_one_drk_check=True),
        environ={"PATH": "/bin"},
    )
    assert enabled["INTAKE_PARTNER_ACKNOWLEDGEMENT_ENABLED"] == "1"
    assert enabled["INTAKE_STAGE_ONE_DRK_CHECK_ENABLED"] == "1"


def test_browser_opens_only_after_both_services_are_ready(tmp_path, monkeypatch) -> None:
    events: list[tuple[str, str]] = []
    _patch_ready_start(monkeypatch)
    monkeypatch.setattr(
        launcher,
        "wait_for_http",
        lambda url, **kwargs: events.append(("ready", url)),
    )
    monkeypatch.setattr(
        launcher,
        "open_default_browser",
        lambda url: events.append(("browser", url)),
    )
    monkeypatch.setattr(
        launcher,
        "supervise_children",
        lambda named: 0,
    )

    options = _options(tmp_path)
    assert launcher.run_local_start(options) == 0
    assert events == [
        ("ready", options.health_url),
        ("ready", options.ui_url),
        ("browser", options.ui_url),
    ]


def test_no_browser_skips_opening_the_ui(tmp_path, monkeypatch) -> None:
    opened: list[str] = []
    _patch_ready_start(monkeypatch)
    monkeypatch.setattr(launcher, "open_default_browser", opened.append)
    monkeypatch.setattr(launcher, "supervise_children", lambda named: 0)
    assert launcher.run_local_start(_options(tmp_path, open_browser=False)) == 0
    assert opened == []


def test_ctrl_c_stops_both_child_processes(tmp_path, monkeypatch) -> None:
    api = FakeProc(pid=11)
    ui = FakeProc(pid=22)
    stopped: list[FakeProc] = []
    _patch_ready_start(monkeypatch, procs=[api, ui])
    monkeypatch.setattr(
        "referral_pipeline.local_process.terminate_process_tree",
        lambda proc: stopped.append(proc),
    )
    monkeypatch.setattr(
        "referral_pipeline.local_process.time.sleep",
        lambda _seconds: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    assert launcher.run_local_start(_options(tmp_path, open_browser=False)) == 0
    assert api in stopped
    assert ui in stopped


def test_unexpected_child_exit_stops_everything_and_fails(tmp_path, monkeypatch, capsys) -> None:
    api = FakeProc(pid=11)
    ui = FakeProc(code=1, pid=22)
    stopped: list[FakeProc] = []
    _patch_ready_start(monkeypatch, procs=[api, ui])
    monkeypatch.setattr(
        "referral_pipeline.local_process.terminate_process_tree",
        lambda proc: stopped.append(proc),
    )
    monkeypatch.setattr(launcher, "open_default_browser", lambda url: None)
    assert launcher.run_local_start(_options(tmp_path, open_browser=False)) == 1
    assert api in stopped
    assert ui in stopped
    assert "frontend exited unexpectedly" in capsys.readouterr().err


def test_occupied_port_fails_before_spawning(tmp_path, monkeypatch, capsys) -> None:
    spawned: list[list[str]] = []
    monkeypatch.setattr(launcher, "run_start_preflight", lambda options: _ready_preflight())
    monkeypatch.setattr(launcher, "frontend_dependencies_present", lambda path: True)
    monkeypatch.setattr(launcher, "npm_executable", lambda: "npm.cmd")
    monkeypatch.setattr(launcher, "port_is_occupied", lambda host, port: port == 8787)
    monkeypatch.setattr(
        launcher,
        "spawn_child",
        lambda command, **kwargs: spawned.append(list(command)) or FakeProc(),
    )
    monkeypatch.setattr(launcher, "open_default_browser", lambda url: None)

    assert launcher.run_local_start(_options(tmp_path)) == 1
    assert spawned == []
    err = capsys.readouterr().err
    assert "8787" in err
    assert "--api-port" in err


def test_port_is_occupied_detects_a_listener() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = int(sock.getsockname()[1])
        assert port_is_occupied("127.0.0.1", port) is True


def test_unexpected_exception_stops_started_children(tmp_path, monkeypatch, capsys) -> None:
    api = FakeProc(pid=11)
    ui = FakeProc(pid=22)
    stopped: list[FakeProc] = []
    supervise_called: list[object] = []
    _patch_ready_start(monkeypatch, procs=[api, ui])
    monkeypatch.setattr(
        "referral_pipeline.local_process.terminate_process_tree",
        lambda proc: stopped.append(proc),
    )
    monkeypatch.setattr(
        launcher,
        "open_default_browser",
        lambda url: (_ for _ in ()).throw(RuntimeError("browser helper failed")),
    )
    monkeypatch.setattr(
        launcher,
        "supervise_children",
        lambda named: supervise_called.append(named) or 0,
    )
    assert launcher.run_local_start(_options(tmp_path)) == 1
    assert api in stopped
    assert ui in stopped
    assert supervise_called == []
    err = capsys.readouterr().err
    assert "unexpected failure" in err
    assert "RuntimeError" in err


def test_start_preflight_loads_dotenv_before_selecting_workflow_backend(
    tmp_path, monkeypatch
) -> None:
    order: list[str] = []
    captured: dict[str, object] = {}

    def fake_load_env() -> None:
        order.append("dotenv")
        monkeypatch.setenv("WORKFLOW_DATABASE_BACKEND", "supabase")

    def fake_preflight(**kwargs):
        order.append("preflight")
        captured.update(kwargs)
        return _ready_preflight()

    monkeypatch.delenv("WORKFLOW_DATABASE_BACKEND", raising=False)
    monkeypatch.setattr(launcher, "load_launcher_env", fake_load_env)
    monkeypatch.setattr(launcher, "run_stage_one_preflight", fake_preflight)

    launcher.run_start_preflight(_options(tmp_path))
    assert order == ["dotenv", "preflight"]
    assert captured["require_supabase"] is True
    assert captured["live_supabase"] is True
    assert captured["live_outlook"] is True
    assert captured["live"] is False


def test_start_preflight_validates_only_selected_capabilities(tmp_path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_preflight(**kwargs):
        captured.update(kwargs)
        return _ready_preflight()

    monkeypatch.setattr(launcher, "load_launcher_env", lambda: None)
    monkeypatch.setattr(launcher, "run_stage_one_preflight", fake_preflight)
    monkeypatch.delenv("WORKFLOW_DATABASE_BACKEND", raising=False)
    launcher.run_start_preflight(_options(tmp_path))
    assert captured == {
        "live": False,
        "require_supabase": False,
        "require_drk": False,
        "require_partner_acknowledgement": False,
        "live_outlook": True,
        "live_supabase": False,
    }

    launcher.run_start_preflight(
        _options(
            tmp_path,
            workflow_database_backend="supabase",
            stage_one_drk_check=True,
            partner_acknowledgement=True,
        )
    )
    assert captured == {
        "live": False,
        "require_supabase": True,
        "require_drk": True,
        "require_partner_acknowledgement": True,
        "live_outlook": True,
        "live_supabase": True,
    }


def test_preflight_failure_prints_corrective_action_and_does_not_spawn(
    tmp_path, monkeypatch, capsys
) -> None:
    spawned: list[list[str]] = []
    monkeypatch.setattr(
        launcher,
        "run_start_preflight",
        lambda options: {
            "ready": False,
            "checks": [
                {
                    "name": "internal_reviewer",
                    "status": "error",
                    "detail": (
                        "REVIEW_RECIPIENT_EMAIL is required and cannot fall back to the referral sender. "
                        "Remediation: set REVIEW_RECIPIENT_EMAIL to an internal intake-team address."
                    ),
                }
            ],
        },
    )
    monkeypatch.setattr(
        launcher,
        "spawn_child",
        lambda command, **kwargs: spawned.append(list(command)) or FakeProc(),
    )
    assert launcher.run_local_start(_options(tmp_path)) == 1
    assert spawned == []
    err = capsys.readouterr().err
    assert "startup: preflight failed" in err
    assert "REVIEW_RECIPIENT_EMAIL" in err
    assert "Remediation:" in err


def test_missing_frontend_dependencies_ask_for_npm_install(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(launcher, "run_start_preflight", lambda options: _ready_preflight())
    monkeypatch.setattr(launcher, "frontend_dependencies_present", lambda path: False)
    assert launcher.run_local_start(_options(tmp_path)) == 1
    assert "npm install" in capsys.readouterr().err


def test_cli_start_options_map_to_launch_options(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("INTAKE_DATA_ROOT", str(tmp_path / "from-env"))
    args = intake._build_parser().parse_args(
        [
            "start",
            "--no-browser",
            "--stage-one-drk-check",
            "--partner-acknowledgement",
            "--workflow-database-backend",
            "sqlite",
            "--data-root",
            str(tmp_path / "cli-root"),
            "--api-port",
            "9001",
            "--frontend-port",
            "5174",
        ]
    )
    options = launcher.launch_options_from_args(args, root=tmp_path)
    assert options.open_browser is False
    assert options.stage_one_drk_check is True
    assert options.partner_acknowledgement is True
    assert options.workflow_database_backend == "sqlite"
    assert options.data_root == (tmp_path / "cli-root").resolve()
    assert options.api_port == 9001
    assert options.frontend_port == 5174


def test_start_pins_env_workflow_backend_on_the_api_command(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WORKFLOW_DATABASE_BACKEND", "supabase")
    monkeypatch.setattr(launcher, "load_launcher_env", lambda: None)
    args = intake._build_parser().parse_args(["start", "--no-browser"])
    options = launcher.launch_options_from_args(args, root=tmp_path)
    assert options.workflow_database_backend == "supabase"
    command = build_api_command(options)
    assert command[command.index("--workflow-database-backend") + 1] == "supabase"
    env = child_environment(options, environ={"PATH": "/bin"})
    assert env["WORKFLOW_DATABASE_BACKEND"] == "supabase"
    assert env["WORKFLOW_READ_EXISTING_REMOTE"] == "1"


def test_startup_summary_warns_when_ledger_jobs_used_supabase(tmp_path) -> None:
    from Outlook.mail import InboundPdfAttachment
    from referral_pipeline.state import InboxState

    data_root = tmp_path / "intake-service"
    data_root.mkdir()
    InboxState(data_root / "state.sqlite").enqueue(
        InboundPdfAttachment(
            "outlook-graph",
            "message-1",
            "attachment-1",
            "referral.pdf",
            b"%PDF-1.4\n",
        ),
        artifact_path=tmp_path / "referral.pdf",
        options={"workflow_database_backend": "supabase"},
    )
    summary = launcher.format_startup_summary(_options(tmp_path))
    assert "also reads existing Supabase cases" in summary
    assert "previously written to Supabase" in summary
