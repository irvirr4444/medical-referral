"""Safe DRK chart prefill that never clicks Create/Submit.

The Selenium path fills only explicit canonical draft values and retains the
browser for operator review. Tests inject an adapter so pytest never opens DRK.
"""

from __future__ import annotations

import atexit
import threading
from typing import Any, Protocol

from referral_pipeline.workflow.operation_policy import HandoffExecutionError


STOPPED_BEFORE = "Create/Submit"
_OPEN_SESSIONS: dict[str, tuple[Any, list[str]]] = {}
_SESSION_LOCK = threading.Lock()


class DrkPrefillAdapter(Protocol):
    def prefill(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def inspect(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class DrkChartPrefillExecutor:
    def __init__(self, adapter: DrkPrefillAdapter | None = None) -> None:
        self.adapter = adapter

    def preview(self, payload: dict[str, Any]) -> dict[str, Any]:
        draft, blockers = _draft_state(payload)
        return {
            "operation_type": "prefill-drk-chart",
            "ready_for_fill": not blockers,
            "blockers": blockers,
            "filled": False,
            "submitted": False,
            "stopped_before": STOPPED_BEFORE,
            "automatic_submit": False,
            "would_prefill": True,
            "populated_fields": [],
            "current_url": None,
            "draft_present": bool(draft),
        }

    def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        _draft, blockers = _draft_state(payload)
        result = {
            "operation_type": "prefill-drk-chart",
            "ready_for_fill": not blockers,
            "blockers": list(blockers),
            "filled": False,
            "submitted": False,
            "stopped_before": STOPPED_BEFORE,
            "automatic_submit": False,
            "would_prefill": False,
            "populated_fields": [],
            "current_url": None,
        }
        if blockers:
            result["status"] = "blocked"
            return result
        adapter = self.adapter or SeleniumDrkPrefillAdapter()
        evidence = adapter.prefill(payload)
        populated = list(evidence.get("populated_fields") or [])
        filled = bool(evidence.get("filled")) and bool(populated)
        result.update(
            {
                "filled": filled,
                "populated_fields": populated,
                "current_url": evidence.get("current_url"),
                "notes": evidence.get("notes") or [],
                "submitted": False,
                "stopped_before": STOPPED_BEFORE,
            }
        )
        if evidence.get("blockers"):
            result["blockers"] = list(evidence["blockers"])
            result["filled"] = False
            result["status"] = "blocked"
            return result
        if not filled:
            raise HandoffExecutionError(
                "DRK prefill did not populate any fields; Selenium work was not proven"
            )
        return result

    def inspect(self, payload: dict[str, Any]) -> dict[str, Any]:
        adapter = self.adapter or SeleniumDrkPrefillAdapter()
        return adapter.inspect(payload)


class SeleniumDrkPrefillAdapter:
    """Authenticate, open Patient Intake, fill fields, and stop before Create/Submit."""

    def prefill(self, payload: dict[str, Any]) -> dict[str, Any]:
        from drk_emr.create_patient.fill import (
            assert_create_patient_untouched,
            fill_intake_draft,
            navigate_to_patient_intake,
        )

        data = _draft_payload(payload)
        session_key = _session_key(payload)
        driver = None
        try:
            driver, login_notes = _open_logged_in_driver()
            navigate_to_patient_intake(driver)
            fill_result = fill_intake_draft(driver, data)
            assert_create_patient_untouched(driver)
            populated = list(fill_result.get("populated_fields") or [])
            _retain_session(session_key, driver, populated)
            current_url = getattr(driver, "current_url", None)
            driver = None
            return {
                "filled": bool(populated),
                "submitted": False,
                "stopped_before": STOPPED_BEFORE,
                "current_url": current_url,
                "populated_fields": populated,
                "notes": [*(fill_result.get("notes") or []), login_notes],
                "session_retained": True,
                "review_required": True,
            }
        finally:
            if driver is not None:
                driver.quit()

    def inspect(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_key = _session_key(payload)
        with _SESSION_LOCK:
            retained = _OPEN_SESSIONS.get(session_key)
        if retained is None:
            return {
                "filled": False,
                "populated_fields": [],
                "submitted": False,
                "stopped_before": STOPPED_BEFORE,
                "blockers": ["no retained DRK prefill session is available for inspection"],
            }
        driver, populated = retained
        try:
            current_url = getattr(driver, "current_url", None)
            return {
                "filled": bool(populated),
                "populated_fields": populated,
                "current_url": current_url,
                "submitted": False,
                "stopped_before": STOPPED_BEFORE,
                "session_retained": True,
            }
        except Exception:
            _close_session(session_key)
            return {
                "filled": False,
                "populated_fields": [],
                "submitted": False,
                "stopped_before": STOPPED_BEFORE,
                "blockers": ["the retained DRK prefill browser is no longer available"],
            }


def _draft_state(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    draft = payload.get("drk_draft")
    if not isinstance(draft, dict):
        return {}, ["DRK handoff payload is missing a normalized draft"]
    blockers = [str(item) for item in draft.get("blockers") or [] if str(item).strip()]
    if draft.get("ready_for_fill") is False:
        blockers.append("DRK draft is not ready for fill")
    try:
        data = _draft_payload(payload)
    except Exception as error:
        blockers.append(f"DRK draft is invalid: {error}")
    else:
        if not data.demographics.first_name or not data.demographics.last_name:
            blockers.append("DRK prefill requires explicit first and last name values")
    return draft, blockers


def _patient_label(payload: dict[str, Any]) -> str:
    normalized = payload.get("normalized") if isinstance(payload.get("normalized"), dict) else {}
    return str(
        normalized.get("patient_name") or payload.get("patient_label") or ""
    ).strip()


def _draft_payload(payload: dict[str, Any]):
    from drk_emr.create_patient.schema import DrkCreateDraftEnvelope

    draft = payload.get("drk_draft")
    if not isinstance(draft, dict):
        raise HandoffExecutionError("DRK handoff payload is missing a normalized draft")
    return DrkCreateDraftEnvelope.model_validate(draft).payload


def _session_key(payload: dict[str, Any]) -> str:
    return str(payload.get("case_id") or payload.get("referral_id") or _patient_label(payload)).strip()


def _retain_session(key: str, driver: Any, populated: list[str]) -> None:
    if not key:
        raise HandoffExecutionError("DRK prefill requires a workflow case identifier")
    _close_session(key)
    with _SESSION_LOCK:
        _OPEN_SESSIONS[key] = (driver, populated)


def _close_session(key: str) -> None:
    with _SESSION_LOCK:
        retained = _OPEN_SESSIONS.pop(key, None)
    if retained is None:
        return
    try:
        retained[0].quit()
    except Exception:
        pass


def _close_all_sessions() -> None:
    with _SESSION_LOCK:
        keys = list(_OPEN_SESSIONS)
    for key in keys:
        _close_session(key)


atexit.register(_close_all_sessions)


def _open_logged_in_driver() -> tuple[Any, dict[str, str]]:
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from drk_emr.common.browser import login, login_url_for, make_driver, require_env

    username = require_env("EMR_USERNAME")
    password = require_env("EMR_PASSWORD")
    emr_url = require_env("EMR_URL")
    tmp = TemporaryDirectory(prefix="drk-prefill-")
    driver = make_driver(Path(tmp.name))
    driver._prefill_tmp = tmp  # noqa: SLF001 - keep temp profile alive until quit
    login(driver, login_url_for(emr_url), username, password)
    return driver, {"login": "ok"}
