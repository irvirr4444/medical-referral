"""Export two complete read-only snapshots for each reviewed sample patient.

For each patient this writes:

* ``<slug>.monday.json`` — the current Master Sheet row with every column.
* ``<slug>.drk.json`` — every supported DRK dashboard business payload plus
  additional patient-specific JSON responses observed during the Selenium read.

The files contain real PHI, are written beneath ``output/`` (gitignored), and
must not be committed or shared outside the authorized restricted workspace.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import re
import shutil
import sys
import tempfile
import unicodedata
import zlib
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urljoin, urlsplit

import requests
from pypdf import PdfReader


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from dotenv import load_dotenv  # noqa: E402

from drk_emr.common.browser import (  # noqa: E402
    DASHBOARD_PATH,
    clear_network_requests,
    emr_root,
)
from drk_emr.common.patient_search import (  # noqa: E402
    search_patients_on_dashboard,
    select_search_candidate,
)
from drk_emr.common.redaction import normalize_url_pattern  # noqa: E402
from drk_emr.live_reader import DrkLiveReaderConfig, DrkPatientReader  # noqa: E402
from drk_emr.live_reader.capture import wait_for_network_idle  # noqa: E402
from referral_pipeline.integrations.monday.reader import (  # noqa: E402
    fetch_items_by_column_value,
    fetch_items_by_name_search,
    find_patients,
)
from referral_pipeline.integrations.monday.transport import monday_graphql  # noqa: E402


BOARD_ID = "5815942462"
MONDAY_FULL_ROW_QUERY = """
query ($boardIds: [ID!], $itemIds: [ID!]!) {
  boards(ids: $boardIds) {
    id
    name
    columns { id title type settings_str }
  }
  items(ids: $itemIds) {
    id
    name
    created_at
    updated_at
    state
    board { id name }
    group { id title }
    column_values { id text value }
  }
}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-dir", type=Path, default=REPO_ROOT / "eval" / "gold")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "output" / "activity-logs" / "monday-patients",
    )
    parser.add_argument(
        "--patient",
        action="append",
        default=[],
        help="Export only this reviewed patient; repeat to select multiple patients.",
    )
    parser.add_argument(
        "--allow-unreviewed",
        action="store_true",
        help="Allow explicit patient names outside eval/gold; matching must still be unique.",
    )
    parser.add_argument("--board-id", default=BOARD_ID)
    return parser.parse_args()


