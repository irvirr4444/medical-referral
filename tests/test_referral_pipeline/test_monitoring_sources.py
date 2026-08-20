from __future__ import annotations

import json
from datetime import datetime, timezone

from referral_pipeline.monitoring.drk_source import load_drk_snapshots
from referral_pipeline.monitoring.drk_capture import load_drk_capture_snapshots
from referral_pipeline.monitoring.monday_source import monday_item_to_snapshot
from master_sheet_reader import FIELD_COLUMNS


NOW = datetime(2026, 8, 6, tzinfo=timezone.utc)


def test_monday_source_maps_all_stage_five_fields_from_raw_columns() -> None:
    item = {
        "id": "monday-1",
        "name": "Synthetic Patient",
        "updated_at": "2026-08-05T22:00:00Z",
        "group": {"id": "working", "title": "Working pipeline"},
        "column_values": [
            {"id": FIELD_COLUMNS["case_manager"], "text": "Example Manager"},
            {"id": FIELD_COLUMNS["sent_to_cm"], "text": "Yes"},
            {"id": FIELD_COLUMNS["referral_sent_to_provider"], "text": "Yes"},
            {"id": FIELD_COLUMNS["provider"], "text": "Example Provider"},
            {"id": FIELD_COLUMNS["due_date"], "text": "2026-08-05"},
            {"id": FIELD_COLUMNS["appointment_date"], "text": "2026-08-07"},
            {"id": FIELD_COLUMNS["scheduling_complete"], "text": "Yes"},
            {"id": FIELD_COLUMNS["scheduled_status"], "text": "Scheduled"},
            {"id": FIELD_COLUMNS["visit_status"], "text": "Seen"},
            {"id": FIELD_COLUMNS["qa_hold_reason"], "text": "None"},
            {"id": FIELD_COLUMNS["discharge_reason"], "text": "None"},
            {"id": FIELD_COLUMNS["dob"], "text": "1960-01-02"},
            {"id": FIELD_COLUMNS["referral_received"], "text": "2026-08-01"},
        ],
    }

    snapshot = monday_item_to_snapshot(item, observed_at=NOW)

    assert snapshot.source == "monday"
    assert snapshot.external_id == "monday-1"
    assert snapshot.monday_item_id == "monday-1"
    assert snapshot.patient_label == "Synthetic Patient"
    assert snapshot.group == "Working pipeline"
    assert snapshot.case_manager == "Example Manager"
    assert snapshot.sent_to_case_manager == "Yes"
    assert snapshot.referral_sent_to_provider == "Yes"
    assert snapshot.provider == "Example Provider"
    assert snapshot.due_date == "2026-08-05"
    assert snapshot.appointment_date == "2026-08-07"
    assert snapshot.scheduling_complete == "Yes"
    assert snapshot.scheduled_status == "Scheduled"
    assert snapshot.visit_status == "Seen"
    assert snapshot.qa_hold_reason == "None"
    assert snapshot.discharge_reason == "None"
    assert snapshot.details == {
        "dob": "1960-01-02",
        "referral_received": "2026-08-01",
    }


