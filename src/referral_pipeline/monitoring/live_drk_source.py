"""Bounded, round-robin live DRK source for linked active Monday patients."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Protocol

from drk_emr.live_reader import DrkLiveReaderConfig, DrkPatientReader
from referral_pipeline.monitoring.config import MonitoringConfig
from referral_pipeline.monitoring.drk_capture import (
    DEFAULT_PROFILE_PATH,
    load_drk_capture_profile,
    normalize_drk_card_payloads,
)
from referral_pipeline.monitoring.models import OperationalSnapshot, PatientLink
from referral_pipeline.monitoring.store import WorkflowStore


ROTATION_CURSOR = "drk_live_rotation"


@dataclass(frozen=True)
class LiveDrkTarget:
    patient_id: str
    entity_id: str
    monday_item_id: str
    patient_label: str | None


@dataclass(frozen=True)
class LiveDrkBatch:
    snapshots: tuple[OperationalSnapshot, ...]
    attempted: int
    failures: tuple[dict[str, str], ...]
    next_cursor: str | None
    elapsed_seconds: float

    @property
    def status(self) -> str:
        if self.attempted == 0:
            return "idle"
        if not self.failures:
            return "ok"
        return "failed" if len(self.failures) == self.attempted else "partial"


class _Reader(Protocol):
    def __enter__(self) -> "_Reader": ...
    def __exit__(self, type_: object, value: object, traceback: object) -> None: ...
    def read_patient(self, patient_id: str): ...


ReaderFactory = Callable[[DrkLiveReaderConfig], _Reader]


def select_live_drk_targets(
    monday_snapshots: list[OperationalSnapshot],
    links: list[PatientLink],
    *,
    config: MonitoringConfig,
    cursor: str | None,
    limit: int,
) -> list[LiveDrkTarget]:
    if limit < 1:
        raise ValueError("live DRK patient limit must be at least 1")
    active_by_item = {
        snapshot.monday_item_id: snapshot
        for snapshot in monday_snapshots
        if snapshot.monday_item_id and _is_active(snapshot, config)
    }
    targets = [
        LiveDrkTarget(
            patient_id=str(link.drk_patient_id),
            entity_id=link.entity_id,
            monday_item_id=str(link.monday_item_id),
            patient_label=(
                active_by_item[str(link.monday_item_id)].patient_label or link.patient_label
            ),
        )
        for link in links
        if link.drk_patient_id
        and link.monday_item_id
        and str(link.monday_item_id) in active_by_item
    ]
    targets.sort(key=lambda target: _patient_sort_key(target.patient_id))
    if not targets:
        return []
    ids = [target.patient_id for target in targets]
    start = ids.index(cursor) + 1 if cursor in ids else 0
    rotated = targets[start:] + targets[:start]
    return rotated[:limit]


def load_live_drk_snapshots(
    *,
    monday_snapshots: list[OperationalSnapshot],
    store: WorkflowStore,
    monitoring_config: MonitoringConfig,
    observed_at: datetime,
    browser_profile_dir: Path,
    max_patients: int,
    capture_profile_path: str | Path = DEFAULT_PROFILE_PATH,
    reader_config: DrkLiveReaderConfig | None = None,
    reader_factory: ReaderFactory | None = None,
) -> LiveDrkBatch:
    started = time.perf_counter()
    targets = select_live_drk_targets(
        monday_snapshots,
        store.list_patient_links(),
        config=monitoring_config,
        cursor=store.read_cursor(ROTATION_CURSOR),
        limit=max_patients,
    )
    if not targets:
        return LiveDrkBatch(
            snapshots=(),
            attempted=0,
            failures=(),
            next_cursor=None,
            elapsed_seconds=round(time.perf_counter() - started, 2),
        )

    snapshots: list[OperationalSnapshot] = []
    failures: list[dict[str, str]] = []
    try:
        capture_profile = load_drk_capture_profile(capture_profile_path)
        effective_config = reader_config or DrkLiveReaderConfig.from_environment(
            profile_dir=browser_profile_dir
        )
        factory = reader_factory or (lambda config: DrkPatientReader(config))
        with factory(effective_config) as reader:
            for target in targets:
                try:
                    capture = reader.read_patient(target.patient_id)
                    snapshot = normalize_drk_card_payloads(
                        capture.cards,
                        profile=capture_profile,
                        observed_at=capture.observed_at,
                        expected_patient_id=target.patient_id,
                        context="live DRK reader",
                    )
                    snapshots.append(
                        snapshot.model_copy(
                            update={
                                "referral_id": target.entity_id,
                                "monday_item_id": target.monday_item_id,
                                "patient_label": snapshot.patient_label or target.patient_label,
                                "details": {
                                    **snapshot.details,
                                    "adapter": "drk_live_selenium",
                                },
                            }
                        )
                    )
                except Exception as error:  # noqa: BLE001 - one patient must not stop the batch
                    failures.append(
                        {"patient_id": target.patient_id, "error_type": type(error).__name__}
                    )
    except Exception as error:  # noqa: BLE001 - login/browser startup can fail the whole batch
        failures = [
            {"patient_id": target.patient_id, "error_type": type(error).__name__}
            for target in targets
        ]

    return LiveDrkBatch(
        snapshots=tuple(snapshots),
        attempted=len(targets),
        failures=tuple(failures),
        next_cursor=targets[-1].patient_id,
        elapsed_seconds=round(time.perf_counter() - started, 2),
    )


def _is_active(snapshot: OperationalSnapshot, config: MonitoringConfig) -> bool:
    group = _normalize(snapshot.group)
    if any(fragment and fragment in group for fragment in config.inactive_group_fragments):
        return False
    return _normalize(snapshot.visit_status) not in config.inactive_visit_statuses


def _patient_sort_key(patient_id: str) -> tuple[int, int | str]:
    return (0, int(patient_id)) if patient_id.isdigit() else (1, patient_id)


def _normalize(value: object) -> str:
    return " ".join(str(value or "").casefold().split())
