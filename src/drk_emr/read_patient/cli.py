from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import shutil
import sys
import time
import zlib
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import requests
from dotenv import load_dotenv
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from seleniumwire import webdriver

from drk_emr.common.models import DirectReplayResult, EndpointRecord, utc_timestamp_compact
from drk_emr.common.patient_search import (
    click_search_candidate,
    dashboard_search_query,
    search_patients_on_dashboard,
    select_search_candidate,
)
from drk_emr.common.redaction import (
    mask_sensitive_headers,
    normalize_url_pattern,
)


LOGIN_PATH = "/Login/LoginView"
DASHBOARD_PATH = "/Dashboard"
PATIENT_DASHBOARD_PATH = "/PatientDashboard/Index/"
READONLY_TAB_ALLOWLIST = ("insurance", "wound", "progress", "chart", "document", "history", "note")


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_log(message: str) -> None:
    print(message, file=sys.stderr)


def _require_env(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def _emr_root(emr_url: str) -> str:
    parsed = urlsplit(emr_url)
    if not parsed.scheme or not parsed.netloc:
        raise RuntimeError("EMR_URL must be an absolute URL, e.g. https://drkemr.com or https://drkemr.com/Login/LoginView")
    return f"{parsed.scheme}://{parsed.netloc}"


def _build_urls(emr_url: str, patient_id: str | None = None) -> tuple[str, str]:
    root = _emr_root(emr_url)
    login_url = f"{root}{LOGIN_PATH}"
    if patient_id:
        return login_url, f"{root}{PATIENT_DASHBOARD_PATH}?patientId={patient_id}"
    return login_url, f"{root}{DASHBOARD_PATH}"


def _extract_patient_id_from_url(url: str) -> str | None:
    parsed = urlsplit(url)
    query = parse_qs(parsed.query)
    values = query.get("patientId") or query.get("patientid")
    if values and values[0].strip():
        return values[0].strip()
    return None


def _open_patient_by_name(
    driver: webdriver.Chrome,
    patient_name: str,
    *,
    date_of_birth: str | None = None,
    phone: str | None = None,
    mrn: str | None = None,
) -> tuple[str, str]:
    """Search given-name-first, then open the row matching NAME/DOB/MRN/PHONE."""
    wait = WebDriverWait(driver, 25)
    query = dashboard_search_query(patient_name)
    snapshot = search_patients_on_dashboard(driver, patient_name)
    if snapshot.error and not snapshot.candidates:
        raise RuntimeError(f"DRK patient search failed: {snapshot.error} query={query!r}")
    chosen = select_search_candidate(
        snapshot.candidates,
        name=patient_name,
        date_of_birth=date_of_birth,
        phone=phone,
        mrn=mrn,
    )
    if chosen is None:
        rows = [
            {
                "name": item.display_name,
                "dob": item.date_of_birth,
                "mrn": item.mrn,
                "phone": item.phone,
                "age": item.age,
                "sex": item.sex,
            }
            for item in snapshot.candidates
        ]
        raise RuntimeError(
            "DRK search returned multiple rows and none uniquely matched DOB/phone/MRN. "
            f"query={query!r} rows={rows}"
        )
    _safe_log(
        f"Opening DRK search row query={query!r} name={chosen.display_name!r} "
        f"dob={chosen.date_of_birth!r} row={chosen.row_index}"
    )
    click_search_candidate(driver, chosen)
    wait.until(lambda d: _extract_patient_id_from_url(d.current_url) is not None)
    patient_id = _extract_patient_id_from_url(driver.current_url)
    if not patient_id:
        raise RuntimeError("Patient search succeeded visually but patientId was missing from the URL.")
    dashboard_url = f"{_emr_root(driver.current_url)}{PATIENT_DASHBOARD_PATH}?patientId={patient_id}"
    _safe_log(f"Opened patient by name; resolved patientId={patient_id}")
    return patient_id, dashboard_url


def _make_driver(profile_dir: Path) -> webdriver.Chrome:
    seleniumwire_options = {
        "request_storage": "memory",
        "disable_encoding": False,
    }
    options = ChromeOptions()
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--window-size=1600,1200")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-sync")
    return webdriver.Chrome(options=options, seleniumwire_options=seleniumwire_options)


