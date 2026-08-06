"""Configuration for deterministic scheduling and visit monitoring rules."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONFIG_PATH = Path(__file__).with_name("monitoring_config.example.json")


@dataclass(frozen=True)
class MonitoringConfig:
    timezone: str
    end_of_day: str
    notification_recipients: tuple[str, ...]
    sent_to_case_manager_labels: frozenset[str]
    scheduled_status_labels: frozenset[str]
    scheduling_complete_labels: frozenset[str]
    inactive_group_fragments: tuple[str, ...]
    inactive_visit_statuses: frozenset[str]
    seen_statuses: frozenset[str]
    not_seen_statuses: frozenset[str]
    hold_statuses: frozenset[str]
    healed_statuses: frozenset[str]
    expired_statuses: frozenset[str]
    discharged_status_prefixes: tuple[str, ...]
    not_seen_review_threshold: int


def load_monitoring_config(path: str | Path | None = None) -> MonitoringConfig:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    scheduling = payload.get("scheduling") or {}
    visits = payload.get("visits") or {}
    env_recipients = os.getenv("WORKFLOW_NOTIFICATION_RECIPIENTS")
    recipients = (
        [value.strip() for value in env_recipients.split(",") if value.strip()]
        if env_recipients is not None
        else _clean_list(payload.get("notification_recipients"))
    )
    return MonitoringConfig(
        timezone=os.getenv("WCW_TIMEZONE", str(payload.get("timezone") or "America/Los_Angeles")),
        end_of_day=os.getenv("WCW_END_OF_DAY", str(payload.get("end_of_day") or "17:00")),
        notification_recipients=tuple(recipients),
        sent_to_case_manager_labels=_normalized_set(scheduling.get("sent_to_case_manager_labels") or ["Yes"]),
        scheduled_status_labels=_normalized_set(scheduling.get("scheduled_status_labels") or ["Scheduled"]),
        scheduling_complete_labels=_normalized_set(scheduling.get("scheduling_complete_labels") or ["Yes"]),
        inactive_group_fragments=tuple(_normalize(value) for value in scheduling.get("inactive_group_fragments") or []),
        inactive_visit_statuses=_normalized_set(scheduling.get("inactive_visit_statuses") or []),
        seen_statuses=_normalized_set(visits.get("seen_statuses") or ["Seen"]),
        not_seen_statuses=_normalized_set(visits.get("not_seen_statuses") or ["Not Seen"]),
        hold_statuses=_normalized_set(visits.get("hold_statuses") or ["On Holds List", "Hospitalized"]),
        healed_statuses=_normalized_set(visits.get("healed_statuses") or ["Healed", "QA - WX HEALED"]),
        expired_statuses=_normalized_set(visits.get("expired_statuses") or ["Deceased", "Expired"]),
        discharged_status_prefixes=tuple(_normalize(value) for value in visits.get("discharged_status_prefixes") or ["DC -", "INACTIVE/DC"]),
        not_seen_review_threshold=int(
            os.getenv("WCW_NOT_SEEN_REVIEW_THRESHOLD", str(visits.get("not_seen_review_threshold") or 3))
        ),
    )


def _clean_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _normalized_set(values: object) -> frozenset[str]:
    return frozenset(_normalize(value) for value in _clean_list(values))


def _normalize(value: object) -> str:
    return " ".join(str(value or "").casefold().split())
