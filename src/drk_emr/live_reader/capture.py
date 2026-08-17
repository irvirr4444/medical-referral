"""Capture supported DRK dashboard card responses from one browser navigation."""

from __future__ import annotations

import gzip
import json
import time
import zlib
from typing import Any
from urllib.parse import urlsplit

from drk_emr.common.redaction import normalize_url_pattern


CARD_MARKERS: dict[str, tuple[str, ...]] = {
    "patient_information": ("/PatientDashboard/GetPatientDemographics/",),
    "admission": ("/PatientDashboard/GetAdmissionSummary/",),
    "communications": ("/PatientDashboard/GetCommunicationsPaginated/",),
    "encounters": ("/PatientDashboard/GetEncounters/",),
    "diagnosis": (
        "/PatientDashboard/GetDiagnosis",
        "/PatientDashboard/GetDiagnoses",
        "/PatientDashboard/GetDiagnosisCodes",
    ),
    "medications_allergies": (
        "/PatientDashboard/GetDoseSpotMedications/",
        "/PatientDashboard/GetDoseSpotAllergies/",
    ),
    "insurance": (
        "/PatientDashboard/GetInsurances/",
        "/PatientDashboard/GetEligibilityHistory/",
    ),
    "custom_scans": ("/PatientDashboard/GetCustomScans/",),
    "billing": ("/PatientDashboard/GetPatientBilling",),
    "pipeline": ("/PatientDashboard/API/GetBvPipelineStatus/",),
    "quick_notes": ("/PatientDashboard/GetQuickNotes/",),
}

# Same-origin XHR fallback when selenium-wire misses dashboard JSON.
CARD_FETCH_PATHS: tuple[tuple[str, str], ...] = (
    ("patient_information", "/PatientDashboard/GetPatientDemographics/{id}"),
    ("admission", "/PatientDashboard/GetAdmissionSummary/{id}"),
    ("communications", "/PatientDashboard/GetCommunicationsPaginated/{id}?page=1&pageSize=100"),
    ("encounters", "/PatientDashboard/GetEncounters/{id}?page=1&pageSize=100"),
    ("medications_allergies", "/PatientDashboard/GetDoseSpotMedications/{id}"),
    ("medications_allergies", "/PatientDashboard/GetDoseSpotAllergies/{id}"),
    ("insurance", "/PatientDashboard/GetInsurances/{id}"),
    ("insurance", "/PatientDashboard/GetEligibilityHistory/{id}"),
    ("custom_scans", "/PatientDashboard/GetCustomScans/{id}?skip=0&take=100"),
    ("billing", "/PatientDashboard/GetPatientBilling?patientId={id}"),
    ("pipeline", "/PatientDashboard/API/GetBvPipelineStatus/{id}"),
    ("quick_notes", "/PatientDashboard/GetQuickNotes/{id}"),
)


class DrkCaptureError(RuntimeError):
    pass


def wait_for_network_idle(
    driver: Any,
    *,
    idle_seconds: float,
    timeout_seconds: float,
) -> None:
    started = time.monotonic()
    last_count = len(getattr(driver, "requests", []))
    last_change = time.monotonic()
    while time.monotonic() - started < timeout_seconds:
        current_count = len(getattr(driver, "requests", []))
        if current_count != last_count:
            last_count = current_count
            last_change = time.monotonic()
        if time.monotonic() - last_change >= idle_seconds:
            return
        time.sleep(0.2)
    raise DrkCaptureError("DRK dashboard network did not become idle before timeout")


def capture_dashboard_cards(
    driver: Any,
    *,
    allowed_host: str,
    patient_id: str,
    require_demographics: bool = True,
) -> dict[str, dict[str, Any]]:
    latest: dict[tuple[str, str, str], dict[str, Any]] = {}
    for request in getattr(driver, "requests", []):
        response = getattr(request, "response", None)
        url = str(getattr(request, "url", "") or "")
        if response is None or urlsplit(url).netloc.casefold() != allowed_host.casefold():
            continue
        content_type = str(response.headers.get("Content-Type") or "").casefold()
        if "application/json" not in content_type:
            continue
        card_name = _card_for_url(url)
        if card_name is None:
            continue
        try:
            business_data = json.loads(_decode_body(response).decode("utf-8", errors="replace"))
        except (UnicodeError, json.JSONDecodeError):
            continue
        method = str(getattr(request, "method", "GET") or "GET").upper()
        normalized_url = normalize_url_pattern(url, patient_id)
        latest[(card_name, method, normalized_url)] = {
            "endpoint": {
                "method": method,
                "url": normalized_url,
                "status": int(response.status_code),
            },
            "business_data": business_data,
        }

    cards: dict[str, dict[str, Any]] = {}
    for card_name in CARD_MARKERS:
        records = [
            record
            for (record_card, _method, _url), record in latest.items()
            if record_card == card_name
        ]
        cards[card_name] = {
            "card": card_name,
            "record_count": len(records),
            "records": records,
        }
    if require_demographics and not cards["patient_information"]["records"]:
        raise DrkCaptureError("DRK patient demographics response was not captured")
    return cards