def load_identities(gold_dir: Path) -> list[dict[str, Any]]:
    identities: list[dict[str, Any]] = []
    for path in sorted(gold_dir.glob("*.gold.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        record = payload.get("record") or {}
        identities.append(
            {
                "name": record.get("patient_name"),
                "date_of_birth": record.get("patient_dob"),
                "phone": record.get("patient_phone"),
                "mrn": record.get("patient_mrn"),
            }
        )
    if len(identities) != 7:
        raise RuntimeError(f"Expected 7 reviewed sample identities, found {len(identities)}")
    return identities


def patient_slug(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", normalized.casefold()).strip("-") or "patient"


def select_identities(
    identities: list[dict[str, Any]], requested: list[str], *, allow_unreviewed: bool = False
) -> list[dict[str, Any]]:
    if not requested:
        return identities
    selected: list[dict[str, Any]] = []
    for requested_name in requested:
        requested_slug = patient_slug(requested_name)
        requested_terms = set(requested_slug.split("-"))
        matches = [
            identity
            for identity in identities
            if requested_slug == patient_slug(str(identity.get("name") or ""))
            or requested_terms
            == set(patient_slug(str(identity.get("name") or "")).split("-"))
        ]
        if len(matches) != 1:
            if allow_unreviewed and not matches:
                selected.append({"name": requested_name})
                continue
            names = ", ".join(str(item.get("name")) for item in identities)
            raise RuntimeError(
                f"--patient {requested_name!r} matched {len(matches)} patients; choose one of: {names}"
            )
        if matches[0] not in selected:
            selected.append(matches[0])
    return selected


def name_similarity(left: str, right: str) -> float:
    def canonical(value: str) -> str:
        text = " ".join(value.casefold().replace("-", " ").split())
        if "," in text:
            family, given = [part.strip() for part in text.split(",", 1)]
            text = f"{given} {family}"
        return "".join(char for char in text if char.isalnum() or char == " ")

    return SequenceMatcher(None, canonical(left), canonical(right)).ratio()


def find_monday_item(identity: dict[str, Any], board_id: str) -> dict[str, Any]:
    candidates = list(
        fetch_items_by_name_search(name=identity["name"], board_id=board_id).items
    )
    matches = find_patients(candidates, name=identity["name"])
    if len(matches) != 1 and identity.get("date_of_birth"):
        dob_value = datetime.strptime(identity["date_of_birth"], "%m/%d/%Y").strftime(
            "%Y-%m-%d"
        )
        dob_candidates = list(
            fetch_items_by_column_value(
                field="dob", value=dob_value, board_id=board_id, max_items=100
            ).items
        )
        combined = {str(item.get("id")): item for item in [*candidates, *dob_candidates]}
        ranked = sorted(
            (
                (name_similarity(identity["name"], str(item.get("name") or "")), item)
                for item in combined.values()
            ),
            key=lambda pair: pair[0],
            reverse=True,
        )
        matches = [ranked[0][1]] if ranked and ranked[0][0] >= 0.72 else []
    if len(matches) != 1:
        raise RuntimeError(
            f"Monday patient {identity['name']!r} matched {len(matches)} items"
        )
    return matches[0]


def parse_monday_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def monday_full_row(identity: dict[str, Any], board_id: str) -> dict[str, Any]:
    matched = find_monday_item(identity, board_id)
    response = monday_graphql(
        MONDAY_FULL_ROW_QUERY,
        variables={"boardIds": [str(board_id)], "itemIds": [str(matched["id"])]},
    )
    data = response.get("data") or {}
    boards = data.get("boards") or []
    items = data.get("items") or []
    if len(boards) != 1 or len(items) != 1:
        raise RuntimeError(f"Monday full-row query failed for {identity['name']!r}")

    board = boards[0]
    item = items[0]
    definitions = {str(column["id"]): column for column in board.get("columns") or []}
    values = {str(value["id"]): value for value in item.get("column_values") or []}
    columns: list[dict[str, Any]] = []
    for column_id, definition in definitions.items():
        current = values.get(column_id) or {}
        columns.append(
            {
                "id": column_id,
                "title": definition.get("title"),
                "type": definition.get("type"),
                "text": current.get("text"),
                "value": parse_monday_value(current.get("value")),
            }
        )

    return {
        "item_id": str(item.get("id")),
        "name": item.get("name"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "state": item.get("state"),
        "group": item.get("group"),
        "columns": columns,
    }


def drk_match(reader: DrkPatientReader, identity: dict[str, Any]) -> str:
    assert reader.driver is not None
    raw_name = " ".join(str(identity["name"]).split())
    variants = [raw_name]
    if "," in raw_name:
        family, given = [part.strip() for part in raw_name.split(",", 1)]
        variants.extend([given, f"{given.split()[0]} {family.split()[0]}"])
    else:
        tokens = raw_name.split()
        if len(tokens) >= 3:
            variants.extend([f"{tokens[0]} {tokens[-1]}", f"{tokens[-1]} {tokens[0]}"])

    seen_queries: set[str] = set()
    last_count = 0
    for query in variants:
        if query.casefold() in seen_queries:
            continue
        seen_queries.add(query.casefold())
        reader.driver.get(f"{emr_root(reader.config.emr_url)}{DASHBOARD_PATH}")
        snapshot = search_patients_on_dashboard(reader.driver, query)
        last_count = len(snapshot.candidates)
        match = select_search_candidate(
            snapshot.candidates,
            name=identity["name"],
            date_of_birth=identity.get("date_of_birth"),
            phone=identity.get("phone"),
            mrn=identity.get("mrn"),
        )
        if match is not None and match.patient_id:
            return str(match.patient_id)
    raise RuntimeError(
        f"DRK patient {identity['name']!r} was not uniquely matched "
        f"({last_count} candidates across safe name variants)"
    )


def decode_response_body(response: Any) -> bytes:
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


def normalize_ids(value: str, identifiers: list[str]) -> str:
    normalized = value
    for identifier in sorted(set(identifiers), key=len, reverse=True):
        if identifier:
            normalized = normalized.replace(identifier, "{id}")
    return normalized


def capture_current_json_responses(
    driver: Any, identifiers: list[str]
) -> list[dict[str, Any]]:
    """Capture all same-origin JSON generated by the current read-only page."""
    allowed_host = urlsplit(str(driver.current_url)).netloc.casefold()
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for request in getattr(driver, "requests", []):
        response = getattr(request, "response", None)
        url = str(getattr(request, "url", "") or "")
        if response is None or urlsplit(url).netloc.casefold() != allowed_host:
            continue
        content_type = str(response.headers.get("Content-Type") or "").casefold()
        if "application/json" not in content_type:
            continue
        try:
            payload = json.loads(
                decode_response_body(response).decode("utf-8", errors="replace")
            )
        except (UnicodeError, json.JSONDecodeError):
            continue
        method = str(getattr(request, "method", "GET") or "GET").upper()
        normalized_url = normalize_ids(url, identifiers)
        latest[(method, normalized_url)] = {
            "endpoint": {
                "method": method,
                "url": normalized_url,
                "status": int(response.status_code),
            },
            "data": payload,
        }
    return [latest[key] for key in sorted(latest)]


def fetch_json_in_page(
    driver: Any,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Use the authenticated page session for an explicitly read-only JSON call."""
    script = """
const path = arguments[0];
const method = arguments[1];
const payload = arguments[2];
const done = arguments[arguments.length - 1];
const options = {
  method,
  credentials: 'same-origin',
  headers: { 'Accept': 'application/json' }
};
if (payload !== null) {
  options.headers['Content-Type'] = 'application/json';
  options.body = JSON.stringify(payload);
}
fetch(path, options).then(async response => {
  const text = await response.text();
  let body = null;
  try { body = JSON.parse(text); } catch (error) { body = null; }
  done({ status: response.status, body, raw_text: body === null ? text : null });
}).catch(error => done({ status: 0, body: null, error: String(error) }));
"""
    if hasattr(driver, "set_script_timeout"):
        driver.set_script_timeout(60)
    result = driver.execute_async_script(script, path, method, payload)
    return result if isinstance(result, dict) else {"status": 0, "body": None}


def page_link_inventory(driver: Any, identifiers: list[str]) -> list[dict[str, Any]]:
    """Inventory same-origin links without following unknown or mutating routes."""
    links = driver.execute_script(
        """
const origin = window.location.origin;
return Array.from(document.querySelectorAll('a[href]')).map(anchor => {
  try {
    const url = new URL(anchor.href, document.baseURI);
    if (url.origin !== origin) return null;
    return {
      url: url.href,
      text: (anchor.innerText || anchor.textContent || '').trim(),
      title: anchor.title || null
    };
  } catch (error) { return null; }
}).filter(Boolean);
"""
    )
    unique: dict[str, dict[str, Any]] = {}
    for link in links if isinstance(links, list) else []:
        if not isinstance(link, dict):
            continue
        url = str(link.get("url") or "")
        if not url:
            continue
        normalized = normalize_ids(url, identifiers)
        unique[normalized] = {
            "url": normalized,
            "text": str(link.get("text") or "").strip() or None,
            "title": link.get("title"),
        }
    return [unique[key] for key in sorted(unique)]


def url_inventory(value: Any) -> list[str]:
    """Collect absolute URLs exposed by DRK payloads for coverage auditing."""
    found: set[str] = set()
    if isinstance(value, dict):
        for item in value.values():
            found.update(url_inventory(item))
    elif isinstance(value, list):
        for item in value:
            found.update(url_inventory(item))
    elif isinstance(value, str) and value.casefold().startswith(("http://", "https://")):
        found.add(value)
    return sorted(found)


def read_only_json_get(driver: Any, path: str) -> dict[str, Any]:
    result = fetch_json_in_page(driver, path)
    result["endpoint"] = {"method": "GET", "url": path}
    return result


def therapy_payloads(
    driver: Any,
    patient_id: str,
    pipeline_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Capture patient-scoped therapy details exposed by DRK's tracker UIs."""
    pipeline_data: dict[str, Any] = {}
    for record in pipeline_records:
        body = record.get("data") if isinstance(record, dict) else None
        if not isinstance(body, dict):
            continue
        candidate = body.get("data") if isinstance(body.get("data"), dict) else body
        if candidate.get("pipelineEntryId"):
            pipeline_data = candidate
            break

    result: dict[str, Any] = {
        "pls_dressing_state": read_only_json_get(
            driver, f"/BvTherapy/API/GetPlsDressingState/{patient_id}"
        ),
        "pipeline_entry": [],
        "tracks": [],
    }
    entry_id = str(pipeline_data.get("pipelineEntryId") or "").strip()
    if entry_id:
        for path in (
            f"/BvTherapy/API/GetHub/{entry_id}",
            f"/BvPipeline/API/GetTracksForEntry/{entry_id}",
            f"/BvAuth/API/GetByEntry/{entry_id}",
            f"/BvTherapy/API/GetShuttle?pipelineEntryId={entry_id}",
        ):
            result["pipeline_entry"].append(read_only_json_get(driver, path))

    for track in pipeline_data.get("therapyTrackStatuses") or []:
        if not isinstance(track, dict):
            continue
        track_id = str(track.get("trackId") or "").strip()
        if not track_id:
            continue
        therapy_name = str(track.get("therapyTypeName") or "").strip()
        paths = [
            f"/BvTherapy/API/GetTrackerHeader/{track_id}",
            f"/BvTherapy/API/GetTrackerAuths/{track_id}",
            f"/BvPipeline/API/Automation/EventsForTrack/{track_id}",
            f"/BvPipeline/API/VisitStatusForTrack/{track_id}",
            f"/BvTherapy/API/GetShuttle?therapyTrackId={track_id}",
        ]
        specific = {
            "graft": "GetGraftTracker",
            "mist": "GetMistTracker",
            "collagen": "GetCollagenTracker",
            "lymphedema": "GetLymphedemaTracker",
        }.get(therapy_name.casefold())
        if specific:
            paths.append(f"/BvTherapy/API/{specific}/{track_id}")
        if therapy_name.casefold() in {"mist", "lymphedema"}:
            paths.append(
                f"/BvTherapy/API/GetScheduleConflicts?therapyTrackId={track_id}"
            )
        result["tracks"].append(
            {
                "track_id": track_id,
                "therapy_type": therapy_name or None,
                "payloads": [read_only_json_get(driver, path) for path in paths],
            }
        )
    return result


def browser_session(driver: Any) -> requests.Session:
    session = requests.Session()
    try:
        user_agent = driver.execute_script("return navigator.userAgent")
        if user_agent:
            session.headers["User-Agent"] = str(user_agent)
    except Exception:
        pass
    for cookie in driver.get_cookies():
        session.cookies.set(
            cookie.get("name"),
            cookie.get("value"),
            domain=cookie.get("domain"),
            path=cookie.get("path", "/"),
        )
    return session


def safe_filename(value: str, *, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode(
        "ascii"
    )
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", normalized).strip("._")
    return cleaned[:160] or fallback


def download_binary(
    session: requests.Session,
    url: str,
    destination: Path,
    *,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    digest = hashlib.sha256()
    size = 0
    try:
        with session.get(url, stream=True, timeout=timeout_seconds) as response:
            response.raise_for_status()
            content_type = str(response.headers.get("Content-Type") or "")
            with temporary.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    handle.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
        temporary.replace(destination)
        return {
            "status": "downloaded",
            "path": str(destination.resolve()),
            "bytes": size,
            "sha256": digest.hexdigest(),
            "content_type": content_type,
        }
    except Exception as error:
        temporary.unlink(missing_ok=True)
        return {
            "status": "error",
            "url": url,
            "error_type": type(error).__name__,
            "error": str(error),
        }


def lists_named(value: Any, name: str) -> list[list[Any]]:
    found: list[list[Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == name and isinstance(item, list):
                found.append(item)
            found.extend(lists_named(item, name))
    elif isinstance(value, list):
        for item in value:
            found.extend(lists_named(item, name))
    return found


def card_entities(cards: dict[str, dict[str, Any]], card: str, entity: str) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for record in (cards.get(card) or {}).get("records") or []:
        for collection in lists_named(record.get("business_data"), entity):
            entities.extend(item for item in collection if isinstance(item, dict))
    unique: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(entities):
        key = str(item.get("id") or item.get("encounterServiceId") or index)
        unique[key] = item
    return list(unique.values())


def download_scans(
    cards: dict[str, dict[str, Any]],
    session: requests.Session,
    output_dir: Path,
) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    for index, scan in enumerate(card_entities(cards, "custom_scans", "scans"), start=1):
        url = str(scan.get("fileUrl") or "").strip()
        if not url:
            manifest.append({"scan_id": scan.get("id"), "status": "missing_url"})
            continue
        extension = str(scan.get("fileType") or "bin").casefold().lstrip(".") or "bin"
        base_name = safe_filename(
            str(scan.get("fileName") or scan.get("description") or ""),
            fallback=f"scan-{index}",
        )
        if not base_name.casefold().endswith(f".{extension}"):
            base_name = f"{base_name}.{extension}"
        scan_id = str(scan.get("id") or index)
        destination = output_dir / f"{scan_id}-{base_name}"
        result = download_binary(session, url, destination)
        result.update(
            {
                "scan_id": scan.get("id"),
                "file_name": scan.get("fileName"),
                "file_type": scan.get("fileType"),
            }
        )
        manifest.append(result)
    return manifest


def note_dom(driver: Any) -> dict[str, Any]:
    return driver.execute_script(
        """
const blocked = /(password|token|csrf|xsrf|verification)/i;
const fields = Array.from(document.querySelectorAll('input, select, textarea, [contenteditable="true"]'))
  .map((element, index) => {
    const name = element.name || element.id || `field-${index}`;
    if (blocked.test(name)) return null;
    const type = (element.type || element.tagName || '').toLowerCase();
    let value = element.value;
    if (type === 'checkbox' || type === 'radio') value = !!element.checked;
    let selectedText = null;
    if (element.tagName === 'SELECT' && element.selectedIndex >= 0) {
      selectedText = element.options[element.selectedIndex]?.text || null;
    }
    if (element.isContentEditable) value = element.innerText || element.textContent || '';
    return { name, type, value, selected_text: selectedText };
  }).filter(Boolean);
return {
  title: document.title,
  url: window.location.href,
  text: document.body ? document.body.innerText : '',
  fields
};
"""
    )


def download_printable_note_source(
    session: requests.Session,
    base_url: str,
    encounter: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any] | None:
    encounter_id = str(encounter.get("id") or "").strip()
    service_id = str(encounter.get("encounterServiceId") or "").strip()
    if not encounter_id:
        return None
    path = (
        f"/Note/PrintableNote/{service_id}"
        if bool(encounter.get("isBeta")) and service_id
        else f"/Encounter/ProgressNote?EncounterId={encounter_id}"
    )
    url = urljoin(base_url, path)
    provisional = output_dir / f"encounter-{encounter_id}.bin"
    result = download_binary(session, url, provisional)
    if result.get("status") != "downloaded":
        result["encounter_id"] = encounter_id
        return result
    content_type = str(result.get("content_type") or "").casefold()
    extension = ".pdf" if "pdf" in content_type else ".html" if "html" in content_type else ".bin"
    final = provisional.with_suffix(extension)
    provisional.replace(final)
    result["path"] = str(final.resolve())
    result["encounter_id"] = encounter_id
    result["artifact_kind"] = "printable_source"
    return result


def render_printable_note_pdf(
    driver: Any,
    base_url: str,
    encounter: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any] | None:
    """Render DRK's authenticated printable note view into a standalone PDF."""
    encounter_id = str(encounter.get("id") or "").strip()
    service_id = str(encounter.get("encounterServiceId") or "").strip()
    if not encounter_id:
        return None
    path = (
        f"/Note/PrintableNote/{service_id}"
        if bool(encounter.get("isBeta")) and service_id
        else f"/Encounter/ProgressNote?EncounterId={encounter_id}"
    )
    url = urljoin(base_url, path)
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"encounter-{encounter_id}.pdf"
    temporary = destination.with_suffix(".pdf.part")
    try:
        clear_network_requests(driver)
        driver.get(url)
        try:
            wait_for_network_idle(driver, idle_seconds=1.0, timeout_seconds=20.0)
        except Exception:
            pass
        page = driver.execute_script(
            """
return {
  ready_state: document.readyState,
  title: document.title || '',
  text: document.body ? document.body.innerText : '',
  password_fields: document.querySelectorAll('input[type="password"]').length
};
"""
        )
        current_path = urlsplit(str(driver.current_url)).path.casefold()
        page_text = str((page or {}).get("text") or "").strip()
        if "/login" in current_path or int((page or {}).get("password_fields") or 0):
            raise RuntimeError("Printable encounter redirected to the DRK login page")
        if len(page_text) < 20:
            raise RuntimeError("Printable encounter rendered without meaningful note text")

        driver.execute_script(
            """
document.body.classList.add('no-sidebar');
let style = document.getElementById('codex-standalone-print-style');
if (!style) {
  style = document.createElement('style');
  style.id = 'codex-standalone-print-style';
  document.head.appendChild(style);
}
style.textContent = `
  #nav-wrapper, #mobile-nav-fab, #nav-backdrop,
  [role="tooltip"], .tooltip::before, .tooltip::after {
    display: none !important;
  }
  html, body {
    padding-left: 0 !important;
    margin-left: 0 !important;
    background: #ffffff !important;
  }
  @media print {
    #nav-wrapper, #mobile-nav-fab, #nav-backdrop {
      display: none !important;
    }
    html, body {
      padding-left: 0 !important;
      margin-left: 0 !important;
      background: #ffffff !important;
    }
  }
`;
"""
        )

        rendered = driver.execute_cdp_cmd(
            "Page.printToPDF",
            {
                "printBackground": True,
                "preferCSSPageSize": True,
                "displayHeaderFooter": False,
                "paperWidth": 8.5,
                "paperHeight": 11,
                "marginTop": 0.25,
                "marginBottom": 0.25,
                "marginLeft": 0.25,
                "marginRight": 0.25,
            },
        )
        pdf_bytes = base64.b64decode(str(rendered.get("data") or ""), validate=True)
        if not pdf_bytes.startswith(b"%PDF-"):
            raise RuntimeError("Chrome did not return a valid PDF document")
        temporary.write_bytes(pdf_bytes)
        reader = PdfReader(str(temporary))
        if not reader.pages:
            raise RuntimeError("Rendered encounter PDF has no pages")
        extracted_text = "\n".join((page.extract_text() or "") for page in reader.pages)
        if len(extracted_text.strip()) < 20:
            raise RuntimeError("Rendered encounter PDF contains no extractable note text")
        temporary.replace(destination)
        return {
            "status": "downloaded",
            "artifact_kind": "rendered_pdf",
            "encounter_id": encounter_id,
            "path": str(destination.resolve()),
            "bytes": len(pdf_bytes),
            "sha256": hashlib.sha256(pdf_bytes).hexdigest(),
            "content_type": "application/pdf",
            "page_count": len(reader.pages),
            "source_url": normalize_ids(url, [encounter_id, service_id]),
            "source_title": str((page or {}).get("title") or "") or None,
        }
    except Exception as error:
        temporary.unlink(missing_ok=True)
        return {
            "status": "error",
            "artifact_kind": "rendered_pdf",
            "encounter_id": encounter_id,
            "source_url": normalize_ids(url, [encounter_id, service_id]),
            "error_type": type(error).__name__,
            "error": str(error),
        }


def capture_encounter_notes(
    reader: DrkPatientReader,
    patient_id: str,
    encounters: list[dict[str, Any]],
    output_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    assert reader.driver is not None
    driver = reader.driver
    base_url = emr_root(reader.config.emr_url)
    session = browser_session(driver)
    notes: list[dict[str, Any]] = []
    downloads: list[dict[str, Any]] = []
    for index, encounter in enumerate(encounters, start=1):
        encounter_id = str(encounter.get("id") or "").strip()
        service_id = str(encounter.get("encounterServiceId") or "").strip()
        if not encounter_id:
            continue
        if bool(encounter.get("isBeta")):
            query = urlencode(
                {
                    "noteTypeId": encounter.get("noteTypeId") or "",
                    "patientId": patient_id,
                    "providerId": encounter.get("providerId") or "",
                    "encounterServiceId": service_id,
                    "encounterId": encounter_id,
                    "isNew": "false",
                }
            )
            note_url = urljoin(base_url, f"/Note?{query}")
        else:
            note_url = urljoin(base_url, f"/Encounter/Encounter?EncounterId={encounter_id}")

        clear_network_requests(driver)
        driver.get(note_url)
        try:
            wait_for_network_idle(driver, idle_seconds=1.0, timeout_seconds=20.0)
        except Exception:
            pass
        dom = note_dom(driver)
        dom["url"] = normalize_ids(str(dom.get("url") or note_url), [patient_id, encounter_id, service_id])
        dom["same_origin_links"] = page_link_inventory(
            driver, [patient_id, encounter_id, service_id]
        )
        notes.append(
            {
                "encounter": encounter,
                "page": dom,
                "network_payloads": capture_current_json_responses(
                    driver, [patient_id, encounter_id, service_id]
                ),
            }
        )
        printable_source = download_printable_note_source(
            session, base_url, encounter, output_dir
        )
        if printable_source:
            downloads.append(printable_source)
        printable_pdf = render_printable_note_pdf(
            driver, base_url, encounter, output_dir
        )
        if printable_pdf:
            downloads.append(printable_pdf)
        print(
            f"    note {index}/{len(encounters)} encounter={encounter_id} "
            f"fields={len(dom.get('fields') or [])}",
            flush=True,
        )
    return notes, downloads


def additional_patient_payloads(
    driver: Any, patient_id: str, known_urls: set[str]
) -> list[dict[str, Any]]:
    """Keep extra same-origin patient JSON observed beyond supported cards."""
    allowed_host = urlsplit(str(driver.current_url)).netloc.casefold()
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for request in getattr(driver, "requests", []):
        response = getattr(request, "response", None)
        url = str(getattr(request, "url", "") or "")
        if response is None or urlsplit(url).netloc.casefold() != allowed_host:
            continue
        if patient_id not in url:
            continue
        content_type = str(response.headers.get("Content-Type") or "").casefold()
        if "application/json" not in content_type:
            continue
        normalized_url = normalize_url_pattern(url, patient_id)
        if normalized_url in known_urls:
            continue
        try:
            payload = json.loads(decode_response_body(response).decode("utf-8", errors="replace"))
        except (UnicodeError, json.JSONDecodeError):
            continue
        method = str(getattr(request, "method", "GET") or "GET").upper()
        latest[(method, normalized_url)] = {
            "endpoint": {
                "method": method,
                "url": normalized_url,
                "status": int(response.status_code),
            },
            "data": payload,
        }
    return [latest[key] for key in sorted(latest)]


def drk_full_snapshot(
    reader: DrkPatientReader,
    identity: dict[str, Any],
    binary_output_dir: Path,
) -> dict[str, Any]:
    patient_id = drk_match(reader, identity)
    capture = reader.read_patient(patient_id)
    known_urls: set[str] = set()
    patient: dict[str, Any] = {
        "patient_id": capture.patient_id,
        "captured_at": capture.observed_at.isoformat(),
    }
    for card_name, card in capture.cards.items():
        records: list[dict[str, Any]] = []
        for record in card.get("records") or []:
            endpoint = record.get("endpoint") or {}
            endpoint_url = str(endpoint.get("url") or "")
            if endpoint_url:
                known_urls.add(endpoint_url)
            records.append(
                {
                    "endpoint": endpoint,
                    "data": record.get("business_data"),
                }
            )
        patient[card_name] = records
    assert reader.driver is not None
    patient["additional_patient_payloads"] = additional_patient_payloads(
        reader.driver, patient_id, known_urls
    )
    patient["dashboard_same_origin_links"] = page_link_inventory(
        reader.driver, [patient_id]
    )

    # Despite using POST, this DRK endpoint is read-only (GetPatientBilledLedger)
    # and is the dashboard's own mechanism for retrieving claim/service history.
    patient["billing_ledger"] = fetch_json_in_page(
        reader.driver,
        "/PatientDashboard/GetPatientBilledLedger",
        method="POST",
        payload={
            "patientId": patient_id,
            "startDate": "1900-01-01",
            "endDate": date.today().isoformat(),
        },
    )
    patient["therapy_details"] = therapy_payloads(
        reader.driver,
        patient_id,
        patient.get("pipeline") or [],
    )

    download_root = binary_output_dir / patient_slug(identity["name"])
    session = browser_session(reader.driver)
    patient["downloaded_documents"] = download_scans(
        capture.cards, session, download_root / "documents"
    )

    encounters = card_entities(capture.cards, "encounters", "encounters")
    notes, note_downloads = capture_encounter_notes(
        reader,
        patient_id,
        encounters,
        download_root / "encounter-notes",
    )
    patient["encounter_notes"] = notes
    patient["downloaded_encounter_notes"] = note_downloads
    patient["exposed_urls"] = url_inventory(patient)
    return patient


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    temporary.replace(path)
    print(f"Wrote {path.resolve()}", flush=True)


def main() -> int:
    args = parse_args()
    load_dotenv(REPO_ROOT / ".env")
    identities = select_identities(
        load_identities(args.gold_dir),
        args.patient,
        allow_unreviewed=args.allow_unreviewed,
    )

    for index, identity in enumerate(identities, start=1):
        print(f"[{index}/{len(identities)}] Monday row: {identity['name']}", flush=True)
        write_json(
            args.output_dir / f"{patient_slug(identity['name'])}.monday.json",
            monday_full_row(identity, args.board_id),
        )

    profile_parent = REPO_ROOT / "tmp"
    profile_parent.mkdir(parents=True, exist_ok=True)
    profile_dir = Path(tempfile.mkdtemp(prefix="drk-full-snapshot-", dir=profile_parent))
    try:
        config = DrkLiveReaderConfig.from_environment(profile_dir=profile_dir)
        with DrkPatientReader(config) as reader:
            for index, identity in enumerate(identities, start=1):
                print(f"[{index}/{len(identities)}] DRK snapshot: {identity['name']}", flush=True)
                write_json(
                    args.output_dir / f"{patient_slug(identity['name'])}.drk.json",
                    drk_full_snapshot(
                        reader,
                        identity,
                        args.output_dir / "binaries",
                    ),
                )
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
