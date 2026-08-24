"""Targeted Stage 1 subsystem retry without repeating completed work."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from referral_pipeline.monitoring.models import WorkflowEvent


RETRYABLE_STEPS = ("extraction", "monday", "drk", "acknowledgement", "workflow")


def parse_retry_step(value: str | None) -> str:
    step = str(value or "all").strip().casefold()
    if step in {"all", *RETRYABLE_STEPS}:
        return step
    raise ValueError(
        "retry_step must be all, extraction, monday, drk, acknowledgement, or workflow"
    )


def load_existing_manifest(artifact_path: str | Path | None) -> dict[str, Any] | None:
    if not artifact_path:
        return None
    path = Path(artifact_path).parent / "manifest.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def completed_subsystems(events: list[WorkflowEvent]) -> set[str]:
    latest = latest_event_by_type(events)
    completed: set[str] = set()
    if "extraction_completed" in latest:
        completed.add("extraction")
    if "monday_duplicate_checked" in latest:
        completed.add("monday")
    if "drk_duplicate_checked" in latest:
        completed.add("drk")
    if "partner_acknowledgement_sent" in latest:
        completed.add("acknowledgement")
    if "partner_contact_confirmation_requested" in latest or "partner_contact_confirmed" in latest:
        completed.add("review")
    if "assignment_requested" in latest or "intake_follow_up_required" in latest:
        completed.add("workflow")
    return completed


def latest_event_by_type(events: list[WorkflowEvent]) -> dict[str, WorkflowEvent]:
    latest: dict[str, WorkflowEvent] = {}
    for event in events:
        current = latest.get(event.event_type)
        if current is None or event.occurred_at >= current.occurred_at:
            latest[event.event_type] = event
    return latest


def next_event_revision(events: list[WorkflowEvent]) -> int:
    """Return a monotonic revision independent of inbox retry attempt_count."""
    highest = 0
    for event in events:
        revision = event.details.get("revision") if isinstance(event.details, dict) else None
        if isinstance(revision, int) and revision > highest:
            highest = revision
        key = str(event.event_key or "")
        marker = key.rsplit(":rev", 1)
        if len(marker) == 2 and marker[1].isdigit():
            highest = max(highest, int(marker[1]))
    return highest + 1


def should_run_step(step: str, *, retry_step: str, completed: set[str]) -> bool:
    if retry_step == step:
        return True
    if retry_step != "all":
        return False
    return step not in completed


def identity_option_keys() -> frozenset[str]:
    return frozenset(
        {
            "workflow_database_backend",
            "synthetic_persistence_allowed",
            "source_sender",
            "source_conversation_id",
        }
    )


def merge_refreshed_options(
    stored: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    """Replace operator-controlled flags while preserving per-document identity."""
    merged = dict(current)
    for key in identity_option_keys():
        if key in stored:
            merged[key] = stored[key]
    return merged