def fill_missing_cards_via_fetch(
    driver: Any,
    cards: dict[str, dict[str, Any]],
    patient_id: str,
) -> dict[str, dict[str, Any]]:
    """Fill cards selenium-wire missed by fetching APIs inside the logged-in page."""
    if not hasattr(driver, "execute_async_script"):
        return cards
    specs: list[dict[str, str]] = []
    for card_name, path in CARD_FETCH_PATHS:
        formatted = path.replace("{id}", patient_id)
        marker = path.split("{id}")[0].split("?")[0]
        existing = (cards.get(card_name) or {}).get("records") or []
        if any(
            marker.casefold()
            in str(((record.get("endpoint") or {}).get("url") if isinstance(record, dict) else "") or "").casefold()
            for record in existing
        ):
            continue
        specs.append({"card": card_name, "path": formatted})
    if not specs:
        return cards
    try:
        if hasattr(driver, "set_script_timeout"):
            driver.set_script_timeout(30)
        payloads = driver.execute_async_script(_IN_PAGE_FETCH_SCRIPT, specs)
    except Exception:
        return cards
    if not isinstance(payloads, list):
        return cards
    for item in payloads:
        if not isinstance(item, dict):
            continue
        card_name = str(item.get("card") or "")
        if card_name not in CARD_MARKERS:
            continue
        status = int(item.get("status") or 0)
        if status < 200 or status >= 300:
            continue
        body = item.get("body")
        if not isinstance(body, dict):
            continue
        card = cards.setdefault(
            card_name,
            {"card": card_name, "record_count": 0, "records": []},
        )
        records = list(card.get("records") or [])
        records.append(
            {
                "endpoint": {
                    "method": "GET",
                    "url": str(item.get("path") or ""),
                    "status": status,
                },
                "business_data": body,
            }
        )
        card["records"] = records
        card["record_count"] = len(records)
        cards[card_name] = card
    return cards


_IN_PAGE_FETCH_SCRIPT = """
const specs = arguments[0];
const done = arguments[arguments.length - 1];
Promise.all(specs.map(async (spec) => {
  try {
    const res = await fetch(spec.path, {
      credentials: 'same-origin',
      headers: { 'Accept': 'application/json' }
    });
    let body = null;
    try { body = await res.json(); } catch (error) { body = null; }
    return { card: spec.card, status: res.status, path: spec.path, body };
  } catch (error) {
    return { card: spec.card, status: 0, path: spec.path, body: null };
  }
})).then(done);
"""


def scrape_diagnosis_card(driver: Any) -> list[dict[str, Any]]:
    """Diagnosis codes are often server-rendered into #diagnosisCard, not a JSON API."""
    import re

    try:
        card = driver.find_element("id", "diagnosisCard")
    except Exception:
        return []
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", card)
        time.sleep(0.8)
    except Exception:
        pass

    try:
        rows = driver.find_elements("css selector", "#diagnosisCard .pd-dx-row")
    except Exception:
        return []
    diagnoses: list[dict[str, Any]] = []
    for row in rows:
        try:
            code_el = row.find_elements("css selector", ".pd-dx-code")
            desc_el = row.find_elements("css selector", ".pd-dx-desc")
            code = (code_el[0].text if code_el else "").strip()
            description = (desc_el[0].text if desc_el else "").strip()
            text = (row.text or "").strip()
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            added = next((ln.replace("Added ", "", 1) for ln in lines if ln.lower().startswith("added ")), None)
            is_primary = any(ln.upper() == "PRIMARY" for ln in lines)
            status = next((ln for ln in lines if ln.lower() in {"active", "inactive", "resolved"}), None)
            if not code and lines:
                maybe = lines[0]
                if re.match(r"^[A-Z]\d{2}", maybe):
                    code = maybe
            if not code:
                continue
            diagnoses.append(
                {
                    "code": code,
                    "description": description
                    or next(
                        (
                            ln
                            for ln in lines
                            if ln != code
                            and not ln.lower().startswith("added")
                            and ln.upper() != "PRIMARY"
                            and ln.lower() not in {"active", "inactive", "resolved"}
                        ),
                        None,
                    ),
                    "added": added,
                    "is_primary": is_primary,
                    "status": status,
                }
            )
        except Exception:
            continue
    return diagnoses


def attach_diagnosis_dom(cards: dict[str, dict[str, Any]], diagnoses: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if cards.get("diagnosis", {}).get("records") or not diagnoses:
        return cards
    cards["diagnosis"] = {
        "card": "diagnosis",
        "record_count": 1,
        "records": [
            {
                "endpoint": {
                    "method": "DOM",
                    "url": "/PatientDashboard/Index/?patientId={patientId}#diagnosisCard",
                    "status": 200,
                },
                "business_data": {
                    "source": "diagnosisCard DOM scrape",
                    "count": len(diagnoses),
                    "diagnoses": diagnoses,
                },
            }
        ],
    }
    return cards


def _card_for_url(url: str) -> str | None:
    for card_name, markers in CARD_MARKERS.items():
        if any(marker.casefold() in url.casefold() for marker in markers):
            return card_name
    return None


def _decode_body(response: Any) -> bytes:
    body = response.body or b""
    encoding = str(response.headers.get("Content-Encoding") or "").casefold()
    try:
        if "gzip" in encoding:
            return gzip.decompress(body)
        if "deflate" in encoding:
            return zlib.decompress(body)
    except (OSError, zlib.error):
        return body
    return body
