"""Step 5 transition rules based only on explicit recorded statuses."""

from __future__ import annotations

from dataclasses import dataclass

from referral_pipeline.monitoring.config import MonitoringConfig
from referral_pipeline.monitoring.models import OperationalSnapshot


@dataclass(frozen=True)
class VisitTransition:
    event_types: tuple[str, ...]
    consecutive_not_seen: int
    review_required: bool = False


def evaluate_visit_transition(
    previous: OperationalSnapshot,
    current: OperationalSnapshot,
    *,
    config: MonitoringConfig,
    consecutive_not_seen: int,
) -> VisitTransition:
    previous_outcome = _norm(previous.visit_outcome or previous.visit_status)
    current_outcome = _norm(current.visit_outcome or current.visit_status)
    previous_hold = _is_hold(previous, config)
    current_hold = _is_hold(current, config)
    events: list[str] = []
    counter = consecutive_not_seen

    new_recorded_visit = bool(
        current.visit_event_id
        and current.visit_event_id != previous.visit_event_id
    )
    if current_outcome != previous_outcome or new_recorded_visit:
        if current_outcome in config.seen_statuses:
            events.append("visit_seen")
            counter = 0
        elif current_outcome in config.not_seen_statuses:
            events.append("visit_not_seen")
            counter += 1

    if current_hold and not previous_hold:
        events.append("patient_on_hold")
    elif previous_hold and not current_hold:
        events.append("patient_returned_from_hold")

    previous_clinical = _clinical_signals(previous)
    current_clinical = _clinical_signals(current)
    if _matches_any(current_clinical, config.healed_statuses) and not _matches_any(
        previous_clinical, config.healed_statuses
    ):
        events.append("recorded_healed_status")
    if _matches_any(current_clinical, config.expired_statuses) and not _matches_any(
        previous_clinical, config.expired_statuses
    ):
        events.append("recorded_expired_status")
    if _is_discharged(current, config) and not _is_discharged(previous, config):
        events.append("recorded_discharge_status")

    review_required = "visit_not_seen" in events and counter >= config.not_seen_review_threshold
    if review_required:
        events.append("noncompliance_discharge_review_required")
    return VisitTransition(tuple(events), counter, review_required)


def _is_hold(snapshot: OperationalSnapshot, config: MonitoringConfig) -> bool:
    return _matches_any(_clinical_signals(snapshot), config.hold_statuses)


def _is_discharged(snapshot: OperationalSnapshot, config: MonitoringConfig) -> bool:
    values = _clinical_signals(snapshot)
    group = _norm(snapshot.group)
    if "discharged" in group:
        return True
    return any(
        value.startswith(prefix)
        for value in values
        for prefix in config.discharged_status_prefixes
        if prefix
    )


def _clinical_signals(snapshot: OperationalSnapshot) -> set[str]:
    return {
        value
        for value in (
            _norm(snapshot.visit_status),
            _norm(snapshot.visit_outcome),
            _norm(snapshot.qa_hold_reason),
            _norm(snapshot.discharge_reason),
        )
        if value
    }


def _matches_any(values: set[str], expected: frozenset[str]) -> bool:
    return bool(values & expected)


def _norm(value: object) -> str:
    return " ".join(str(value or "").casefold().split())
