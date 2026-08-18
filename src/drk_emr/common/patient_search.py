"""Dashboard patient search helpers for DRK duplicate gating and chart reads.

Search uses given-name-first text. When a name has three or more tokens, only
the first two are typed (Anita Rodriguez Hernandez → Anita Rodriguez). Matching
never clicks the top row blindly: NAME, DOB, MRN, and PHONE from the results
table pick the row.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

from drk_emr.common.browser import DASHBOARD_PATH, clear_network_requests, safe_log


SUMMARY_RE = re.compile(r"(?P<count>\d+)\s+results?", re.IGNORECASE)
SEARCH_PATH = "/Dashboard/SearchPatients"
NAME_CELL_RE = re.compile(
    r"^(?P<name>.+?)"
    r"(?:\s+(?P<status>Active|Inactive|Hold|On\s+Hold))?"
    r"(?:\s+(?P<age>\d+)\s*y(?:ears?)?\s*[·.\-]\s*(?P<sex>[A-Za-z]+))?"
    r"$",
    re.IGNORECASE,
)


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
    row_index: int | None = None
    age: int | None = None
    sex: str | None = None


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


def dashboard_search_query(name: str) -> str:
    """Given-name-first search text; first two tokens when three or more names exist.

    ``Rodriguez Hernandez, Anita`` and ``Anita Rodriguez Hernandez`` both become
    ``Anita Rodriguez``. Two-token names stay as ``First Last``.
    """
    text = " ".join((name or "").split())
    if not text:
        return ""
    if "," in text:
        family, given = [part.strip() for part in text.split(",", 1)]
        given_tokens = given.split()
        family_tokens = family.split()
        if given_tokens and family_tokens:
            return _title_tokens(given_tokens[0], family_tokens[0])
        return _title_tokens(*(given_tokens or family_tokens))
    tokens = text.split()
    if len(tokens) >= 3:
        return _title_tokens(tokens[0], tokens[1])
    return _title_tokens(*tokens)


def parse_name_cell(text: str | None) -> dict[str, Any]:
    raw = " ".join((text or "").split())
    if not raw:
        return {"name": None, "status": None, "age": None, "sex": None}
    match = NAME_CELL_RE.match(raw)
    if not match:
        return {"name": raw, "status": None, "age": None, "sex": None}
    age_text = match.group("age")
    sex = match.group("sex")
    return {
        "name": " ".join((match.group("name") or "").split()) or None,
        "status": match.group("status"),
        "age": int(age_text) if age_text else None,
        "sex": sex.upper() if sex else None,
    }


def normalize_search_dob(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if "T" in text:
        text = text.split("T", 1)[0]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) == 8:
        if int(digits[:4]) > 1900:
            return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"
        return f"{digits[4:]}-{digits[:2]}-{digits[2:4]}"
    return None


def normalize_search_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) >= 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits[-10:] if len(digits) >= 10 else digits or None


def select_search_candidate(
    candidates: list[SearchCandidate] | tuple[SearchCandidate, ...],
    *,
    name: str | None = None,
    date_of_birth: str | None = None,
    phone: str | None = None,
    mrn: str | None = None,
    as_of: date | None = None,
) -> SearchCandidate | None:
    """Pick the results-table row that matches DOB, then phone, then MRN.

    A single remaining row is accepted. Multiple unresolved rows return None.
    """
    rows = list(candidates)
    if not rows:
        return None
    if len(rows) == 1:
        return rows[0]

    wanted_dob = normalize_search_dob(date_of_birth)
    wanted_phone = normalize_search_phone(phone)
    wanted_mrn = _clean_mrn(mrn)
    expected_age = _age_on(wanted_dob, as_of) if wanted_dob else None

    dob_hits = [row for row in rows if wanted_dob and normalize_search_dob(row.date_of_birth) == wanted_dob]
    if len(dob_hits) == 1:
        return dob_hits[0]
    if len(dob_hits) > 1:
        rows = dob_hits

    phone_hits = [row for row in rows if wanted_phone and normalize_search_phone(row.phone) == wanted_phone]
    if len(phone_hits) == 1:
        return phone_hits[0]
    if len(phone_hits) > 1:
        rows = phone_hits

    mrn_hits = [row for row in rows if wanted_mrn and _clean_mrn(row.mrn) == wanted_mrn]
    if len(mrn_hits) == 1:
        return mrn_hits[0]
    if len(mrn_hits) > 1:
        rows = mrn_hits

    age_hits = [row for row in rows if expected_age is not None and row.age == expected_age]
    if len(age_hits) == 1:
        return age_hits[0]

    name_hits = [row for row in rows if _name_tokens_overlap(name, row.display_name)]
    if len(name_hits) == 1:
        return name_hits[0]
    return None


def click_search_candidate(driver: Any, candidate: SearchCandidate) -> None:
    rows = _visible_result_rows(driver)
    row = None
    if candidate.row_index is not None and 0 <= candidate.row_index < len(rows):
        row = rows[candidate.row_index]
    else:
        for item in rows:
            cell = _name_cell(item)
            parsed = parse_name_cell(cell.text if cell is not None else item.text)
            if parsed["name"] and parsed["name"].casefold() == (candidate.display_name or "").casefold():
                row = item
                break
    if row is None:
        raise RuntimeError("Matching DRK search row is no longer visible.")
    cell = _name_cell(row)
    if cell is None:
        raise RuntimeError("Matching DRK search row has no name cell.")
    cell.click()


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


def _name_cell(row: Any) -> Any | None:
    cells = row.find_elements(By.CSS_SELECTOR, "td.name-cell")
    return cells[0] if cells else None


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
    if not matches:
        return []
    seen: set[str] = set()
    unique: list[SearchCandidate] = []
    for item in matches:
        if item.patient_id in seen:
            continue
        seen.add(item.patient_id)
        unique.append(item)
    return unique


def candidates_from_result_table(driver: Any) -> list[SearchCandidate]:
    """Read NAME / DOB / MRN / PHONE from the visible search dropdown."""
    candidates: list[SearchCandidate] = []
    for index, row in enumerate(_visible_result_rows(driver)):
        cells = row.find_elements(By.CSS_SELECTOR, "td")
        texts = [(cell.text or "").strip() for cell in cells]
        parsed = parse_name_cell(texts[0] if texts else (row.text or ""))
        patient_id = (
            (row.get_attribute("data-patient-id") or row.get_attribute("data-id") or "").strip()
        )
        candidates.append(
            SearchCandidate(
                patient_id=patient_id,
                display_name=parsed["name"],
                date_of_birth=texts[1] if len(texts) > 1 else None,
                mrn=texts[2] if len(texts) > 2 else None,
                phone=texts[3] if len(texts) > 3 else None,
                status_display=parsed["status"],
                source="search_table",
                row_index=index,
                age=parsed["age"],
                sex=parsed["sex"],
            )
        )
    return candidates


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
            if count == 0 and rows == 0:
                return summary, count, rows, True
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
    query = dashboard_search_query(patient_name)
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
    api_candidates = candidates_from_search_requests(driver, query=query)
    table_candidates = candidates_from_result_table(driver)
    candidates = _merge_candidates(api_candidates, table_candidates)

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


def _merge_candidates(
    api_candidates: list[SearchCandidate],
    table_candidates: list[SearchCandidate],
) -> list[SearchCandidate]:
    if not table_candidates:
        return api_candidates
    if not api_candidates or len(api_candidates) != len(table_candidates):
        return table_candidates
    merged: list[SearchCandidate] = []
    for api, table in zip(api_candidates, table_candidates):
        merged.append(
            SearchCandidate(
                patient_id=api.patient_id or table.patient_id,
                display_name=table.display_name or api.display_name,
                first_name=api.first_name,
                last_name=api.last_name,
                date_of_birth=table.date_of_birth or api.date_of_birth,
                mrn=table.mrn or api.mrn,
                phone=table.phone or api.phone,
                email=api.email,
                facility_name=api.facility_name,
                status_display=table.status_display or api.status_display,
                source="search_table" if table.date_of_birth or table.phone else api.source,
                row_index=table.row_index,
                age=table.age,
                sex=table.sex,
            )
        )
    return merged


def _title_tokens(*tokens: str) -> str:
    parts = []
    for token in tokens:
        cleaned = token.strip()
        if not cleaned:
            continue
        parts.append(cleaned[:1].upper() + cleaned[1:].lower() if len(cleaned) > 1 else cleaned.upper())
    return " ".join(parts)


def _clean_mrn(value: str | None) -> str | None:
    text = " ".join(str(value or "").split())
    return text or None


def _age_on(dob: str, as_of: date | None) -> int | None:
    try:
        born = datetime.strptime(dob, "%Y-%m-%d").date()
    except ValueError:
        return None
    today = as_of or date.today()
    years = today.year - born.year
    if (today.month, today.day) < (born.month, born.day):
        years -= 1
    return years


def _name_tokens_overlap(expected: str | None, actual: str | None) -> bool:
    wanted = {token for token in dashboard_search_query(expected or "").upper().split() if token}
    seen = {token for token in (actual or "").upper().split() if token}
    return bool(wanted) and wanted.issubset(seen)
