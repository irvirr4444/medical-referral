"""Shared classification for failures that are safe to retry later."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass

from intake_extractor.llm.reliability import CapacityExhaustedError, is_capacity_error


TRANSIENT_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504, 529})
PERMANENT_STATUSES = frozenset({400, 401, 403, 404, 413, 422})
NETWORK_ERROR_NAMES = frozenset(
    {
        "APIConnectionError",
        "APITimeoutError",
        "ConnectionError",
        "ReadTimeout",
        "Timeout",
        "TimeoutError",
        "URLError",
    }
)
TRANSIENT_MESSAGE_MARKERS = (
    "complexity budget",
    "connection reset",
    "connection timed out",
    "overloaded",
    "quota exceeded",
    "rate limit",
    "rate_limit",
    "temporarily unavailable",
    "timed out",
    "timeout",
)


@dataclass(frozen=True)
class RetryDecision:
    error_kind: str


def classify_retry(error: Exception) -> RetryDecision | None:
    """Classify transient Anthropic, Outlook, Monday, and network failures."""
    chain = list(_error_chain(error))
    if any(_status(exc) in PERMANENT_STATUSES for exc in chain):
        return None

    for exc in chain:
        dependency = _dependency(exc)
        if dependency == "anthropic" and (
            isinstance(exc, CapacityExhaustedError) or is_capacity_error(exc)
        ):
            return RetryDecision(error_kind="capacity")
        if _status(exc) in TRANSIENT_STATUSES:
            return RetryDecision(error_kind=f"{dependency}_transient")
        if type(exc).__name__ in NETWORK_ERROR_NAMES:
            return RetryDecision(error_kind=f"{dependency}_transient")
        if any(marker in _error_text(exc) for marker in TRANSIENT_MESSAGE_MARKERS):
            return RetryDecision(error_kind=f"{dependency}_transient")
    return None


def _error_chain(error: Exception) -> Iterator[Exception]:
    current: BaseException | None = error
    seen: set[int] = set()
    while isinstance(current, Exception) and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _status(error: Exception) -> int | None:
    value = getattr(error, "status_code", None)
    if value is None:
        value = getattr(error, "status", None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _dependency(error: Exception) -> str:
    name = type(error).__name__
    module = type(error).__module__.casefold()
    if name in {"CapacityExhaustedError", "CanonicalExtractionError"} or "anthropic" in module:
        return "anthropic"
    if name == "OutlookGraphError" or module.startswith("outlook"):
        return "outlook"
    if name == "MondayAPIError" or "monday" in module:
        return "monday"
    return "network"


def _error_text(error: Exception) -> str:
    values = [str(error)]
    response = getattr(error, "response", None)
    if response is not None:
        try:
            values.append(json.dumps(response, sort_keys=True))
        except TypeError:
            values.append(str(response))
    return " ".join(values).casefold()
