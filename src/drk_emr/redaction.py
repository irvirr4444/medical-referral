from __future__ import annotations

import copy
import re
from collections.abc import Iterable
from typing import Any
from urllib.parse import parse_qsl, quote_plus, urlsplit, urlunsplit

SENSITIVE_HEADER_PATTERNS = (
    "cookie",
    "authorization",
    "token",
    "csrf",
    "xsrf",
    "verification",
    "secret",
    "session",
)

PII_KEY_PATTERNS = (
    "name",
    "dob",
    "birth",
    "phone",
    "email",
    "address",
    "mrn",
    "username",
    "password",
    "userpassword",
    "userspassword",
)

SENSITIVE_QUERY_KEYS = {
    "password",
    "username",
    "userName",
    "token",
    "authorization",
    "cookie",
    "session",
    "csrf",
    "xsrf",
    "__requestverificationtoken",
}


def mask_secret(value: str, keep_last: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= keep_last:
        return "*" * len(value)
    return "*" * (len(value) - keep_last) + value[-keep_last:]


def mask_sensitive_headers(headers: dict[str, str]) -> dict[str, str]:
    masked: dict[str, str] = {}
    for key, value in headers.items():
        key_lower = key.lower()
        if any(pattern in key_lower for pattern in SENSITIVE_HEADER_PATTERNS):
            masked[key] = f"[MASKED:{mask_secret(value)}]"
        else:
            masked[key] = value
    return masked


def contains_sensitive_header(name: str) -> bool:
    return any(pattern in name.lower() for pattern in SENSITIVE_HEADER_PATTERNS)


def normalize_url_pattern(url: str, patient_id: str | None = None) -> str:
    parsed = urlsplit(url)
    path = parsed.path
    if patient_id:
        path = path.replace(patient_id, "{patientId}")
    path = re.sub(r"/\d{3,}", "/{id}", path)

    query_items: list[tuple[str, str]] = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() == "patientid":
            query_items.append((key, "{patientId}"))
        elif key.lower() in {k.lower() for k in SENSITIVE_QUERY_KEYS}:
            query_items.append((key, "[REDACTED]"))
        elif value.isdigit() and len(value) >= 3:
            query_items.append((key, "{id}"))
        else:
            query_items.append((key, value))

    query_parts: list[str] = []
    for key, value in query_items:
        value_part = value if value in {"{patientId}", "{id}", "[REDACTED]"} else quote_plus(value)
        query_parts.append(f"{quote_plus(key)}={value_part}")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "&".join(query_parts), ""))


def redact_json_payload(payload: Any) -> Any:
    redacted = copy.deepcopy(payload)
    return _redact_recursive(redacted)


def _redact_recursive(value: Any, key_name: str | None = None) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, inner in value.items():
            out[key] = _redact_recursive(inner, key)
        return out
    if isinstance(value, list):
        return [_redact_recursive(item, key_name) for item in value]
    if isinstance(value, str):
        if key_name and any(pattern in key_name.lower() for pattern in PII_KEY_PATTERNS):
            return "[REDACTED]"
        if "@" in value and "." in value:
            return "[REDACTED]"
        if re.search(r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b", value):
            return "[REDACTED]"
        if re.search(r"\b\d{10,}\b", value):
            return "[REDACTED]"
    return value


def leak_check_strings(text: str, forbidden_values: Iterable[str]) -> list[str]:
    leaks: list[str] = []
    for value in forbidden_values:
        if value and value in text:
            leaks.append(value)
    return leaks