def _is_json_response(request: Any, allowed_host: str) -> bool:
    response = request.response
    if response is None:
        return False
    parsed = urlsplit(request.url)
    if parsed.netloc.lower() != allowed_host.lower():
        return False
    content_type = (response.headers.get("Content-Type") or response.headers.get("content-type") or "").lower()
    return "application/json" in content_type


def _decode_response_body(response: Any) -> bytes:
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


def _json_or_text(body: bytes) -> Any:
    text = body.decode("utf-8", errors="replace")
    return json.loads(text)


def _wait_for_network_idle(driver: webdriver.Chrome, idle_seconds: float = 2.5, timeout_seconds: float = 30.0) -> None:
    start = time.time()
    last_len = len(driver.requests)
    last_change = time.time()
    while time.time() - start < timeout_seconds:
        current_len = len(driver.requests)
        if current_len != last_len:
            last_len = current_len
            last_change = time.time()
        if (time.time() - last_change) >= idle_seconds:
            return
        time.sleep(0.3)
    _safe_log("Network idle timeout reached; proceeding with captured requests so far.")


def _find_login_elements(driver: webdriver.Chrome) -> tuple[Any, Any, Any]:
    wait = WebDriverWait(driver, 20)
    username = wait.until(
        ec.presence_of_element_located(
            (
                By.XPATH,
                "//input[@placeholder='User Name' or @name='User Name' or @id='UserName' or @name='UserName']",
            )
        )
    )
    password = wait.until(
        ec.presence_of_element_located(
            (
                By.XPATH,
                "//input[@type='password' and (@placeholder='Password' or @name='Password' or @id='Password')]",
            )
        )
    )
    login_button = wait.until(ec.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Login']")))
    return username, password, login_button


def _detect_auth_blocker(driver: webdriver.Chrome) -> str | None:
    lower = driver.page_source.lower()
    if "captcha" in lower:
        return "CAPTCHA detected after login flow."
    if "two-factor" in lower or "2fa" in lower or "verification code" in lower:
        return "2FA challenge detected after login flow."
    return None


def _login(driver: webdriver.Chrome, login_url: str, username: str, password: str) -> tuple[bool, float, str]:
    start = time.time()
    driver.get(login_url)
    user_field, pass_field, login_button = _find_login_elements(driver)
    user_field.clear()
    user_field.send_keys(username)
    pass_field.clear()
    pass_field.send_keys(password)
    login_button.click()

    wait = WebDriverWait(driver, 30)
    try:
        wait.until(lambda d: DASHBOARD_PATH.lower() in d.current_url.lower() or LOGIN_PATH.lower() not in d.current_url.lower())
    except Exception:
        pass
    blocker = _detect_auth_blocker(driver)
    if blocker:
        return False, time.time() - start, blocker
    if LOGIN_PATH.lower() in driver.current_url.lower():
        if "invalid username and password" in driver.page_source.lower():
            return False, time.time() - start, "Login remained on login page with invalid credential message."
        return False, time.time() - start, "Login remained on login page."
    # Prefer landing on Dashboard; if redirected elsewhere authenticated, still continue.
    try:
        wait.until(lambda d: DASHBOARD_PATH.lower() in d.current_url.lower())
    except Exception:
        pass
    return True, time.time() - start, ""


def _section_click_candidates(driver: webdriver.Chrome) -> list[Any]:
    candidates: list[Any] = []
    for text in READONLY_TAB_ALLOWLIST:
        xpath = (
            f"//a[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text}')]"
            f" | //button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text}')]"
            f" | //li[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text}')]"
        )
        candidates.extend(driver.find_elements(By.XPATH, xpath))
    unique: list[Any] = []
    seen = set()
    for item in candidates:
        key = (item.tag_name, item.text.strip())
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _capture_section_requests(driver: webdriver.Chrome, section: str, allowed_host: str) -> tuple[list[EndpointRecord], list[dict[str, Any]]]:
    records: list[EndpointRecord] = []
    replay_meta: list[dict[str, Any]] = []
    for request in driver.requests:
        if not _is_json_response(request, allowed_host):
            continue
        response = request.response
        assert response is not None
        try:
            parsed_json = _json_or_text(_decode_response_body(response))
        except Exception:
            continue
        req_headers = {str(k): str(v) for k, v in request.headers.items()}
        resp_headers = {str(k): str(v) for k, v in response.headers.items()}
        body_text = request.body.decode("utf-8", errors="replace") if request.body else None
        records.append(
            EndpointRecord(
                section=section,
                url=request.url,
                method=request.method,
                request_headers=mask_sensitive_headers(req_headers),
                request_body=body_text,
                response_status=int(response.status_code),
                response_headers=mask_sensitive_headers(resp_headers),
                response_json=parsed_json,
                observed_at_utc=_now_utc_iso(),
            )
        )
        replay_meta.append(
            {
                "section": section,
                "url": request.url,
                "method": request.method,
                "status_code": int(response.status_code),
                "response_json": parsed_json,
                "request_headers_raw": req_headers,
            }
        )
    return records, replay_meta


def _choose_replay_targets(replay_meta: list[dict[str, Any]], max_items: int = 3) -> list[dict[str, Any]]:
    chosen: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in replay_meta:
        if item["method"].upper() != "GET":
            continue
        if int(item["status_code"]) >= 400:
            continue
        key = (item["method"], item["url"])
        if key in seen:
            continue
        seen.add(key)
        chosen.append(item)
        if len(chosen) >= max_items:
            break
    return chosen


def _filtered_replay_headers(headers: dict[str, str], include_optional: bool = True) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in headers.items():
        lk = key.lower()
        if lk in {"host", "content-length", "connection"}:
            continue
        if lk == "cookie":
            continue
        if not include_optional and lk in {"referer", "origin", "x-requested-with", "__requestverificationtoken", "x-xsrf-token"}:
            continue
        out[key] = value
    return out


def _json_equal(a: Any, b: Any) -> bool:
    return json.dumps(a, sort_keys=True, separators=(",", ":")) == json.dumps(b, sort_keys=True, separators=(",", ":"))


def _run_direct_replay(
    targets: list[dict[str, Any]],
    cookies: list[dict[str, Any]],
) -> tuple[list[DirectReplayResult], requests.Session]:
    session = requests.Session()
    for cookie in cookies:
        session.cookies.set(
            cookie.get("name"),
            cookie.get("value"),
            domain=cookie.get("domain"),
            path=cookie.get("path", "/"),
            secure=bool(cookie.get("secure", False)),
        )

    results: list[DirectReplayResult] = []
    for target in targets:
        headers_full = _filtered_replay_headers(target["request_headers_raw"], include_optional=True)
        resp_full = session.get(target["url"], headers=headers_full, timeout=30, allow_redirects=False)
        try:
            parsed = resp_full.json()
            match = "yes" if _json_equal(parsed, target["response_json"]) else "partial"
        except Exception:
            parsed = None
            match = "no"

        notes = "Replay with full observed headers."
        if resp_full.status_code < 400:
            headers_min = _filtered_replay_headers(target["request_headers_raw"], include_optional=False)
            resp_min = session.get(target["url"], headers=headers_min, timeout=30, allow_redirects=False)
            if resp_min.status_code < 400:
                notes += " Optional headers not required in this check."
                headers_full = headers_min
            else:
                notes += f" Optional-header drop failed ({resp_min.status_code}), keeping full header set."

        results.append(
            DirectReplayResult(
                endpoint_url=target["url"],
                method=target["method"],
                section=target["section"],
                headers_sent=sorted(headers_full.keys()),
                status_code=resp_full.status_code,
                success=resp_full.status_code < 400,
                json_match=match,
                notes=notes,
            )
        )
    return results, session


def _run_lifetime_probe(session: requests.Session, endpoint_url: str, headers: dict[str, str], intervals_minutes: list[int]) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    elapsed_minutes = 0
    for minutes in intervals_minutes:
        sleep_minutes = max(0, minutes - elapsed_minutes)
        if sleep_minutes:
            _safe_log(f"Waiting {sleep_minutes} minute(s) before session probe at +{minutes}m...")
            time.sleep(sleep_minutes * 60)
        resp = session.get(endpoint_url, headers=headers, timeout=30, allow_redirects=False)
        observations.append(
            {
                "minutes_after_login": minutes,
                "status_code": resp.status_code,
                "content_type": resp.headers.get("Content-Type", ""),
                "looks_like_login_html": "text/html" in resp.headers.get("Content-Type", "").lower()
                and "login" in resp.text[:500].lower(),
            }
        )
        if resp.status_code >= 400:
            break
        elapsed_minutes = minutes
    return observations


def _write_json_file(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    os.chmod(temp, 0o600)
    temp.replace(path)
    os.chmod(path, 0o600)


def _persist_catalog(records: list[EndpointRecord], catalog_path: Path) -> None:
    catalog_payload = [record.to_dict() for record in records]
    _write_json_file(catalog_path, catalog_payload)


def _print_catalog_terminal(records: list[EndpointRecord]) -> None:
    # Intentionally excludes raw cookie/token values because headers were masked at capture time.
    print(json.dumps([record.to_dict() for record in records], indent=2, ensure_ascii=True))


BUSINESS_ENDPOINT_MARKERS = (
    "/PatientDashboard/GetPatientDemographics/",
    "/PatientDashboard/GetAdmissionSummary/",
    "/PatientDashboard/GetCommunicationsPaginated/",
    "/PatientDashboard/GetEncounters/",
    "/PatientDashboard/GetDiagnosis",
    "/PatientDashboard/GetDiagnoses",
    "/PatientDashboard/GetDoseSpotMedications/",
    "/PatientDashboard/GetDoseSpotAllergies/",
    "/PatientDashboard/GetInsurances/",
    "/PatientDashboard/GetEligibilityHistory/",
    "/PatientDashboard/GetCustomScans/",
    "/PatientDashboard/GetPatientBilling",
    "/PatientDashboard/API/GetBvPipelineStatus/",
)

# Dashboard card -> endpoint path markers (business payloads only).
DASHBOARD_CARD_MARKERS: dict[str, tuple[str, ...]] = {
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
}


def _safe_patient_folder_name(patient_name: str | None, patient_id: str | None = None) -> str:
    """Filesystem-safe folder name for patient outputs."""
    raw = (patient_name or "").strip()
    if not raw and patient_id:
        raw = f"patient-{patient_id}"
    if not raw:
        raw = "unknown-patient"
    cleaned = re.sub(r"[^\w\s\-]+", "", raw, flags=re.UNICODE)
    cleaned = re.sub(r"[\s\-]+", "_", cleaned).strip("_")
    return cleaned or "unknown-patient"


def _latest_matching_records(records: list[EndpointRecord], markers: tuple[str, ...]) -> list[EndpointRecord]:
    latest: dict[tuple[str, str], EndpointRecord] = {}
    for record in records:
        if any(marker in record.url for marker in markers):
            latest[(record.method, record.url)] = record
    return [latest[key] for key in sorted(latest)]


def _scrape_diagnosis_card(driver: webdriver.Chrome) -> list[dict[str, Any]]:
    """Diagnosis codes are often server-rendered into #diagnosisCard, not a JSON API."""
    try:
        card = driver.find_element(By.ID, "diagnosisCard")
    except Exception:
        return []
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", card)
        time.sleep(0.8)
    except Exception:
        pass

    rows = driver.find_elements(By.CSS_SELECTOR, "#diagnosisCard .pd-dx-row")
    diagnoses: list[dict[str, Any]] = []
    for row in rows:
        try:
            code_el = row.find_elements(By.CSS_SELECTOR, ".pd-dx-code")
            desc_el = row.find_elements(By.CSS_SELECTOR, ".pd-dx-desc")
            code = (code_el[0].text if code_el else "").strip()
            description = (desc_el[0].text if desc_el else "").strip()
            text = (row.text or "").strip()
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            added = next((ln.replace("Added ", "", 1) for ln in lines if ln.lower().startswith("added ")), None)
            is_primary = any(ln.upper() == "PRIMARY" for ln in lines)
            status = next((ln for ln in lines if ln.lower() in {"active", "inactive", "resolved"}), None)
            if not code and lines:
                # fallback: first token looks like ICD code
                maybe = lines[0]
                if re.match(r"^[A-Z]\d{2}", maybe):
                    code = maybe
            if code.endswith(".") and len(code) <= 5:
                # keep trailing dot when shown that way in UI (e.g. I10.)
                pass
            if not code:
                continue
            diagnoses.append(
                {
                    "code": code,
                    "description": description or next((ln for ln in lines if ln != code and not ln.lower().startswith("added") and ln.upper() != "PRIMARY" and ln.lower() not in {"active", "inactive", "resolved"}), None),
                    "added": added,
                    "is_primary": is_primary,
                    "status": status,
                }
            )
        except Exception:
            continue
    return diagnoses


def _persist_dashboard_card_jsons(
    records: list[EndpointRecord],
    output_dir: Path,
    patient_id: str,
    diagnosis_dom: list[dict[str, Any]] | None = None,
) -> dict[str, Path]:
    """Write one business-only JSON per patient dashboard card."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths: dict[str, Path] = {}
    for card_name, markers in DASHBOARD_CARD_MARKERS.items():
        matched = _latest_matching_records(records, markers)
        card_records = [
            {
                "endpoint": {
                    "method": record.method,
                    "url": normalize_url_pattern(record.url, patient_id),
                    "status": record.response_status,
                },
                "business_data": record.response_json,
            }
            for record in matched
        ]
        # Fallback: scrape diagnosis card DOM when no diagnosis JSON API was captured.
        if card_name == "diagnosis" and not card_records and diagnosis_dom:
            card_records = [
                {
                    "endpoint": {
                        "method": "DOM",
                        "url": f"/PatientDashboard/Index/?patientId={{patientId}}#diagnosisCard",
                        "status": 200,
                    },
                    "business_data": {
                        "source": "diagnosisCard DOM scrape",
                        "count": len(diagnosis_dom),
                        "diagnoses": diagnosis_dom,
                    },
                }
            ]
        payload = {
            "card": card_name,
            "record_count": len(card_records),
            "records": card_records,
        }
        path = output_dir / f"{card_name}.json"
        _write_json_file(path, payload)
        output_paths[card_name] = path
    return output_paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DRK EMR endpoint discovery runner.")
    parser.add_argument("--output-dir", default="output", help="Base output directory (gitignored).")
    parser.add_argument(
        "--lifetime-window",
        type=int,
        default=0,
        choices=(0, 5, 15, 60),
        help="Optional cookie lifetime probe minutes. Default 0 = finish immediately after fetch.",
    )
    parser.add_argument(
        "--print-catalog",
        action="store_true",
        help="Print captured endpoint catalog to terminal after capture (sensitive auth values remain masked).",
    )
    args = parser.parse_args(argv)

    load_dotenv()
    emr_url = _require_env("EMR_URL")
    username = _require_env("EMR_USERNAME")
    password = _require_env("EMR_PASSWORD")
    patient_name = os.getenv("TEST_PATIENT_NAME", "").strip()
    patient_id = os.getenv("TEST_PATIENT_ID", "").strip()
    patient_dob = os.getenv("TEST_PATIENT_DOB", "").strip() or None
    patient_phone = os.getenv("TEST_PATIENT_PHONE", "").strip() or None
    patient_mrn = os.getenv("TEST_PATIENT_MRN", "").strip() or None
    if not patient_name and not patient_id:
        raise RuntimeError("Set TEST_PATIENT_NAME (preferred) or TEST_PATIENT_ID in .env")
    login_url, home_or_dashboard_url = _build_urls(emr_url, patient_id if not patient_name else None)
    allowed_host = urlsplit(login_url).netloc
    patient_dashboard_url = home_or_dashboard_url

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = utc_timestamp_compact()
    patient_folder = _safe_patient_folder_name(patient_name, patient_id)
    # Single patient output location: output/drk-browser-profile/<patient-name>/
    patient_output_dir = output_dir / "drk-browser-profile" / patient_folder
    patient_output_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(patient_output_dir, 0o700)
    catalog_path = patient_output_dir / f"endpoint_catalog_{ts}.json"
    # Temporary Chrome profile nested under the patient folder; deleted after run.
    chrome_profile_dir = patient_output_dir / "_chrome_profile"
    if chrome_profile_dir.exists():
        shutil.rmtree(chrome_profile_dir, ignore_errors=True)
    chrome_profile_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(chrome_profile_dir, 0o700)

    login_ok = False
    login_message = ""
    login_seconds = 0.0
    records: list[EndpointRecord] = []
    replay_meta: list[dict[str, Any]] = []
    replay_results: list[DirectReplayResult] = []
    lifetime_obs: list[dict[str, Any]] = []
    card_json_paths: dict[str, Path] = {}

    driver: webdriver.Chrome | None = None
    session_headers_for_probe: dict[str, str] = {}
    probe_url = ""

    try:
        driver = _make_driver(chrome_profile_dir)
        login_ok, login_seconds, login_message = _login(driver, login_url, username, password)
        if not login_ok:
            raise RuntimeError(f"Login failed: {login_message}")

        # Resolve patient by name via Dashboard search (preferred), else direct ID URL.
        if patient_name:
            patient_id, patient_dashboard_url = _open_patient_by_name(
                driver,
                patient_name,
                date_of_birth=patient_dob,
                phone=patient_phone,
                mrn=patient_mrn,
            )
        else:
            patient_dashboard_url = home_or_dashboard_url

        # Re-resolve folder if name/id became available after search.
        patient_folder = _safe_patient_folder_name(patient_name, patient_id)
        patient_output_dir = output_dir / "drk-browser-profile" / patient_folder
        patient_output_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(patient_output_dir, 0o700)
        catalog_path = patient_output_dir / f"endpoint_catalog_{ts}.json"

        # Capture patient dashboard JSON APIs (card data loads on this page).
        driver.requests.clear()
        driver.get(patient_dashboard_url)
        _wait_for_network_idle(driver)
        phase_records, phase_meta = _capture_section_requests(driver, "Dashboard load", allowed_host)
        records.extend(phase_records)
        replay_meta.extend(phase_meta)
        _persist_catalog(records, catalog_path)
        _safe_log(f"Captured {len(phase_records)} JSON request(s) from dashboard load.")

        diagnosis_dom = _scrape_diagnosis_card(driver)
        if diagnosis_dom:
            _safe_log(f"Scraped {len(diagnosis_dom)} diagnosis code(s) from diagnosisCard DOM.")

        if args.print_catalog:
            _print_catalog_terminal(records)
        card_json_paths = _persist_dashboard_card_jsons(
            records,
            patient_output_dir,
            patient_id,
            diagnosis_dom=diagnosis_dom,
        )

        # Optional quick direct API replay (no wait unless --lifetime-window > 0).
        targets = _choose_replay_targets(replay_meta, max_items=3)
        cookies = driver.get_cookies()
        replay_results, req_session = _run_direct_replay(targets, cookies)
        if replay_results:
            first = replay_results[0]
            original = next(item for item in targets if item["url"] == first.endpoint_url)
            session_headers_for_probe = _filtered_replay_headers(original["request_headers_raw"], include_optional=True)
            probe_url = first.endpoint_url

        driver.quit()
        driver = None

        if args.lifetime_window > 0 and probe_url:
            intervals = (
                [5]
                if args.lifetime_window == 5
                else [5, 10, 15]
                if args.lifetime_window == 15
                else [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]
            )
            lifetime_obs = _run_lifetime_probe(req_session, probe_url, session_headers_for_probe, intervals)

        _persist_catalog(records, catalog_path)

        summary = {
            "patient_output_dir": str(patient_output_dir),
            "catalog_path": str(catalog_path),
            "resolved_patient_id": patient_id,
            "opened_by_name": bool(patient_name),
            "login_seconds": login_seconds,
            "login_message": login_message,
            "card_json_paths": {k: str(v) for k, v in card_json_paths.items()},
            "captured_records": len(records),
            "replay_results": [asdict(item) for item in replay_results],
            "lifetime_observations": lifetime_obs,
        }
        _safe_log(json.dumps(summary, indent=2))
        return 0
    except Exception as exc:
        _safe_log(f"Run aborted: {exc}")
        return 1
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
        # Only remove temporary Chrome profile; keep patient JSON outputs.
        if chrome_profile_dir.exists():
            shutil.rmtree(chrome_profile_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

