from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


def utc_timestamp_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


@dataclass
class EndpointRecord:
    section: str
    url: str
    method: str
    request_headers: dict[str, str]
    request_body: str | None
    response_status: int
    response_headers: dict[str, str]
    response_json: Any
    observed_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DirectReplayResult:
    endpoint_url: str
    method: str
    section: str
    headers_sent: list[str]
    status_code: int
    success: bool
    json_match: str
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

