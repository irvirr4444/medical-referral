"""Dashboard patient search helpers for DRK duplicate gating.

This module lists candidates and never auto-opens the first match.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

from drk_emr.common.browser import DASHBOARD_PATH, clear_network_requests, safe_log


SUMMARY_RE = re.compile(r"(?P<count>\d+)\s+results?", re.IGNORECASE)
SEARCH_PATH = "/Dashboard/SearchPatients"


@dataclass(frozen=True)
class SearchCandidate:
    patient_id: str
    display_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: str | None = None
    mrn: str | None = None
    phone: str | None = None
    email: str | None = None
    facility_name: str | None = None
    status_display: str | None = None
    source: str = "search_api"


@dataclass(frozen=True)
class PatientSearchSnapshot:
    query: str
    summary_text: str | None
    result_count: int | None
    row_count: int
    candidates: tuple[SearchCandidate, ...]
    stable: bool
    error: str | None = None


def parse_summary_count(summary_text: str | None) -> int | None:
    if not summary_text:
        return None
    match = SUMMARY_RE.search(summary_text)
    if not match:
        return None
    return int(match.group("count"))


def _visible_result_rows(driver: Any) -> list[Any]:
    rows = driver.find_elements(
        By.CSS_SELECTOR,
        "#dashPatientSearch .psearch-results-wrap table.tbl tbody tr",
    )
    visible: list[Any] = []
    for row in rows:
        try:
            if row.is_displayed():
                visible.append(row)
        except Exception:
            continue
    return visible


def _summary_text(driver: Any) -> str | None:
    nodes = driver.find_elements(By.CSS_SELECTOR, "#dashPatientSearch .psearch-meta .summary")
    for node in nodes:
        try:
            if node.is_displayed():
                text = (node.text or "").strip()
                if text:
                    return text
        except Exception:
            continue
    if nodes:
        return (nodes[0].text or "").strip() or None
    return None


def _candidate_from_api_row(row: dict[str, Any]) -> SearchCandidate | None:
    patient_id = row.get("id")
    if patient_id is None or str(patient_id).strip() == "":
        return None
    mrn = row.get("mrn")
    return SearchCandidate(
        patient_id=str(patient_id).strip(),
        display_name=(row.get("name") or None),
        first_name=(row.get("firstName") or None),
        last_name=(row.get("lastName") or None),
        date_of_birth=(row.get("dateOfBirth") or None),
        mrn=None if mrn in (None, "") else str(mrn),
        phone=(row.get("phone") or None) or None,
        email=(row.get("email") or None) or None,
        facility_name=(row.get("facilityName") or None),
        status_display=(row.get("statusDisplay") or None),
        source="search_api",
    )


def _decode_response_body(response: Any) -> bytes:
    import gzip
    import zlib

    body = response.body or b""
    encoding = (response.headers.get("Content-Encoding") or "").lower()
    try:
        if "gzip" in encoding:
            return gzip.decompress(body)
        if "deflate" in encoding:
            return zlib.decompress(body)
    except Exception:
        return body
    return body


def candidates_from_search_requests(driver: Any, *, query: str) -> list[SearchCandidate]:
    """Prefer the SearchPatients XHR that the dashboard fires for this query."""
    wanted = " ".join(query.lower().split())
    matches: list[SearchCandidate] = []
    for request in getattr(driver, "requests", []):
        url = getattr(request, "url", "") or ""
        if SEARCH_PATH.lower() not in url.lower():
            continue
        parsed = urlsplit(url)
        params = parse_qs(parsed.query)
        request_query = " ".join(unquote((params.get("query") or [""])[0]).lower().split())
        if request_query and request_query != wanted:
            continue
        response = getattr(request, "response", None)
        if response is None:
            continue
        try:
            payload = json.loads(_decode_response_body(response).decode("utf-8", errors="replace"))
        except Exception:
            continue
        patients = payload.get("patients") if isinstance(payload, dict) else None
        if not isinstance(patients, list):
            continue
        for row in patients:
            if isinstance(row, dict):
                candidate = _candidate_from_api_row(row)
                if candidate is not None:
                    matches.append(candidate)
    # Keep last matching response only (latest search).
    if not matches:
        return []
    # Deduplicate by patient id while preserving order.
    seen: set[str] = set()
    unique: list[SearchCandidate] = []
    for item in matches:
        if item.patient_id in seen:
            continue
        seen.add(item.patient_id)
        unique.append(item)
    return unique


def wait_for_stable_search_results(
    driver: Any,
    *,
    timeout_seconds: float = 12.0,
    settle_seconds: float = 0.8,
) -> tuple[str | None, int | None, int, bool]:
    """Wait until summary count and visible row count stop changing."""
    deadline = time.time() + timeout_seconds
    last: tuple[str | None, int | None, int] | None = None
    stable_since: float | None = None
    while time.time() < deadline:
        summary = _summary_text(driver)
        count = parse_summary_count(summary)
        rows = len(_visible_result_rows(driver))
        current = (summary, count, rows)
        now = time.time()
        if current != last:
            last = current
            stable_since = now
        elif stable_since is not None and (now - stable_since) >= settle_seconds:
            # Zero-result searches often have a summary and no rows.
            if count == 0 and rows == 0:
                return summary, count, rows, True
            # Non-zero searches need the summary and matching row presence when possible.
            if count is not None:
                return summary, count, rows, True
        time.sleep(0.15)
    summary = _summary_text(driver)
    count = parse_summary_count(summary)
    rows = len(_visible_result_rows(driver))
    return summary, count, rows, False


def search_patients_on_dashboard(
    driver: Any,
    patient_name: str,
    *,
    timeout_seconds: float = 12.0,
) -> PatientSearchSnapshot:
    """Type a name into dashboard search and return a stable candidate snapshot."""
    query = " ".join((patient_name or "").split())
    if not query:
        return PatientSearchSnapshot(
            query=query,
            summary_text=None,
            result_count=None,
            row_count=0,
            candidates=(),
            stable=False,
            error="missing_search_name",
        )

    wait = WebDriverWait(driver, 25)
    wait.until(lambda d: DASHBOARD_PATH.lower() in d.current_url.lower())
    wait.until(ec.presence_of_element_located((By.ID, "dashPatientSearch")))

    clear_network_requests(driver)
    search_label = wait.until(
        ec.element_to_be_clickable(
            (By.CSS_SELECTOR, "#dashPatientSearch label.psearch-input[for='patientSearchInput']")
        )
    )
    search_label.click()
    search_input = wait.until(ec.element_to_be_clickable((By.ID, "patientSearchInput")))
    search_input.clear()
    search_input.send_keys(query)

    summary, count, row_count, stable = wait_for_stable_search_results(
        driver,
        timeout_seconds=timeout_seconds,
    )
    candidates = candidates_from_search_requests(driver, query=query)

    # Fail closed if the UI claims results but we could not resolve candidates.
    error = None
    if not stable:
        error = "search_results_unstable"
    elif count is None:
        error = "missing_search_summary"
    elif count == 0 and row_count == 0:
        candidates = []
    elif count > 0 and not candidates and row_count == 0:
        error = "search_count_without_candidates"
    elif count > 0 and not candidates and row_count > 0:
        error = "unable_to_resolve_candidate_ids"

    safe_log(
        f"DRK patient search query={query!r} summary={summary!r} "
        f"count={count} rows={row_count} candidates={len(candidates)} stable={stable}"
    )
    return PatientSearchSnapshot(
        query=query,
        summary_text=summary,
        result_count=count,
        row_count=row_count,
        candidates=tuple(candidates),
        stable=stable,
        error=error,
    )
