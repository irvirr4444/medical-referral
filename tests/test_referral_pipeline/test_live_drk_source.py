from __future__ import annotations

from datetime import datetime, timezone

from drk_emr.live_reader import DrkLiveReaderConfig, DrkPatientCapture
from referral_pipeline.monitoring.config import load_monitoring_config
from referral_pipeline.monitoring.live_drk_source import (
    load_live_drk_snapshots,
    select_live_drk_targets,
)
from referral_pipeline.monitoring.models import OperationalSnapshot, PatientLink
from referral_pipeline.monitoring.sqlite_store import SQLiteWorkflowStore


NOW = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)


def test_target_selection_uses_active_linked_patients_and_rotates() -> None:
    config = load_monitoring_config()
    monday = [
        _monday("m1", "Active One", "Working pipeline"),
        _monday("m2", "Active Two", "Working pipeline"),
        _monday("m3", "Inactive", "Discharged Patients"),
    ]
    links = [
        _link("e1", "m1", "101"),
        _link("e2", "m2", "102"),
        _link("e3", "m3", "103"),
        PatientLink(entity_id="unlinked", drk_patient_id="104", updated_at=NOW),
    ]

    targets = select_live_drk_targets(
        monday,
        links,
        config=config,
        cursor="101",
        limit=2,
    )

    assert [target.patient_id for target in targets] == ["102", "101"]


def test_live_source_normalizes_in_memory_and_preserves_linkage(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    store.upsert_patient_link(_link("ref-1", "m1", "101"))
    monday = [_monday("m1", "Active One", "Working pipeline")]
    config = load_monitoring_config()
    reader_config = DrkLiveReaderConfig(
        emr_url="https://drk.test",
        username="test-user",
        password="test-password",
        profile_dir=tmp_path / "profile",
    )

    class Reader:
        def __enter__(self):
            return self

        def __exit__(self, _type, _value, _traceback):
            return None

        def read_patient(self, patient_id: str):
            return DrkPatientCapture(
                patient_id=patient_id,
                observed_at=NOW,
                cards=_cards(patient_id),
            )

    batch = load_live_drk_snapshots(
        monday_snapshots=monday,
        store=store,
        monitoring_config=config,
        observed_at=NOW,
        browser_profile_dir=tmp_path / "profile",
        max_patients=10,
        reader_config=reader_config,
        reader_factory=lambda _config: Reader(),
    )

    assert batch.status == "ok"
    assert batch.attempted == 1
    assert batch.next_cursor == "101"
    snapshot = batch.snapshots[0]
    assert snapshot.referral_id == "ref-1"
    assert snapshot.monday_item_id == "m1"
    assert snapshot.drk_patient_id == "101"
    assert snapshot.visit_status == "Seen"
    assert snapshot.details["adapter"] == "drk_live_selenium"


def _monday(item_id: str, name: str, group: str) -> OperationalSnapshot:
    return OperationalSnapshot(
        source="monday",
        external_id=item_id,
        monday_item_id=item_id,
        patient_label=name,
        group=group,
        observed_at=NOW,
    )


def _link(entity_id: str, monday_item_id: str, drk_patient_id: str) -> PatientLink:
    return PatientLink(
        entity_id=entity_id,
        monday_item_id=monday_item_id,
        drk_patient_id=drk_patient_id,
        patient_label=f"Patient {drk_patient_id}",
        updated_at=NOW,
    )


def _cards(patient_id: str) -> dict:
    return {
        "patient_information": {
            "card": "patient_information",
            "record_count": 1,
            "records": [
                {
                    "endpoint": {"method": "GET", "url": "demographics", "status": 200},
                    "business_data": {
                        "data": {"id": int(patient_id), "fullName": "Active One"}
                    },
                }
            ],
        },
        "encounters": {
            "card": "encounters",
            "record_count": 1,
            "records": [
                {
                    "endpoint": {"method": "GET", "url": "encounters", "status": 200},
                    "business_data": {
                        "data": [
                            {
                                "encounterId": "visit-1",
                                "visitStatus": "Seen",
                                "appointmentDate": "2026-08-07T10:00:00Z",
                            }
                        ]
                    },
                }
            ],
        },
        "pipeline": {"card": "pipeline", "record_count": 0, "records": []},
    }
