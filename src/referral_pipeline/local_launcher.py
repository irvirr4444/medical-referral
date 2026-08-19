"""Local development/demo launcher for the referral pipeline."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from dotenv import load_dotenv

from referral_pipeline.local_process import (
    LaunchError,
    frontend_dependencies_present,
    npm_executable,
    occupied_port_message,
    port_is_occupied,
    spawn_child,
    stop_children,
    supervise_children,
    wait_for_http,
)
from referral_pipeline.stage_one.preflight import run_stage_one_preflight


DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8787
DEFAULT_FRONTEND_PORT = 5173
DEFAULT_DATA_ROOT = Path("tmp") / "intake-service"
API_READY_TIMEOUT_SECONDS = 45.0
FRONTEND_READY_TIMEOUT_SECONDS = 90.0
UNSAFE_API_FLAGS = (
    "--force",
    "--apply",
    "--confirm-master-sheet-write",
    "--confirm-monday-write",
    "--execute",
    "--requeue",
    "--send-partner-acknowledgement",
    "--drk-duplicate-check",
    "--live-drk",
)


@dataclass(frozen=True)
class LaunchOptions:
    repo_root: Path
    data_root: Path
    api_host: str = DEFAULT_API_HOST
    api_port: int = DEFAULT_API_PORT
    frontend_port: int = DEFAULT_FRONTEND_PORT
    open_browser: bool = True
    stage_one_drk_check: bool = False
    partner_acknowledgement: bool = False
    workflow_database_backend: str | None = None
    max_approval_messages: int = 25

    @property
    def frontend_dir(self) -> Path:
        return self.repo_root / "frontend"

    @property
    def api_url(self) -> str:
        return f"http://{self.api_host}:{self.api_port}"

    @property
    def ui_url(self) -> str:
        return f"http://127.0.0.1:{self.frontend_port}/"

    @property
    def health_url(self) -> str:
        return f"{self.api_url}/health"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_launcher_env() -> None:
    load_dotenv()


def resolve_data_root(
    explicit: Path | None,
    environ: Mapping[str, str] | None = None,
    *,
    cwd: Path | None = None,
) -> Path:
    if explicit is not None:
        return explicit.expanduser().resolve()
    source = os.environ if environ is None else environ
    configured = str(source.get("INTAKE_DATA_ROOT", "")).strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return ((cwd or Path.cwd()) / DEFAULT_DATA_ROOT).resolve()


def effective_workflow_backend(
    explicit: str | None,
    environ: Mapping[str, str] | None = None,
) -> str:
    source = os.environ if environ is None else environ
    raw = (explicit or source.get("WORKFLOW_DATABASE_BACKEND") or "sqlite").strip().casefold()
    return raw if raw in {"sqlite", "supabase"} else "sqlite"


def launch_options_from_args(
    args: argparse.Namespace,
    *,
    root: Path | None = None,
) -> LaunchOptions:
    load_launcher_env()
    return LaunchOptions(
        repo_root=root or repo_root(),
        data_root=resolve_data_root(getattr(args, "data_root", None)),
        api_port=int(args.api_port),
        frontend_port=int(args.frontend_port),
        open_browser=not bool(args.no_browser),
        stage_one_drk_check=bool(args.stage_one_drk_check),
        partner_acknowledgement=bool(args.partner_acknowledgement),
        workflow_database_backend=effective_workflow_backend(args.workflow_database_backend),
    )


def build_api_command(options: LaunchOptions) -> list[str]:
    command = [
        sys.executable,
        str(options.repo_root / "run_pipeline.py"),
        "inbox-api",
        "--host",
        options.api_host,
        "--port",
        str(options.api_port),
        "--data-root",
        str(options.data_root),
        "--start-monitor",
        "--workflow-database-backend",
        effective_workflow_backend(options.workflow_database_backend),
        # The default 100 fetches uniqueBody for 100 messages every cycle,
        # which took 100+s against a mailbox this session's testing had
        # grown, so the 30s-interval approval cycle ran back-to-back and
        # starved the live UI's own Outlook calls of latency headroom.
        "--max-approval-messages",
        str(options.max_approval_messages),
    ]
    if options.partner_acknowledgement:
        command.append("--partner-acknowledgement")
    if options.stage_one_drk_check:
        command.append("--stage-one-drk-check")
    return command


def build_frontend_command(*, port: int, npm: str) -> list[str]:
    return [
        npm,
        "run",
        "dev",
        "--",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--strictPort",
    ]


def child_environment(
    options: LaunchOptions,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    source = os.environ if environ is None else environ
    env = dict(source)
    env["INTAKE_DATA_ROOT"] = str(options.data_root)
    env["INTAKE_PARTNER_ACKNOWLEDGEMENT_ENABLED"] = (
        "1" if options.partner_acknowledgement else "0"
    )
    env["INTAKE_STAGE_ONE_DRK_CHECK_ENABLED"] = "1" if options.stage_one_drk_check else "0"
    env["VITE_INTAKE_API_TARGET"] = options.api_url
    env["WORKFLOW_DATABASE_BACKEND"] = effective_workflow_backend(
        options.workflow_database_backend,
        source,
    )
    env["WORKFLOW_READ_EXISTING_REMOTE"] = "1"
    return env


def workflow_store_label(
    options: LaunchOptions,
    environ: Mapping[str, str] | None = None,
) -> str:
    source = os.environ if environ is None else environ
    backend = effective_workflow_backend(options.workflow_database_backend, source)
    if backend == "supabase":
        return "supabase"
    sqlite_path = Path(
        source.get("WORKFLOW_SQLITE_PATH") or (options.data_root / "workflow-monitor.sqlite")
    )
    return f"sqlite ({sqlite_path}); also reads existing Supabase cases"


def ledger_job_backends(data_root: Path) -> set[str]:
    db = data_root / "state.sqlite"
    if not db.is_file():
        return set()
    try:
        with sqlite3.connect(db) as connection:
            rows = connection.execute(
                "SELECT options_json FROM processed_attachments WHERE options_json IS NOT NULL"
            ).fetchall()
    except sqlite3.Error:
        return set()
    found: set[str] = set()
    for (raw,) in rows:
        try:
            options = json.loads(raw) if isinstance(raw, str) else {}
        except json.JSONDecodeError:
            continue
        if not isinstance(options, dict):
            continue
        value = str(options.get("workflow_database_backend") or "").strip().casefold()
        if value in {"sqlite", "supabase"}:
            found.add(value)
    return found


def format_startup_summary(options: LaunchOptions) -> str:
    lines = [
        "WCW Referral Pipeline",
        f"Data root: {options.data_root}",
        f"Workflow store: {workflow_store_label(options)}",
        "Inbox monitor: running",
        f"API: {options.api_url}",
        f"UI: http://127.0.0.1:{options.frontend_port}",
        "Stop with Ctrl+C",
    ]
    backend = effective_workflow_backend(options.workflow_database_backend)
    remote_jobs = ledger_job_backends(options.data_root)
    if "supabase" in remote_jobs and backend != "supabase":
        lines.insert(
            3,
            "Note: inbox jobs were previously written to Supabase; confirmations still apply there.",
        )
    return "\n".join(lines)


def format_preflight_failure(result: Mapping[str, Any]) -> str:
    lines = ["startup: preflight failed"]
    for check in result.get("checks") or []:
        if not isinstance(check, dict) or check.get("status") != "error":
            continue
        name = str(check.get("name") or "check")
        detail = str(check.get("detail") or "failed")
        lines.append(f"- {name}: {detail}")
    return "\n".join(lines)


def run_start_preflight(options: LaunchOptions) -> dict[str, object]:
    load_launcher_env()
    backend = effective_workflow_backend(options.workflow_database_backend)
    supabase = backend == "supabase"
    return run_stage_one_preflight(
        live=False,
        require_supabase=supabase,
        require_drk=options.stage_one_drk_check,
        require_partner_acknowledgement=options.partner_acknowledgement,
        live_outlook=True,
        live_supabase=supabase,
    )


def open_default_browser(url: str) -> None:
    webbrowser.open(url)


def run_from_cli_args(args: argparse.Namespace) -> int:
    return run_local_start(launch_options_from_args(args))


def run_local_start(options: LaunchOptions) -> int:
    load_launcher_env()
    children: list[Any] = []
    try:
        return _run_local_start(options, children)
    except LaunchError as error:
        print(str(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    except Exception as error:  # noqa: BLE001 - launcher must still stop children
        print(
            f"startup: error: unexpected failure ({type(error).__name__}: {error}).",
            file=sys.stderr,
        )
        return 1
    finally:
        stop_children(children)


def _run_local_start(options: LaunchOptions, children: list[Any]) -> int:
    if options.api_port < 1 or options.frontend_port < 1:
        raise LaunchError("startup: error: ports must be positive integers.")

    os.environ["INTAKE_DATA_ROOT"] = str(options.data_root)

    preflight = run_start_preflight(options)
    if not preflight.get("ready"):
        raise LaunchError(format_preflight_failure(preflight))

    frontend_dir = options.frontend_dir
    if not frontend_dependencies_present(frontend_dir):
        raise LaunchError(
            "startup: error: frontend dependencies are missing. Run npm install in frontend/."
        )

    npm = npm_executable()
    if port_is_occupied(options.api_host, options.api_port):
        raise LaunchError(
            occupied_port_message("API", options.api_host, options.api_port, "--api-port")
        )
    if port_is_occupied("127.0.0.1", options.frontend_port):
        raise LaunchError(
            occupied_port_message("UI", "127.0.0.1", options.frontend_port, "--frontend-port")
        )

    env = child_environment(options)
    api = spawn_child(build_api_command(options), env=env)
    children.append(api)
    wait_for_http(options.health_url, timeout_seconds=API_READY_TIMEOUT_SECONDS)

    frontend = spawn_child(
        build_frontend_command(port=options.frontend_port, npm=npm),
        cwd=frontend_dir,
        env=env,
    )
    children.append(frontend)
    wait_for_http(options.ui_url, timeout_seconds=FRONTEND_READY_TIMEOUT_SECONDS)

    print(format_startup_summary(options), flush=True)
    if options.open_browser:
        open_default_browser(options.ui_url)

    return supervise_children(
        (
            ("inbox API", api),
            ("frontend", frontend),
        )
    )
