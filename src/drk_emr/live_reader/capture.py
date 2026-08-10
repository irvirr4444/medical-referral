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
    "encounters": ("/PatientDashboard/GetEncounters/",),
    "pipeline": ("/PatientDashboard/API/GetBvPipelineStatus/",),
}


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
    if not cards["patient_information"]["records"]:
        raise DrkCaptureError("DRK patient demographics response was not captured")
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
