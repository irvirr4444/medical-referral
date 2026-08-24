"""Read-only Stage 1 configuration and connectivity checks."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import asdict, dataclass
from typing import Callable

import requests
from dotenv import load_dotenv

from Outlook.graph import OutlookGraphClient, OutlookGraphConfig
from referral_pipeline.persistence_policy import SyntheticPersistencePolicy


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    status: str
    detail: str


def run_stage_one_preflight(
    *,
    live: bool = False,
    require_supabase: bool | None = None,
    require_drk: bool = False,
    require_partner_acknowledgement: bool = False,
    live_outlook: bool | None = None,
    live_supabase: bool | None = None,
) -> dict[str, object]:
    load_dotenv()
    checks: list[PreflightCheck] = []
    reviewer = os.getenv("REVIEW_RECIPIENT_EMAIL", "").strip()
    checks.append(
        _required(
            "internal_reviewer",
            bool(reviewer),
            "Internal intake-team review recipient configured"
            if reviewer
            else (
                "REVIEW_RECIPIENT_EMAIL is required and cannot fall back to the referral sender. "
                "Remediation: set REVIEW_RECIPIENT_EMAIL to an internal intake-team address."
            ),
        )
    )

    policy = SyntheticPersistencePolicy.from_environment()
    checks.append(
        _required(
            "synthetic_allowlist",
            bool(policy.allowed_sha256),
            f"{len(policy.allowed_sha256)} synthetic PDF hashes loaded from {policy.manifest_path}",
        )
    )
    checks.append(_environment_group("anthropic", ("ANTHROPIC_API_KEY",), required=True))
    checks.append(
        _environment_group(
            "outlook",
            ("OUTLOOK_TENANT_ID", "OUTLOOK_CLIENT_ID", "OUTLOOK_CLIENT_SECRET", "OUTLOOK_MAILBOX"),
            required=True,
        )
    )

    if require_supabase is None:
        supabase_enabled = bool(
            os.getenv("WORKFLOW_DATABASE_BACKEND", "sqlite").strip().casefold() == "supabase"
            or os.getenv("REFERRAL_REVIEW_STORE", "sqlite").strip().casefold() == "supabase"
            or os.getenv("SUPABASE_URL", "").strip()
            or _supabase_key()
        )
    else:
        supabase_enabled = require_supabase
    checks.append(_supabase_configuration(required=supabase_enabled))
    checks.append(
        _environment_group(
            "monday_read",
            ("MONDAY_DOT_COM_API_KEY",),
            required=False,
        )
    )
    checks.append(
        _environment_group(
            "drk_read",
            ("EMR_URL", "EMR_USERNAME", "EMR_PASSWORD"),
            required=require_drk,
        )
    )
    if require_partner_acknowledgement:
        outlook_vars = (
            "OUTLOOK_TENANT_ID",
            "OUTLOOK_CLIENT_ID",
            "OUTLOOK_CLIENT_SECRET",
            "OUTLOOK_MAILBOX",
        )
        outlook_ok = all(os.getenv(variable, "").strip() for variable in outlook_vars)
        checks.append(
            _required(
                "partner_acknowledgement",
                outlook_ok,
                "Outlook mailbox is configured for partner acknowledgement"
                if outlook_ok
                else (
                    "Partner acknowledgement requires Outlook Mail.Send. "
                    "Remediation: set OUTLOOK_TENANT_ID, OUTLOOK_CLIENT_ID, "
                    "OUTLOOK_CLIENT_SECRET, and OUTLOOK_MAILBOX."
                ),
            )
        )

    checks.append(_capture("case_manager_roster", _check_roster))
    checks.append(_capture("local_schema", _check_local_schema))

    check_outlook_live = live if live_outlook is None else live_outlook
    check_supabase_live = live if live_supabase is None else live_supabase
    if check_outlook_live and not any(
        check.name == "outlook" and check.status == "error" for check in checks
    ):
        checks.append(_capture("outlook_live", _check_outlook))
    if live and os.getenv("MONDAY_DOT_COM_API_KEY", "").strip():
        checks.append(_capture("monday_live", _check_monday))
        checks.append(_capture("monday_board", _check_monday_board))
    if (
        check_supabase_live
        and supabase_enabled
        and os.getenv("SUPABASE_URL", "").strip()
        and _supabase_key()
    ):
        checks.append(_capture("supabase_schema", _check_supabase))
    if live and os.getenv("EMR_URL", "").strip() and os.getenv("EMR_USERNAME", "").strip():
        checks.append(_capture("drk_live", _check_drk))

    errors = sum(check.status == "error" for check in checks)
    warnings = sum(check.status == "warning" for check in checks)
    return {
        "ready": errors == 0,
        "live_checks": live,
        "errors": errors,
        "warnings": warnings,
        "checks": [asdict(check) for check in checks],
    }


def _required(name: str, condition: bool, detail: str) -> PreflightCheck:
    return PreflightCheck(name, "ok" if condition else "error", detail)


def _environment_group(name: str, variables: tuple[str, ...], *, required: bool) -> PreflightCheck:
    missing = [variable for variable in variables if not os.getenv(variable, "").strip()]
    if not missing:
        return PreflightCheck(name, "ok", "Configuration present")
    status = "error" if required else "warning"
    detail = f"Not configured: {', '.join(missing)}"
    if required:
        detail += f". Remediation: set {', '.join(missing)}."
    return PreflightCheck(name, status, detail)


def _supabase_key() -> str:
    return (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    )


def _supabase_configuration(*, required: bool) -> PreflightCheck:
    missing = []
    if not os.getenv("SUPABASE_URL", "").strip():
        missing.append("SUPABASE_URL")
    if not _supabase_key():
        missing.append("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_SERVICE_KEY")
    if not missing:
        return PreflightCheck("supabase", "ok", "Backend configuration present")
    detail = f"Not configured: {', '.join(missing)}"
    if required:
        detail += f". Remediation: set {', '.join(missing)}."
    return PreflightCheck(
        "supabase",
        "error" if required else "warning",
        detail,
    )


def _capture(name: str, check: Callable[[], str]) -> PreflightCheck:
    try:
        return PreflightCheck(name, "ok", check())
    except Exception as error:  # noqa: BLE001 - doctor reports failures without crashing
        return PreflightCheck(name, "error", f"{type(error).__name__}: {error}")


def _check_outlook() -> str:
    client = OutlookGraphClient(OutlookGraphConfig.from_environment())
    roles = set(_jwt_claims(client._token()).get("roles") or [])  # noqa: SLF001
    missing = {"Mail.Read", "Mail.Send"} - roles
    if missing:
        raise RuntimeError(
            "Missing Microsoft Graph application roles: "
            + ", ".join(sorted(missing))
            + ". Remediation: grant Mail.Read and Mail.Send to the app registration."
        )
    client.get_json(
        f"/users/{client.config.mailbox}/mailFolders/inbox/messages?$select=id&$top=1"
    )
    reviewer = os.getenv("REVIEW_RECIPIENT_EMAIL", "").strip()
    return (
        "Mailbox read succeeded; application Mail.Read and Mail.Send are present"
        + (f"; internal reviewer {reviewer} is configured" if reviewer else "")
    )


def _jwt_claims(token: str) -> dict[str, object]:
    try:
        encoded = token.split(".")[1]
        payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        claims = json.loads(payload)
    except (IndexError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError("Could not inspect Microsoft Graph token roles") from error
    return claims if isinstance(claims, dict) else {}


def _check_monday() -> str:
    from monday_api import monday_graphql

    payload = monday_graphql("query { me { id } }")
    if not (payload.get("data") or {}).get("me"):
        raise RuntimeError("Monday did not return the current user. Remediation: verify MONDAY_DOT_COM_API_KEY.")
    return "Monday read-only identity query succeeded"


def _check_monday_board() -> str:
    import sys
    from pathlib import Path

    monday_dir = Path(__file__).resolve().parents[2] / "monday.com"
    if str(monday_dir) not in sys.path:
        sys.path.insert(0, str(monday_dir))
    from master_sheet_writer import load_master_sheet_write_config
    from monday_api import monday_graphql

    config_path = Path(
        os.getenv("MASTER_SHEET_WRITE_CONFIG")
        or monday_dir / "master_sheet_write_config.example.json"
    )
    config = load_master_sheet_write_config(config_path)
    payload = monday_graphql(
        "query ($ids: [ID!]) { boards(ids: $ids) { id name } }",
        variables={"ids": [str(config.board_id)]},
    )
    boards = ((payload.get("data") or {}).get("boards") or [])
    if not boards:
        raise RuntimeError(
            f"Master Sheet board {config.board_id} is not readable. "
            "Remediation: confirm the API key can access the configured Monday board."
        )
    board = boards[0]
    return f"Master Sheet board {board.get('id')} ({board.get('name')}) is readable"


def _check_roster() -> str:
    from referral_pipeline.workflow.roster import load_case_manager_roster

    managers = load_case_manager_roster()
    if not managers:
        raise RuntimeError(
            "Case-manager roster is empty. Remediation: populate case_managers.json "
            "or set CASE_MANAGER_ROSTER_PATH."
        )
    return f"{len(managers)} case managers loaded from the configured roster"


def _check_local_schema() -> str:
    import sqlite3
    from pathlib import Path

    from referral_pipeline.monitoring.sqlite_store import SQLiteWorkflowStore

    workflow_path = Path(
        os.getenv("WORKFLOW_SQLITE_PATH")
        or Path(os.getenv("INTAKE_DATA_ROOT", "tmp/intake-service")) / "workflow-monitor.sqlite"
    )
    SQLiteWorkflowStore(workflow_path)
    with sqlite3.connect(workflow_path) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        operation_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(wcw_external_operations)")
        }
    required = {
        "wcw_workflow_cases",
        "wcw_workflow_events",
        "wcw_work_items",
        "wcw_workflow_decisions",
        "wcw_external_operations",
    }
    missing = sorted(required - tables)
    if missing:
        raise RuntimeError(
            "Local workflow schema is missing "
            + ", ".join(missing)
            + ". Remediation: recreate the SQLite workflow database."
        )
    needed_operation_columns = {"lease_until", "claimed_by"}
    missing_op_columns = sorted(needed_operation_columns - operation_columns)
    if missing_op_columns:
        raise RuntimeError(
            "wcw_external_operations is missing "
            + ", ".join(missing_op_columns)
            + ". Remediation: reopen the SQLite workflow store so claim/lease columns migrate."
        )
    state_path = Path(os.getenv("INTAKE_DATA_ROOT", "tmp/intake-service")) / "state.sqlite"
    from referral_pipeline.review.store import ReviewStore

    ReviewStore(state_path)
    with sqlite3.connect(state_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(referral_reviews)")
        }
    needed = {
        "review_id",
        "workflow_case_id",
        "workflow_apply_status",
        "workflow_apply_attempts",
        "workflow_apply_last_error",
    }
    missing_columns = sorted(needed - columns)
    if missing_columns:
        raise RuntimeError(
            "referral_reviews is missing "
            + ", ".join(missing_columns)
            + ". Remediation: open the review store once so SQLite migrates apply-state columns."
        )
    return "Local Stage 2-3 tables present; referral_reviews apply-state columns present"


def _check_drk() -> str:
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from drk_emr.common.browser import login, login_url_for, make_driver, require_env

    username = require_env("EMR_USERNAME")
    password = require_env("EMR_PASSWORD")
    emr_url = require_env("EMR_URL")
    # ignore_cleanup_errors: Chrome on Windows often keeps cache files open
    # briefly after quit(), which would otherwise raise WinError 32.
    tmp = TemporaryDirectory(prefix="drk-preflight-", ignore_cleanup_errors=True)
    driver = None
    current = ""
    try:
        driver = make_driver(Path(tmp.name))
        login(driver, login_url_for(emr_url), username, password)
        current = str(driver.current_url)
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
        try:
            tmp.cleanup()
        except OSError:
            pass
    if "dashboard" not in current.casefold():
        raise RuntimeError(
            "DRK login did not reach the dashboard. Remediation: verify EMR_URL and the DRK account."
        )
    return "DRK login succeeded and the dashboard is reachable"


def _check_supabase() -> str:
    base_url = os.environ["SUPABASE_URL"].rstrip("/")
    key = _supabase_key()
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    targets = {
        "wcw_workflow_cases": "case_id,status,current_stage,attention_due_at",
        "wcw_workflow_events": "event_key,event_type,entity_id",
        "wcw_work_items": "work_item_id,case_id,status,due_at",
        "wcw_workflow_decisions": "decision_id,idempotency_key,case_id",
        "wcw_external_operations": "operation_id,idempotency_key,operation_type,status,lease_until,claimed_by",
        "referral_reviews": (
            "review_id,review_purpose,workflow_case_id,workflow_apply_status,"
            "workflow_apply_attempts,workflow_apply_last_error"
        ),
    }
    for table, columns in targets.items():
        response = requests.get(
            f"{base_url}/rest/v1/{table}",
            headers=headers,
            params={"select": columns, "limit": "0"},
            timeout=20,
        )
        if not response.ok:
            raise RuntimeError(
                f"{table} is unavailable or missing expected columns (HTTP {response.status_code}). "
                "Remediation: apply supabase/migrations in filename order."
            )
    return "Required Stage 1-3 Supabase tables and apply-state columns are readable"
