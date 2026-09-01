"""Live Monday GraphQL and DRK Selenium adapters for the patient profile API."""

from __future__ import annotations

import os
import shutil
import threading
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, TypeVar

from drk_emr.common.browser import DASHBOARD_PATH, emr_root
from drk_emr.common.patient_search import search_patients_on_dashboard
from drk_emr.live_reader.config import DrkLiveReaderConfig
from drk_emr.live_reader.reader import DrkPatientReader
from patient_profile.lookup import drk_profile_from_cards, is_chrome_session_error
from referral_pipeline.integrations.monday.reader import fetch_items_by_name_search

REPO_ROOT = Path(__file__).resolve().parents[2]

_drk_lock = threading.RLock()
_reader: DrkPatientReader | None = None
T = TypeVar("T")


def live_monday_fetch(name: str) -> list[dict[str, Any]]:
    return list(fetch_items_by_name_search(name=name).items)


def live_drk_search(name: str) -> list[dict[str, Any]]:
    def search(reader: DrkPatientReader) -> list[dict[str, Any]]:
        assert reader.driver is not None
        reader.driver.get(f"{emr_root(reader.config.emr_url)}{DASHBOARD_PATH}")
        snapshot = search_patients_on_dashboard(reader.driver, name, open_unique=True)
        if snapshot.error:
            raise RuntimeError(_search_error_message(snapshot.error))
        return [
            {
                "patient_id": item.patient_id,
                "display_name": item.display_name,
                "first_name": item.first_name,
                "last_name": item.last_name,
                "date_of_birth": item.date_of_birth,
                "mrn": item.mrn,
                "phone": item.phone,
                "email": item.email,
                "facility_name": item.facility_name,
                "status_display": item.status_display,
            }
            for item in snapshot.candidates
        ]

    return _with_reader_retry(search)


def live_drk_read(patient_id: str) -> dict[str, Any]:
    def read(reader: DrkPatientReader) -> dict[str, Any]:
        capture = reader.read_patient(patient_id)
        return drk_profile_from_cards(
            capture.patient_id,
            capture.cards,
            observed_at=capture.observed_at.isoformat(),
        )

    return _with_reader_retry(read)


def _with_reader_retry(operation: Callable[[DrkPatientReader], T]) -> T:
    """Retry once with a new browser when Chrome's cached session has died."""
    for attempt in range(2):
        try:
            with _drk_lock:
                return operation(_drk_reader())
        except Exception as exc:
            if not is_chrome_session_error(exc) or attempt == 1:
                raise
            with _drk_lock:
                _invalidate_reader()
    raise AssertionError("unreachable")


def _drk_reader() -> DrkPatientReader:
    global _reader
    with _drk_lock:
        if _reader is not None:
            return _reader
        last_error: Exception | None = None
        for attempt in range(2):
            profile_dir = _new_profile_dir(attempt)
            if profile_dir.exists():
                shutil.rmtree(profile_dir, ignore_errors=True)
            profile_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(profile_dir, 0o700)
            config = replace(
                DrkLiveReaderConfig.from_environment(profile_dir=profile_dir),
                headless=_profile_headless(),
            )
            reader = DrkPatientReader(config)
            try:
                reader.open()
                _reader = reader
                return _reader
            except Exception as exc:
                last_error = exc
                try:
                    reader.close()
                except Exception:
                    pass
                shutil.rmtree(profile_dir, ignore_errors=True)
                if not is_chrome_session_error(exc) or attempt == 1:
                    break
        _reader = None
        assert last_error is not None
        raise last_error


def _invalidate_reader() -> None:
    global _reader
    if _reader is None:
        return
    try:
        _reader.close()
    except Exception:
        pass
    _reader = None


def _new_profile_dir(attempt: int) -> Path:
    return REPO_ROOT / "tmp" / f"drk-patient-profile-{os.getpid()}-{attempt}-{uuid.uuid4().hex[:8]}"


def _profile_headless() -> bool:
    # Monitoring live_reader defaults to headless via DRK_LIVE_HEADLESS.
    # Profile lookups match the working CLI (headed) unless this override is on.
    value = os.getenv("DRK_PROFILE_HEADLESS")
    if value is None:
        return False
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def _search_error_message(code: str) -> str:
    messages = {
        "unable_to_resolve_candidate_ids": (
            "DRK found the patient in search but could not open the chart. Reload to retry."
        ),
        "search_results_unstable": "DRK search results did not settle. Reload to retry.",
        "missing_search_summary": "DRK search did not return a result summary.",
        "search_count_without_candidates": "DRK search reported a match but no patient row.",
        "missing_search_name": "DRK search is missing a patient name.",
    }
    return messages.get(code, code)