def test_drk_source_maps_linkage_without_copying_full_chart(tmp_path) -> None:
    path = tmp_path / "drk.json"
    path.write_text(
        json.dumps(
            {
                "patients": [
                    {
                        "patient_id": "drk-1",
                        "referral_id": "ref-1",
                        "monday_item_id": "monday-1",
                        "patient_name": "Synthetic Patient",
                        "dob": "1960-01-02",
                        "visit_status": "Seen",
                        "visit_id": "visit-1",
                        "progress_note_status": "Signed",
                        "clinical_note": "must not be copied",
                        "ssn": "000-00-0000",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    snapshot = load_drk_snapshots(path, observed_at=NOW)[0]

    assert snapshot.referral_id == "ref-1"
    assert snapshot.monday_item_id == "monday-1"
    assert snapshot.drk_patient_id == "drk-1"
    assert snapshot.visit_event_id == "visit-1"
    assert snapshot.details == {"dob": "1960-01-02"}


def test_drk_source_maps_all_stage_six_fields(tmp_path) -> None:
    path = tmp_path / "drk-complete.json"
    path.write_text(
        json.dumps(
            {
                "patients": [
                    {
                        "patient_id": "321",
                        "referral_id": "case-1",
                        "monday_item_id": "monday-1",
                        "patient_name": "Synthetic Patient",
                        "dob": "1960-01-02",
                        "provider": "Example Provider",
                        "appointment_date": "2026-08-07",
                        "visit_status": "Seen",
                        "visit_outcome": "Seen",
                        "visit_event_id": "visit-1",
                        "progress_note_status": "Signed",
                        "hold_status": "None",
                        "discharge_status": "None",
                        "updated_at": "2026-08-07T18:00:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    snapshot = load_drk_snapshots(path, observed_at=NOW)[0]

    assert snapshot.source == "drk"
    assert snapshot.external_id == "321"
    assert snapshot.referral_id == "case-1"
    assert snapshot.monday_item_id == "monday-1"
    assert snapshot.drk_patient_id == "321"
    assert snapshot.patient_label == "Synthetic Patient"
    assert snapshot.provider == "Example Provider"
    assert snapshot.appointment_date == "2026-08-07"
    assert snapshot.visit_status == "Seen"
    assert snapshot.visit_outcome == "Seen"
    assert snapshot.visit_event_id == "visit-1"
    assert snapshot.progress_note_status == "Signed"
    assert snapshot.qa_hold_reason == "None"
    assert snapshot.discharge_reason == "None"
    assert snapshot.source_updated_at == "2026-08-07T18:00:00Z"
    assert snapshot.details == {"dob": "1960-01-02"}


def test_drk_capture_adapter_maps_latest_explicit_encounter_with_evidence(tmp_path) -> None:
    capture = tmp_path / "drk-browser-profile" / "Synthetic_Patient"
    capture.mkdir(parents=True)
    _write_card(
        capture / "patient_information.json",
        "patient_information",
        {
            "data": {
                "id": 321,
                "fullName": "Synthetic Patient",
                "dateOfBirth": "1960-01-02T00:00:00Z",
            }
        },
    )
    _write_card(
        capture / "encounters.json",
        "encounters",
        {
            "data": [
                {
                    "encounterId": "visit-1",
                    "appointmentDate": "2026-08-01T10:00:00Z",
                    "visitStatus": "Not Seen",
                    "lastUpdated": "2026-08-01T18:00:00Z",
                },
                {
                    "encounterId": "visit-2",
                    "appointmentDate": "2026-08-06T10:00:00Z",
                    "visitStatus": "Seen",
                    "progressNoteStatus": "Signed",
                    "providerName": "Synthetic Provider",
                    "lastUpdated": "2026-08-06T18:00:00Z",
                },
            ]
        },
    )

    snapshot = load_drk_capture_snapshots(tmp_path / "drk-browser-profile", observed_at=NOW)[0]

    assert snapshot.drk_patient_id == "321"
    assert snapshot.patient_label == "Synthetic Patient"
    assert snapshot.visit_event_id == "visit-2"
    assert snapshot.visit_status == "Seen"
    assert snapshot.progress_note_status == "Signed"
    assert snapshot.provider == "Synthetic Provider"
    assert snapshot.details["adapter"] == "drk_selenium_capture"
    assert snapshot.details["observed_field_sources"]["visit_status"]["card"] == "encounters"
    assert "visit_outcome" in snapshot.details["missing_monitoring_fields"]
    assert snapshot.details["normalization_status"] == "partial"


def test_drk_capture_adapter_refuses_to_invent_missing_patient_id(tmp_path) -> None:
    capture = tmp_path / "Unknown_Patient"
    capture.mkdir()
    _write_card(
        capture / "patient_information.json",
        "patient_information",
        {"data": {"fullName": "Unknown Patient"}},
    )

    try:
        load_drk_capture_snapshots(capture, observed_at=NOW)
    except ValueError as error:
        assert "missing an explicit patient ID" in str(error)
    else:
        raise AssertionError("capture without patient ID should fail closed")


def _write_card(path, card: str, business_data: object) -> None:
    path.write_text(
        json.dumps(
            {
                "card": card,
                "record_count": 1,
                "records": [
                    {
                        "endpoint": {"method": "GET", "url": "https://drk.test", "status": 200},
                        "business_data": business_data,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
