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


def run_stage_one_preflight(*, live: bool = False) -> dict[str, object]:
    load_dotenv()
    checks: list[PreflightCheck] = []
    reviewer = os.getenv("REVIEW_RECIPIENT_EMAIL", "").strip()
    checks.append(
        _required(
            "internal_reviewer",
            bool(reviewer),
            "Internal intake-team review recipient configured"
            if reviewer
            else "REVIEW_RECIPIENT_EMAIL is required and cannot fall back to the referral sender",
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

    supabase_enabled = bool(
        os.getenv("WORKFLOW_DATABASE_BACKEND", "sqlite").strip().casefold() == "supabase"
        or os.getenv("REFERRAL_REVIEW_STORE", "sqlite").strip().casefold() == "supabase"
        or os.getenv("SUPABASE_URL", "").strip()
        or _supabase_key()
    )
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
            required=False,
        )
    )

    if live and not any(check.name == "outlook" and check.status == "error" for check in checks):
        checks.append(_capture("outlook_live", _check_outlook))
    if live and os.getenv("MONDAY_DOT_COM_API_KEY", "").strip():
        checks.append(_capture("monday_live", _check_monday))
    if live and supabase_enabled and os.getenv("SUPABASE_URL", "").strip() and _supabase_key():
        checks.append(_capture("supabase_schema", _check_supabase))

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
    return PreflightCheck(name, status, f"Not configured: {', '.join(missing)}")


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
    return PreflightCheck(
        "supabase",
        "error" if required else "warning",
        f"Not configured: {', '.join(missing)}",
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
        raise RuntimeError("Missing Microsoft Graph application roles: " + ", ".join(sorted(missing)))
    client.get_json(
        f"/users/{client.config.mailbox}/mailFolders/inbox/messages?$select=id&$top=1"
    )
    return "Mailbox read succeeded; application Mail.Read and Mail.Send are present"


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
        raise RuntimeError("Monday did not return the current user")
    return "Monday read-only identity query succeeded"


def _check_supabase() -> str:
    base_url = os.environ["SUPABASE_URL"].rstrip("/")
    key = _supabase_key()
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    targets = {
        "wcw_workflow_cases": "case_id,status",
        "wcw_workflow_events": "event_key,event_type,entity_id",
        "referral_reviews": "review_id,review_purpose,workflow_case_id",
    }
    for table, columns in targets.items():
        response = requests.get(
            f"{base_url}/rest/v1/{table}",
            headers=headers,
            params={"select": columns, "limit": "0"},
            timeout=20,
        )
        if not response.ok:
            raise RuntimeError(f"{table} is unavailable or missing expected columns (HTTP {response.status_code})")
    return "Required Stage 1 Supabase tables and columns are readable"
