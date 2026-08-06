from __future__ import annotations

import json
from datetime import datetime, timezone

from referral_pipeline.monitoring.drk_source import load_drk_snapshots


NOW = datetime(2026, 8, 6, tzinfo=timezone.utc)


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
